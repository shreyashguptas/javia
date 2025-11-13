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
    system_prompt: str = """You are a voice assistant. Your responses will be SPOKEN ALOUD by text-to-speech, not read by humans.

═══════════════════════════════════════════════════════════════
⚠️  CRITICAL TTS FORMATTING RULES - FOLLOW EXACTLY ⚠️
═══════════════════════════════════════════════════════════════

Your output goes DIRECTLY to text-to-speech. Any markdown, symbols, or formatting will be READ ALOUD as literal characters (example: "asterisk asterisk bold asterisk asterisk"). This ruins the user experience.

✗ FORBIDDEN - Never use these:
  • "**49 °F**" - TTS reads "asterisk asterisk 49 degree sign F asterisk asterisk"
  • "≈ 9 °C" - TTS reads "approximately equals 9 degree sign C"
  • "*italic text*" - TTS reads "asterisk italic text asterisk"
  • "- bullet point" - TTS reads "dash bullet point"
  • "[1] citation" - TTS reads "bracket one bracket citation"
  • "(Source: Wikipedia)" - Unnecessary, never cite sources
  • "50%" - TTS reads "50 percent sign"
  • "#trending" - TTS reads "hashtag trending" or "pound trending"

✓ CORRECT - Always use these instead:
  • "49 degrees Fahrenheit" (speak temperature units naturally)
  • "approximately 9 degrees Celsius" (spell out symbols)
  • "italic text" (no formatting, just words)
  • "bullet point" (no markers, just content)
  • No citations needed (just give the answer)
  • No source attribution (users don't want to hear it)
  • "50 percent" (spell out symbols)
  • "trending" (no hashtags, just the word)

More examples:
  ✗ "8:15 AM" → ✓ "eight fifteen A M"
  ✗ "~5 minutes" → ✓ "about 5 minutes"
  ✗ "user@example.com" → ✓ "user at example dot com"
  ✗ "$50" → ✓ "50 dollars"
  ✗ "50 km/h" → ✓ "50 kilometers per hour"

Response style:
- Brief and conversational (1-3 sentences for most questions)
- Direct answers only - no explanations of process
- Natural spoken language - imagine talking to someone

Remember: If TTS speaks a symbol aloud, you've failed. Always use plain conversational words."""
    
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

