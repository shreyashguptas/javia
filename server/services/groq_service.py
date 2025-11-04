"""Groq API service for transcription, LLM, and TTS operations"""
import time
import logging
from pathlib import Path
from typing import Optional, Tuple, List, Dict
import requests
from config import settings

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


def check_ffmpeg_available() -> bool:
    """
    Check if ffmpeg is available on the system.

    Returns:
        bool: True if ffmpeg is available, False otherwise
    """
    try:
        import subprocess
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        return False


def check_ffprobe_available() -> bool:
    """
    Check if ffprobe is available on the system.

    Returns:
        bool: True if ffprobe is available, False otherwise
    """
    try:
        import subprocess
        result = subprocess.run(
            ["ffprobe", "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        return False


def compress_audio_for_groq(audio_file_path: Path) -> Path:
    """
    Compress audio file to optimal format for Groq API while preserving stereo quality.

    Preserves stereo channels and higher sample rate for better quality.
    Uses FLAC codec for efficient compression without quality loss.

    Args:
        audio_file_path: Path to input audio file

    Returns:
        Path to compressed audio file

    Raises:
        TranscriptionError: If compression fails
    """
    import subprocess
    import tempfile

    # Check if ffmpeg is available
    if not check_ffmpeg_available():
        raise TranscriptionError(
            "Audio compression failed: ffmpeg is not installed. "
            "Please install ffmpeg on the server system. "
            "Run: apt update && apt install ffmpeg"
        )

    logger.info(f"Compressing audio for Groq API: {audio_file_path}")

    # Create temporary file for compressed output
    with tempfile.NamedTemporaryFile(suffix=".flac", delete=False) as temp_file:
        compressed_path = Path(temp_file.name)

    try:
        # Preserve stereo and sample rate, just change codec to FLAC for compression
        # This maintains audio quality while reducing file size
        cmd = [
            "ffmpeg", "-y", "-i", str(audio_file_path),
            "-c:a", "flac",  # FLAC codec (lossless compression)
            "-compression_level", "8",  # High compression
            str(compressed_path)
        ]

        logger.debug(f"Running ffmpeg compression: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            raise TranscriptionError(f"Audio compression failed: {result.stderr}")

        original_size = audio_file_path.stat().st_size
        compressed_size = compressed_path.stat().st_size
        compression_ratio = (1 - compressed_size / original_size) * 100

        logger.info(f"Audio compressed: {original_size} → {compressed_size} bytes ({compression_ratio:.1f}% reduction)")

        return compressed_path

    except subprocess.TimeoutExpired:
        compressed_path.unlink(missing_ok=True)
        raise TranscriptionError("Audio compression timeout")
    except Exception as e:
        compressed_path.unlink(missing_ok=True)
        raise TranscriptionError(f"Audio compression failed: {e}")


def split_audio_into_chunks(audio_file_path: Path, max_chunk_size_mb: int = 45) -> list[Path]:
    """
    Split large audio files into chunks that fit within Groq's size limits.

    Args:
        audio_file_path: Path to input audio file
        max_chunk_size_mb: Maximum chunk size in MB (defaults to 45MB, leaving safety buffer)

    Returns:
        List of chunk file paths

    Raises:
        TranscriptionError: If splitting fails
    """
    import subprocess
    import tempfile

    # Check if ffprobe is available
    if not check_ffprobe_available():
        raise TranscriptionError(
            "Audio splitting failed: ffprobe is not installed. "
            "Please install ffmpeg on the server system. "
            "Run: apt update && apt install ffmpeg"
        )

    logger.info(f"Splitting audio into chunks: {audio_file_path}")

    file_size_mb = audio_file_path.stat().st_size / (1024 * 1024)
    if file_size_mb <= max_chunk_size_mb:
        # No need to split
        return [audio_file_path]

    try:
        # Get audio duration using ffprobe
        probe_cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", str(audio_file_path)
        ]

        probe_result = subprocess.run(
            probe_cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        if probe_result.returncode != 0:
            raise TranscriptionError(f"Failed to get audio duration: {probe_result.stderr}")

        import json
        probe_data = json.loads(probe_result.stdout)
        duration = float(probe_data["format"]["duration"])

        # Calculate number of chunks needed
        # Estimate compressed chunk size (FLAC at 48kHz stereo is ~5-7 MB/minute)
        # FLAC compression typically achieves 30-50% reduction from WAV
        bytes_per_minute = 6 * 1024 * 1024  # 6MB per minute estimate for 48kHz stereo FLAC
        max_chunk_bytes = max_chunk_size_mb * 1024 * 1024
        chunk_duration_minutes = max_chunk_bytes / bytes_per_minute  # minutes
        chunk_duration_seconds = chunk_duration_minutes * 60  # Convert to seconds

        num_chunks = int(duration / chunk_duration_seconds) + 1
        actual_chunk_duration = duration / num_chunks

        logger.info(f"Splitting {duration:.1f}s audio into {num_chunks} chunks of ~{actual_chunk_duration:.1f}s each")

        chunk_paths = []

        for i in range(num_chunks):
            start_time = i * actual_chunk_duration

            with tempfile.NamedTemporaryFile(suffix=".flac", delete=False) as temp_file:
                chunk_path = Path(temp_file.name)

            # Extract chunk using ffmpeg - preserve original audio properties
            cmd = [
                "ffmpeg", "-y",
                "-i", str(audio_file_path),
                "-ss", str(start_time),
                "-t", str(actual_chunk_duration),
                "-c:a", "flac",  # FLAC codec for compression
                "-compression_level", "8",  # High compression
                str(chunk_path)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode != 0:
                # Clean up created chunks
                for path in chunk_paths:
                    path.unlink(missing_ok=True)
                chunk_path.unlink(missing_ok=True)
                raise TranscriptionError(f"Audio chunking failed on chunk {i+1}: {result.stderr}")

            chunk_paths.append(chunk_path)
            logger.info(f"Created chunk {i+1}/{num_chunks}: {chunk_path} ({chunk_path.stat().st_size} bytes)")

        return chunk_paths

    except Exception as e:
        raise TranscriptionError(f"Audio splitting failed: {e}")


def transcribe_audio_chunks(chunk_paths: list[Path]) -> str:
    """
    Transcribe multiple audio chunks and combine the results.

    Args:
        chunk_paths: List of audio chunk file paths

    Returns:
        Combined transcription text

    Raises:
        TranscriptionError: If transcription fails
    """
    logger.info(f"Transcribing {len(chunk_paths)} audio chunks")

    transcriptions = []

    try:
        for i, chunk_path in enumerate(chunk_paths):
            logger.info(f"Transcribing chunk {i+1}/{len(chunk_paths)}")

            # Transcribe this chunk
            chunk_transcription = transcribe_single_chunk(chunk_path)
            transcriptions.append(chunk_transcription.strip())

            # Clean up chunk file immediately after successful transcription
            chunk_path.unlink(missing_ok=True)

        # Combine transcriptions with spacing
        full_transcription = " ".join(transcriptions)

        # Clean up any double spaces or awkward transitions
        full_transcription = " ".join(full_transcription.split())

        logger.info(f"Combined transcription: {full_transcription[:200]}...")
        return full_transcription

    finally:
        # Ensure all remaining chunks are cleaned up, even if an exception occurred
        for chunk_path in chunk_paths:
            try:
                if chunk_path.exists():
                    chunk_path.unlink()
                    logger.debug(f"Cleaned up remaining chunk: {chunk_path}")
            except Exception as e:
                # Log but don't raise - we're in cleanup mode
                logger.warning(f"Failed to clean up chunk {chunk_path}: {e}")


def transcribe_single_chunk(audio_file_path: Path) -> str:
    """
    Transcribe a single audio chunk using Groq Whisper API.

    Args:
        audio_file_path: Path to audio chunk file

    Returns:
        Transcribed text

    Raises:
        TranscriptionError: If transcription fails
    """
    logger.info(f"Transcribing single chunk: {audio_file_path}")

    if not audio_file_path.exists():
        raise TranscriptionError("Audio chunk file not found")

    file_size = audio_file_path.stat().st_size

    if file_size < 100:
        raise TranscriptionError(f"Audio chunk too small ({file_size} bytes)")

    if file_size > settings.max_audio_size_bytes:
        raise TranscriptionError(
            f"Audio chunk too large ({file_size} bytes), max {settings.max_audio_size_bytes}"
        )

    max_retries = 3
    for attempt in range(max_retries):
        try:
            with open(audio_file_path, 'rb') as audio_file:
                files = {
                    'file': ('audio.flac', audio_file, 'audio/flac')
                }
                data = {
                    'model': settings.whisper_model
                }
                headers = {
                    'Authorization': f'Bearer {settings.groq_api_key}'
                }

                logger.info(f"Sending {file_size} bytes FLAC chunk to Whisper API (attempt {attempt + 1}/{max_retries})")

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

                    logger.info(f"Chunk transcription successful: {transcription[:100]}...")
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


def transcribe_audio(audio_file_path: Path) -> str:
    """
    Transcribe audio using Groq Whisper API with compression and chunking support

    Handles large files by:
    1. Compressing to FLAC format (preserving stereo and sample rate)
    2. Splitting into chunks if still too large
    3. Transcribing chunks individually and combining results

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

    original_size = audio_file_path.stat().st_size

    if original_size < 100:
        raise TranscriptionError(f"Audio file too small ({original_size} bytes)")

    try:
        # Step 1: Compress audio to optimal format for Groq
        compressed_path = compress_audio_for_groq(audio_file_path)

        try:
            # Step 2: Check if compressed file needs chunking
            compressed_size = compressed_path.stat().st_size
            # Leave 5MB buffer below configured limit for safety margin
            max_chunk_size_mb = settings.max_audio_size_mb - 5
            max_chunk_size_bytes = max_chunk_size_mb * 1024 * 1024

            if compressed_size <= max_chunk_size_bytes:
                # Single chunk - transcribe directly
                logger.info(f"Audio fits in single chunk ({compressed_size} bytes <= {max_chunk_size_mb}MB), transcribing directly")
                return transcribe_single_chunk(compressed_path)
            else:
                # Multiple chunks needed
                logger.info(f"Audio too large ({compressed_size} bytes > {max_chunk_size_mb}MB), splitting into chunks")
                chunk_paths = split_audio_into_chunks(compressed_path, max_chunk_size_mb)
                return transcribe_audio_chunks(chunk_paths)

        finally:
            # Clean up compressed file
            compressed_path.unlink(missing_ok=True)

    except Exception as e:
        if isinstance(e, TranscriptionError):
            raise
        raise TranscriptionError(f"Transcription pipeline failed: {e}")


def query_llm(user_text: str, conversation_history: Optional[List[Dict[str, str]]] = None) -> str:
    """
    Query Groq LLM for response with optional conversation history
    
    Args:
        user_text: User's transcribed text
        conversation_history: Optional list of previous messages in format [{'role': 'user'|'assistant', 'content': '...'}, ...]
        
    Returns:
        LLM response text
        
    Raises:
        LLMError: If LLM query fails
    """
    logger.info(f"Querying LLM with text: {user_text[:100]}...")
    
    if not user_text or not user_text.strip():
        raise LLMError("Cannot query LLM with empty text")
    
    # Build messages array: system prompt + conversation history + new user message
    messages = [
        {'role': 'system', 'content': settings.system_prompt}
    ]
    
    # Add conversation history if provided
    if conversation_history:
        messages.extend(conversation_history)
        logger.info(f"Using conversation history with {len(conversation_history)} previous messages")
    
    # Add current user message
    messages.append({'role': 'user', 'content': user_text.strip()})
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {settings.groq_api_key}'
            }
            
            payload = {
                'model': settings.llm_model,
                'messages': messages,
                'max_tokens': 1000,
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
                
                # Log response metrics
                response_length = len(llm_response)
                response_words = len(llm_response.split())
                usage = result.get('usage', {})
                completion_tokens = usage.get('completion_tokens', 'N/A')
                
                logger.info(f"LLM response: {llm_response[:100]}...")
                logger.info(f"Response metrics - Length: {response_length} chars, Words: {response_words}, Tokens: {completion_tokens}")
                
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

