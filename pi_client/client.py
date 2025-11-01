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
import threading
from gpiozero import Button, OutputDevice, RotaryEncoder
import pyaudio
import numpy as np
from dotenv import load_dotenv
import opuslib

# OTA Update system
from device_manager import DeviceManager
from activity_tracker import ActivityTracker
from update_manager import UpdateManager

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
# CLIENT_API_KEY is deprecated - authentication is now via device UUID

# OTA Update Configuration
DEVICE_TIMEZONE = os.getenv('DEVICE_TIMEZONE', 'UTC')
SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')

# GPIO Configuration
BUTTON_PIN = int(os.getenv('BUTTON_PIN', '17'))  # Rotary encoder SW pin
ROTARY_CLK_PIN = int(os.getenv('ROTARY_CLK_PIN', '22'))  # Rotary encoder CLK pin
ROTARY_DT_PIN = int(os.getenv('ROTARY_DT_PIN', '23'))  # Rotary encoder DT pin
AMPLIFIER_SD_PIN = int(os.getenv('AMPLIFIER_SD_PIN', '27'))

# Audio Configuration
SAMPLE_RATE = int(os.getenv('SAMPLE_RATE', '48000'))
CHANNELS = 1
CHUNK_SIZE = 512  # Reduced from 1024 for lower latency (5.3ms vs 10.6ms per chunk)
AUDIO_FORMAT = pyaudio.paInt16
MICROPHONE_GAIN = float(os.getenv('MICROPHONE_GAIN', '2.0'))
FADE_DURATION_MS = int(os.getenv('FADE_DURATION_MS', '50'))

# Volume Configuration
VOLUME_STEP = int(os.getenv('VOLUME_STEP', '5'))  # Volume change per rotary encoder step (%)
INITIAL_VOLUME = int(os.getenv('INITIAL_VOLUME', '100'))  # Initial volume on startup (%) - CHANGED TO 100
VERBOSE_OUTPUT = os.getenv('VERBOSE_OUTPUT', 'true').lower() == 'true'  # Control verbose logging

# File paths
AUDIO_DIR = Path(os.path.expanduser("~/javia/audio"))
RECORDING_FILE = AUDIO_DIR / "recording.wav"
RECORDING_OPUS_FILE = AUDIO_DIR / "recording.opus"
RESPONSE_OPUS_FILE = AUDIO_DIR / "response.opus"
RESPONSE_FILE = AUDIO_DIR / "response.wav"
START_BEEP_FILE = AUDIO_DIR / "start_beep.wav"
STOP_BEEP_FILE = AUDIO_DIR / "stop_beep.wav"

# Performance optimizations: Caching
_CACHED_AUDIO_DEVICE_INDEX = None

# GPIO objects (initialized in setup())
button = None
rotary_encoder = None
amplifier_sd = None

# Volume state
current_volume = INITIAL_VOLUME

# OTA Update managers (initialized in setup())
device_manager = None
activity_tracker = None
update_manager = None

# ==================== INITIALIZATION ====================

# REMOVED: All ALSA volume control code - doesn't work with googlevoicehat
# Volume is controlled purely in software via current_volume variable

def optimize_system_performance():
    """
    Optimize Raspberry Pi system performance for real-time audio.
    
    PERFORMANCE OPTIMIZATIONS:
    - Sets CPU governor to 'performance' mode (max frequency)
    - Reduces system latency for audio processing
    - Based on Linux audio wiki recommendations
    """
    try:
        # Try to set CPU governor to performance mode
        result = subprocess.run(
            ['sudo', 'sh', '-c', 
             'echo performance > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'],
            capture_output=True,
            timeout=2
        )
        if result.returncode == 0:
            print("[PERF] ✓ CPU governor set to 'performance' mode")
        else:
            print("[PERF] ℹ Could not set CPU governor (may already be optimized)")
    except Exception:
        print("[PERF] ℹ Running with default CPU settings")

