"""Configuration management for voice assistant server"""
import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Groq API Configuration
    groq_api_key: str
    
    # Server Security
    server_api_key: str
    
    # Model Configurations
    whisper_model: str = "whisper-large-v3-turbo"
    llm_model: str = "openai/gpt-oss-20b"
    tts_model: str = "playai-tts"
    tts_voice: str = "Cheyenne-PlayAI"
    
    # System Prompt
    system_prompt: str = """You are a helpful and intelligent voice assistant. Adapt your response length based on what the question requires:

- For simple, straightforward questions with direct answers (like math, facts, definitions), be concise and clear - usually 1-2 sentences.
- For questions that ask "how", "why", or require explanation, context, or multiple steps, provide thorough and helpful answers with appropriate detail.
- For open-ended or complex topics, give comprehensive responses that fully address the question.

Always use clear, simple language at the appropriate level for the question. Prioritize being helpful and informative over being brief. Your goal is to give the right amount of information - not too little, not too much."""
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"
    
    # Audio Configuration
    max_audio_size_mb: int = 25
    sample_rate: int = 48000
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    @property
    def max_audio_size_bytes(self) -> int:
        """Convert MB to bytes"""
        return self.max_audio_size_mb * 1024 * 1024


# Global settings instance
settings = Settings()

