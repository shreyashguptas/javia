#!/usr/bin/env python3
"""
Raspberry Pi Voice Assistant Client
Records audio, sends to server for processing, plays response
"""

import os

# Suppress JACK server startup attempts (must be set before importing pyaudio)
os.environ['JACK_NO_START_SERVER'] = '1'
os.environ['JACK_NO_AUDIO_RESERVATION'] = '1'

import sys
import time
import wave
import requests
import subprocess
from pathlib import Path
from urllib.parse import unquote
import RPi.GPIO as GPIO
import pyaudio
import numpy as np
from dotenv import load_dotenv

# Suppress ALSA warnings
from ctypes import *
ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)

def py_error_handler(filename, line, function, err, fmt):
    """Suppress ALSA error messages"""
    pass

c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)

try:
    asound = cdll.LoadLibrary('libasound.so.2')
    asound.snd_lib_error_set_handler(c_error_handler)
except:
    pass

# Load environment variables
load_dotenv()

# ==================== CONFIGURATION ====================

# Server Configuration
SERVER_URL = os.getenv('SERVER_URL', 'http://localhost:8000')
CLIENT_API_KEY = os.getenv('CLIENT_API_KEY', 'YOUR_API_KEY_HERE')

# GPIO Configuration
BUTTON_PIN = int(os.getenv('BUTTON_PIN', '17'))
AMPLIFIER_SD_PIN = int(os.getenv('AMPLIFIER_SD_PIN', '27'))

# Audio Configuration
SAMPLE_RATE = int(os.getenv('SAMPLE_RATE', '48000'))
CHANNELS = 1
CHUNK_SIZE = 1024
AUDIO_FORMAT = pyaudio.paInt16
MICROPHONE_GAIN = float(os.getenv('MICROPHONE_GAIN', '2.0'))
FADE_DURATION_MS = int(os.getenv('FADE_DURATION_MS', '50'))
BEEP_VOLUME = float(os.getenv('BEEP_VOLUME', '0.4'))  # 0.0-1.0, matches TTS output

# File paths
AUDIO_DIR = Path(os.path.expanduser("~/javia/audio"))
RECORDING_FILE = AUDIO_DIR / "recording.wav"
RESPONSE_FILE = AUDIO_DIR / "response.wav"
START_BEEP_FILE = AUDIO_DIR / "start_beep.wav"
STOP_BEEP_FILE = AUDIO_DIR / "stop_beep.wav"

# Performance optimization: Cached audio device index
_CACHED_AUDIO_DEVICE_INDEX = None

# ==================== INITIALIZATION ====================

