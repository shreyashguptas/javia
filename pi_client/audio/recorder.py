#!/usr/bin/env python3
"""
Audio Recorder for Pi Voice Assistant Client
Records audio from I2S microphone using PyAudio or arecord fallback
"""

import time
import wave
import subprocess
import pyaudio
import logging
import config
from audio.hardware_detect import is_googlevoicehat, get_alsa_device_name

logger = logging.getLogger(__name__)


# ==================== ALSA MIXER CONTROL ====================

def ensure_capture_volume():
    """
    Ensure ALSA capture volume is set to maximum for I2S microphones.
    
    I2S microphones like INMP441 don't have hardware volume control,
    but ALSA mixer settings can affect the recording level.
    """
    try:
        # Try to set capture volume to 100% using amixer
        result = subprocess.run(
            ['amixer', 'sset', 'Capture', '100%'],
            capture_output=True,
            text=True,
            timeout=2
        )
        
        if result.returncode == 0:
            logger.info("[AUDIO] ✓ Set capture volume to 100%")
        else:
            # Capture control might not exist - that's okay for some drivers
            logger.debug("[AUDIO] Capture volume control not available (this is normal for I2S mics)")
    except FileNotFoundError:
        logger.debug("[AUDIO] amixer not found (okay for direct I2S recording)")
    except Exception as e:
        logger.debug(f"[AUDIO] Could not set capture volume: {e}")


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
        return self.chunk_count * config.CHUNK_SIZE / config.SAMPLE_RATE


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
    # Return cached value if available
    if config._CACHED_AUDIO_DEVICE_INDEX is not None:
        return config._CACHED_AUDIO_DEVICE_INDEX
    
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
    config._CACHED_AUDIO_DEVICE_INDEX = device_index
    
    if device_index is None:
        print("[ERROR] No input device found after scanning all devices")
    
    return device_index


