"""Configuration management for voice assistant server"""
import os
from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Groq API Configuration
    groq_api_key: str
    
    # OpenAI API Configuration (for embeddings only)
    openai_api_key: str
    
    # Server Security
    server_api_key: str
    
    # Supabase Configuration
    supabase_url: str
    supabase_key: str
    supabase_service_key: str
    
    # Model Configurations
    whisper_model: str = "whisper-large-v3-turbo"
    llm_model: str = "groq/compound-mini"  # 3x faster than compound, optimized for low latency
    tts_model: str = "playai-tts"
    tts_voice: str = "Cheyenne-PlayAI"
    embedding_model: str = "text-embedding-3-small"
    llm_max_tokens: int = 256  # Strict limit for concise voice responses (≈30-40sec speech)

    # System Prompt - Optimized for Text-to-Speech Output
    system_prompt: str = """You are a voice assistant. Your responses will be spoken aloud, so optimize for listening:

CRITICAL RULES:
- Use plain conversational language only - NO markdown, asterisks, bullets, or formatting
- Speak numbers naturally: say "49 degrees Fahrenheit" not "49 °F"
- Spell out symbols: "percent" not "%", "equals" not "=", "at" not "@"
- Never cite sources or explain your process - just give the answer
- Keep responses brief and natural (1-3 sentences for most questions)
- For times, say "8:15 AM" as "eight fifteen A M"
- No hashtags - if mentioning one, say "hashtag" before the word

Remember: Users are LISTENING, not reading. Be conversational and clear."""
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"
    allowed_origins: Optional[str] = "*"  # Comma-separated list of allowed origins, or "*" for all
    
    # Audio Configuration
    max_audio_size_mb: int = 50  # Allow larger files before compression/chunking
    sample_rate: int = 48000
    # Opus Configuration
    opus_bitrate: int = 64000  # Default to 64kbps to match client
    opus_target_sample_rate: int = 24000  # Preferred speech rate for Opus
    
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
    
    @property
    def cors_origins(self) -> List[str]:
        """Parse allowed origins for CORS middleware"""
        if not self.allowed_origins or self.allowed_origins.strip() == "*":
            return ["*"]
        # Split by comma and strip whitespace
        origins = [origin.strip() for origin in self.allowed_origins.split(",")]
        return origins


# Global settings instance
settings = Settings()