def setup():
    """Initialize the system"""
    print("\n" + "="*50)
    print("Raspberry Pi Voice Assistant Client Starting...")
    print("="*50 + "\n")
    
    # Create audio directory
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[INIT] Audio directory: {AUDIO_DIR}")
    
    # Clean up old recordings (but keep beep files)
    try:
        if RECORDING_FILE.exists():
            RECORDING_FILE.unlink()
        if RESPONSE_FILE.exists():
            RESPONSE_FILE.unlink()
        print(f"[INIT] Cleaned up old audio files")
    except Exception as e:
        print(f"[INIT] Could not clean old files: {e}")
    
    # Setup GPIO
    GPIO.setwarnings(False)  # Suppress warnings about channels already in use
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    print(f"[INIT] Button configured on GPIO{BUTTON_PIN}")
    
    # Setup amplifier shutdown pin
    GPIO.setup(AMPLIFIER_SD_PIN, GPIO.OUT)
    GPIO.output(AMPLIFIER_SD_PIN, GPIO.LOW)  # Start with amp muted
    print(f"[INIT] Amplifier SD pin configured on GPIO{AMPLIFIER_SD_PIN}")
    
    # Check API key
    if CLIENT_API_KEY in ["YOUR_API_KEY_HERE", "YOUR_SECURE_API_KEY_HERE", ""]:
        print("\n[ERROR] CLIENT API KEY NOT SET!")
        print("[ERROR] Please set your API key in the .env file.")
        print("[ERROR] Run the setup script: bash ~/javia_client/deploy/setup.sh")
        sys.exit(1)
    
    # Check server URL
    if SERVER_URL == "http://localhost:8000":
        print("\n[WARNING] Using default server URL (localhost:8000)")
        print("[WARNING] Please set SERVER_URL in .env for production use")
    
    print(f"[INIT] Server URL: {SERVER_URL}")
    
    # Test audio devices
    print("\n[INIT] Checking audio devices...")
    try:
        result = subprocess.run(['arecord', '-l'], 
                              capture_output=True, text=True, check=True)
        print("[INIT] Recording devices found:")
        print(result.stdout)
    except Exception as e:
        print(f"[WARNING] Could not list recording devices: {e}")
    
    try:
        result = subprocess.run(['aplay', '-l'], 
                              capture_output=True, text=True, check=True)
        print("[INIT] Playback devices found:")
        print(result.stdout)
    except Exception as e:
        print(f"[WARNING] Could not list playback devices: {e}")
    
    # Generate beep sounds (always regenerate to ensure they're correct)
    print("\n[INIT] Setting up audio feedback beeps...")
    generate_beep_sounds()
    
    # Verify beep files exist
    if START_BEEP_FILE.exists() and STOP_BEEP_FILE.exists():
        print(f"[INIT] ✓ Beep files ready:")
        print(f"[INIT]   - Start: {START_BEEP_FILE}")
        print(f"[INIT]   - Stop:  {STOP_BEEP_FILE}")
    else:
        print(f"[WARNING] Beep files missing! Audio feedback disabled.")
    
    print("\n[READY] System ready! Press button to start...\n")

# ==================== BEEP SOUNDS ====================

