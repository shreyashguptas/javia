"""Pydantic models for conversation sessions and messages"""
from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field
from uuid import UUID


class MessageRole(str, Enum):
    """Message role enumeration"""
    USER = "user"
    ASSISTANT = "assistant"


class ConversationSession(BaseModel):
    """Response model for conversation session"""
    id: UUID
    device_id: UUID
    created_at: datetime
    last_activity_at: datetime
    is_active: bool


class ConversationMessage(BaseModel):
    """Response model for conversation message"""
    id: UUID
    session_id: UUID
    role: MessageRole
    content: str
    created_at: datetime


class ConversationHistory(BaseModel):
    """Response model for conversation history with messages"""
    session: ConversationSession
    messages: List[ConversationMessage]
    total_messages: int