def record_audio_with_arecord(gpio_manager):
    """
    Record audio using arecord command (more reliable for I2S devices).
    
    This method bypasses PyAudio which has compatibility issues with some
    ALSA configurations, particularly the googlevoicehat driver.
    
    Args:
        gpio_manager: GPIOManager instance for button control
    
    Returns:
        bool: True if successful, False otherwise
    """
    logger.info("[AUDIO] Recording with arecord... SPEAK NOW!")
    logger.info("[AUDIO] " + "="*40)
    
    process = None
    
    try:
        # Ensure capture volume is set correctly
        ensure_capture_volume()
        
        # Get ALSA device name from hardware detection
        device_name = get_alsa_device_name()
        
        # For I2S microphones (like INMP441), we need to use hw: instead of plughw:
        # to avoid ALSA's software mixing which can cause issues
        # Change plughw to hw for better compatibility with I2S devices
        if "plughw" in device_name:
            # Try hw: first for I2S devices (better performance)
            device_name_hw = device_name.replace("plughw", "hw")
            logger.info(f"[AUDIO] Using hw: device for I2S microphone: {device_name_hw}")
            device_name = device_name_hw
        
        # Start arecord in background with verbose mode to capture any warnings
        # Note: We capture both stdout and stderr to see ALSA messages
        process = subprocess.Popen(
            [
                'arecord',
                '-D', device_name,              # ALSA device (hw: for I2S is more reliable)
                '-f', 'S16_LE',                 # 16-bit signed little-endian
                '-r', str(config.SAMPLE_RATE),  # 48000 Hz
                '-c', str(config.CHANNELS),     # 1 channel (mono)
                '-V', 'mono',                   # Verbose mode + VU meter (helps debug levels)
                str(config.RECORDING_FILE)      # Output file
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True  # Get text output for stderr monitoring
        )
        
        logger.info(f"[AUDIO] arecord started (PID: {process.pid}) on device: {device_name}")
        
        # Wait for button to be released first
        while gpio_manager.button.is_pressed:
            time.sleep(0.005)
        
        # Record until button is pressed again
        start_time = time.time()
        while not gpio_manager.button.is_pressed:
            # Progress indicator every second
            elapsed = time.time() - start_time
            if int(elapsed) > 0 and int(elapsed) % 1 == 0:
                if int(elapsed * 10) % 10 == 0:  # Only print once per second
                    logger.info(f"[AUDIO] {int(elapsed)}s recorded...")
            time.sleep(0.1)
        
        logger.info("[AUDIO] " + "="*40)
        logger.info("[BUTTON] *** BUTTON PRESSED! Stopping recording... ***")
        
        # Stop arecord gracefully
        process.terminate()
        
        try:
            stdout, stderr = process.communicate(timeout=2)
            
            # Log any errors or warnings from arecord
            if stderr:
                # Filter out common harmless warnings
                for line in stderr.split('\n'):
                    if line.strip() and 'VU meter' not in line and '|' not in line:
                        if 'warning' in line.lower() or 'error' in line.lower():
                            logger.warning(f"[AUDIO] arecord: {line.strip()}")
                        else:
                            logger.debug(f"[AUDIO] arecord: {line.strip()}")
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
        
        # Wait for button release
        while gpio_manager.button.is_pressed:
            time.sleep(0.005)
        
        # Check if file was created
        if not config.RECORDING_FILE.exists():
            logger.error("[ERROR] Recording file was not created")
            return False
        
        file_size = config.RECORDING_FILE.stat().st_size
        duration = time.time() - start_time
        
        # Calculate expected minimum file size (at least 0.5 seconds of audio)
        # 48000 Hz * 2 bytes/sample * 1 channel * 0.5 seconds = 48000 bytes minimum
        expected_min_size = config.SAMPLE_RATE * 2 * config.CHANNELS * 0.5
        
        if file_size < expected_min_size:
            logger.error(f"[ERROR] Recording file is too small ({file_size} bytes, expected >{expected_min_size:.0f})")
            logger.error("[ERROR] Microphone may not be working - check hardware connections")
            logger.error("[ERROR] Verify INMP441 is connected to GPIO20 (PCM_DIN)")
        elif file_size < 1000:
            logger.warning(f"[WARNING] Recording file is very small ({file_size} bytes)")
        else:
            logger.info(f"[AUDIO] ✓ Recording looks good ({duration:.1f}s, {file_size:,} bytes)")
        
        logger.info(f"[AUDIO] Saved: {config.RECORDING_FILE}")
        
        # Additional diagnostic: Check if file contains mostly silence
        try:
            import wave
            import numpy as np
            with wave.open(str(config.RECORDING_FILE), 'rb') as wf:
                audio_data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
                max_amplitude = np.abs(audio_data).max()
                avg_amplitude = np.abs(audio_data).mean()
                
                logger.info(f"[AUDIO] Signal levels - Max: {max_amplitude}/32768, Avg: {avg_amplitude:.1f}/32768")
                
                if max_amplitude < 100:
                    logger.warning("[WARNING] Audio signal is very weak - microphone might not be working!")
                    logger.warning("[WARNING] Check that INMP441 L/R pin is connected to ground")
                    logger.warning("[WARNING] Check that INMP441 VDD has 3.3V power")
                elif max_amplitude < 1000:
                    logger.warning("[WARNING] Audio signal is quiet - consider checking microphone gain")
        except Exception as diag_error:
            logger.debug(f"[DEBUG] Could not analyze audio levels: {diag_error}")
        
        return True
        
    except Exception as e:
        logger.error(f"[ERROR] Recording failed: {e}")
        import traceback
        logger.debug(f"{traceback.format_exc()}")
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


def record_audio(gpio_manager):
    """
    Record RAW audio from I2S microphone - NO processing on Pi.
    
    STRATEGY:
    - Detects hardware type first (googlevoicehat vs other)
    - Uses arecord for googlevoicehat (eliminates segfaults)
    - Uses PyAudio for other devices (with arecord fallback)
    
    CRITICAL PERFORMANCE OPTIMIZATION:
    - Zero audio processing on Pi (just raw capture)
    - Amplification handled by server (has powerful CPU)
    - Fastest possible recording - minimal CPU usage
    - Instant availability after recording stops
    
    Args:
        gpio_manager: GPIOManager instance for button control
    
    Returns:
        bool: True if successful, False otherwise
    """
    # Detect hardware and route to appropriate method
    if is_googlevoicehat():
        # Use arecord for googlevoicehat (prevents segmentation faults)
        logger.info("[AUDIO] ✓ Detected googlevoicehat driver - using arecord for reliability")
        return record_audio_with_arecord(gpio_manager)
    
    # For other hardware, try PyAudio with arecord fallback
    logger.info("[AUDIO] Recording... SPEAK NOW!")
    logger.info("[AUDIO] " + "="*40)
    
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
            # Clean up PyAudio before fallback
            try:
                if audio:
                    audio.terminate()
                    audio = None
            except Exception as cleanup_error:
                print(f"[DEBUG] PyAudio cleanup error: {cleanup_error}")
            return record_audio_with_arecord(gpio_manager)
        
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
                format=pyaudio.paInt16,
                channels=config.CHANNELS,
                rate=config.SAMPLE_RATE,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=config.CHUNK_SIZE  # 512 samples = 10.6ms latency at 48kHz
            )
            print(f"[AUDIO] ✓ Stream opened successfully")
        except Exception as e:
            print(f"[ERROR] Failed to open audio stream: {e}")
            print(f"[DEBUG] Trying without specifying device index...")
            # Try without specifying device (use default)
            try:
                stream = audio.open(
                    format=pyaudio.paInt16,
                    channels=config.CHANNELS,
                    rate=config.SAMPLE_RATE,
                    input=True,
                    frames_per_buffer=config.CHUNK_SIZE
                )
                print(f"[AUDIO] ✓ Stream opened with default device")
            except Exception as e2:
                print(f"[ERROR] Failed to open stream with default device: {e2}")
                print("[INFO] Falling back to arecord method...")
                # Clean up PyAudio before fallback
                try:
                    if audio:
                        audio.terminate()
                        audio = None
                except Exception as cleanup_error:
                    print(f"[DEBUG] PyAudio cleanup error: {cleanup_error}")
                return record_audio_with_arecord(gpio_manager)
        
        # Initialize recorder - NO amplification (done on server)
        recorder = StreamingAudioRecorder()
        
        # Wait for button to be released first
        while gpio_manager.button.is_pressed:
            time.sleep(0.005)
        
        # Record until button is pressed again - RAW audio only
        while not gpio_manager.button.is_pressed:
            try:
                data = stream.read(config.CHUNK_SIZE, exception_on_overflow=False)
                recorder.add_chunk(data)  # Just store, no processing!
                
                # Progress indicator every second
                if recorder.chunk_count % (config.SAMPLE_RATE // config.CHUNK_SIZE) == 0:
                    seconds = recorder.chunk_count // (config.SAMPLE_RATE // config.CHUNK_SIZE)
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
        sample_width = audio.get_sample_size(pyaudio.paInt16)
        
        # Close audio resources
        if stream is not None:
            stream.stop_stream()
            stream.close()
            stream = None
        if audio is not None:
            audio.terminate()
            audio = None
        
        # Wait for button release
        while gpio_manager.button.is_pressed:
            time.sleep(0.005)
        
        # Get RAW audio data - zero processing time!
        print(f"[AUDIO] Raw audio ready (server will amplify)")
        audio_data = recorder.get_audio_data()
        
        # Save to WAV file
        with wave.open(str(config.RECORDING_FILE), 'wb') as wf:
            wf.setnchannels(config.CHANNELS)
            wf.setsampwidth(sample_width)
            wf.setframerate(config.SAMPLE_RATE)
            wf.writeframes(audio_data)
        
        # Validate saved file
        if not config.RECORDING_FILE.exists():
            print("[ERROR] Recording file was not saved")
            return False
        
        file_size = config.RECORDING_FILE.stat().st_size
        if file_size < 1000:
            print(f"[WARNING] Recording file is very small ({file_size} bytes)")
        
        print(f"[AUDIO] Saved: {config.RECORDING_FILE} ({file_size} bytes)")
        return True
        
    except Exception as e:
        print(f"[ERROR] Recording failed: {e}")
        import traceback
        print(f"[DEBUG] {traceback.format_exc()}")
        return False
        
    finally:
        # Defensive cleanup - ensure resources are freed even on errors
        # This prevents resource leaks that could cause issues on next recording
        if stream is not None:
            try:
                stream.stop_stream()
            except Exception as stop_error:
                print(f"[DEBUG] Stream stop error (ignored): {stop_error}")
            
            try:
                stream.close()
            except Exception as close_error:
                print(f"[DEBUG] Stream close error (ignored): {close_error}")
            
            stream = None
        
        if audio is not None:
            try:
                audio.terminate()
            except Exception as terminate_error:
                print(f"[DEBUG] PyAudio terminate error (ignored): {terminate_error}")
            
            audio = None

