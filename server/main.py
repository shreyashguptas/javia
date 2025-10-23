"""FastAPI server for voice assistant processing"""
import logging
import tempfile
import wave
from pathlib import Path
from typing import Optional
import uuid
from urllib.parse import quote
import numpy as np
import opuslib

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


def decompress_opus_to_wav(opus_path: Path, wav_path: Path):
    """
    Decompress Opus file to WAV for Groq API processing.
    
    PERFORMANCE BENEFIT:
    - Groq Whisper API requires WAV format
    - Fast decompression on server's powerful CPU
    - Supports client's Opus upload format
    
    Args:
        opus_path: Path to input Opus file
        wav_path: Path to output WAV file
    """
    try:
        logger.debug(f"Decompressing Opus to WAV: {opus_path}")
        
        # Read Opus file (custom format with length prefixes)
        with open(opus_path, 'rb') as f:
            # Read header
            sample_rate = int.from_bytes(f.read(4), 'little')
            channels = int.from_bytes(f.read(1), 'little')
            num_packets = int.from_bytes(f.read(4), 'little')
            
            logger.debug(f"Opus file: {sample_rate}Hz, {channels}ch, {num_packets} packets")
            
            # Create Opus decoder
            decoder = opuslib.Decoder(sample_rate, channels)
            
            # Decode all packets
            pcm_chunks = []
            for _ in range(num_packets):
                # Read packet length and packet
                packet_len = int.from_bytes(f.read(2), 'little')
                packet = f.read(packet_len)
                
                # Decode packet (frame size = 960 for 20ms at 48kHz)
                pcm_data = decoder.decode(packet, 960)
                pcm_chunks.append(pcm_data)
        
        # Combine all PCM data
        full_pcm = b''.join(pcm_chunks)
        
        # Write WAV file
        with wave.open(str(wav_path), 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            wf.writeframes(full_pcm)
        
        logger.debug(f"Decompressed to WAV: {wav_path.stat().st_size} bytes")
        
    except Exception as e:
        logger.error(f"Opus decompression failed: {e}")
        raise


def compress_wav_to_opus(wav_path: Path, opus_path: Path, bitrate: int = 96000):
    """
    Compress WAV file to Opus for efficient response transfer.
    
    PERFORMANCE BENEFIT:
    - 90% file size reduction for TTS responses
    - 10x faster download to Pi client
    - Server CPU can handle compression easily
    
    Args:
        wav_path: Path to input WAV file
        opus_path: Path to output Opus file
        bitrate: Bitrate in bits/second (default 96000)
    """
    try:
        logger.debug(f"Compressing WAV to Opus: {wav_path}")
        
        # DIAGNOSTIC: Validate input WAV before compression
        try:
            with open(wav_path, 'rb') as f:
                header_bytes = f.read(16)
                logger.info(f"[DIAGNOSTIC] Input WAV first 16 bytes: {header_bytes.hex()}")
                logger.info(f"[DIAGNOSTIC] Input WAV starts with RIFF: {header_bytes.startswith(b'RIFF')}")
        except Exception as e:
            logger.error(f"[DIAGNOSTIC] Error reading input WAV header: {e}")
        
        # Read WAV file
        with wave.open(str(wav_path), 'rb') as wf:
            sample_rate = wf.getframerate()
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            n_frames = wf.getnframes()
            pcm_data = wf.readframes(n_frames)
        
        logger.debug(f"WAV file: {sample_rate}Hz, {channels}ch, {sample_width*8}-bit, {n_frames} frames")
        logger.info(f"[DIAGNOSTIC] PCM data size: {len(pcm_data)} bytes")
        
        # Validate format
        if sample_width != 2:
            raise ValueError(f"Expected 16-bit audio, got {sample_width*8}-bit")
        
        # Create Opus encoder
        encoder = opuslib.Encoder(sample_rate, channels, opuslib.APPLICATION_VOIP)
        encoder.bitrate = bitrate
        encoder.complexity = 10  # Maximum quality
        
        # Encode in chunks (Opus frame size for 48kHz: 960 samples = 20ms)
        frame_size = 960  # 20ms at 48kHz
        frame_bytes = frame_size * channels * sample_width
        
        opus_chunks = []
        offset = 0
        
        while offset < len(pcm_data):
            # Get chunk
            chunk = pcm_data[offset:offset + frame_bytes]
            
            # Pad last chunk if necessary
            if len(chunk) < frame_bytes:
                chunk += b'\x00' * (frame_bytes - len(chunk))
            
            # Encode chunk
            opus_frame = encoder.encode(chunk, frame_size)
            opus_chunks.append(opus_frame)
            
            offset += frame_bytes
        
        # Write Opus file with custom format (length prefixes)
        with open(opus_path, 'wb') as f:
            # Write header: sample_rate (4 bytes), channels (1 byte), num_packets (4 bytes)
            f.write(sample_rate.to_bytes(4, 'little'))
            f.write(channels.to_bytes(1, 'little'))
            f.write(len(opus_chunks).to_bytes(4, 'little'))
            
            # Write each Opus packet with length prefix
            for packet in opus_chunks:
                f.write(len(packet).to_bytes(2, 'little'))
                f.write(packet)
        
        original_size = wav_path.stat().st_size
        compressed_size = opus_path.stat().st_size
        compression_ratio = (1 - compressed_size / original_size) * 100
        
        logger.debug(f"Compressed: {original_size} → {compressed_size} bytes ({compression_ratio:.1f}% reduction)")
        
        # DIAGNOSTIC: Validate Opus output
        try:
            with open(opus_path, 'rb') as f:
                opus_header = f.read(16)
                logger.info(f"[DIAGNOSTIC] Opus file first 16 bytes: {opus_header.hex()}")
                # Verify custom header format
                if len(opus_header) >= 9:
                    read_sample_rate = int.from_bytes(opus_header[0:4], 'little')
                    read_channels = int.from_bytes(opus_header[4:5], 'little')
                    read_num_packets = int.from_bytes(opus_header[5:9], 'little')
                    logger.info(f"[DIAGNOSTIC] Opus header: {read_sample_rate}Hz, {read_channels}ch, {read_num_packets} packets")
                    logger.info(f"[DIAGNOSTIC] ✓ Opus file created successfully")
        except Exception as e:
            logger.error(f"[DIAGNOSTIC] Error validating Opus output: {e}")
        
    except Exception as e:
        logger.error(f"Opus compression failed: {e}")
        raise


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
    audio: UploadFile = File(..., description="Audio file (WAV or Opus format)"),
    session_id: Optional[str] = Form(None, description="Optional session ID for conversation history"),
    microphone_gain: Optional[str] = Form("1.0", description="Microphone gain to apply (offloaded from Pi)"),
    api_key: str = Depends(verify_api_key)
):
    """
    Process audio file through the complete pipeline:
    0. Decompress Opus (if Opus format) and amplify audio (if gain > 1.0)
    1. Transcribe audio using Whisper
    2. Query LLM with transcription
    3. Generate speech from LLM response
    4. Compress to Opus and return audio file with metadata headers
    
    Args:
        audio: Uploaded audio file (Opus or WAV)
        session_id: Optional session ID for conversation history
        microphone_gain: Gain to apply to audio (default 1.0, Pi sends its configured gain)
        api_key: API key for authentication (from header)
        
    Returns:
        Opus audio file response with transcription and LLM response in headers
    """
    temp_input_file = None
    temp_decompressed_file = None
    temp_amplified_file = None
    temp_output_wav_file = None
    temp_output_opus_file = None
    
    try:
        # Validate content type (accept both Opus and WAV)
        is_opus = audio.content_type in ["audio/opus", "audio/ogg"]
        is_wav = audio.content_type in ["audio/wav", "audio/wave", "audio/x-wav"]
        
        if not is_opus and not is_wav:
            logger.warning(f"Invalid content type: {audio.content_type}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid content type: {audio.content_type}. Expected audio/opus or audio/wav"
            )
        
        # Create temporary file for input audio
        suffix = ".opus" if is_opus else ".wav"
        temp_input_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        temp_input_path = Path(temp_input_file.name)
        
        # Save uploaded file
        content = await audio.read()
        file_size = len(content)
        
        logger.info(f"Received {suffix} audio file: {file_size} bytes")
        
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
        
        # Step 0a: Decompress Opus to WAV if needed
        if is_opus:
            logger.info("Step 0a: Decompressing Opus to WAV...")
            temp_decompressed_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            temp_decompressed_path = Path(temp_decompressed_file.name)
            temp_decompressed_file.close()
            
            decompress_opus_to_wav(temp_input_path, temp_decompressed_path)
            wav_path_for_processing = temp_decompressed_path
        else:
            # Already WAV
            wav_path_for_processing = temp_input_path
        
        # Step 0b: Amplify audio on server (offload processing from Pi)
        gain = float(microphone_gain or "1.0")
        if gain != 1.0:
            logger.info(f"Step 0b: Amplifying audio with gain {gain}x (offloaded from Pi)...")
            temp_amplified_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            temp_amplified_path = Path(temp_amplified_file.name)
            temp_amplified_file.close()
            
            amplify_audio_file(wav_path_for_processing, temp_amplified_path, gain)
            # Use amplified audio for transcription
            audio_path_for_transcription = temp_amplified_path
        else:
            # No amplification needed
            audio_path_for_transcription = wav_path_for_processing
        
        # Step 1: Transcribe audio
        logger.info("Step 1: Transcribing audio...")
        transcription = transcribe_audio(audio_path_for_transcription)
        
        # Step 2: Query LLM
        logger.info("Step 2: Querying LLM...")
        llm_response = query_llm(transcription, session_id)
        
        # Step 3: Generate speech (WAV)
        logger.info("Step 3: Generating speech...")
        temp_output_wav_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        temp_output_wav_path = Path(temp_output_wav_file.name)
        temp_output_wav_file.close()
        
        generate_speech(llm_response, temp_output_wav_path)
        
        # Step 4: Compress WAV to Opus for efficient transfer
        logger.info("Step 4: Compressing response to Opus...")
        temp_output_opus_file = tempfile.NamedTemporaryFile(delete=False, suffix=".opus")
        temp_output_opus_path = Path(temp_output_opus_file.name)
        temp_output_opus_file.close()
        
        compress_wav_to_opus(temp_output_wav_path, temp_output_opus_path, bitrate=96000)
        
        # Return Opus audio file with metadata in headers
        # URL-encode header values to handle Unicode characters (HTTP headers must be latin-1 compatible)
        logger.info("Processing complete, returning Opus audio file")
        
        return FileResponse(
            path=str(temp_output_opus_path),
            media_type="audio/opus",
            filename="response.opus",
            headers={
                "X-Transcription": quote(transcription, safe=''),
                "X-LLM-Response": quote(llm_response, safe=''),
                "X-Session-ID": quote(session_id or "", safe=''),
            },
            background=lambda: cleanup_temp_files(
                temp_input_path, 
                temp_decompressed_path if temp_decompressed_file else None,
                temp_amplified_path if temp_amplified_file else None, 
                temp_output_wav_path,
                temp_output_opus_path
            )
        )
        
    except GroqServiceError as e:
        logger.error(f"Groq service error: {e}")
        # Clean up temp files
        cleanup_temp_files(
            temp_input_path if temp_input_file else None,
            temp_decompressed_path if temp_decompressed_file else None,
            temp_amplified_path if temp_amplified_file else None,
            temp_output_wav_path if temp_output_wav_file else None,
            temp_output_opus_path if temp_output_opus_file else None
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Service error: {str(e)}"
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        # Clean up temp files
        cleanup_temp_files(
            temp_input_path if temp_input_file else None,
            temp_decompressed_path if temp_decompressed_file else None,
            temp_amplified_path if temp_amplified_file else None,
            temp_output_wav_path if temp_output_wav_file else None,
            temp_output_opus_path if temp_output_opus_file else None
        )
        raise
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        # Clean up temp files
        cleanup_temp_files(
            temp_input_path if temp_input_file else None,
            temp_decompressed_path if temp_decompressed_file else None,
            temp_amplified_path if temp_amplified_file else None,
            temp_output_wav_path if temp_output_wav_file else None,
            temp_output_opus_path if temp_output_opus_file else None
        )
        
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