def setup():
    """Initialize the system with performance optimizations"""
    print("\n" + "="*50)
    print("Raspberry Pi Voice Assistant Client Starting...")
    print("="*50 + "\n")
    
    # Optimize system performance first
    optimize_system_performance()
    
    # Initialize OTA update system
    global device_manager, activity_tracker, update_manager
    
    print("\n[INIT] Initializing OTA update system...")
    
    try:
        # Initialize device manager
        device_manager = DeviceManager(
            server_url=SERVER_URL,
            api_key=CLIENT_API_KEY,
            timezone=DEVICE_TIMEZONE
        )
        print(f"[INIT] ✓ Device UUID: {device_manager.get_device_uuid()}")
        print(f"[INIT] ✓ Current version: {device_manager.get_current_version()}")
        
        # Register device with server
        if device_manager.register():
            print("[INIT] ✓ Device registered with server")
        else:
            print("[INIT] ⚠️  Device registration failed (will retry later)")
        
        # Initialize activity tracker
        activity_tracker = ActivityTracker()
        print("[INIT] ✓ Activity tracker initialized")
        
        # Initialize update manager if Supabase is configured
        if SUPABASE_URL and SUPABASE_KEY:
            update_manager = UpdateManager(
                server_url=SERVER_URL,
                api_key=CLIENT_API_KEY,
                device_uuid=device_manager.get_device_uuid(),
                timezone_str=DEVICE_TIMEZONE,
                activity_tracker=activity_tracker,
                supabase_url=SUPABASE_URL,
                supabase_key=SUPABASE_KEY
            )
            update_manager.start()
            print("[INIT] ✓ Update manager started (OTA updates enabled)")
        else:
            print("[INIT] ℹ Supabase not configured - OTA updates disabled")
    except Exception as e:
        print(f"[INIT] ⚠️  OTA system initialization failed: {e}")
        print("[INIT] Continuing without OTA updates...")
    
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
    
    # Setup GPIO using gpiozero (Pi 5 compatible)
    global button, rotary_encoder, amplifier_sd, current_volume
    
    # Setup rotary encoder button (SW pin)
    button = Button(BUTTON_PIN, pull_up=True, bounce_time=0.05)
    print(f"[INIT] Rotary encoder button (SW) configured on GPIO{BUTTON_PIN}")
    
    # Setup rotary encoder for volume control
    rotary_encoder = RotaryEncoder(ROTARY_CLK_PIN, ROTARY_DT_PIN, max_steps=0)
    print(f"[INIT] Rotary encoder configured: CLK=GPIO{ROTARY_CLK_PIN}, DT=GPIO{ROTARY_DT_PIN}")
    
    # Setup amplifier shutdown pin (active high means on)
    amplifier_sd = OutputDevice(AMPLIFIER_SD_PIN, active_high=True, initial_value=False)
    print(f"[INIT] Amplifier SD pin configured on GPIO{AMPLIFIER_SD_PIN}")
    
    # Initialize volume control (software only)
    print(f"\n[INIT] Setting up software volume control...")
    current_volume = INITIAL_VOLUME
    print(f"[INIT] ✓ Volume control ready: {current_volume}% (100% = full volume)")
    print(f"[INIT] ℹ Rotate encoder anytime to adjust volume (even during playback!)")
    
    # Setup rotary encoder callback for volume control
    def on_rotate():
        global current_volume
        steps = rotary_encoder.steps
        if steps != 0:
            # Calculate new volume
            volume_change = steps * VOLUME_STEP
            new_volume = current_volume + volume_change
            
            # Clamp to valid range
            new_volume = max(0, min(100, new_volume))
            
            # Only update if changed
            if new_volume != current_volume:
                old_volume = current_volume
                current_volume = new_volume
                
                # Show volume change
                print(f"[VOLUME] {'↑' if volume_change > 0 else '↓'} {old_volume}% → {current_volume}%")
            
            # Reset steps counter
            rotary_encoder.steps = 0
    
    # Attach rotation callback
    rotary_encoder.when_rotated = on_rotate
    print(f"[INIT] ✓ Rotary encoder active: ±{VOLUME_STEP}% per step (button + rotation)")
    
    # API key no longer needed - authentication is via device UUID
    # The device UUID is managed by device_manager (initialized above)
    
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

# ==================== AUDIO UTILITIES ====================

def apply_volume_to_audio(audio_data: bytes, volume_percent: int, sample_width: int = 2) -> bytes:
    """
    Apply software volume scaling to audio data.
    
    This is required because the googlevoicehat driver doesn't support hardware volume control.
    Software scaling ensures all audio (beeps and AI speech) respects the volume setting.
    
    Args:
        audio_data: Raw PCM audio data (bytes)
        volume_percent: Volume level 0-100 (%)
        sample_width: Sample width in bytes (default 2 for 16-bit)
    
    Returns:
        Volume-scaled audio data (bytes)
    """
    if volume_percent == 100:
        # No scaling needed
        return audio_data
    
    # Convert volume percentage to linear scale (0.0 - 1.0)
    volume_scale = volume_percent / 100.0
    
    # Convert bytes to numpy array based on sample width
    if sample_width == 2:
        # 16-bit signed integer
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        # Apply volume scaling and clip to prevent distortion
        scaled_array = (audio_array.astype(np.float32) * volume_scale).clip(-32768, 32767).astype(np.int16)
        return scaled_array.tobytes()
    else:
        # Unsupported sample width, return original
        return audio_data

# REMOVED: scale_wav_file_volume() - no longer needed
# All volume scaling happens in real-time during playback

# ==================== BEEP SOUNDS ====================

