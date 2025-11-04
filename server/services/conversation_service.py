"""Conversation service for managing sessions and message history"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from uuid import UUID

from utils.supabase_client import get_supabase_admin_client
from models.conversations import (
    ConversationSession,
    ConversationMessage,
    ConversationHistory,
    MessageRole
)

logger = logging.getLogger(__name__)

# Session timeout: 30 minutes
SESSION_TIMEOUT_MINUTES = 30


class ConversationServiceError(Exception):
    """Base exception for conversation service errors"""
    pass


def is_session_expired(session: ConversationSession) -> bool:
    """
    Check if a session has expired (30 minutes of inactivity).
    
    Args:
        session: Conversation session to check
        
    Returns:
        True if session is expired, False otherwise
    """
    if not session.is_active:
        return True
    
    now = datetime.now(timezone.utc)
    last_activity = session.last_activity_at
    
    # Handle timezone-aware datetime
    if last_activity.tzinfo is None:
        last_activity = last_activity.replace(tzinfo=timezone.utc)
    
    time_diff = now - last_activity
    return time_diff > timedelta(minutes=SESSION_TIMEOUT_MINUTES)


def get_or_create_session(device_id: UUID, session_id: Optional[UUID] = None) -> ConversationSession:
    """
    Get an active session or create a new one.
    
    If session_id is provided:
    - Check if session exists and is active
    - Check if session has expired (30 min inactivity)
    - Return existing session if valid, create new if expired/not found
    
    If session_id is None:
    - Look for active non-expired session for device
    - Create new session if none found
    
    Args:
        device_id: Device UUID
        session_id: Optional session UUID to look up
        
    Returns:
        ConversationSession (existing or newly created)
        
    Raises:
        ConversationServiceError: If session management fails
    """
    try:
        supabase = get_supabase_admin_client()
        
        # If session_id provided, try to get that specific session
        if session_id:
            result = supabase.table("conversation_sessions").select("*").eq("id", session_id).execute()
            
            if result.data:
                session = ConversationSession(**result.data[0])
                
                # Check if session is expired
                if is_session_expired(session):
                    logger.info(f"Session {session_id} expired, creating new session")
                    # Mark old session as inactive
                    supabase.table("conversation_sessions").update({
                        "is_active": False
                    }).eq("id", session_id).execute()
                elif session.is_active and session.device_id == device_id:
                    # Valid active session - update last_activity_at
                    now = datetime.now(timezone.utc).isoformat()
                    updated = supabase.table("conversation_sessions").update({
                        "last_activity_at": now
                    }).eq("id", session_id).execute()
                    return ConversationSession(**updated.data[0])
        
        # No valid session found - look for active session for device
        result = supabase.table("conversation_sessions").select("*").eq(
            "device_id", str(device_id)
        ).eq("is_active", True).order("last_activity_at", desc=True).limit(1).execute()
        
        if result.data:
            session = ConversationSession(**result.data[0])
            
            # Check if session is expired
            if not is_session_expired(session):
                # Valid active session - update last_activity_at
                now = datetime.now(timezone.utc).isoformat()
                updated = supabase.table("conversation_sessions").update({
                    "last_activity_at": now
                }).eq("id", session.id).execute()
                return ConversationSession(**updated.data[0])
            else:
                logger.info(f"Active session {session.id} expired, creating new session")
                # Mark old session as inactive
                supabase.table("conversation_sessions").update({
                    "is_active": False
                }).eq("id", session.id).execute()
        
        # Create new session
        now = datetime.now(timezone.utc).isoformat()
        insert_data = {
            "device_id": str(device_id),
            "created_at": now,
            "last_activity_at": now,
            "is_active": True
        }
        
        created = supabase.table("conversation_sessions").insert(insert_data).execute()
        session_data = created.data[0]
        logger.info(f"Created new conversation session {session_data['id']} for device {device_id}")
        
        return ConversationSession(**session_data)
        
    except Exception as e:
        logger.error(f"Failed to get or create session: {e}")
        raise ConversationServiceError(f"Session management failed: {str(e)}")


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
        
        # Also update session last_activity_at
        supabase.table("conversation_sessions").update({
            "last_activity_at": now
        }).eq("id", session_id).execute()
        
        logger.debug(f"Added {role.value} message to session {session_id}")
        
        return ConversationMessage(**message_data)
        
    except Exception as e:
        logger.error(f"Failed to add message: {e}")
        raise ConversationServiceError(f"Failed to store message: {str(e)}")

