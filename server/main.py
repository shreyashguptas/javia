"""FastAPI server for voice assistant processing"""
import logging
import tempfile
import wave
from pathlib import Path
from typing import Optional
import uuid
from urllib.parse import quote
import numpy as np

from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, status, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from middleware.auth import verify_api_key
from models.requests import (
    ProcessAudioResponse,
    ErrorResponse,
    HealthResponse
)
from services.groq_service import (
    transcribe_audio,
    query_llm,
    generate_speech,
    GroqServiceError
)

# Configure logging
logging.basicConfig(
    level=settings.log_level.upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Voice Assistant API",
    description="Server-side processing for voice assistant using Groq API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware (restrict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict to specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def amplify_audio_file(input_path: Path, output_path: Path, gain: float = 2.0):
    """
    Amplify audio file on the server (offloads processing from Pi Zero 2 W).
    
    PERFORMANCE BENEFIT:
    - Server CPU is much more powerful than Pi Zero 2 W
    - Frees Pi for instant audio capture without processing
    - Amplification takes <1ms on server vs 50-100ms on Pi
    
    Args:
        input_path: Path to input WAV file
        output_path: Path to save amplified WAV file
        gain: Amplification factor (default 2.0)
    """
    if gain == 1.0:
        # No amplification needed - just copy
        import shutil
        shutil.copy(input_path, output_path)
        return
    
    try:
        # Read WAV file
        with wave.open(str(input_path), 'rb') as wf_in:
            params = wf_in.getparams()
            audio_data = wf_in.readframes(wf_in.getnframes())
        
        # Convert to numpy array
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        
        # Amplify with vectorized operations (extremely fast)
        amplified = (audio_array.astype(np.float32) * gain).clip(-32768, 32767).astype(np.int16)
        
        # Write amplified audio
        with wave.open(str(output_path), 'wb') as wf_out:
            wf_out.setparams(params)
            wf_out.writeframes(amplified.tobytes())
        
        logger.debug(f"Amplified audio with gain {gain}x")
        
    except Exception as e:
        logger.warning(f"Could not amplify audio: {e}, using original")
        import shutil
        shutil.copy(input_path, output_path)


@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint - health check"""
    return HealthResponse(
        status="healthy",
        version="1.0.0"
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        version="1.0.0"
    )


@app.post(
    "/api/v1/process",
    response_class=FileResponse,
    responses={
        200: {
            "description": "Audio response file",
            "content": {"audio/wav": {}},
            "headers": {
                "X-Transcription": {"description": "Transcribed text", "schema": {"type": "string"}},
                "X-LLM-Response": {"description": "LLM response text", "schema": {"type": "string"}},
            }
        },
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    summary="Process audio and return speech response",
    description="Upload audio file, transcribe it, get LLM response, and return TTS audio"
)
async def process_audio(
    audio: UploadFile = File(..., description="Audio file (WAV format)"),
    session_id: Optional[str] = Form(None, description="Optional session ID for conversation history"),
    microphone_gain: Optional[str] = Form("1.0", description="Microphone gain to apply (offloaded from Pi)"),
    api_key: str = Depends(verify_api_key)
):
    """
    Process audio file through the complete pipeline:
    0. Amplify audio (if gain > 1.0) - offloaded from Pi Zero 2 W
    1. Transcribe audio using Whisper
    2. Query LLM with transcription
    3. Generate speech from LLM response
    4. Return audio file with metadata headers
    
    Args:
        audio: Uploaded audio file
        session_id: Optional session ID for conversation history
        microphone_gain: Gain to apply to audio (default 1.0, Pi sends its configured gain)
        api_key: API key for authentication (from header)
        
    Returns:
        Audio file response with transcription and LLM response in headers
    """
    temp_input_file = None
    temp_amplified_file = None
    temp_output_file = None
    
    try:
        # Validate content type
        if audio.content_type not in ["audio/wav", "audio/wave", "audio/x-wav"]:
            logger.warning(f"Invalid content type: {audio.content_type}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid content type: {audio.content_type}. Expected audio/wav"
            )
        
        # Create temporary file for input audio
        temp_input_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        temp_input_path = Path(temp_input_file.name)
        
        # Save uploaded file
        content = await audio.read()
        file_size = len(content)
        
        logger.info(f"Received audio file: {file_size} bytes")
        
        # Validate file size
        if file_size > settings.max_audio_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large: {file_size} bytes. Max: {settings.max_audio_size_bytes}"
            )
        
        if file_size < 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File too small, likely empty or corrupted"
            )
        
        temp_input_file.write(content)
        temp_input_file.close()
        
        # Step 0: Amplify audio on server (offload processing from Pi)
        gain = float(microphone_gain or "1.0")
        if gain != 1.0:
            logger.info(f"Step 0: Amplifying audio with gain {gain}x (offloaded from Pi)...")
            temp_amplified_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            temp_amplified_path = Path(temp_amplified_file.name)
            temp_amplified_file.close()
            
            amplify_audio_file(temp_input_path, temp_amplified_path, gain)
            # Use amplified audio for transcription
            audio_path_for_transcription = temp_amplified_path
        else:
            # No amplification needed
            audio_path_for_transcription = temp_input_path
        
        # Step 1: Transcribe audio
        logger.info("Step 1: Transcribing audio...")
        transcription = transcribe_audio(audio_path_for_transcription)
        
        # Step 2: Query LLM
        logger.info("Step 2: Querying LLM...")
        llm_response = query_llm(transcription, session_id)
        
        # Step 3: Generate speech
        logger.info("Step 3: Generating speech...")
        temp_output_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        temp_output_path = Path(temp_output_file.name)
        temp_output_file.close()
        
        generate_speech(llm_response, temp_output_path)
        
        # Return audio file with metadata in headers
        # URL-encode header values to handle Unicode characters (HTTP headers must be latin-1 compatible)
        logger.info("Processing complete, returning audio file")
        
        return FileResponse(
            path=str(temp_output_path),
            media_type="audio/wav",
            filename="response.wav",
            headers={
                "X-Transcription": quote(transcription, safe=''),
                "X-LLM-Response": quote(llm_response, safe=''),
                "X-Session-ID": quote(session_id or "", safe=''),
            },
            background=lambda: cleanup_temp_files(
                temp_input_path, 
                temp_amplified_path if temp_amplified_file else None, 
                temp_output_path
            )
        )
        
    except GroqServiceError as e:
        logger.error(f"Groq service error: {e}")
        # Clean up temp files
        if temp_input_file:
            try:
                Path(temp_input_file.name).unlink(missing_ok=True)
            except:
                pass
        if temp_amplified_file:
            try:
                Path(temp_amplified_file.name).unlink(missing_ok=True)
            except:
                pass
        if temp_output_file:
            try:
                Path(temp_output_file.name).unlink(missing_ok=True)
            except:
                pass
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Service error: {str(e)}"
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        # Clean up temp files
        if temp_input_file:
            try:
                Path(temp_input_file.name).unlink(missing_ok=True)
            except:
                pass
        if temp_amplified_file:
            try:
                Path(temp_amplified_file.name).unlink(missing_ok=True)
            except:
                pass
        if temp_output_file:
            try:
                Path(temp_output_file.name).unlink(missing_ok=True)
            except:
                pass
        raise
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        # Clean up temp files
        if temp_input_file:
            try:
                Path(temp_input_file.name).unlink(missing_ok=True)
            except:
                pass
        if temp_amplified_file:
            try:
                Path(temp_amplified_file.name).unlink(missing_ok=True)
            except:
                pass
        if temp_output_file:
            try:
                Path(temp_output_file.name).unlink(missing_ok=True)
            except:
                pass
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


def cleanup_temp_files(*files: Path):
    """Clean up temporary files"""
    for file_path in files:
        try:
            if file_path and file_path.exists():
                file_path.unlink()
                logger.debug(f"Cleaned up temp file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up temp file {file_path}: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        reload=False
    )

