"""Pydantic models for API requests and responses"""
from typing import Optional
from pydantic import BaseModel, Field


class ProcessAudioRequest(BaseModel):
    """Request model for audio processing (metadata)"""
    session_id: Optional[str] = Field(
        None,
        description="Optional session ID for conversation history tracking"
    )


class ProcessAudioResponse(BaseModel):
    """Response model for successful audio processing"""
    transcription: str = Field(..., description="Transcribed text from audio")
    llm_response: str = Field(..., description="LLM response text")
    session_id: Optional[str] = Field(None, description="Session ID used")


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")