def generate_beep_sounds():
    """Generate pleasant beep sounds for start and stop feedback"""
    try:
        sample_rate = 44100  # Standard sample rate for beeps
        
        # Volume level to match voice response output (normalized)
        # Configurable via BEEP_VOLUME in .env (0.0-1.0)
        beep_volume = BEEP_VOLUME
        
        # Start beep: Short rising tone (600Hz -> 900Hz)
        print("[INIT] Generating start beep sound...")
        duration = 0.1  # 100ms - short and snappy
        num_samples = int(sample_rate * duration)
        t = np.linspace(0, duration, num_samples)
        
        # Frequency sweep from 600Hz to 900Hz
        start_freq = 600
        end_freq = 900
        frequency = np.linspace(start_freq, end_freq, num_samples)
        phase = 2 * np.pi * np.cumsum(frequency) / sample_rate
        
        # Generate tone
        tone = np.sin(phase)
        
        # Generate envelope with exact length matching - quick attack/release
        attack_len = num_samples // 5
        sustain_len = num_samples // 2
        release_len = num_samples - attack_len - sustain_len  # Ensure exact match
        
        envelope = np.concatenate([
            np.linspace(0, 1, attack_len),   # Quick attack
            np.ones(sustain_len),            # Brief sustain
            np.linspace(1, 0, release_len)   # Quick release
        ])
        
        # Apply envelope and volume
        start_beep = (tone * envelope * beep_volume * 32767).astype(np.int16)
        
        # Save start beep
        with wave.open(str(START_BEEP_FILE), 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(start_beep.tobytes())
        
        print(f"[INIT] ✓ Start beep saved: {START_BEEP_FILE} ({len(start_beep) * 2} bytes)")
        
        # Stop beep: Reverse of start (falling tone 900Hz -> 600Hz)
        print("[INIT] Generating stop beep sound...")
        # Use same duration for consistency
        duration = 0.1  # 100ms
        num_samples = int(sample_rate * duration)
        t = np.linspace(0, duration, num_samples)
        
        # Frequency sweep from 900Hz to 600Hz (reverse of start)
        start_freq = 900
        end_freq = 600
        frequency = np.linspace(start_freq, end_freq, num_samples)
        phase = 2 * np.pi * np.cumsum(frequency) / sample_rate
        
        # Generate tone
        tone = np.sin(phase)
        
        # Generate envelope with exact length matching - same as start beep
        attack_len = num_samples // 5
        sustain_len = num_samples // 2
        release_len = num_samples - attack_len - sustain_len  # Ensure exact match
        
        envelope = np.concatenate([
            np.linspace(0, 1, attack_len),   # Quick attack
            np.ones(sustain_len),            # Brief sustain
            np.linspace(1, 0, release_len)   # Quick release
        ])
        
        # Apply envelope and volume
        stop_beep = (tone * envelope * beep_volume * 32767).astype(np.int16)
        
        # Save stop beep
        with wave.open(str(STOP_BEEP_FILE), 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(stop_beep.tobytes())
        
        print(f"[INIT] ✓ Stop beep saved: {STOP_BEEP_FILE} ({len(stop_beep) * 2} bytes)")
        print(f"[INIT] ✓ Beep sounds generated successfully (volume: {int(beep_volume*100)}%)")
        
    except Exception as e:
        print(f"[WARNING] Could not generate beep sounds: {e}")
        import traceback
        print(f"[WARNING] Traceback: {traceback.format_exc()}")

def play_beep(beep_file, description=""):
    """Play a short beep sound through the amplifier"""
    if not beep_file.exists():
        print(f"[BEEP] ⚠ Warning: Beep file not found: {beep_file}")
        print(f"[BEEP] Expected at: {beep_file}")
        return
    
    process = None
    try:
        print(f"[BEEP] 🔊 Playing {description} beep...")
        
        # Enable amplifier
        GPIO.output(AMPLIFIER_SD_PIN, GPIO.HIGH)
        time.sleep(0.05)  # Stabilization time - critical for audibility
        
        # Play beep with blocking call for reliability
        result = subprocess.run(
            ['aplay', '-q', '-D', 'plughw:0,0', str(beep_file)],
            capture_output=True,
            timeout=1.0
        )
        
        if result.returncode != 0:
            print(f"[BEEP] ⚠ aplay returned error: {result.returncode}")
            if result.stderr:
                print(f"[BEEP] Error: {result.stderr.decode()}")
        else:
            print(f"[BEEP] ✓ {description} beep completed")
        
        # Small delay to ensure audio completes
        time.sleep(0.05)
        
        # Disable amplifier
        GPIO.output(AMPLIFIER_SD_PIN, GPIO.LOW)
        
    except subprocess.TimeoutExpired:
        print(f"[BEEP] ⚠ Timeout playing beep")
        GPIO.output(AMPLIFIER_SD_PIN, GPIO.LOW)
    except Exception as e:
        print(f"[BEEP] ⚠ Error: {e}")
        import traceback
        print(f"[BEEP] Traceback: {traceback.format_exc()}")
        GPIO.output(AMPLIFIER_SD_PIN, GPIO.LOW)

# ==================== BUTTON HANDLING ====================

def wait_for_button_press():
    """Wait for button press"""
    print("[BUTTON] Waiting for button press to start recording...")
    
    while GPIO.input(BUTTON_PIN) == GPIO.HIGH:
        time.sleep(0.01)
    
    print("[BUTTON] *** BUTTON PRESSED! Starting recording... ***")
    
    # Play start beep IMMEDIATELY (before debounce for instant feedback)
    play_beep(START_BEEP_FILE, "start")
    
    time.sleep(0.05)  # Debounce

def wait_for_button_release():
    """Wait for button press again to stop recording"""
    print("[BUTTON] Press button again to stop recording...")
    
    # Wait for button to be released first
    while GPIO.input(BUTTON_PIN) == GPIO.LOW:
        time.sleep(0.01)
    
    # Now wait for button press again
    while GPIO.input(BUTTON_PIN) == GPIO.HIGH:
        time.sleep(0.01)
    
    print("[BUTTON] *** BUTTON PRESSED! Stopping recording... ***")
    
    # Play stop beep to indicate mic stopped listening
    play_beep(STOP_BEEP_FILE, "stop")
    
    time.sleep(0.05)  # Debounce
    
    # Wait for release
    while GPIO.input(BUTTON_PIN) == GPIO.LOW:
        time.sleep(0.01)
    
    print("[BUTTON] Released. Processing audio...\n")

# ==================== AUDIO RECORDING ====================

def amplify_audio_batch(frames, gain=2.0):
    """
    Amplify audio data with optimized batch processing.
    
    PERFORMANCE OPTIMIZATIONS:
    - Batch processing: Process all frames at once instead of individually
    - Pre-allocated buffer: Single numpy array allocation for entire recording
    - In-place operations: Minimize memory allocations
    - Efficient clipping: Single clip operation on entire buffer
    
    Args:
        frames: List of audio chunks (bytes)
        gain: Amplification factor (default 2.0)
    
    Returns:
        bytes: Amplified audio data ready for WAV file
    """
    if gain == 1.0:
        # No amplification needed - just concatenate
        return b''.join(frames)
    
    try:
        # Calculate total size for pre-allocation
        total_bytes = sum(len(frame) for frame in frames)
        total_samples = total_bytes // 2  # 2 bytes per int16 sample
        
        # Pre-allocate single buffer for entire recording (major optimization)
        audio_buffer = np.empty(total_samples, dtype=np.int16)
        
        # Copy all chunks into pre-allocated buffer
        offset = 0
        for frame in frames:
            frame_array = np.frombuffer(frame, dtype=np.int16)
            frame_len = len(frame_array)
            audio_buffer[offset:offset + frame_len] = frame_array
            offset += frame_len
        
        # Batch amplification with in-place operations
        # Use float32 for intermediate calculation to avoid overflow
        audio_float = audio_buffer.astype(np.float32)
        audio_float *= gain
        
        # Clip to valid int16 range
        np.clip(audio_float, -32768, 32767, out=audio_float)
        
        # Convert back to int16 in-place
        audio_buffer = audio_float.astype(np.int16)
        
        return audio_buffer.tobytes()
        
    except Exception as e:
        print(f"[WARNING] Batch amplification failed: {e}, falling back to concatenation")
        return b''.join(frames)

def get_audio_device_index(audio):
    """
    Find and cache the I2S audio input device index.
    
    PERFORMANCE OPTIMIZATION:
    - Caches device index globally to avoid repeated enumeration
    - Only scans devices once per program execution
    
    Args:
        audio: PyAudio instance
    
    Returns:
        int: Device index or None if not found
    """
    global _CACHED_AUDIO_DEVICE_INDEX
    
    # Return cached value if available
    if _CACHED_AUDIO_DEVICE_INDEX is not None:
        return _CACHED_AUDIO_DEVICE_INDEX
    
    # Find I2S input device (first time only)
    device_index = None
    device_count = audio.get_device_count()
    
    # First pass: Look for Voice HAT devices
    for i in range(device_count):
        try:
            info = audio.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0 and ('googlevoicehat' in info['name'].lower() or 
                                                  'voicehat' in info['name'].lower() or
                                                  'sndrpigooglevoi' in info['name'].lower()):
                device_index = i
                break
        except Exception:
            continue
    
    # Second pass: If Voice HAT not found, use any valid input device
    if device_index is None:
        for i in range(device_count):
            try:
                info = audio.get_device_info_by_index(i)
                if info['maxInputChannels'] > 0:
                    device_index = i
                    break
            except Exception:
                continue
    
    # Cache the result
    _CACHED_AUDIO_DEVICE_INDEX = device_index
    return device_index

def record_audio():
    """
    Record audio from I2S microphone until button is pressed again.
    
    PERFORMANCE OPTIMIZATIONS:
    - Uses cached device index (avoids repeated enumeration)
    - Batch audio amplification (processes entire recording at once)
    - Pre-allocated buffers in amplification function
    """
    print("[AUDIO] Setting up recording...")
    
    audio = None
    stream = None
    
    try:
        audio = pyaudio.PyAudio()
        
        # Use cached device lookup (major performance improvement)
        device_index = get_audio_device_index(audio)
        
        # Final validation
        if device_index is None:
            print("[ERROR] No input devices found!")
            print("[ERROR] Please check your audio hardware configuration")
            return False
        
        # Validate selected device
        try:
            device_info = audio.get_device_info_by_index(device_index)
            if device_info['maxInputChannels'] < 1:
                print("[ERROR] Selected device has no input channels")
                return False
        except Exception as e:
            print(f"[ERROR] Could not validate device: {e}")
            return False
        
        # Open stream
        stream = audio.open(
            format=AUDIO_FORMAT,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=CHUNK_SIZE
        )
        
        print("[AUDIO] Recording... SPEAK NOW!")
        print("[AUDIO] " + "="*40)
        
        frames = []
        chunks_recorded = 0
        
        # Wait for button to be released first
        while GPIO.input(BUTTON_PIN) == GPIO.LOW:
            time.sleep(0.01)
        
        # Record until button is pressed again
        while GPIO.input(BUTTON_PIN) == GPIO.HIGH:
            try:
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                frames.append(data)
                chunks_recorded += 1
                
                # Progress indicator every second
                if chunks_recorded % (SAMPLE_RATE // CHUNK_SIZE) == 0:
                    seconds = chunks_recorded // (SAMPLE_RATE // CHUNK_SIZE)
                    print(f"[AUDIO] {seconds} seconds recorded...")
            except Exception as e:
                print(f"[WARNING] Audio buffer issue: {e}")
                continue
        
        print("[AUDIO] " + "="*40)
        print("[BUTTON] *** BUTTON PRESSED! Stopping recording... ***")
        
        # Validate recording length
        if len(frames) == 0:
            print("[ERROR] No audio data recorded")
            return False
        
        # Calculate total recording time
        total_seconds = chunks_recorded / (SAMPLE_RATE / CHUNK_SIZE)
        print(f"[AUDIO] Recording complete ({total_seconds:.1f} seconds)")
        
        # Get sample width BEFORE terminating audio object
        sample_width = audio.get_sample_size(AUDIO_FORMAT)
        
        # Now close audio resources before playing beep to avoid conflicts
        if stream is not None:
            stream.stop_stream()
            stream.close()
            stream = None
        if audio is not None:
            audio.terminate()
            audio = None
        
        # Play stop beep to indicate recording stopped
        play_beep(STOP_BEEP_FILE, "stop")
        
        # Wait for button release
        while GPIO.input(BUTTON_PIN) == GPIO.LOW:
            time.sleep(0.01)
        
        # Batch amplification (major performance improvement over per-chunk processing)
        print(f"[AUDIO] Processing audio with gain {MICROPHONE_GAIN}x...")
        audio_data = amplify_audio_batch(frames, MICROPHONE_GAIN)
        
        # Save to WAV file
        with wave.open(str(RECORDING_FILE), 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(sample_width)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_data)
        
        # Validate saved file
        if not RECORDING_FILE.exists():
            print("[ERROR] Recording file was not saved")
            return False
        
        file_size = RECORDING_FILE.stat().st_size
        if file_size < 1000:
            print(f"[WARNING] Recording file is very small ({file_size} bytes)")
        
        print(f"[AUDIO] Saved: {RECORDING_FILE} ({file_size} bytes)")
        return True
        
    except Exception as e:
        print(f"[ERROR] Recording failed: {e}")
        import traceback
        print(f"[DEBUG] {traceback.format_exc()}")
        return False
        
    finally:
        # Clean up resources
        try:
            if stream is not None:
                stream.stop_stream()
                stream.close()
        except:
            pass
        
        try:
            if audio is not None:
                audio.terminate()
        except:
            pass

# ==================== SERVER COMMUNICATION ====================

def send_to_server():
    """Send audio to server and receive response"""
    print("[SERVER] Sending audio to server for processing...")
    
    if not RECORDING_FILE.exists():
        print("[ERROR] Recording file not found")
        return False
    
    file_size = RECORDING_FILE.stat().st_size
    if file_size < 100:
        print(f"[ERROR] Recording file too small ({file_size} bytes)")
        return False
    
    try:
        # Prepare request
        headers = {
            'X-API-Key': CLIENT_API_KEY
        }
        
        with open(RECORDING_FILE, 'rb') as audio_file:
            files = {
                'audio': ('recording.wav', audio_file, 'audio/wav')
            }
            data = {
                'session_id': None  # TODO: Implement session management
            }
            
            print(f"[SERVER] Uploading {file_size} bytes...")
            
            # Send request with timeout
            response = requests.post(
                f"{SERVER_URL}/api/v1/process",
                headers=headers,
                files=files,
                data=data,
                timeout=120,  # 2 minutes timeout for full processing
                stream=True
            )
            
            print(f"[SERVER] Response code: {response.status_code}")
            
            if response.status_code == 200:
                # Get metadata from headers (URL-decode to handle Unicode characters)
                transcription = unquote(response.headers.get('X-Transcription', ''))
                llm_response = unquote(response.headers.get('X-LLM-Response', ''))
                
                print(f"[SUCCESS] Transcription: \"{transcription}\"")
                print(f"[SUCCESS] LLM Response: \"{llm_response}\"")
                
                # Save response audio
                total_bytes = 0
                with open(RESPONSE_FILE, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            total_bytes += len(chunk)
                
                if total_bytes == 0:
                    print("[ERROR] Received empty audio file")
                    return False
                
                print(f"[SUCCESS] Audio saved: {RESPONSE_FILE} ({total_bytes} bytes)")
                return True
                
            elif response.status_code == 401:
                print("[ERROR] Unauthorized - Invalid API key")
                return False
            elif response.status_code == 403:
                print("[ERROR] Forbidden - Access denied")
                return False
            else:
                print(f"[ERROR] Server error {response.status_code}: {response.text}")
                return False
                
    except requests.exceptions.Timeout:
        print("[ERROR] Request timeout - server took too long to respond")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"[ERROR] Connection error: {e}")
        print("[ERROR] Check if server is running and accessible")
        return False
    except Exception as e:
        print(f"[ERROR] Failed to communicate with server: {e}")
        import traceback
        print(f"[DEBUG] {traceback.format_exc()}")
        return False

# ==================== AUDIO PLAYBACK ====================

def apply_fade_in_out(wav_file, fade_duration_ms=50):
    """Apply fade-in and fade-out effects to eliminate clicks"""
    temp_file = None
    try:
        # Read the WAV file parameters first
        with wave.open(str(wav_file), 'rb') as wf:
            params = wf.getparams()
            channels = params.nchannels
            sampwidth = params.sampwidth
            framerate = params.framerate
            n_frames = params.nframes
        
        # Validate we have audio data
        if n_frames == 0:
            print(f"[WARNING] Audio file is empty, skipping fade")
            return
        
        # Determine dtype based on sample width
        if sampwidth == 1:
            dtype = np.uint8
            is_unsigned = True
        elif sampwidth == 2:
            dtype = np.int16
            is_unsigned = False
        elif sampwidth == 4:
            dtype = np.int32
            is_unsigned = False
        else:
            print(f"[WARNING] Unsupported sample width for fade: {sampwidth} bytes")
            return
        
        # Calculate fade length in frames
        fade_frames = int((fade_duration_ms / 1000.0) * framerate)
        fade_frames = min(fade_frames, n_frames // 4)
        
        if fade_frames < 10:
            print(f"[WARNING] Audio too short for fade effect ({n_frames} frames)")
            return
        
        fade_samples = fade_frames * channels
        
        print(f"[DEBUG] Applying {fade_duration_ms}ms fade ({fade_frames} frames, {fade_samples} samples)")
        
        # Create fade curves
        fade_in_curve = np.linspace(0, 1, fade_samples)
        fade_in_curve = 0.5 * (1 - np.cos(np.pi * fade_in_curve))
        
        fade_out_curve = np.linspace(1, 0, fade_samples)
        fade_out_curve = 0.5 * (1 - np.cos(np.pi * fade_out_curve))
        
        # Create temporary file
        temp_file = wav_file.parent / f"{wav_file.stem}_fade_temp.wav"
        
        # Process file
        with wave.open(str(wav_file), 'rb') as wf_in:
            with wave.open(str(temp_file), 'wb') as wf_out:
                wf_out.setnchannels(channels)
                wf_out.setsampwidth(sampwidth)
                wf_out.setframerate(framerate)
                
                # Process beginning
                beginning_data = wf_in.readframes(fade_frames)
                if len(beginning_data) == 0:
                    print(f"[WARNING] No beginning data to fade")
                    return
                    
                beginning_array = np.frombuffer(beginning_data, dtype=dtype).copy()
                
                # Ensure arrays match in size
                if len(beginning_array) != len(fade_in_curve):
                    print(f"[WARNING] Size mismatch: audio={len(beginning_array)}, fade={len(fade_in_curve)}")
                    # Truncate or pad fade curve to match
                    if len(beginning_array) < len(fade_in_curve):
                        fade_in_curve = fade_in_curve[:len(beginning_array)]
                    else:
                        beginning_array = beginning_array[:len(fade_in_curve)]
                
                if is_unsigned:
                    beginning_array = beginning_array.astype(np.int16) - 128
                
                beginning_array = (beginning_array * fade_in_curve).astype(beginning_array.dtype)
                
                if is_unsigned:
                    beginning_array = (beginning_array + 128).clip(0, 255).astype(np.uint8)
                
                wf_out.writeframes(beginning_array.tobytes())
                
                # Copy middle portion
                middle_frames = n_frames - (2 * fade_frames)
                if middle_frames > 0:
                    chunk_size = 4096
                    frames_written = 0
                    while frames_written < middle_frames:
                        frames_to_read = min(chunk_size, middle_frames - frames_written)
                        chunk = wf_in.readframes(frames_to_read)
                        if not chunk:
                            break
                        wf_out.writeframes(chunk)
                        frames_written += frames_to_read
                
                # Process ending
                ending_data = wf_in.readframes(fade_frames)
                if len(ending_data) == 0:
                    print(f"[WARNING] No ending data to fade")
                    return
                    
                ending_array = np.frombuffer(ending_data, dtype=dtype).copy()
                
                # Ensure arrays match in size
                if len(ending_array) != len(fade_out_curve):
                    print(f"[WARNING] Size mismatch: audio={len(ending_array)}, fade={len(fade_out_curve)}")
                    # Truncate or pad fade curve to match
                    if len(ending_array) < len(fade_out_curve):
                        fade_out_curve = fade_out_curve[:len(ending_array)]
                    else:
                        ending_array = ending_array[:len(fade_out_curve)]
                
                if is_unsigned:
                    ending_array = ending_array.astype(np.int16) - 128
                
                ending_array = (ending_array * fade_out_curve).astype(ending_array.dtype)
                
                if is_unsigned:
                    ending_array = (ending_array + 128).clip(0, 255).astype(np.uint8)
                
                wf_out.writeframes(ending_array.tobytes())
        
        # Replace original file
        temp_file.replace(wav_file)
        print(f"[AUDIO] Applied fade-in/fade-out effects")
        
    except Exception as e:
        print(f"[WARNING] Could not apply fade effects: {e}")
        if temp_file is not None and temp_file.exists():
            try:
                temp_file.unlink()
            except:
                pass

def add_silence_padding(wav_file, padding_ms=150):
    """Add silence padding to beginning and end of WAV file"""
    temp_file = None
    try:
        temp_file = wav_file.parent / f"{wav_file.stem}_temp.wav"
        
        with wave.open(str(wav_file), 'rb') as wf_in:
            params = wf_in.getparams()
            channels = params.nchannels
            sampwidth = params.sampwidth
            framerate = params.framerate
            
            # Determine dtype
            if sampwidth == 1:
                dtype = np.uint8
                default_value = 128
            elif sampwidth == 2:
                dtype = np.int16
                default_value = 0
            elif sampwidth == 4:
                dtype = np.int32
                default_value = 0
            else:
                print(f"[WARNING] Unsupported sample width: {sampwidth} bytes")
                return
            
            # Calculate padding length
            padding_frames = int((padding_ms / 1000.0) * framerate)
            silence_samples = padding_frames * channels
            silence = np.full(silence_samples, default_value, dtype=dtype)
            silence_bytes = silence.tobytes()
            
            # Write to temporary file with padding
            with wave.open(str(temp_file), 'wb') as wf_out:
                wf_out.setnchannels(channels)
                wf_out.setsampwidth(sampwidth)
                wf_out.setframerate(framerate)
                
                # Write leading silence
                wf_out.writeframes(silence_bytes)
                
                # Copy original audio
                chunk_size = 4096
                while True:
                    frames = wf_in.readframes(chunk_size)
                    if not frames:
                        break
                    wf_out.writeframes(frames)
                
                # Write trailing silence
                wf_out.writeframes(silence_bytes)
        
        # Replace original file
        temp_file.replace(wav_file)
        print(f"[AUDIO] Added {padding_ms}ms silence padding")
        
    except Exception as e:
        print(f"[WARNING] Could not add silence padding: {e}")
        if temp_file is not None and temp_file.exists():
            try:
                temp_file.unlink()
            except:
                pass

def play_audio():
    """Play audio through I2S amplifier with SD pin control"""
    if not RESPONSE_FILE.exists():
        print("[ERROR] Response file not found")
        return False
    
    process = None
    try:
        print("[PLAYBACK] Preparing audio...")
        
        # Apply fade and padding to eliminate clicks
        apply_fade_in_out(RESPONSE_FILE, fade_duration_ms=FADE_DURATION_MS)
        add_silence_padding(RESPONSE_FILE, padding_ms=150)
        
        # Enable amplifier
        GPIO.output(AMPLIFIER_SD_PIN, GPIO.HIGH)
        time.sleep(0.200)  # Stabilization time
        
        # Play audio
        print("[PLAYBACK] Playing response... (Press button to interrupt)")
        process = subprocess.Popen(
            ['aplay', '-D', 'plughw:0,0', str(RESPONSE_FILE)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Monitor button during playback
        interrupted = False
        while process.poll() is None:
            if GPIO.input(BUTTON_PIN) == GPIO.LOW:
                print("\n[INTERRUPT] *** BUTTON PRESSED! Stopping playback... ***")
                process.terminate()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                interrupted = True
                break
            time.sleep(0.01)
        
        # Wait for audio to fully complete
        time.sleep(0.200)
        
        # Disable amplifier
        GPIO.output(AMPLIFIER_SD_PIN, GPIO.LOW)
        
        if interrupted:
            print("[INTERRUPT] Playback cancelled!")
            while GPIO.input(BUTTON_PIN) == GPIO.LOW:
                time.sleep(0.01)
            return False
        else:
            print("[PLAYBACK] Complete!")
            return True
            
    except Exception as e:
        print(f"[ERROR] Playback error: {e}")
        GPIO.output(AMPLIFIER_SD_PIN, GPIO.LOW)
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1)
            except:
                process.kill()
        return False

# ==================== MAIN LOOP ====================

def main():
    """Main program loop"""
    try:
        setup()
        
        while True:
            # Wait for button press
            wait_for_button_press()
            
            print("\n" + "="*50)
            print("STARTING CONVERSATION")
            print("="*50 + "\n")
            
            # Step 1: Record
            print("[STEP 1/3] Recording audio...")
            if not record_audio():
                print("[ERROR] Recording failed. Restarting...")
                time.sleep(2)
                continue
            
            # Step 2: Send to server
            print("\n[STEP 2/3] Processing on server...")
            if not send_to_server():
                print("[ERROR] Server processing failed. Restarting...")
                time.sleep(2)
                continue
            
            # Step 3: Play
            print("\n[STEP 3/3] Playing response...")
            playback_completed = play_audio()
            
            if playback_completed:
                print("\n[COMPLETE] Conversation complete!")
                print("="*50 + "\n")
                time.sleep(1)
            else:
                print("\n[INTERRUPT] Waiting for next button press...")
                print("="*50 + "\n")
                time.sleep(0.5)
            
    except KeyboardInterrupt:
        print("\n\n[EXIT] Shutting down...")
    finally:
        GPIO.cleanup()
        print("[EXIT] GPIO cleanup complete")

if __name__ == "__main__":
    main()

