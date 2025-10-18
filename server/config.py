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
    tts_voice: str = "Chip-PlayAI"
    
    # System Prompt
    system_prompt: str = "You are a helpful voice assistant that gives concise, factual answers. Keep responses brief and conversational, under 3 sentences."
    
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