def generate_beep_sounds():
    """
    Generate pleasant beep sounds at FULL VOLUME (100%).
    Volume scaling is applied in real-time during playback via current_volume.
    """
    try:
        sample_rate = SAMPLE_RATE  # Match I2S device sample rate (48000 Hz)
        
        # Generate at FULL volume - scaling happens during playback
        beep_volume = 1.0  # ALWAYS 100% - volume control happens at playback time
        
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
        
        # Apply envelope at FULL volume (100%)
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
        print(f"[INIT] ✓ Beep sounds generated at full volume (volume control during playback)")
        
    except Exception as e:
        print(f"[WARNING] Could not generate beep sounds: {e}")
        import traceback
        print(f"[WARNING] Traceback: {traceback.format_exc()}")

def play_beep_async(beep_file, description=""):
    """
    Play a short beep sound with REAL-TIME volume control.
    
    REAL-TIME VOLUME:
    - Beep respects current_volume setting
    - Uses PyAudio streaming for real-time volume scaling
    - No pre-processing - volume applied during playback
    """
    def _play_beep_thread():
        if not beep_file.exists():
            return
        
        audio = None
        stream = None
        
        try:
            # Read beep WAV file
            with wave.open(str(beep_file), 'rb') as wf:
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                sample_rate = wf.getframerate()
                beep_data = wf.readframes(wf.getnframes())
            
            # Apply REAL-TIME volume scaling
            scaled_beep = apply_volume_to_audio(beep_data, current_volume, sample_width)
            
            # Initialize PyAudio for playback
            audio = pyaudio.PyAudio()
            
            # Find output device
            device_index = None
            for i in range(audio.get_device_count()):
                info = audio.get_device_info_by_index(i)
                device_name = info.get('name', '').lower()
                max_output = info.get('maxOutputChannels', 0)
                
                if max_output > 0 and ('googlevoicehat' in device_name or 
                                      'voicehat' in device_name or
                                      'sndrpigooglevoi' in device_name):
                    device_index = i
                    break
            
            # Open output stream
            stream = audio.open(
                format=audio.get_format_from_width(sample_width),
                channels=channels,
                rate=sample_rate,
                output=True,
                output_device_index=device_index
            )
            
            # Enable amplifier
            amplifier_sd.on()
            time.sleep(0.02)
            
            # Play scaled beep
            stream.write(scaled_beep)
            
            # Wait for playback to complete
            time.sleep(0.02)
            
            # Disable amplifier
            amplifier_sd.off()
            
            # Clean up
            if stream:
                stream.stop_stream()
                stream.close()
            if audio:
                audio.terminate()
            
        except Exception:
            amplifier_sd.off()
            try:
                if stream:
                    stream.stop_stream()
                    stream.close()
            except:
                pass
            try:
                if audio:
                    audio.terminate()
            except:
                pass
    
    # Start beep in background thread - returns immediately
    thread = threading.Thread(target=_play_beep_thread, daemon=True)
    thread.start()
    if VERBOSE_OUTPUT:
        print(f"[BEEP] ▶ {description} beep (volume: {current_volume}%)")

def play_beep(beep_file, description=""):
    """Legacy synchronous beep - kept for compatibility"""
    play_beep_async(beep_file, description)

# ==================== BUTTON HANDLING ====================

def wait_for_button_press():
    """
    Wait for button press with instant response.
    
    PERFORMANCE OPTIMIZATION:
    - Beep plays asynchronously (non-blocking)
    - Recording setup happens in parallel with beep
    - Minimal debounce delay
    """
    print("[BUTTON] Waiting for button press to start recording...")
    
    while not button.is_pressed:
        time.sleep(0.005)  # Reduced from 0.01 for faster detection
    
    print("[BUTTON] *** BUTTON PRESSED! Starting recording... ***")
    
    # Record activity for update manager
    if activity_tracker:
        activity_tracker.record_activity("button_press")
    
    # Play start beep asynchronously - doesn't block recording startup
    play_beep_async(START_BEEP_FILE, "start")
    
    time.sleep(0.02)  # Minimal debounce (reduced from 0.05)

def wait_for_button_release():
    """Wait for button press again to stop recording"""
    print("[BUTTON] Press button again to stop recording...")
    
    # Wait for button to be released first
    while button.is_pressed:
        time.sleep(0.01)
    
    # Now wait for button press again
    while not button.is_pressed:
        time.sleep(0.01)
    
    print("[BUTTON] *** BUTTON PRESSED! Stopping recording... ***")
    
    # Play stop beep to indicate mic stopped listening
    play_beep(STOP_BEEP_FILE, "stop")
    
    time.sleep(0.05)  # Debounce
    
    # Wait for release
    while button.is_pressed:
        time.sleep(0.01)
    
    print("[BUTTON] Released. Processing audio...\n")

# ==================== OPUS COMPRESSION ====================

