"""Groq API service for transcription, LLM, and TTS operations"""
import time
import logging
from pathlib import Path
from typing import Optional, Tuple
import requests
from server.config import settings

logger = logging.getLogger(__name__)

# Groq API endpoints
GROQ_WHISPER_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_LLM_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_TTS_URL = "https://api.groq.com/openai/v1/audio/speech"


class GroqServiceError(Exception):
    """Base exception for Groq service errors"""
    pass


class TranscriptionError(GroqServiceError):
    """Error during audio transcription"""
    pass


class LLMError(GroqServiceError):
    """Error during LLM query"""
    pass


class TTSError(GroqServiceError):
    """Error during text-to-speech generation"""
    pass


def transcribe_audio(audio_file_path: Path) -> str:
    """
    Transcribe audio using Groq Whisper API
    
    Args:
        audio_file_path: Path to audio file
        
    Returns:
        Transcribed text
        
    Raises:
        TranscriptionError: If transcription fails
    """
    logger.info(f"Transcribing audio from {audio_file_path}")
    
    if not audio_file_path.exists():
        raise TranscriptionError("Audio file not found")
    
    file_size = audio_file_path.stat().st_size
    
    if file_size < 100:
        raise TranscriptionError(f"Audio file too small ({file_size} bytes)")
    
    if file_size > settings.max_audio_size_bytes:
        raise TranscriptionError(
            f"Audio file too large ({file_size} bytes), max {settings.max_audio_size_bytes}"
        )
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with open(audio_file_path, 'rb') as audio_file:
                files = {
                    'file': ('audio.wav', audio_file, 'audio/wav')
                }
                data = {
                    'model': settings.whisper_model
                }
                headers = {
                    'Authorization': f'Bearer {settings.groq_api_key}'
                }
                
                logger.info(f"Sending {file_size} bytes to Whisper API (attempt {attempt + 1}/{max_retries})")
                
                response = requests.post(
                    GROQ_WHISPER_URL,
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=60
                )
                
                logger.info(f"Whisper API response: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    transcription = result.get('text', '').strip()
                    
                    if not transcription:
                        raise TranscriptionError("Transcription returned empty text")
                    
                    logger.info(f"Transcription successful: {transcription[:100]}...")
                    return transcription
                    
                elif response.status_code == 429:
                    logger.warning("Rate limited, waiting before retry...")
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                else:
                    error_msg = f"API error {response.status_code}: {response.text}"
                    logger.error(error_msg)
                    raise TranscriptionError(error_msg)
                    
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                logger.warning(f"Request timeout, retrying... (attempt {attempt + 1}/{max_retries})")
                time.sleep(1)
                continue
            else:
                raise TranscriptionError("Request timeout after retries")
                
        except requests.exceptions.ConnectionError as e:
            raise TranscriptionError(f"Connection error: {e}")
        
        except Exception as e:
            if isinstance(e, TranscriptionError):
                raise
            raise TranscriptionError(f"Unexpected error: {e}")
    
    raise TranscriptionError("Failed after all retry attempts")


def query_llm(user_text: str, session_id: Optional[str] = None) -> str:
    """
    Query Groq LLM for response
    
    Args:
        user_text: User's transcribed text
        session_id: Optional session ID for conversation history
        
    Returns:
        LLM response text
        
    Raises:
        LLMError: If LLM query fails
    """
    logger.info(f"Querying LLM with text: {user_text[:100]}...")
    
    if not user_text or not user_text.strip():
        raise LLMError("Cannot query LLM with empty text")
    
    # TODO: Implement session-based conversation history
    # For now, each request is independent
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {settings.groq_api_key}'
            }
            
            payload = {
                'model': settings.llm_model,
                'messages': [
                    {'role': 'system', 'content': settings.system_prompt},
                    {'role': 'user', 'content': user_text.strip()}
                ],
                'max_tokens': 150,
                'temperature': 0.7
            }
            
            logger.info(f"Sending query to LLM (attempt {attempt + 1}/{max_retries})")
            
            response = requests.post(
                GROQ_LLM_URL,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            logger.info(f"LLM API response: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                
                if 'choices' not in result or len(result['choices']) == 0:
                    raise LLMError("Invalid LLM response structure")
                
                llm_response = result['choices'][0]['message']['content']
                
                if not llm_response or llm_response.strip() == "":
                    raise LLMError("LLM returned empty response")
                
                logger.info(f"LLM response: {llm_response[:100]}...")
                return llm_response.strip()
                
            elif response.status_code == 429:
                logger.warning("Rate limited, waiting before retry...")
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            else:
                error_msg = f"API error {response.status_code}: {response.text}"
                logger.error(error_msg)
                raise LLMError(error_msg)
                
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                logger.warning(f"Request timeout, retrying... (attempt {attempt + 1}/{max_retries})")
                time.sleep(1)
                continue
            else:
                raise LLMError("Request timeout after retries")
                
        except requests.exceptions.ConnectionError as e:
            raise LLMError(f"Connection error: {e}")
        
        except Exception as e:
            if isinstance(e, LLMError):
                raise
            raise LLMError(f"Unexpected error: {e}")
    
    raise LLMError("Failed after all retry attempts")


def generate_speech(text: str, output_path: Path) -> None:
    """
    Generate speech using Groq TTS API
    
    Args:
        text: Text to convert to speech
        output_path: Path to save generated audio file
        
    Raises:
        TTSError: If TTS generation fails
    """
    logger.info(f"Generating speech for text: {text[:100]}...")
    
    if not text or not text.strip():
        raise TTSError("Cannot generate speech from empty text")
    
    # Validate text length
    if len(text) > 4096:
        logger.warning(f"Text too long ({len(text)} chars), truncating to 4096")
        text = text[:4096]
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {settings.groq_api_key}'
            }
            
            payload = {
                'model': settings.tts_model,
                'input': text.strip(),
                'voice': settings.tts_voice,
                'response_format': 'wav'
            }
            
            logger.info(f"Requesting TTS (attempt {attempt + 1}/{max_retries})")
            
            response = requests.post(
                GROQ_TTS_URL,
                headers=headers,
                json=payload,
                timeout=60,
                stream=True
            )
            
            logger.info(f"TTS API response: {response.status_code}")
            
            if response.status_code == 200:
                total_bytes = 0
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            total_bytes += len(chunk)
                
                if total_bytes == 0:
                    raise TTSError("Received empty audio file")
                
                logger.info(f"Audio saved: {output_path} ({total_bytes} bytes)")
                return
                
            elif response.status_code == 429:
                logger.warning("Rate limited, waiting before retry...")
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            else:
                error_msg = f"API error {response.status_code}: {response.text}"
                logger.error(error_msg)
                raise TTSError(error_msg)
                
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                logger.warning(f"Request timeout, retrying... (attempt {attempt + 1}/{max_retries})")
                time.sleep(1)
                continue
            else:
                raise TTSError("Request timeout after retries")
                
        except requests.exceptions.ConnectionError as e:
            raise TTSError(f"Connection error: {e}")
        
        except Exception as e:
            if isinstance(e, TTSError):
                raise
            raise TTSError(f"Unexpected error: {e}")
    
    raise TTSError("Failed after all retry attempts")

