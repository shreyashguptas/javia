"""Groq API service for transcription, LLM, and TTS operations"""
import time
import logging
from pathlib import Path
from typing import Optional, Tuple, Literal
import requests
from config import settings

logger = logging.getLogger(__name__)

# Groq API endpoints
GROQ_WHISPER_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_LLM_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_TTS_URL = "https://api.groq.com/openai/v1/audio/speech"

# Technical term indicators for complexity analysis
TECHNICAL_TERMS = {
    # Medical terms
    'pathophysiology', 'myocardial', 'infarction', 'cardiovascular', 'diagnosis', 
    'treatment', 'syndrome', 'disease', 'symptom', 'etiology', 'prognosis',
    'therapeutic', 'pharmacological', 'clinical', 'acute', 'chronic',
    # Legal terms
    'jurisdiction', 'litigation', 'liability', 'statute', 'precedent', 'tort',
    'plaintiff', 'defendant', 'constitution', 'amendment', 'regulation',
    # Financial terms
    'amortization', 'derivative', 'equity', 'portfolio', 'liquidity', 'volatility',
    'arbitrage', 'capitalization', 'diversification', 'fiscal', 'monetary',
    # Programming/technical
    'algorithm', 'encryption', 'protocol', 'database', 'architecture', 'implementation',
    'framework', 'asynchronous', 'authentication', 'optimization', 'deployment',
    'infrastructure', 'kubernetes', 'microservice', 'blockchain', 'neural',
    # Science
    'quantum', 'molecular', 'thermodynamic', 'electromagnetic', 'hypothesis',
    'experiment', 'theory', 'phenomenon', 'particle', 'equation'
}

ComplexityLevel = Literal["simple", "moderate", "complex"]


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


def analyze_query_complexity(text: str) -> ComplexityLevel:
    """
    Analyze query complexity using heuristics.
    
    Factors considered:
    - Length (characters and words)
    - Lexical diversity (unique words / total words)
    - Presence of technical terms
    - Question indicators (how, why, explain suggest complexity)
    
    Args:
        text: User query text
        
    Returns:
        Complexity level: "simple", "moderate", or "complex"
    """
    text_lower = text.lower().strip()
    
    # Basic metrics
    char_count = len(text)
    words = text_lower.split()
    word_count = len(words)
    
    # Lexical diversity (unique words / total words)
    unique_words = set(words)
    lexical_diversity = len(unique_words) / word_count if word_count > 0 else 0
    
    # Check for technical terms
    technical_term_count = sum(1 for word in words if word in TECHNICAL_TERMS)
    
    # Check for complexity indicators
    complexity_indicators = ['explain', 'how does', 'why does', 'what is the difference',
                            'compare', 'describe', 'elaborate', 'detail', 'pathophysiology']
    has_complexity_indicator = any(indicator in text_lower for indicator in complexity_indicators)
    
    # Check for question words suggesting depth
    depth_questions = ['why', 'how']
    has_depth_question = any(text_lower.startswith(q) for q in depth_questions)
    
    # Scoring logic
    complexity_score = 0
    
    # Length-based scoring
    if char_count <= settings.complexity_len_simple_max:
        complexity_score += 0  # Simple
    elif char_count >= settings.complexity_len_complex_min:
        complexity_score += 2  # Complex
    else:
        complexity_score += 1  # Moderate
    
    # Lexical diversity
    if lexical_diversity >= settings.complexity_lexical_diversity_min:
        complexity_score += 1
    
    # Technical terms (strong indicator)
    if technical_term_count >= 2:
        complexity_score += 2
    elif technical_term_count == 1:
        complexity_score += 1
    
    # Complexity indicators
    if has_complexity_indicator:
        complexity_score += 1
    
    # Depth questions
    if has_depth_question:
        complexity_score += 1
    
    # Classify based on score
    if complexity_score <= 1:
        level = "simple"
    elif complexity_score >= 4:
        level = "complex"
    else:
        level = "moderate"
    
    logger.info(
        f"Complexity analysis: level={level}, score={complexity_score}, "
        f"chars={char_count}, words={word_count}, "
        f"lexical_diversity={lexical_diversity:.2f}, "
        f"technical_terms={technical_term_count}"
    )
    
    return level