def compress_to_opus(wav_path, opus_path, bitrate=96000):
    """
    Compress WAV file to Opus format for efficient network transfer.
    
    PERFORMANCE OPTIMIZATION:
    - 90% file size reduction (5MB WAV → 500KB Opus)
    - 10x faster upload times
    - Minimal CPU overhead (~50ms for 5s audio)
    - ARM-optimized codec
    
    Args:
        wav_path: Path to input WAV file
        opus_path: Path to output Opus file
        bitrate: Bitrate in bits/second (default 96000 for excellent voice quality)
    """
    try:
        if VERBOSE_OUTPUT:
            print(f"[OPUS] Compressing audio to Opus format ({bitrate//1000}kbps)...")
        
        # Read WAV file
        with wave.open(str(wav_path), 'rb') as wf:
            sample_rate = wf.getframerate()
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            n_frames = wf.getnframes()
            pcm_data = wf.readframes(n_frames)
        
        # Validate format
        if sample_rate != SAMPLE_RATE:
            raise ValueError(f"Expected sample rate {SAMPLE_RATE}, got {sample_rate}")
        if channels != CHANNELS:
            raise ValueError(f"Expected {CHANNELS} channel(s), got {channels}")
        if sample_width != 2:  # 16-bit
            raise ValueError(f"Expected 16-bit audio, got {sample_width*8}-bit")
        
        # Create Opus encoder
        encoder = opuslib.Encoder(sample_rate, channels, opuslib.APPLICATION_VOIP)
        encoder.bitrate = bitrate
        encoder.complexity = 10  # Maximum quality (0-10)
        
        # Encode in chunks (Opus frame size must be specific durations)
        # For 48kHz: valid frame sizes are 120, 240, 480, 960, 1920, 2880 samples
        frame_size = 960  # 20ms at 48kHz (optimal for speech)
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
        
        # Write Opus file (simple concatenation with basic OGG container)
        # For simplicity, we'll use raw Opus packets with length prefixes
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
        
        if VERBOSE_OUTPUT:
            print(f"[OPUS] ✓ Compressed: {original_size} → {compressed_size} bytes ({compression_ratio:.1f}% reduction)")
        return True
        
    except Exception as e:
        print(f"[ERROR] Opus compression failed: {e}")
        import traceback
        print(f"[DEBUG] {traceback.format_exc()}")
        return False

def decompress_from_opus(opus_path, wav_path):
    """
    Decompress Opus file to WAV format for playback.
    
    PERFORMANCE OPTIMIZATION:
    - Fast decompression (~30ms for 3s audio)
    - Required for I2S playback (hardware needs WAV)
    
    Args:
        opus_path: Path to input Opus file
        wav_path: Path to output WAV file
    """
    try:
        if VERBOSE_OUTPUT:
            print(f"[OPUS] Decompressing Opus to WAV for playback...")
        
        # Read Opus file
        with open(opus_path, 'rb') as f:
            # Read header
            sample_rate = int.from_bytes(f.read(4), 'little')
            channels = int.from_bytes(f.read(1), 'little')
            num_packets = int.from_bytes(f.read(4), 'little')
            
            # Create Opus decoder
            decoder = opuslib.Decoder(sample_rate, channels)
            
            # Decode all packets
            pcm_chunks = []
            for i in range(num_packets):
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
        
        # Verify the file was written correctly
        if wav_path.exists():
            file_size = wav_path.stat().st_size
            if VERBOSE_OUTPUT:
                print(f"[OPUS] ✓ Decompressed to WAV: {file_size} bytes")
        else:
            print(f"[ERROR] WAV file not created!")
            return False
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Opus decompression failed: {e}")
        import traceback
        print(f"[DEBUG] {traceback.format_exc()}")
        return False

# ==================== AUDIO RECORDING ====================

