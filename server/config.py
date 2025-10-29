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
    
    # System Prompt - Dynamic response length guidance
    system_prompt: str = (
        "You are a helpful voice assistant that adapts response length to question complexity. "
        "For simple, factual questions (like 'Who was the first president?'), answer in one clear, "
        "succinct sentence. For moderately complex questions, provide 2-3 sentences with helpful context. "
        "For complex questions requiring detailed explanation (medical terms, technical concepts, "
        "multi-part inquiries), provide a thorough, structured answer with necessary context, examples, "
        "and caveats. Always prioritize clarity and completeness over brevity when the question demands it."
    )
    
    # LLM Configuration - Dynamic token allocation by complexity
    llm_tokens_simple: int = 100        # Short factual answers (1-2 sentences)
    llm_tokens_moderate: int = 300      # Medium explanations (2-4 sentences)
    llm_tokens_complex: int = 800       # Detailed responses (multiple paragraphs)
    
    # LLM Temperature by complexity tier
    llm_temp_simple: float = 0.5        # More deterministic for facts
    llm_temp_moderate: float = 0.7      # Balanced creativity
    llm_temp_complex: float = 0.8       # More creative for detailed explanations
    
    # Timeout Configuration
    llm_timeout_s: int = 45             # LLM API timeout (increased for complex queries)
    tts_timeout_s: int = 90             # TTS API timeout (handles longer responses)
    
    # Complexity Analysis Thresholds
    complexity_len_simple_max: int = 50         # Max chars for simple classification
    complexity_len_complex_min: int = 150       # Min chars for complex classification
    complexity_lexical_diversity_min: float = 0.6  # Unique word ratio for complexity
    
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

