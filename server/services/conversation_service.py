"""Conversation service for managing sessions and message history"""
import logging
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Tuple
from uuid import UUID
import numpy as np

from utils.supabase_client import get_supabase_admin_client
from models.conversations import (
    ConversationSession,
    ConversationMessage,
    ConversationHistory,
    ThreadDecision,
    MessageRole
)
from services.groq_service import (
    embed_text,
    estimate_tokens,
    summarize_thread,
    EmbeddingError,
    SummarizationError
)

logger = logging.getLogger(__name__)

# Dynamic threading constants
HARD_TIMEOUT_MINUTES = 90  # Maximum time gap before forcing new thread
SIMILARITY_THRESHOLD = 0.75  # Minimum cosine similarity to continue thread
TOKEN_BUDGET = 4000  # Maximum tokens for context
SUMMARY_TRIGGER_TOKENS = 3000  # Trigger summarization when approaching budget
SUMMARY_TRIGGER_MESSAGES = 4  # Trigger summarization after N messages (periodic refresh)
SUMMARY_MIN_MESSAGES = 2  # Generate summary after first Q&A pair


class ConversationServiceError(Exception):
    """Base exception for conversation service errors"""
    pass


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Compute cosine similarity between two vectors.
    
    Args:
        vec1: First vector
        vec2: Second vector
        
    Returns:
        Cosine similarity score (0.0 to 1.0)
    """
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    
    try:
        vec1_array = np.array(vec1)
        vec2_array = np.array(vec2)
        
        dot_product = np.dot(vec1_array, vec2_array)
        norm1 = np.linalg.norm(vec1_array)
        norm2 = np.linalg.norm(vec2_array)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
    except Exception as e:
        logger.warning(f"Cosine similarity calculation failed: {e}")
        return 0.0


def _build_system_message(summary: Optional[str], has_messages: bool) -> Tuple[Optional[Dict[str, str]], int]:
    """
    Build system message for context and calculate its token count.
    
    Returns system message dict and token count for reservation.
    Single source of truth for system message content.
    
    Args:
        summary: Thread summary if available
        has_messages: Whether thread has messages
        
    Returns:
        Tuple of (system_message_dict or None, token_count)
    """
    if summary:
        # Add summary as system note
        system_msg_content = f"Previous conversation context: {summary}"
        system_msg = {
            "role": "system",
            "content": system_msg_content
        }
        reserved_tokens = estimate_tokens([system_msg_content])
        return system_msg, reserved_tokens
    elif has_messages:
        # No summary but messages exist - add context hint for LLM
        context_hint_content = "This is a continuation of a previous conversation. Use the message history to understand context."
        system_msg = {
            "role": "system",
            "content": context_hint_content
        }
        reserved_tokens = estimate_tokens([context_hint_content])
        return system_msg, reserved_tokens
    else:
        # No system message needed
        return None, 0


def _should_summarize(message_count: int, token_count: Optional[int] = None) -> Tuple[bool, Optional[str]]:
    """
    Determine if thread should be summarized based on triggers.
    
    Consolidates all summarization trigger conditions in one place.
    
    Args:
        message_count: Current message count in thread
        token_count: Optional token count for threshold check
        
    Returns:
        Tuple of (should_summarize: bool, reason: str or None)
    """
    # CRITICAL: Generate initial summary after first Q&A pair (2 messages)
    if message_count == SUMMARY_MIN_MESSAGES:
        return True, "initial_summary"
    
    # Periodic summary refresh (every 4 messages)
    if message_count % SUMMARY_TRIGGER_MESSAGES == 0:
        return True, "periodic_refresh"
    
    # Token threshold check
    if token_count is not None and token_count >= SUMMARY_TRIGGER_TOKENS:
        return True, "token_threshold"
    
    return False, None


def resolve_thread(
    device_id: UUID,
    optional_session_id: Optional[UUID],
    user_text: str,
    user_embedding: List[float]
) -> ThreadDecision:
    """
    Resolve which thread to use for a new user message using dynamic policy.
    
    Policy:
    - Continue thread if (Δt ≤ HARD_TIMEOUT) OR (similarity ≥ SIMILARITY_THRESHOLD)
    - Start new thread if (Δt > HARD_TIMEOUT AND similarity < SIMILARITY_THRESHOLD)
    - Similarity check uses summary_embedding when available (best quality)
    - If no summary_embedding exists, uses time-based policy only (no similarity check)
    
    Args:
        device_id: Device UUID
        optional_session_id: Optional specific session ID to check
        user_text: User's message text
        user_embedding: Embedding vector for user text
        
    Returns:
        ThreadDecision with thread_id and decision metadata
        
    Raises:
        ConversationServiceError: If thread resolution fails
    """
    try:
        supabase = get_supabase_admin_client()
        now = datetime.now(timezone.utc)
        threshold_time = now - timedelta(minutes=HARD_TIMEOUT_MINUTES)
        
        # If specific session_id provided, check that first
        if optional_session_id:
            result = supabase.table("conversation_sessions").select("*").eq(
                "id", optional_session_id
            ).eq("device_id", str(device_id)).execute()
            
            if result.data:
                session_data = result.data[0]
                last_activity = datetime.fromisoformat(
                    session_data["last_activity_at"].replace("Z", "+00:00")
                ) if isinstance(session_data["last_activity_at"], str) else session_data["last_activity_at"]
                
                if last_activity.tzinfo is None:
                    last_activity = last_activity.replace(tzinfo=timezone.utc)
                
                delta_t = (now - last_activity).total_seconds() / 60.0
                
                # Check similarity - use summary embedding if available
                # If no summary_embedding exists, use time-based policy only (no similarity check)
                similarity = None
                similarity_method = None
                
                if session_data.get("summary_embedding"):
                    try:
                        thread_embedding = session_data["summary_embedding"]
                        # Handle case where Supabase returns vector as string or list
                        if isinstance(thread_embedding, str):
                            # Parse string representation: "[0.1,0.2,0.3]"
                            thread_embedding = json.loads(thread_embedding)
                        elif not isinstance(thread_embedding, list):
                            raise ValueError(f"Unexpected embedding type: {type(thread_embedding)}")
                        
                        similarity = cosine_similarity(user_embedding, thread_embedding)
                        similarity_method = "summary"
                        logger.debug(
                            f"Thread {optional_session_id}: Using summary embedding for similarity check: {similarity:.3f}"
                        )
                    except Exception as e:
                        logger.warning(
                            f"Similarity calculation failed for thread {optional_session_id}: {e}"
                        )
                else:
                    logger.debug(
                        f"Thread {optional_session_id}: No summary_embedding available, "
                        f"using time-based policy only (delta_t={delta_t:.1f}min)"
                    )
                
                # Apply policy: Continue if (Δt ≤ HARD_TIMEOUT) OR (similarity ≥ SIMILARITY_THRESHOLD)
                if delta_t <= HARD_TIMEOUT_MINUTES or (similarity and similarity >= SIMILARITY_THRESHOLD):
                    # Continue thread
                    reason = (
                        f"Continuing thread: delta_t={delta_t:.1f}min"
                        + (f", similarity={similarity:.3f} ({similarity_method})" if similarity and similarity_method else "")
                    )
                    logger.info(
                        f"Thread resolution: continuing thread {optional_session_id} - {reason}"
                    )
                    
                    # Update last_activity_at
                    supabase.table("conversation_sessions").update({
                        "last_activity_at": now.isoformat()
                    }).eq("id", optional_session_id).execute()
                    
                    return ThreadDecision(
                        thread_id=optional_session_id,
                        decision="continue",
                        delta_t_minutes=delta_t,
                        similarity_score=similarity,
                        reason=reason
                    )
                else:
                    # Thread expired or low similarity - mark inactive
                    logger.info(
                        f"Thread resolution: thread {optional_session_id} expired/low similarity "
                        f"(delta_t={delta_t:.1f}min, similarity={similarity}), creating new thread"
                    )
                    supabase.table("conversation_sessions").update({
                        "is_active": False
                    }).eq("id", optional_session_id).execute()
        
        # Look for recent threads for this device
        result = supabase.table("conversation_sessions").select("*").eq(
            "device_id", str(device_id)
        ).gte("last_activity_at", threshold_time.isoformat()).order(
            "last_activity_at", desc=True
        ).limit(1).execute()
        
        if result.data:
            session_data = result.data[0]
            session_id = UUID(session_data["id"])
            last_activity = datetime.fromisoformat(
                session_data["last_activity_at"].replace("Z", "+00:00")
            ) if isinstance(session_data["last_activity_at"], str) else session_data["last_activity_at"]
            
            if last_activity.tzinfo is None:
                last_activity = last_activity.replace(tzinfo=timezone.utc)
            
            delta_t = (now - last_activity).total_seconds() / 60.0
            
            # Check similarity - use summary embedding if available
            # If no summary_embedding exists, use time-based policy only (no similarity check)
            similarity = None
            similarity_method = None
            
            if session_data.get("summary_embedding"):
                try:
                    thread_embedding = session_data["summary_embedding"]
                    # Handle case where Supabase returns vector as string or list
                    if isinstance(thread_embedding, str):
                        # Parse string representation: "[0.1,0.2,0.3]"
                        thread_embedding = json.loads(thread_embedding)
                    elif not isinstance(thread_embedding, list):
                        raise ValueError(f"Unexpected embedding type: {type(thread_embedding)}")
                    
                    similarity = cosine_similarity(user_embedding, thread_embedding)
                    similarity_method = "summary"
                    logger.debug(
                        f"Thread {session_id}: Using summary embedding for similarity check: {similarity:.3f}"
                    )
                except Exception as e:
                    logger.warning(f"Similarity calculation failed for thread {session_id}: {e}")
            else:
                logger.debug(
                    f"Thread {session_id}: No summary_embedding available, "
                    f"using time-based policy only (delta_t={delta_t:.1f}min)"
                )
            
            # Apply policy: Continue if (Δt ≤ HARD_TIMEOUT) OR (similarity ≥ SIMILARITY_THRESHOLD)
            if delta_t <= HARD_TIMEOUT_MINUTES or (similarity and similarity >= SIMILARITY_THRESHOLD):
                # Continue thread
                reason = (
                    f"Continuing thread: delta_t={delta_t:.1f}min"
                    + (f", similarity={similarity:.3f} ({similarity_method})" if similarity and similarity_method else "")
                )
                logger.info(
                    f"Thread resolution: continuing thread {session_id} - {reason}"
                )
                
                # Update last_activity_at
                supabase.table("conversation_sessions").update({
                    "last_activity_at": now.isoformat()
                }).eq("id", str(session_id)).execute()
                
                return ThreadDecision(
                    thread_id=session_id,
                    decision="continue",
                    delta_t_minutes=delta_t,
                    similarity_score=similarity,
                    reason=reason
                )
        
        # Create new thread
        logger.info(f"Thread resolution: creating new thread for device {device_id}")
        insert_data = {
            "device_id": str(device_id),
            "created_at": now.isoformat(),
            "last_activity_at": now.isoformat(),
            "is_active": True,
            "message_count": 0
        }
        
        created = supabase.table("conversation_sessions").insert(insert_data).execute()
        session_data = created.data[0]
        new_thread_id = UUID(session_data["id"])
        
        logger.info(f"Created new conversation thread {new_thread_id} for device {device_id}")
        
        return ThreadDecision(
            thread_id=new_thread_id,
            decision="new",
            delta_t_minutes=0.0,
            similarity_score=None,
            reason="New thread created"
        )
        
    except Exception as e:
        logger.error(f"Failed to resolve thread: {e}", exc_info=True)
        raise ConversationServiceError(f"Thread resolution failed: {str(e)}")


def build_context(thread_id: UUID, token_budget: int = TOKEN_BUDGET) -> List[Dict[str, str]]:
    """
    Build conversation context from thread summary and recent messages.
    
    Args:
        thread_id: Thread UUID
        token_budget: Maximum tokens to include
        
    Returns:
        List of messages in format [{'role': 'user'|'assistant', 'content': '...'}, ...]
        
    Raises:
        ConversationServiceError: If context building fails
    """
    try:
        supabase = get_supabase_admin_client()
        
        # Get thread summary
        session_result = supabase.table("conversation_sessions").select(
            "summary"
        ).eq("id", thread_id).execute()
        
        summary = None
        if session_result.data and session_result.data[0].get("summary"):
            summary = session_result.data[0]["summary"]
        
        # Get recent messages
        messages_result = supabase.table("conversation_messages").select("*").eq(
            "session_id", thread_id
        ).order("created_at", desc=False).execute()
        
        messages = [ConversationMessage(**msg) for msg in messages_result.data]
        
        # Build system message and reserve tokens (single source of truth)
        has_messages = len(messages) > 0
        system_msg, reserved_tokens = _build_system_message(summary, has_messages)
        
        # Build context with system message if available
        context_messages = []
        if system_msg:
            context_messages.append(system_msg)
        
        # Calculate available budget for messages
        available_budget = token_budget - reserved_tokens
        message_texts = [msg.content for msg in messages]
        current_tokens = estimate_tokens(message_texts)
        
        if current_tokens <= available_budget:
            # All messages fit
            for msg in messages:
                context_messages.append({
                    "role": msg.role.value,
                    "content": msg.content
                })
        else:
            # Need to trim - take most recent messages that fit
            trimmed_messages = []
            accumulated_tokens = 0
            
            # Use same reserved_tokens calculated above (no duplicate calculation)
            
            for msg in reversed(messages):  # Start from most recent
                msg_tokens = estimate_tokens([msg.content])
                if accumulated_tokens + msg_tokens <= available_budget:
                    trimmed_messages.insert(0, msg)  # Insert at beginning to maintain order
                    accumulated_tokens += msg_tokens
                else:
                    break
            
            for msg in trimmed_messages:
                context_messages.append({
                    "role": msg.role.value,
                    "content": msg.content
                })
            
            logger.info(
                f"Trimmed context: {len(messages)} messages → {len(trimmed_messages)} messages "
                f"({accumulated_tokens} tokens)"
            )
        
        return context_messages
        
    except Exception as e:
        logger.error(f"Failed to build context: {e}")
        raise ConversationServiceError(f"Context building failed: {str(e)}")


async def update_thread_summary(thread_id: UUID, messages: List[Dict[str, str]]) -> None:
    """
    Update thread summary and embedding based on conversation messages (async).

    OPTIMIZATION: Uses async Groq/OpenAI clients for faster summary and embedding generation.

    Args:
        thread_id: Thread UUID
        messages: List of messages to summarize

    Raises:
        ConversationServiceError: If summary update fails
    """
    logger.info(f"Starting summary update for thread {thread_id} with {len(messages)} messages")

    # Fetch existing summary for incremental updates
    supabase = get_supabase_admin_client()
    existing_summary_result = supabase.table("conversation_sessions").select(
        "summary"
    ).eq("id", str(thread_id)).execute()

    existing_summary = None
    if existing_summary_result.data:
        existing_summary = existing_summary_result.data[0].get("summary")

    is_initial = existing_summary is None
    logger.info(
        f"Summary update type: {'initial' if is_initial else 'incremental'} "
        f"for thread {thread_id} (existing_summary={'present' if existing_summary else 'none'})"
    )

    try:
        # Generate summary (async)
        logger.info(f"Generating summary for thread {thread_id}...")
        summary = await summarize_thread(messages, existing_summary=existing_summary)
        logger.info(f"Summary generated successfully for thread {thread_id}: {summary[:100]}...")
    except SummarizationError as e:
        logger.error(f"Summarization failed for thread {thread_id}: {e}", exc_info=True)

        # Fallback strategy: keep existing summary if available
        if existing_summary:
            logger.warning(
                f"Summary update failed for thread {thread_id}, "
                f"keeping existing summary. Error: {str(e)}"
            )
            # Don't raise - allow system to continue with old summary
            # The summary and embedding remain unchanged in database
            return
        else:
            # No existing summary - extract fallback from first messages
            logger.warning(
                f"Summary update failed for thread {thread_id} with no existing summary. "
                f"Attempting fallback extraction. Error: {str(e)}"
            )
            # Extract key topics from first few messages as fallback
            if messages and len(messages) >= 2:
                fallback_summary = f"User asked about: {messages[0].get('content', '')[:100]}..."
                logger.info(f"Using fallback summary for thread {thread_id}: {fallback_summary[:100]}...")
                summary = fallback_summary
                # Continue with embedding generation below
            else:
                # No fallback possible - raise error
                raise ConversationServiceError(f"Summarization failed with no fallback: {str(e)}")

    # Generate embedding for summary (works for both successful summaries and fallback) (async)
    try:
        logger.info(f"Generating embedding for summary of thread {thread_id}...")
        summary_embedding = await embed_text(summary)
        logger.info(f"Embedding generated successfully for thread {thread_id}: {len(summary_embedding)} dimensions")
    except EmbeddingError as e:
        logger.error(f"Embedding generation failed for thread {thread_id}: {e}", exc_info=True)
        raise ConversationServiceError(f"Embedding generation failed: {str(e)}")
    
    # Update database
    try:
        logger.info(f"Attempting to update database for thread {thread_id}...")
        logger.debug(f"Summary length: {len(summary)} chars, Embedding dimensions: {len(summary_embedding)}")
        
        # Try direct update with array (should work according to Supabase docs)
        update_data = {
            "summary": summary,
            "summary_embedding": summary_embedding  # Pass as list/array
        }
        
        result = supabase.table("conversation_sessions").update(update_data).eq("id", str(thread_id)).execute()
        logger.info(f"Database update call completed for thread {thread_id}")
        
        # Verify the update succeeded
        logger.info(f"Verifying update for thread {thread_id}...")
        verify_result = supabase.table("conversation_sessions").select(
            "summary", "summary_embedding"
        ).eq("id", str(thread_id)).execute()
        
        if verify_result.data:
            has_summary = verify_result.data[0].get("summary") is not None
            has_embedding = verify_result.data[0].get("summary_embedding") is not None
            
            logger.info(
                f"Verification result for thread {thread_id}: "
                f"summary={has_summary}, embedding={has_embedding}"
            )
            
            if has_summary and has_embedding:
                logger.info(f"Successfully updated and verified summary and embedding for thread {thread_id}")
            else:
                logger.error(
                    f"Update completed but verification failed for thread {thread_id}: "
                    f"summary={has_summary}, embedding={has_embedding}"
                )
                # Try alternative format: string representation
                logger.info(f"Attempting alternative string format for embedding...")
                embedding_str = '[' + ','.join(map(str, summary_embedding)) + ']'
                
                retry_data = {
                    "summary": summary,
                    "summary_embedding": embedding_str
                }
                
                retry_result = supabase.table("conversation_sessions").update(retry_data).eq(
                    "id", str(thread_id)
                ).execute()
                
                # Verify again
                verify_retry = supabase.table("conversation_sessions").select(
                    "summary", "summary_embedding"
                ).eq("id", str(thread_id)).execute()
                
                if verify_retry.data:
                    has_summary_retry = verify_retry.data[0].get("summary") is not None
                    has_embedding_retry = verify_retry.data[0].get("summary_embedding") is not None
                    
                    if has_summary_retry and has_embedding_retry:
                        logger.info(f"Successfully updated using string format for thread {thread_id}")
                    else:
                        raise ConversationServiceError(
                            f"Both update methods failed: summary={has_summary_retry}, "
                            f"embedding={has_embedding_retry}"
                        )
                else:
                    raise ConversationServiceError("Failed to verify retry update")
        else:
            logger.error(f"Failed to verify update for thread {thread_id}: no data returned")
            raise ConversationServiceError("Failed to verify summary update")
            
    except Exception as update_error:
        logger.error(
            f"Database update failed for thread {thread_id}: {update_error}",
            exc_info=True
        )
        raise ConversationServiceError(f"Failed to update database: {str(update_error)}")
    
    logger.info(f"Completed summary update for thread {thread_id}")


def get_conversation_history(session_id: UUID) -> ConversationHistory:
    """
    Fetch all messages for a conversation session.
    
    Args:
        session_id: Session UUID
        
    Returns:
        ConversationHistory with session and messages
        
    Raises:
        ConversationServiceError: If fetching history fails
    """
    try:
        supabase = get_supabase_admin_client()
        
        # Get session
        session_result = supabase.table("conversation_sessions").select("*").eq("id", session_id).execute()
        
        if not session_result.data:
            raise ConversationServiceError(f"Session not found: {session_id}")
        
        session = ConversationSession(**session_result.data[0])
        
        # Get all messages for session, ordered by created_at
        messages_result = supabase.table("conversation_messages").select("*").eq(
            "session_id", session_id
        ).order("created_at", desc=False).execute()
        
        messages = [ConversationMessage(**msg) for msg in messages_result.data]
        
        return ConversationHistory(
            session=session,
            messages=messages,
            total_messages=len(messages)
        )
        
    except ConversationServiceError:
        raise
    except Exception as e:
        logger.error(f"Failed to get conversation history: {e}")
        raise ConversationServiceError(f"Failed to fetch conversation history: {str(e)}")


async def add_message(session_id: UUID, role: MessageRole, content: str) -> ConversationMessage:
    """
    Add a message to a conversation session.
    
    Increments message_count and checks if summarization is needed.
    
    Args:
        session_id: Session UUID
        role: Message role (user or assistant)
        content: Message content
        
    Returns:
        Created ConversationMessage
        
    Raises:
        ConversationServiceError: If message storage fails
    """
    try:
        supabase = get_supabase_admin_client()
        
        now = datetime.now(timezone.utc).isoformat()
        
        insert_data = {
            "session_id": str(session_id),
            "role": role.value,
            "content": content,
            "created_at": now
        }
        
        created = supabase.table("conversation_messages").insert(insert_data).execute()
        message_data = created.data[0]
        
        # Get current message count
        session_result = supabase.table("conversation_sessions").select(
            "message_count"
        ).eq("id", session_id).execute()
        
        current_count = session_result.data[0].get("message_count", 0) if session_result.data else 0
        new_count = current_count + 1
        
        # Update session: last_activity_at and message_count
        update_data = {
            "last_activity_at": now,
            "message_count": new_count
        }
        
        supabase.table("conversation_sessions").update(update_data).eq("id", session_id).execute()
        
        logger.info(f"Added {role.value} message to session {session_id} (count: {new_count})")
        
        # Fetch messages once for all checks (token count and summarization)
        messages_result = supabase.table("conversation_messages").select("*").eq(
            "session_id", session_id
        ).order("created_at", desc=False).execute()
        
        messages = [ConversationMessage(**msg) for msg in messages_result.data]
        message_texts = [msg.content for msg in messages]
        token_count = estimate_tokens(message_texts)
        
        logger.debug(
            f"Session {session_id}: message_count={new_count}, token_count={token_count}, "
            f"total_messages={len(messages)}"
        )
        
        # Check if summarization needed using centralized helper
        should_summarize, summarize_reason = _should_summarize(new_count, token_count)
        
        logger.debug(
            f"Summarization check for session {session_id}: should_summarize={should_summarize}, "
            f"reason={summarize_reason}"
        )
        
        if should_summarize:
            # Log the trigger reason
            if summarize_reason == "initial_summary":
                logger.info(f"Summarization triggered: initial summary after first Q&A pair ({new_count} messages)")
            elif summarize_reason == "periodic_refresh":
                logger.info(f"Summarization triggered: periodic refresh at {new_count} messages")
            elif summarize_reason == "token_threshold":
                logger.info(f"Summarization triggered: approaching token budget ({token_count} tokens)")
            
            # Build messages list for summarization
            messages_for_summary = [
                {"role": msg.role.value, "content": msg.content}
                for msg in messages
            ]
            
            # Update summary (errors are properly handled and logged in update_thread_summary)
            try:
                logger.info(
                    f"Calling update_thread_summary for session {session_id} "
                    f"(reason: {summarize_reason}, messages: {len(messages_for_summary)}, "
                    f"tokens: {token_count})"
                )
                await update_thread_summary(session_id, messages_for_summary)
                logger.info(f"Successfully completed summary update for thread {session_id}")
            except ConversationServiceError as e:
                logger.error(
                    f"Summary update failed for thread {session_id} (reason: {summarize_reason}): {e}",
                    exc_info=True
                )
                # Don't raise - allow message to be stored even if summary fails
            except Exception as e:
                logger.error(
                    f"Unexpected error during summary update for thread {session_id} "
                    f"(reason: {summarize_reason}): {e}",
                    exc_info=True
                )
                # Don't raise - allow message to be stored even if summary fails
        
        return ConversationMessage(**message_data)
        
    except Exception as e:
        logger.error(f"Failed to add message: {e}")
        raise ConversationServiceError(f"Failed to store message: {str(e)}")