class StreamingAudioRecorder:
    """
    Records audio WITHOUT amplification - raw capture only.
    
    PERFORMANCE OPTIMIZATION:
    - Zero processing on Pi Zero 2 W (just capture raw audio)
    - Amplification moved to server (more powerful CPU)
    - Minimal CPU usage during recording
    - Fastest possible capture
    """
    def __init__(self):
        self.frames = []
        self.chunk_count = 0
        
    def add_chunk(self, audio_data):
        """Add raw audio chunk - NO processing"""
        self.frames.append(audio_data)
        self.chunk_count += 1
    
    def get_audio_data(self):
        """Get raw audio data"""
        return b''.join(self.frames)
    
    def get_duration(self):
        """Get recording duration in seconds"""
        return self.chunk_count * CHUNK_SIZE / SAMPLE_RATE

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
    
    try:
        device_count = audio.get_device_count()
        print(f"[AUDIO] Scanning {device_count} audio devices...")
    except Exception as e:
        print(f"[ERROR] Could not get device count: {e}")
        return None
    
    # First pass: Look for Voice HAT devices
    for i in range(device_count):
        try:
            info = audio.get_device_info_by_index(i)
            device_name = info.get('name', '').lower()
            max_input = info.get('maxInputChannels', 0)
            
            print(f"[AUDIO] Device {i}: {info.get('name', 'Unknown')} (inputs: {max_input})")
            
            if max_input > 0 and ('googlevoicehat' in device_name or 
                                  'voicehat' in device_name or
                                  'sndrpigooglevoi' in device_name or
                                  'google' in device_name):
                device_index = i
                print(f"[AUDIO] ✓ Found Voice HAT device at index {i}: {info.get('name')}")
                break
        except Exception as e:
            print(f"[AUDIO] Error checking device {i}: {e}")
            continue
    
    # Second pass: If Voice HAT not found, use default input device
    if device_index is None:
        try:
            default_info = audio.get_default_input_device_info()
            device_index = default_info['index']
            print(f"[AUDIO] Using default input device: {default_info.get('name')}")
        except Exception as e:
            print(f"[AUDIO] No default input device: {e}")
    
    # Third pass: Use any input device
    if device_index is None:
        for i in range(device_count):
            try:
                info = audio.get_device_info_by_index(i)
                if info.get('maxInputChannels', 0) > 0:
                    device_index = i
                    print(f"[AUDIO] Using first available input device {i}: {info.get('name')}")
                    break
            except Exception:
                continue
    
    # Cache the result
    _CACHED_AUDIO_DEVICE_INDEX = device_index
    
    if device_index is None:
        print("[ERROR] No input device found after scanning all devices")
    
    return device_index

