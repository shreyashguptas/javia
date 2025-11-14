"""FastAPI server for voice assistant processing"""
import logging
import tempfile
import wave
from pathlib import Path
from typing import Optional
from urllib.parse import quote
import numpy as np
import opuslib
from uuid import UUID

from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, status, Form
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.background import BackgroundTask

from config import settings
from middleware.auth import verify_api_key
from middleware.device_auth import verify_device_uuid
from models.requests import (
    ErrorResponse,
    HealthResponse
)
from models.devices import DeviceResponse
from models.conversations import MessageRole
from services.groq_service import (
    transcribe_audio,
    query_llm,
    generate_speech_streaming,
    GroqServiceError
)
from services.conversation_service import (
    resolve_thread,
    build_context,
    add_message,
    ConversationServiceError
)
from routers import devices, updates

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

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(devices.router)
app.include_router(updates.router)

# OPTIMIZATION: In-memory context cache for pre-warming
# Cache structure: {device_id: {session_id, context, timestamp}}
import time as _t
context_cache = {}
CONTEXT_CACHE_TTL_SECONDS = 300  # 5 minutes


def amplify_audio_file(input_path: Path, output_path: Path, gain: float = 2.0):
    """
    Amplify audio file on the server (offloads processing from Raspberry Pi).
    
    PERFORMANCE BENEFIT:
    - Server CPU is much more powerful than Raspberry Pi
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
            header = f.read(9)
            if len(header) < 9:
                raise ValueError("Invalid Opus header: too short")
            sample_rate = int.from_bytes(header[0:4], 'little')
            channels = int(header[4])
            num_packets = int.from_bytes(header[5:9], 'little')
            
            logger.debug(f"Opus file: {sample_rate}Hz, {channels}ch, {num_packets} packets")

            # Validate header fields
            if channels not in (1, 2):
                raise ValueError(f"Unsupported channel count in Opus header: {channels}")
            if sample_rate not in {8000, 12000, 16000, 24000, 48000}:
                raise ValueError(
                    f"Unsupported Opus sample rate: {sample_rate}. "
                    "Expected one of 8000,12000,16000,24000,48000."
                )
            if num_packets < 0:
                raise ValueError("Invalid packet count in Opus header")
            
            # Create Opus decoder
            decoder = opuslib.Decoder(sample_rate, channels)
            
            # Decode all packets
            # Calculate frame size based on sample rate (20ms frames)
            if sample_rate == 48000:
                frame_size = 960
            elif sample_rate == 24000:
                frame_size = 480
            else:
                frame_size = max(120, int(0.02 * sample_rate))  # ~20ms
            
            pcm_chunks = []
            for _ in range(num_packets):
                # Read packet length and packet
                len_bytes = f.read(2)
                if len(len_bytes) < 2:
                    raise ValueError("Unexpected EOF while reading packet length")
                packet_len = int.from_bytes(len_bytes, 'little')
                if packet_len <= 0:
                    raise ValueError("Invalid packet length in Opus stream")
                packet = f.read(packet_len)
                if len(packet) < packet_len:
                    raise ValueError("Unexpected EOF while reading Opus packet")
                
                # Decode packet with correct frame size for sample rate
                pcm_data = decoder.decode(packet, frame_size)
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


async def stream_wav_to_opus(wav_chunks, bitrate: int = 64000):
    """
    Stream WAV audio chunks through Opus encoder, yielding length-prefixed Opus packets.

    This function:
    1. Parses WAV header to get sample_rate, channels, sample_width
    2. Buffers PCM data until complete Opus frames are available
    3. Encodes frames and yields: header (9 bytes) then length-prefixed packets

    Args:
        wav_chunks: Async iterator of WAV file chunks
        bitrate: Opus bitrate in bits/second (default 64000)

    Yields:
        bytes: Opus header (first yield) then length-prefixed Opus packets
    """
    try:
        # State variables
        buffer = bytearray()
        header_parsed = False
        data_chunk_found = False
        sample_rate = None
        channels = None
        sample_width = None
        encoder = None
        frame_size = None
        frame_bytes = None
        pcm_buffer = bytearray()
        total_packets = 0

        logger.debug("Starting WAV to Opus streaming conversion")

        # Process chunks
        async for chunk in wav_chunks:
            if not chunk:
                continue

            buffer.extend(chunk)

            # Parse WAV header if not done yet
            if not header_parsed and len(buffer) >= 44:
                # WAV format (little-endian):
                # 0-3: "RIFF"
                # 4-7: file size - 8
                # 8-11: "WAVE"
                # 12-15: "fmt "
                # 16-19: fmt chunk size (usually 16)
                # 20-21: audio format (1 = PCM)
                # 22-23: num channels
                # 24-27: sample rate
                # 28-31: byte rate
                # 32-33: block align
                # 34-35: bits per sample
                # 36-39: "data"
                # 40-43: data size

                if buffer[0:4] != b'RIFF' or buffer[8:12] != b'WAVE':
                    raise ValueError("Invalid WAV header")

                channels = int.from_bytes(buffer[22:24], 'little')
                sample_rate = int.from_bytes(buffer[24:28], 'little')
                sample_width = int.from_bytes(buffer[34:36], 'little') // 8  # Convert bits to bytes

                logger.debug(f"Parsed WAV header: {sample_rate}Hz, {channels}ch, {sample_width*8}-bit")

                # Validate format
                if sample_width != 2:
                    raise ValueError(f"Expected 16-bit audio, got {sample_width*8}-bit")

                # Validate/convert sample rate for Opus
                VALID_OPUS_RATES = {8000, 12000, 16000, 24000, 48000}
                if sample_rate not in VALID_OPUS_RATES:
                    logger.warning(f"Sample rate {sample_rate}Hz not Opus-compatible, this may cause issues")
                    # For streaming, we'll use the rate as-is and hope for the best
                    # In production, you'd want to resample, but that's complex for streaming

                # Create Opus encoder
                encoder = opuslib.Encoder(sample_rate, channels, opuslib.APPLICATION_VOIP)
                encoder.bitrate = bitrate
                encoder.complexity = 3  # Low complexity for speed

                # Calculate frame size (20ms)
                if sample_rate == 48000:
                    frame_size = 960
                elif sample_rate == 24000:
                    frame_size = 480
                elif sample_rate == 16000:
                    frame_size = 320
                elif sample_rate == 12000:
                    frame_size = 240
                elif sample_rate == 8000:
                    frame_size = 160
                else:
                    frame_size = max(120, int(0.02 * sample_rate))

                frame_bytes = frame_size * channels * sample_width

                logger.debug(f"Opus encoder configured: frame_size={frame_size}, frame_bytes={frame_bytes}")

                # Yield Opus header: sample_rate (4), channels (1), num_packets (4)
                # Note: we don't know num_packets yet, so we'll write 0 and client will handle it
                header = (
                    sample_rate.to_bytes(4, 'little') +
                    channels.to_bytes(1, 'little') +
                    (0).to_bytes(4, 'little')  # num_packets unknown for streaming
                )
                yield header
                logger.debug("Sent Opus header (9 bytes)")

                header_parsed = True

                # Find data chunk and skip to PCM data
                data_pos = buffer.find(b'data')
                if data_pos != -1:
                    # Skip past "data" and data size (4 bytes for "data" + 4 bytes for data size)
                    pcm_start = data_pos + 8
                    if pcm_start < len(buffer):
                        pcm_buffer.extend(buffer[pcm_start:])
                    # Clear buffer after extracting PCM data
                    buffer = bytearray()
                    data_chunk_found = True
                else:
                    # Data chunk not found yet - need to wait for more chunks
                    # Clear the header portion from buffer to prevent it from being added to pcm_buffer
                    # Keep only the portion after the header (in case data chunk starts in next chunk)
                    # WAV header is typically 44 bytes, but we'll search for "data" marker
                    # For now, we'll keep the buffer but won't add it to pcm_buffer until data chunk is found
                    pass

            # Continue searching for data chunk if header is parsed but data chunk not found yet
            elif header_parsed and not data_chunk_found:
                # Search for data chunk in the accumulated buffer
                data_pos = buffer.find(b'data')
                if data_pos != -1:
                    # Found data chunk - extract PCM data
                    pcm_start = data_pos + 8
                    if pcm_start < len(buffer):
                        pcm_buffer.extend(buffer[pcm_start:])
                    # Clear buffer after extracting PCM data
                    buffer = bytearray()
                    data_chunk_found = True
                # If still not found, keep accumulating in buffer (don't add to pcm_buffer)

            # Process PCM data if header is parsed and data chunk has been found
            elif header_parsed and data_chunk_found:
                pcm_buffer.extend(buffer)
                buffer = bytearray()

                # Encode complete frames
                while len(pcm_buffer) >= frame_bytes:
                    frame = bytes(pcm_buffer[:frame_bytes])
                    pcm_buffer = pcm_buffer[frame_bytes:]

                    # Encode frame
                    opus_packet = encoder.encode(frame, frame_size)
                    total_packets += 1

                    # Yield length-prefixed packet
                    packet_data = len(opus_packet).to_bytes(2, 'little') + opus_packet
                    yield packet_data

        # Handle remaining PCM data (pad last frame if necessary)
        if header_parsed and len(pcm_buffer) > 0:
            if len(pcm_buffer) < frame_bytes:
                # Pad with zeros
                pcm_buffer.extend(b'\x00' * (frame_bytes - len(pcm_buffer)))

            frame = bytes(pcm_buffer[:frame_bytes])
            opus_packet = encoder.encode(frame, frame_size)
            total_packets += 1

            packet_data = len(opus_packet).to_bytes(2, 'little') + opus_packet
            yield packet_data

        logger.debug(f"WAV to Opus streaming complete: {total_packets} packets encoded")

    except Exception as e:
        logger.error(f"Streaming Opus encoding failed: {e}")
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


@app.post("/api/v1/prepare")
async def prepare_context(
    session_id: Optional[str] = Form(None),
    device: DeviceResponse = Depends(verify_device_uuid)
):
    """
    PRE-WARMING endpoint: Fetch and cache conversation context before audio arrives.

    OPTIMIZATION: Called when recording starts (button press) to eliminate DB query
    latency from critical path. Context is cached in memory for 5 minutes.

    Call this when:
    - Button is pressed (recording starts)
    - Before sending audio to /api/v1/process

    Returns:
    - session_id to use for /api/v1/process
    - Caches context in memory for instant retrieval

    Saves 200-500ms from critical path by pre-fetching DB data.
    """
    try:
        # Parse session_id if provided
        parsed_session_id = None
        if session_id:
            try:
                parsed_session_id = UUID(session_id)
            except ValueError:
                logger.warning(f"Invalid session_id format: {session_id}")

        # Generate dummy embedding (we'll use time-based threading)
        dummy_embedding = [0.0] * 1536

        # Resolve thread (time-based only, no embedding needed)
        # BUGFIX: Run in thread pool to avoid blocking async event loop (Supabase performs blocking I/O)
        import asyncio
        thread_decision = await asyncio.to_thread(resolve_thread, device.id, parsed_session_id, "", dummy_embedding)
        resolved_session_id = thread_decision.thread_id

        # Fetch and cache context (async, with parallel DB queries)
        logger.info(f"PRE-WARM: Fetching context for device {device.device_uuid}, session {resolved_session_id}")
        conversation_history = await build_context(resolved_session_id)

        # Cache the context
        cache_key = str(device.id)
        context_cache[cache_key] = {
            'session_id': resolved_session_id,
            'context': conversation_history,
            'timestamp': _t.time()
        }

        logger.info(f"PRE-WARM: Cached context with {len(conversation_history)} messages for device {device.device_uuid}")

        return JSONResponse({
            "status": "ready",
            "session_id": str(resolved_session_id),
            "cached_messages": len(conversation_history),
            "cache_ttl_seconds": CONTEXT_CACHE_TTL_SECONDS
        })

    except Exception as e:
        logger.error(f"PRE-WARM: Failed to prepare context: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@app.post(
    "/api/v1/process",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Audio response file",
            "content": {"audio/opus": {}},
            "headers": {
                "X-Transcription": {"description": "Transcribed text", "schema": {"type": "string"}},
                "X-LLM-Response": {"description": "LLM response text", "schema": {"type": "string"}},
                "X-Session-ID": {"description": "Session ID (if provided)", "schema": {"type": "string"}},
                "X-Stage-Transcribe-ms": {"description": "Transcription stage duration (ms)", "schema": {"type": "string"}},
                "X-Stage-LLM-ms": {"description": "LLM stage duration (ms)", "schema": {"type": "string"}},
                "X-Stage-TTS-ms": {"description": "TTS stage duration (ms)", "schema": {"type": "string"}},
                "X-Stage-Total-ms": {"description": "Total processing time (ms)", "schema": {"type": "string"}},
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
    device: DeviceResponse = Depends(verify_device_uuid)
):
    """
    Process audio file through the complete pipeline:
    0. Decompress Opus (if Opus format) and amplify audio (if gain > 1.0)
    1. Transcribe audio using Whisper
    2. Query LLM with transcription
    3. Generate speech from LLM response
    4. Compress to Opus and return audio file with metadata headers
    
    Authentication:
        Requires device UUID in X-Device-UUID header
        Device must be registered in database with active status
    
    Args:
        audio: Uploaded audio file (Opus or WAV)
        session_id: Optional session ID for conversation history
        microphone_gain: Gain to apply to audio (default 1.0, Pi sends its configured gain)
        device: Device information from authentication middleware
        
    Returns:
        Opus audio file response with transcription and LLM response in headers
    """
    temp_input_file = None
    temp_decompressed_file = None
    temp_amplified_file = None
    temp_output_wav_file = None
    temp_output_opus_file = None
    
    # Initialize path variables to None to avoid NameError in exception handlers
    temp_input_path = None
    temp_decompressed_path = None
    temp_amplified_path = None
    temp_output_wav_path = None
    temp_output_opus_path = None
    
    try:
        import time as _t
        _total_start = _t.time()
        # Validate content type (accept custom Opus or WAV)
        is_opus = audio.content_type == "audio/opus"
        is_wav = audio.content_type in ["audio/wav", "audio/wave", "audio/x-wav"]
        
        if not is_opus and not is_wav:
            logger.warning(f"Invalid content type: {audio.content_type}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid content type: {audio.content_type}. "
                    "Expected audio/opus (custom container) or audio/wav. "
                    "Note: audio/ogg (Ogg Opus) is not supported by this endpoint."
                )
            )
        
        # Create temporary file for input audio
        suffix = ".opus" if is_opus else ".wav"
        temp_input_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        temp_input_path = Path(temp_input_file.name)
        
        # Save uploaded file
        content = await audio.read()
        file_size = len(content)
        
        logger.info(f"Received {suffix} audio file: {file_size} bytes from device {device.device_uuid} ({device.device_name})")
        
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
        
        # Step 1: Transcribe audio (async, optimized)
        # PERFORMANCE OPTIMIZATION: Start transcription and thread resolution in parallel
        logger.info("Step 1: Transcribing audio...")
        _t1 = _t.time()

        # Step 1.5: Resolve thread and build context using dynamic threading
        conversation_thread_id = None
        conversation_history_messages = None

        try:
            # Parse session_id BEFORE cache check for validation
            parsed_session_id = None
            if session_id:
                try:
                    parsed_session_id = UUID(session_id)
                except ValueError:
                    logger.warning(f"Invalid session_id format: {session_id}, creating new session")

            # OPTIMIZATION: Check cache first (pre-warmed by /prepare endpoint)
            cache_key = str(device.id)
            cached_data = context_cache.get(cache_key)
            cache_valid = False

            if cached_data and (_t.time() - cached_data['timestamp']) < CONTEXT_CACHE_TTL_SECONDS:
                cached_session_id = cached_data['session_id']

                # BUGFIX: Validate that cached session matches requested session (if specified)
                # Use cache only if: (1) no specific session requested, OR (2) requested session matches cache
                if parsed_session_id is None or parsed_session_id == cached_session_id:
                    # Cache hit! Use pre-warmed context (saves 200-500ms)
                    # Transcription still needs to complete for LLM, but context is ready
                    transcription = await transcribe_audio(audio_path_for_transcription)
                    conversation_thread_id = cached_session_id
                    conversation_history_messages = cached_data['context']
                    logger.debug(f"CACHE HIT: Using pre-warmed context with {len(conversation_history_messages)} messages (saved ~300ms)")

                    # PERFORMANCE OPTIMIZATION: Keep cache for multiple uses, refresh timestamp
                    # This allows subsequent requests within TTL window to benefit from cache
                    cached_data['timestamp'] = _t.time()
                    context_cache[cache_key] = cached_data
                    cache_valid = True
                else:
                    # Cache mismatch - client requested different session than cached
                    logger.info(f"CACHE MISMATCH: Cached session {cached_session_id} != requested {parsed_session_id}, ignoring cache")
                    del context_cache[cache_key]
                    cached_data = None
            elif cached_data:
                # Cache expired
                logger.info("CACHE EXPIRED: Fetching fresh context from DB")
                del context_cache[cache_key]
                cached_data = None

            if not cache_valid:
                # Cache miss, expired, or mismatch - perform full thread resolution
                if cached_data is None and parsed_session_id is None:
                    logger.info("CACHE MISS: No pre-warmed context available")

                # OPTIMIZATION: Skip embedding generation during critical path (saves 1100-1500ms)
                # Use time-based threading only for now, generate embedding in background
                # Zero vector fallback = time-based policy only (continues thread if < 90min)
                logger.info("Skipping embedding generation for speed (using time-based threading only)")
                user_embedding = [0.0] * 1536  # Zero vector = use time-based policy only

                # PERFORMANCE OPTIMIZATION: Run transcription and thread resolution in parallel
                # Thread resolution uses time-based policy only (doesn't need transcription text)
                import asyncio
                transcription_task = asyncio.create_task(transcribe_audio(audio_path_for_transcription))

                # Run thread resolution in thread pool to avoid blocking
                thread_resolution_task = asyncio.create_task(
                    asyncio.to_thread(resolve_thread, device.id, parsed_session_id, "", user_embedding)
                )

                try:
                    # Wait for both to complete
                    transcription, thread_decision = await asyncio.gather(transcription_task, thread_resolution_task)
                    conversation_thread_id = thread_decision.thread_id

                    logger.info(
                        f"Thread resolution: {thread_decision.decision} - "
                        f"thread_id={conversation_thread_id}, "
                        f"delta_t={thread_decision.delta_t_minutes:.1f}min, "
                        f"similarity={f'{thread_decision.similarity_score:.3f}' if thread_decision.similarity_score is not None else 'N/A'}, "
                        f"reason={thread_decision.reason}"
                    )

                    # Build context from thread (must happen after thread resolution, async with parallel DB queries)
                    conversation_history_messages = await build_context(conversation_thread_id)
                    logger.info(f"Loaded context with {len(conversation_history_messages)} messages")
                except ConversationServiceError:
                    # BUGFIX: Cancel incomplete tasks to prevent duplicate work (especially transcription API calls)
                    # If thread_resolution_task fails, transcription_task continues in background without this
                    for task in [transcription_task, thread_resolution_task]:
                        if not task.done():
                            task.cancel()
                            try:
                                await task
                            except asyncio.CancelledError:
                                pass
                    # Re-raise to be handled by outer exception handler
                    raise

        except ConversationServiceError as e:
            logger.warning(f"Failed to manage conversation thread: {e}, continuing without history")
            conversation_thread_id = None
            # Still need transcription for LLM
            if 'transcription' not in locals():
                transcription = await transcribe_audio(audio_path_for_transcription)

        _transcribe_ms = int((_t.time() - _t1) * 1000)

        # BUGFIX: Send HTTP headers immediately to prevent 502 timeout on long LLM responses
        # Previously, headers were delayed until after LLM completed (~3+ seconds), causing timeouts
        # Now we send headers right away and perform LLM query inside the streaming generator

        # Store conversation messages in background task (non-blocking)
        final_session_id = str(conversation_thread_id) if conversation_thread_id else None

        # Timing for response (headers sent immediately)
        _headers_sent_ms = int((_t.time() - _total_start) * 1000)

        # Chain generators: LLM → TTS streaming → WAV chunks → Opus packets (fully async)
        async def stream_audio_response():
            """Chain LLM + TTS streaming with Opus encoding (async pipeline)"""
            try:
                # Send empty chunk to force HTTP headers to transmit immediately
                # This prevents 502 timeouts by establishing connection before LLM processing
                yield b''

                # Step 2: Query LLM with conversation history (async, optimized)
                logger.info("Step 2: Querying LLM...")
                _t2 = _t.time()
                llm_response = await query_llm(transcription, conversation_history_messages)
                _llm_ms = int((_t.time() - _t2) * 1000)

                # Validate LLM response before attempting TTS (prevents empty text from reaching TTS)
                if not llm_response or not llm_response.strip():
                    logger.error("LLM returned empty response after processing")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Unable to generate response"
                    )

                logger.info(f"⚡ LLM complete: {_llm_ms}ms")

                _t3 = _t.time()  # Start timer for TTS (will stream, no final timing)

                # Step 3 & 4: Stream TTS → Opus encoding (REAL-TIME STREAMING)
                logger.info("Step 3 & 4: Streaming TTS generation and Opus encoding...")
                logger.info("⚡ STREAMING MODE: Client will receive audio as it's generated!")

                # PERFORMANCE DIAGNOSTIC: Track time to first audio chunk
                first_chunk_time = None
                chunk_count = 0

                # Generate speech chunks from Groq TTS API (async generator)
                tts_generator = generate_speech_streaming(llm_response)

                # Encode WAV chunks to Opus packets and stream
                async for opus_packet in stream_wav_to_opus(tts_generator, bitrate=settings.opus_bitrate):
                    if first_chunk_time is None:
                        first_chunk_time = _t.time()
                        ttfc_ms = int((first_chunk_time - _t3) * 1000)
                        logger.info(f"⚡ TTFC (Time to First Chunk): {ttfc_ms}ms")
                    chunk_count += 1
                    yield opus_packet

                logger.info(f"⚡ Streaming complete! Delivered {chunk_count} Opus packets")

                # Schedule async message storage (non-blocking, after streaming complete)
                if conversation_thread_id and transcription and llm_response:
                    import asyncio
                    asyncio.create_task(
                        store_conversation_messages(conversation_thread_id, transcription, llm_response)
                    )

            except Exception as e:
                logger.error(f"Streaming error: {e}")
                raise

        headers = {
            "X-Transcription": quote(transcription, safe=''),
            "X-Session-ID": quote(final_session_id or "", safe=''),
            "X-Stage-Transcribe-ms": str(_transcribe_ms),
            "X-Headers-Sent-ms": str(_headers_sent_ms),  # Time to send headers (immediately)
            "X-Streaming": "true",  # Indicate this is a streaming response
        }

        return StreamingResponse(
            stream_audio_response(),
            media_type="audio/opus",
            headers=headers,
            background=BackgroundTask(
                cleanup_temp_files,
                [
                    temp_input_path,
                    temp_decompressed_path if temp_decompressed_file else None,
                    temp_amplified_path if temp_amplified_file else None,
                    None,  # No temp WAV file (streaming)
                    None   # No temp Opus file (streaming)
                ]
            )
        )
        
    except GroqServiceError as e:
        # Check if it's a TTS error specifically
        from services.groq_service import TTSError
        if isinstance(e, TTSError):
            logger.error(f"TTS generation failed: {e}")
            # Clean up temp files (sync)
            cleanup_temp_files([
                temp_input_path if temp_input_file else None,
                temp_decompressed_path if temp_decompressed_file else None,
                temp_amplified_path if temp_amplified_file else None,
                temp_output_wav_path if temp_output_wav_file else None,
                temp_output_opus_path if temp_output_opus_file else None
            ])

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Text-to-speech generation failed: {str(e)}"
            )

        # Generic Groq service error
        logger.error(f"Groq service error: {e}")
        # Clean up temp files (sync)
        cleanup_temp_files([
            temp_input_path if temp_input_file else None,
            temp_decompressed_path if temp_decompressed_file else None,
            temp_amplified_path if temp_amplified_file else None,
            temp_output_wav_path if temp_output_wav_file else None,
            temp_output_opus_path if temp_output_opus_file else None
        ])

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Service error: {str(e)}"
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        # Clean up temp files (sync)
        cleanup_temp_files([
            temp_input_path if temp_input_file else None,
            temp_decompressed_path if temp_decompressed_file else None,
            temp_amplified_path if temp_amplified_file else None,
            temp_output_wav_path if temp_output_wav_file else None,
            temp_output_opus_path if temp_output_opus_file else None
        ])
        raise
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        # Clean up temp files (sync)
        cleanup_temp_files([
            temp_input_path if temp_input_file else None,
            temp_decompressed_path if temp_decompressed_file else None,
            temp_amplified_path if temp_amplified_file else None,
            temp_output_wav_path if temp_output_wav_file else None,
            temp_output_opus_path if temp_output_opus_file else None
        ])

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


def cleanup_temp_files(file_paths: list):
    """
    Clean up temporary files synchronously.

    Used in both success and error paths. Compatible with FastAPI BackgroundTask.

    Args:
        file_paths: List of Path objects to delete (None values are skipped)
    """
    for file_path in file_paths:
        try:
            if file_path and file_path.exists():
                file_path.unlink()
                logger.debug(f"Cleaned up temp file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up temp file {file_path}: {e}")


async def store_conversation_messages(
    conversation_thread_id: UUID,
    transcription: str,
    llm_response: str
):
    """
    Store conversation messages asynchronously in database.

    OPTIMIZATION: Runs in background without blocking the response.

    Args:
        conversation_thread_id: Conversation thread UUID
        transcription: User's transcribed text
        llm_response: AI's response text
    """
    try:
        # PERFORMANCE OPTIMIZATION: Store both messages in parallel
        # User and assistant messages can be stored concurrently
        import asyncio
        await asyncio.gather(
            add_message(conversation_thread_id, MessageRole.USER, transcription),
            add_message(conversation_thread_id, MessageRole.ASSISTANT, llm_response)
        )
        logger.debug(f"Stored conversation messages for thread {conversation_thread_id}")
    except ConversationServiceError as e:
        logger.warning(f"Failed to store conversation messages: {e}")
    except Exception as e:
        logger.error(f"Unexpected error storing messages: {e}", exc_info=True)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        reload=False
    )

