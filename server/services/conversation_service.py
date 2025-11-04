"""Conversation service for managing sessions and message history"""
import logging
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
SUMMARY_TRIGGER_MESSAGES = 10  # Trigger summarization after N messages (periodic refresh)
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


def generate_message_embedding(thread_id: UUID, num_messages: int = 4) -> Optional[List[float]]:
    """
    Generate embedding from recent messages when summary doesn't exist.
    
    This is a fallback strategy for similarity checks when threads don't have
    summaries yet. It concatenates recent messages and generates an embedding.
    
    Args:
        thread_id: Thread UUID
        num_messages: Number of recent messages to use (default 4)
        
    Returns:
        Embedding vector (1536 dimensions) or None if no messages or error
    """
    try:
        supabase = get_supabase_admin_client()
        
        # Get recent messages
        messages_result = supabase.table("conversation_messages").select("*").eq(
            "session_id", thread_id
        ).order("created_at", desc=True).limit(num_messages).execute()
        
        if not messages_result.data:
            return None
        
        # Concatenate message content (most recent first)
        messages = [ConversationMessage(**msg) for msg in messages_result.data]
        # Reverse to get chronological order
        messages.reverse()
        
        # Build text from messages
        message_texts = []
        for msg in messages:
            role_label = "User" if msg.role == MessageRole.USER else "Assistant"
            message_texts.append(f"{role_label}: {msg.content}")
        
        combined_text = " ".join(message_texts)
        
        if not combined_text.strip():
            return None
        
        # Generate embedding
        embedding = embed_text(combined_text)
        logger.debug(f"Generated message-based embedding for thread {thread_id} from {len(messages)} messages")
        return embedding
        
    except EmbeddingError as e:
        logger.warning(f"Failed to generate message embedding for thread {thread_id}: {e}")
        return None
    except Exception as e:
        logger.warning(f"Error generating message embedding: {e}")
        return None


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
    
    # Periodic summary refresh (every 10 messages)
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
                
                # Check similarity - use summary embedding if available, fallback to message embedding
                similarity = None
                similarity_method = None
                
                if session_data.get("summary_embedding"):
                    try:
                        thread_embedding = session_data["summary_embedding"]
                        similarity = cosine_similarity(user_embedding, thread_embedding)
                        similarity_method = "summary"
                    except Exception as e:
                        logger.warning(f"Similarity calculation failed: {e}")
                else:
                    # Fallback: generate embedding from recent messages
                    try:
                        message_embedding = generate_message_embedding(optional_session_id, num_messages=4)
                        if message_embedding:
                            similarity = cosine_similarity(user_embedding, message_embedding)
                            similarity_method = "messages"
                            logger.debug(f"Used message-based similarity for thread {optional_session_id}: {similarity:.3f}")
                    except Exception as e:
                        logger.warning(f"Failed to generate message embedding for similarity: {e}")
                
                # Apply policy
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
            
            # Check similarity - use summary embedding if available, fallback to message embedding
            similarity = None
            similarity_method = None
            
            if session_data.get("summary_embedding"):
                try:
                    thread_embedding = session_data["summary_embedding"]
                    similarity = cosine_similarity(user_embedding, thread_embedding)
                    similarity_method = "summary"
                except Exception as e:
                    logger.warning(f"Similarity calculation failed: {e}")
            else:
                # Fallback: generate embedding from recent messages
                try:
                    message_embedding = generate_message_embedding(session_id, num_messages=4)
                    if message_embedding:
                        similarity = cosine_similarity(user_embedding, message_embedding)
                        similarity_method = "messages"
                        logger.debug(f"Used message-based similarity for thread {session_id}: {similarity:.3f}")
                except Exception as e:
                    logger.warning(f"Failed to generate message embedding for similarity: {e}")
            
            # Apply policy
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
        logger.error(f"Failed to resolve thread: {e}")
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


def update_thread_summary(thread_id: UUID, messages: List[Dict[str, str]]) -> None:
    """
    Update thread summary and embedding based on conversation messages.
    
    Args:
        thread_id: Thread UUID
        messages: List of messages to summarize
        
    Raises:
        ConversationServiceError: If summary update fails
    """
    try:
        # Generate summary
        summary = summarize_thread(messages)
        
        # Generate embedding for summary
        summary_embedding = embed_text(summary)
        
        # Update database
        supabase = get_supabase_admin_client()
        supabase.table("conversation_sessions").update({
            "summary": summary,
            "summary_embedding": summary_embedding
        }).eq("id", thread_id).execute()
        
        logger.info(f"Updated summary for thread {thread_id}: {summary[:100]}...")
        
    except SummarizationError as e:
        logger.warning(f"Summarization failed for thread {thread_id}: {e}")
        # Don't fail completely - just log warning
    except EmbeddingError as e:
        logger.warning(f"Embedding generation failed for thread {thread_id}: {e}")
        # Don't fail completely - just log warning
    except Exception as e:
        logger.error(f"Failed to update thread summary: {e}")
        raise ConversationServiceError(f"Summary update failed: {str(e)}")


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


def add_message(session_id: UUID, role: MessageRole, content: str) -> ConversationMessage:
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
        
        logger.debug(f"Added {role.value} message to session {session_id} (count: {new_count})")
        
        # Fetch messages once for all checks (token count and summarization)
        messages_result = supabase.table("conversation_messages").select("*").eq(
            "session_id", session_id
        ).order("created_at", desc=False).execute()
        
        messages = [ConversationMessage(**msg) for msg in messages_result.data]
        message_texts = [msg.content for msg in messages]
        token_count = estimate_tokens(message_texts)
        
        # Check if summarization needed using centralized helper
        should_summarize, summarize_reason = _should_summarize(new_count, token_count)
        
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
            
            # Update summary (non-blocking, errors handled internally)
            try:
                logger.info(f"Updating thread summary (reason: {summarize_reason}, messages: {len(messages_for_summary)})")
                update_thread_summary(session_id, messages_for_summary)
                logger.info(f"Successfully updated summary for thread {session_id}")
            except Exception as e:
                logger.warning(f"Failed to update summary for thread {session_id} (reason: {summarize_reason}): {e}")
        
        return ConversationMessage(**message_data)
        
    except Exception as e:
        logger.error(f"Failed to add message: {e}")
        raise ConversationServiceError(f"Failed to store message: {str(e)}")