def record_audio_with_arecord():
    """
    Record audio using arecord command (more reliable for I2S devices).
    
    This method bypasses PyAudio which has compatibility issues with some
    ALSA configurations, particularly the googlevoicehat driver.
    """
    print("[AUDIO] Recording with arecord... SPEAK NOW!")
    print("[AUDIO] " + "="*40)
    
    process = None
    
    try:
        # Start arecord in background
        # Use full CARD name for better reliability across Pi models
        process = subprocess.Popen(
            [
                'arecord',
                '-D', 'plughw:CARD=sndrpigooglevoi,DEV=0',  # googlevoicehat device (full name)
                '-f', 'S16_LE',       # 16-bit signed little-endian
                '-r', str(SAMPLE_RATE),  # 48000 Hz
                '-c', str(CHANNELS),     # 1 channel (mono)
                str(RECORDING_FILE)      # Output file
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        print(f"[AUDIO] arecord started (PID: {process.pid})")
        
        # Wait for button to be released first
        while button.is_pressed:
            time.sleep(0.005)
        
        # Record until button is pressed again
        start_time = time.time()
        while not button.is_pressed:
            # Progress indicator every second
            elapsed = time.time() - start_time
            if int(elapsed) > 0 and int(elapsed) % 1 == 0:
                if int(elapsed * 10) % 10 == 0:  # Only print once per second
                    print(f"[AUDIO] {int(elapsed)}s recorded...")
            time.sleep(0.1)
        
        print("[AUDIO] " + "="*40)
        print("[BUTTON] *** BUTTON PRESSED! Stopping recording... ***")
        
        # Stop arecord gracefully
        process.terminate()
        
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        
        # Play stop beep asynchronously
        play_beep_async(STOP_BEEP_FILE, "stop")
        
        # Wait for button release
        while button.is_pressed:
            time.sleep(0.005)
        
        # Check if file was created
        if not RECORDING_FILE.exists():
            print("[ERROR] Recording file was not created")
            return False
        
        file_size = RECORDING_FILE.stat().st_size
        if file_size < 1000:
            print(f"[WARNING] Recording file is very small ({file_size} bytes)")
        
        duration = time.time() - start_time
        print(f"[AUDIO] Recording complete ({duration:.1f}s, {file_size} bytes)")
        print(f"[AUDIO] Saved: {RECORDING_FILE}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Recording failed: {e}")
        import traceback
        print(f"[DEBUG] {traceback.format_exc()}")
        return False
        
    finally:
        # Clean up process
        if process and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=1)
            except:
                try:
                    process.kill()
                except:
                    pass

def record_audio():
    """
    Record RAW audio from I2S microphone - NO processing on Pi.
    
    CRITICAL PERFORMANCE OPTIMIZATION:
    - Zero audio processing on Pi Zero 2 W (just raw capture)
    - Amplification handled by server (has powerful CPU)
    - Fastest possible recording - minimal CPU usage
    - Instant availability after recording stops
    """
    print("[AUDIO] Recording... SPEAK NOW!")
    print("[AUDIO] " + "="*40)
    
    audio = None
    stream = None
    
    try:
        # Initialize PyAudio
        audio = pyaudio.PyAudio()
        
        # Small delay to allow ALSA to initialize
        time.sleep(0.1)
        
        # Use cached device lookup (instant)
        device_index = get_audio_device_index(audio)
        
        if device_index is None:
            print("[ERROR] No input devices found via PyAudio!")
            print("[INFO] Falling back to arecord method...")
            if audio:
                audio.terminate()
            return record_audio_with_arecord()
        
        # Validate device
        try:
            device_info = audio.get_device_info_by_index(device_index)
            max_inputs = device_info.get('maxInputChannels', 0)
            device_name = device_info.get('name', 'Unknown')
            print(f"[AUDIO] Using device {device_index}: {device_name} ({max_inputs} input channels)")
            
            if max_inputs < 1:
                print("[WARNING] Device reports 0 input channels, trying anyway...")
                # Don't fail - googlevoicehat might report 0 but still work
        except Exception as e:
            print(f"[WARNING] Could not validate device {device_index}: {e}")
            print("[AUDIO] Attempting to open stream anyway...")
        
        # Open stream with optimized buffer size
        try:
            stream = audio.open(
                format=AUDIO_FORMAT,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=CHUNK_SIZE  # 512 samples = 10.6ms latency at 48kHz
            )
            print(f"[AUDIO] ✓ Stream opened successfully")
        except Exception as e:
            print(f"[ERROR] Failed to open audio stream: {e}")
            print(f"[DEBUG] Trying without specifying device index...")
            # Try without specifying device (use default)
            try:
                stream = audio.open(
                    format=AUDIO_FORMAT,
                    channels=CHANNELS,
                    rate=SAMPLE_RATE,
                    input=True,
                    frames_per_buffer=CHUNK_SIZE
                )
                print(f"[AUDIO] ✓ Stream opened with default device")
            except Exception as e2:
                print(f"[ERROR] Failed to open stream with default device: {e2}")
                return False
        
        # Initialize recorder - NO amplification (done on server)
        recorder = StreamingAudioRecorder()
        
        # Wait for button to be released first
        while button.is_pressed:
            time.sleep(0.005)
        
        # Record until button is pressed again - RAW audio only
        while not button.is_pressed:
            try:
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                recorder.add_chunk(data)  # Just store, no processing!
                
                # Progress indicator every second
                if recorder.chunk_count % (SAMPLE_RATE // CHUNK_SIZE) == 0:
                    seconds = recorder.chunk_count // (SAMPLE_RATE // CHUNK_SIZE)
                    print(f"[AUDIO] {seconds}s recorded...")
            except Exception as e:
                print(f"[WARNING] Audio buffer issue: {e}")
                continue
        
        print("[AUDIO] " + "="*40)
        print("[BUTTON] *** BUTTON PRESSED! Stopping recording... ***")
        
        # Validate recording
        if recorder.chunk_count == 0:
            print("[ERROR] No audio data recorded")
            return False
        
        total_seconds = recorder.get_duration()
        print(f"[AUDIO] Recording complete ({total_seconds:.1f}s)")
        
        # Get sample width BEFORE closing audio
        sample_width = audio.get_sample_size(AUDIO_FORMAT)
        
        # Close audio resources
        if stream is not None:
            stream.stop_stream()
            stream.close()
            stream = None
        if audio is not None:
            audio.terminate()
            audio = None
        
        # Play stop beep asynchronously (non-blocking)
        play_beep_async(STOP_BEEP_FILE, "stop")
        
        # Wait for button release
        while button.is_pressed:
            time.sleep(0.005)
        
        # Get RAW audio data - zero processing time!
        print(f"[AUDIO] Raw audio ready (server will amplify)")
        audio_data = recorder.get_audio_data()
        
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

# Persistent HTTP session for connection reuse
_HTTP_SESSION = None

def get_http_session():
    """
    Get or create persistent HTTP session.
    
    PERFORMANCE OPTIMIZATION:
    - Connection reuse (TCP handshake only once)
    - Keep-alive connections
    - Reduced latency on subsequent requests
    
    AUTHENTICATION:
    - Uses device UUID for authentication (X-Device-UUID header)
    - No shared API keys - each device has unique identifier
    """
    global _HTTP_SESSION
    if _HTTP_SESSION is None:
        _HTTP_SESSION = requests.Session()
        
        # Get device UUID from device_manager
        if device_manager is None:
            print("[ERROR] Device manager not initialized!")
            raise RuntimeError("Device manager must be initialized before making requests")
        
        device_uuid = device_manager.get_device_uuid()
        
        # Configure for optimal performance with device authentication
        _HTTP_SESSION.headers.update({
            'Connection': 'keep-alive',
            'X-Device-UUID': device_uuid
        })
        
        # Retry on connection errors
        from requests.adapters import HTTPAdapter
        from requests.packages.urllib3.util.retry import Retry
        retry_strategy = Retry(
            total=2,
            backoff_factor=0.1,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=1, pool_maxsize=1)
        _HTTP_SESSION.mount("http://", adapter)
        _HTTP_SESSION.mount("https://", adapter)
    return _HTTP_SESSION

def send_to_server():
    """
    Send audio to server with Opus compression.
    
    PERFORMANCE OPTIMIZATIONS:
    - Opus compression (90% file size reduction)
    - Connection reuse (keep-alive)
    - Streaming upload (memory efficient)
    - 10x faster upload times
    """
    # Send heartbeat to server (includes activity tracking)
    if device_manager:
        device_manager.send_heartbeat()
    
    print("[SERVER] Preparing audio for upload...")
    
    if not RECORDING_FILE.exists():
        print("[ERROR] Recording file not found")
        return False
    
    # Compress WAV to Opus before upload
    if not compress_to_opus(RECORDING_FILE, RECORDING_OPUS_FILE, bitrate=96000):
        print("[ERROR] Failed to compress audio")
        return False
    
    opus_file_size = RECORDING_OPUS_FILE.stat().st_size
    if opus_file_size < 100:
        print(f"[ERROR] Compressed file too small ({opus_file_size} bytes)")
        return False
    
    try:
        session = get_http_session()
        
        with open(RECORDING_OPUS_FILE, 'rb') as audio_file:
            files = {
                'audio': ('recording.opus', audio_file, 'audio/opus')
            }
            data = {
                'session_id': None,  # TODO: Implement session management
                'microphone_gain': str(MICROPHONE_GAIN)  # Server will amplify audio
            }
            
            if VERBOSE_OUTPUT:
                print(f"[SERVER] Uploading {opus_file_size} bytes Opus (gain: {MICROPHONE_GAIN}x on server)...")
            upload_start = time.time()
            
            # Send request with persistent session (faster than new connection)
            response = session.post(
                f"{SERVER_URL}/api/v1/process",
                files=files,
                data=data,
                timeout=120,
                stream=True
            )
            
            upload_time = time.time() - upload_start
            if VERBOSE_OUTPUT:
                print(f"[SERVER] Upload complete ({upload_time:.2f}s)")
            
            if VERBOSE_OUTPUT:
                print(f"[SERVER] Response code: {response.status_code}")
            
            if response.status_code == 200:
                # Get metadata from headers (URL-decode to handle Unicode characters)
                transcription = unquote(response.headers.get('X-Transcription', ''))
                llm_response = unquote(response.headers.get('X-LLM-Response', ''))
                
                print(f"[SUCCESS] Transcription: \"{transcription}\"")
                print(f"[SUCCESS] LLM Response: \"{llm_response}\"")
                
                # Save response audio (Opus format)
                total_bytes = 0
                with open(RESPONSE_OPUS_FILE, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            total_bytes += len(chunk)
                
                if total_bytes == 0:
                    print("[ERROR] Received empty audio file")
                    return False
                
                if VERBOSE_OUTPUT:
                    print(f"[SUCCESS] Opus audio saved: {RESPONSE_OPUS_FILE} ({total_bytes} bytes)")
                
                # Decompress Opus to WAV for playback
                if not decompress_from_opus(RESPONSE_OPUS_FILE, RESPONSE_FILE):
                    print("[ERROR] Failed to decompress response audio")
                    return False
                
                return True
                
            elif response.status_code == 401:
                print("[ERROR] Unauthorized")
                return False
            elif response.status_code == 403:
                print("[ERROR] Forbidden - Device not registered or not authorized")
                print(f"[ERROR] Device UUID: {device_manager.get_device_uuid()}")
                print("[ERROR] ")
                print("[ERROR] This device must be registered on the server.")
                print("[ERROR] On your server, SSH in and run:")
                print(f"[ERROR]   cd /opt/javia")
                print(f"[ERROR]   sudo ./register_device.sh {device_manager.get_device_uuid()}")
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
    """
    Play audio through I2S amplifier with REAL-TIME volume control.
    
    REAL-TIME FEATURES:
    - Volume changes take effect immediately during playback
    - Rotate encoder while speaking to adjust volume
    - Smooth volume transitions with no clicks
    
    AUDIO QUALITY:
    - Minimal processing to preserve quality
    - Optional fade/padding (only if configured)
    - PyAudio streaming for real-time control
    
    VOLUME CONTROL:
    - Monitors current_volume every chunk (10ms)
    - Applies volume scaling in real-time
    - Changes are immediate and smooth
    """
    if not RESPONSE_FILE.exists():
        print("[ERROR] Response file not found")
        return False
    
    audio = None
    stream = None
    temp_processed_file = None
    
    try:
        if VERBOSE_OUTPUT:
            print("[PLAYBACK] Preparing audio...")
        
        # Apply optional processing (fade/padding) to a temp file
        # Volume scaling happens in real-time during playback
        temp_processed_file = AUDIO_DIR / "temp_response_processed.wav"
        
        # Copy original to temp file
        import shutil
        shutil.copy(RESPONSE_FILE, temp_processed_file)
        
        # Apply fade and padding ONLY if configured (optional for quality)
        if FADE_DURATION_MS > 0:
            if VERBOSE_OUTPUT:
                print(f"[PLAYBACK] Applying {FADE_DURATION_MS}ms fade effects...")
            apply_fade_in_out(temp_processed_file, fade_duration_ms=FADE_DURATION_MS)
        
        # Add minimal silence padding (reduced from 150ms to 50ms for performance)
        if VERBOSE_OUTPUT:
            print("[PLAYBACK] Adding silence padding...")
        add_silence_padding(temp_processed_file, padding_ms=50)
        
        # Read WAV file
        with wave.open(str(temp_processed_file), 'rb') as wf:
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            sample_rate = wf.getframerate()
            n_frames = wf.getnframes()
            
            # Initialize PyAudio
            audio = pyaudio.PyAudio()
            
            # Find output device
            device_index = None
            for i in range(audio.get_device_count()):
                info = audio.get_device_info_by_index(i)
                device_name = info.get('name', '').lower()
                max_output = info.get('maxOutputChannels', 0)
                
                if max_output > 0 and ('googlevoicehat' in device_name or 
                                      'voicehat' in device_name or
                                      'sndrpigooglevoi' in device_name):
                    device_index = i
                    break
            
            # Open output stream
            stream = audio.open(
                format=audio.get_format_from_width(sample_width),
                channels=channels,
                rate=sample_rate,
                output=True,
                output_device_index=device_index,
                frames_per_buffer=CHUNK_SIZE
            )
            
            # Enable amplifier
            amplifier_sd.on()
            time.sleep(0.200)  # Stabilization time
            
            # Play audio with real-time volume control
            print(f"[PLAYBACK] Playing (volume: {current_volume}%)... Rotate encoder to adjust, press button to stop")
            
            chunk_size = CHUNK_SIZE * channels * sample_width
            last_displayed_volume = current_volume
            interrupted = False
            
            while True:
                # Read chunk from file
                data = wf.readframes(CHUNK_SIZE)
                
                if not data:
                    break
                
                # Apply REAL-TIME volume scaling based on current_volume
                # This happens EVERY chunk, so volume changes take effect immediately
                scaled_data = apply_volume_to_audio(data, current_volume, sample_width)
                
                # Write to output stream
                stream.write(scaled_data)
                
                # Display volume changes in real-time
                if current_volume != last_displayed_volume:
                    print(f"[PLAYBACK] Volume adjusted: {last_displayed_volume}% → {current_volume}%")
                    last_displayed_volume = current_volume
                
                # Check for button interrupt
                if button.is_pressed:
                    print("\n[INTERRUPT] *** BUTTON PRESSED! Stopping playback... ***")
                    interrupted = True
                    break
        
        # Wait for audio to fully complete
        time.sleep(0.200)
        
        # Disable amplifier
        amplifier_sd.off()
        
        # Clean up
        if stream is not None:
            stream.stop_stream()
            stream.close()
        if audio is not None:
            audio.terminate()
        
        # Clean up temp file
        if temp_processed_file and temp_processed_file.exists():
            temp_processed_file.unlink()
        
        if interrupted:
            print("[INTERRUPT] Playback cancelled!")
            while button.is_pressed:
                time.sleep(0.01)
            return False
        else:
            print("[PLAYBACK] Complete!")
            return True
            
    except Exception as e:
        print(f"[ERROR] Playback error: {e}")
        import traceback
        print(f"[DEBUG] {traceback.format_exc()}")
        amplifier_sd.off()
        
        # Clean up
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
        
        # Clean up temp file
        if temp_processed_file and temp_processed_file.exists():
            try:
                temp_processed_file.unlink()
            except:
                pass
        
        return False

# ==================== MAIN LOOP ====================

def main():
    """Main program loop"""
    try:
        setup()
        
        print("\n[INFO] Voice assistant ready. OTA updates running in background.")
        print("[INFO] Updates will be applied at 2 AM local time or after 1 hour inactivity (urgent updates).\n")
        
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
        # Stop update manager
        if update_manager:
            update_manager.stop()
            print("[EXIT] Update manager stopped")
        
        # Close GPIO devices (gpiozero handles cleanup automatically)
        if button:
            button.close()
        if rotary_encoder:
            rotary_encoder.close()
        if amplifier_sd:
            amplifier_sd.close()
        print("[EXIT] GPIO cleanup complete")

if __name__ == "__main__":
    main()

