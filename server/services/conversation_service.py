"""Conversation service for managing sessions and message history"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict
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
SUMMARY_TRIGGER_TOKENS = 3500  # Trigger summarization when approaching budget
SUMMARY_TRIGGER_MESSAGES = 20  # Trigger summarization after N messages


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
                
                # Check similarity if thread has summary
                similarity = None
                if session_data.get("summary_embedding"):
                    try:
                        thread_embedding = session_data["summary_embedding"]
                        similarity = cosine_similarity(user_embedding, thread_embedding)
                    except Exception as e:
                        logger.warning(f"Similarity calculation failed: {e}")
                
                # Apply policy
                if delta_t <= HARD_TIMEOUT_MINUTES or (similarity and similarity >= SIMILARITY_THRESHOLD):
                    # Continue thread
                    reason = (
                        f"Continuing thread: delta_t={delta_t:.1f}min"
                        + (f", similarity={similarity:.3f}" if similarity else "")
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
            
            # Check similarity if thread has summary
            similarity = None
            if session_data.get("summary_embedding"):
                try:
                    thread_embedding = session_data["summary_embedding"]
                    similarity = cosine_similarity(user_embedding, thread_embedding)
                except Exception as e:
                    logger.warning(f"Similarity calculation failed: {e}")
            
            # Apply policy
            if delta_t <= HARD_TIMEOUT_MINUTES or (similarity and similarity >= SIMILARITY_THRESHOLD):
                # Continue thread
                reason = (
                    f"Continuing thread: delta_t={delta_t:.1f}min"
                    + (f", similarity={similarity:.3f}" if similarity else "")
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
        
        # Build context with summary if available
        context_messages = []
        
        if summary:
            # Add summary as system note
            context_messages.append({
                "role": "system",
                "content": f"Previous conversation context: {summary}"
            })
        
        # Add recent messages, respecting token budget
        message_texts = [msg.content for msg in messages]
        current_tokens = estimate_tokens(message_texts)
        
        if current_tokens <= token_budget:
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
            
            for msg in reversed(messages):  # Start from most recent
                msg_tokens = estimate_tokens([msg.content])
                if accumulated_tokens + msg_tokens <= token_budget:
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
        
        # Check if summarization needed
        should_summarize = False
        
        # Check message count trigger
        if new_count % SUMMARY_TRIGGER_MESSAGES == 0:
            should_summarize = True
            logger.info(f"Summarization triggered by message count ({new_count})")
        
        # Fetch messages if we need to check token count or summarize
        messages = None
        if not should_summarize:
            # Get all messages to check token count
            messages_result = supabase.table("conversation_messages").select("*").eq(
                "session_id", session_id
            ).order("created_at", desc=False).execute()
            
            messages = [ConversationMessage(**msg) for msg in messages_result.data]
            message_texts = [msg.content for msg in messages]
            token_count = estimate_tokens(message_texts)
            
            if token_count >= SUMMARY_TRIGGER_TOKENS:
                should_summarize = True
                logger.info(f"Summarization triggered by token count ({token_count})")
        
        if should_summarize:
            # Fetch messages if not already fetched (e.g., if triggered by message count)
            if messages is None:
                messages_result = supabase.table("conversation_messages").select("*").eq(
                    "session_id", session_id
                ).order("created_at", desc=False).execute()
                
                messages = [ConversationMessage(**msg) for msg in messages_result.data]
            
            # Build messages list for summarization
            messages_for_summary = [
                {"role": msg.role.value, "content": msg.content}
                for msg in messages
            ]
            
            # Update summary (non-blocking, errors handled internally)
            try:
                update_thread_summary(session_id, messages_for_summary)
            except Exception as e:
                logger.warning(f"Failed to update summary: {e}")
        
        return ConversationMessage(**message_data)
        
    except Exception as e:
        logger.error(f"Failed to add message: {e}")
        raise ConversationServiceError(f"Failed to store message: {str(e)}")