def select_llm_params(complexity: ComplexityLevel) -> Tuple[int, float]:
    """
    Select LLM parameters based on query complexity.
    
    Args:
        complexity: Query complexity level
        
    Returns:
        Tuple of (max_tokens, temperature)
    """
    if complexity == "simple":
        max_tokens = settings.llm_tokens_simple
        temperature = settings.llm_temp_simple
    elif complexity == "complex":
        max_tokens = settings.llm_tokens_complex
        temperature = settings.llm_temp_complex
    else:  # moderate
        max_tokens = settings.llm_tokens_moderate
        temperature = settings.llm_temp_moderate
    
    logger.info(f"Selected LLM params for {complexity}: max_tokens={max_tokens}, temperature={temperature}")
    
    return max_tokens, temperature


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


def query_llm(user_text: str, session_id: Optional[str] = None) -> Tuple[str, ComplexityLevel]:
    """
    Query Groq LLM for response with dynamic token allocation based on complexity
    
    Args:
        user_text: User's transcribed text
        session_id: Optional session ID for conversation history
        
    Returns:
        Tuple of (LLM response text, complexity level)
        
    Raises:
        LLMError: If LLM query fails
    """
    logger.info(f"Querying LLM with text: {user_text[:100]}...")
    
    if not user_text or not user_text.strip():
        raise LLMError("Cannot query LLM with empty text")
    
    # Analyze query complexity
    complexity = analyze_query_complexity(user_text)
    
    # Select parameters based on complexity
    max_tokens, temperature = select_llm_params(complexity)
    
    # Build complexity-aware secondary system hint
    if complexity == "simple":
        complexity_hint = "This appears to be a simple factual question. Provide a clear, one-sentence answer."
    elif complexity == "complex":
        complexity_hint = "This is a complex question requiring detailed explanation. Provide a thorough, well-structured answer with necessary context."
    else:  # moderate
        complexity_hint = "This question requires moderate detail. Provide 2-3 sentences with helpful context."
    
    # TODO: Implement session-based conversation history
    # For now, each request is independent
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            start_time = time.time()
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {settings.groq_api_key}'
            }
            
            payload = {
                'model': settings.llm_model,
                'messages': [
                    {'role': 'system', 'content': settings.system_prompt},
                    {'role': 'system', 'content': complexity_hint},
                    {'role': 'user', 'content': user_text.strip()}
                ],
                'max_tokens': max_tokens,
                'temperature': temperature
            }
            
            logger.info(
                f"Sending query to LLM (attempt {attempt + 1}/{max_retries}) - "
                f"complexity={complexity}, max_tokens={max_tokens}, temp={temperature}"
            )
            
            response = requests.post(
                GROQ_LLM_URL,
                headers=headers,
                json=payload,
                timeout=settings.llm_timeout_s
            )
            
            elapsed_time = time.time() - start_time
            logger.info(f"LLM API response: {response.status_code} (elapsed: {elapsed_time:.2f}s)")
            
            if response.status_code == 200:
                result = response.json()
                
                if 'choices' not in result or len(result['choices']) == 0:
                    raise LLMError("Invalid LLM response structure")
                
                choice = result['choices'][0]
                llm_response = choice['message']['content']
                finish_reason = choice.get('finish_reason', 'unknown')
                
                if not llm_response or llm_response.strip() == "":
                    raise LLMError("LLM returned empty response")
                
                # Log comprehensive metrics
                response_length = len(llm_response)
                response_preview = llm_response[:120].replace('\n', ' ')
                
                logger.info(
                    f"LLM response received - "
                    f"length={response_length} chars, "
                    f"finish_reason={finish_reason}, "
                    f"preview=\"{response_preview}...\""
                )
                
                # Warn if truncated due to token limit
                if finish_reason == "length":
                    logger.warning(
                        f"Response truncated by max_tokens limit ({max_tokens}). "
                        f"Consider increasing {complexity.upper()}_TOKENS setting."
                    )
                
                return llm_response.strip(), complexity
                
            elif response.status_code == 429:
                logger.warning(f"Rate limited (429), waiting before retry with exponential backoff...")
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            else:
                error_msg = f"API error {response.status_code}: {response.text}"
                logger.error(error_msg)
                raise LLMError(error_msg)
                
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                logger.warning(
                    f"Request timeout after {settings.llm_timeout_s}s, "
                    f"retrying... (attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(1)
                continue
            else:
                raise LLMError(
                    f"Request timeout after {settings.llm_timeout_s}s and {max_retries} retries. "
                    f"Consider increasing LLM_TIMEOUT_S."
                )
                
        except requests.exceptions.ConnectionError as e:
            raise LLMError(f"Connection error: {e}")
        
        except Exception as e:
            if isinstance(e, LLMError):
                raise
            raise LLMError(f"Unexpected error: {e}")
    
    raise LLMError("Failed after all retry attempts")


def generate_speech(text: str, output_path: Path) -> None:
    """
    Generate speech using Groq TTS API with configurable timeout
    
    Args:
        text: Text to convert to speech
        output_path: Path to save generated audio file
        
    Raises:
        TTSError: If TTS generation fails
    """
    original_length = len(text)
    logger.info(f"Generating speech for text: {text[:100]}... (length={original_length} chars)")
    
    if not text or not text.strip():
        raise TTSError("Cannot generate speech from empty text")
    
    # Validate and potentially truncate text length
    truncated = False
    if len(text) > 4096:
        truncated = True
        truncation_amount = len(text) - 4096
        logger.warning(
            f"Text exceeds TTS limit ({len(text)} chars > 4096). "
            f"Truncating {truncation_amount} characters."
        )
        text = text[:4096]
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            start_time = time.time()
            
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
            
            logger.info(
                f"Requesting TTS (attempt {attempt + 1}/{max_retries}) - "
                f"text_length={len(text)}, timeout={settings.tts_timeout_s}s"
            )
            
            response = requests.post(
                GROQ_TTS_URL,
                headers=headers,
                json=payload,
                timeout=settings.tts_timeout_s,
                stream=True
            )
            
            elapsed_time = time.time() - start_time
            logger.info(f"TTS API response: {response.status_code} (elapsed: {elapsed_time:.2f}s)")
            
            if response.status_code == 200:
                total_bytes = 0
                chunk_count = 0
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            total_bytes += len(chunk)
                            chunk_count += 1
                
                if total_bytes == 0:
                    raise TTSError("Received empty audio file")
                
                logger.info(
                    f"TTS audio saved: {output_path} - "
                    f"size={total_bytes} bytes, chunks={chunk_count}, "
                    f"truncated={'yes' if truncated else 'no'}"
                )
                
                # Log warning if this was a truncated response
                if truncated:
                    logger.warning(
                        f"TTS generated from truncated text. Original was {original_length} chars. "
                        f"Consider reducing LLM token limits to stay within TTS 4096-char limit."
                    )
                
                return
                
            elif response.status_code == 429:
                logger.warning(f"Rate limited (429), waiting before retry with exponential backoff...")
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            else:
                error_msg = f"API error {response.status_code}: {response.text}"
                logger.error(error_msg)
                raise TTSError(error_msg)
                
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                logger.warning(
                    f"Request timeout after {settings.tts_timeout_s}s, "
                    f"retrying... (attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(1)
                continue
            else:
                raise TTSError(
                    f"Request timeout after {settings.tts_timeout_s}s and {max_retries} retries. "
                    f"Consider increasing TTS_TIMEOUT_S for longer responses."
                )
                
        except requests.exceptions.ConnectionError as e:
            raise TTSError(f"Connection error: {e}")
        
        except Exception as e:
            if isinstance(e, TTSError):
                raise
            raise TTSError(f"Unexpected error: {e}")
    
    raise TTSError("Failed after all retry attempts")

