#!/usr/bin/env python3
"""
Raspberry Pi Voice Assistant Client
Records audio, sends to server for processing, plays response
"""

import os
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

# File paths
AUDIO_DIR = Path(os.path.expanduser("~/javia/audio"))
RECORDING_FILE = AUDIO_DIR / "recording.wav"
RESPONSE_FILE = AUDIO_DIR / "response.wav"

# ==================== INITIALIZATION ====================

def setup():
    """Initialize the system"""
    print("\n" + "="*50)
    print("Raspberry Pi Voice Assistant Client Starting...")
    print("="*50 + "\n")
    
    # Create audio directory
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[INIT] Audio directory: {AUDIO_DIR}")
    
    # Clean up old recordings
    try:
        for old_file in AUDIO_DIR.glob("*.wav"):
            old_file.unlink()
        print(f"[INIT] Cleaned up old audio files")
    except Exception as e:
        print(f"[INIT] Could not clean old files: {e}")
    
    # Setup GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    print(f"[INIT] Button configured on GPIO{BUTTON_PIN}")
    
    # Setup amplifier shutdown pin
    GPIO.setup(AMPLIFIER_SD_PIN, GPIO.OUT)
    GPIO.output(AMPLIFIER_SD_PIN, GPIO.LOW)  # Start with amp muted
    print(f"[INIT] Amplifier SD pin configured on GPIO{AMPLIFIER_SD_PIN}")
    
    # Check API key
    if CLIENT_API_KEY == "YOUR_API_KEY_HERE":
        print("\n[ERROR] CLIENT API KEY NOT SET!")
        print("[ERROR] Please set your API key in the .env file.")
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
    
    print("\n[READY] System ready! Press button to start...\n")

# ==================== BUTTON HANDLING ====================

def wait_for_button_press():
    """Wait for button press"""
    print("[BUTTON] Waiting for button press to start recording...")
    
    while GPIO.input(BUTTON_PIN) == GPIO.HIGH:
        time.sleep(0.01)
    
    print("[BUTTON] *** BUTTON PRESSED! Starting recording... ***")
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
    time.sleep(0.05)  # Debounce
    
    # Wait for release
    while GPIO.input(BUTTON_PIN) == GPIO.LOW:
        time.sleep(0.01)
    
    print("[BUTTON] Released. Processing audio...\n")

# ==================== AUDIO RECORDING ====================

def amplify_audio(audio_data, gain=2.0):
    """Amplify audio data by the specified gain factor"""
    audio_array = np.frombuffer(audio_data, dtype=np.int16)
    amplified = audio_array * gain
    amplified = np.clip(amplified, -32768, 32767)
    amplified = amplified.astype(np.int16)
    return amplified.tobytes()

def record_audio():
    """Record audio from I2S microphone until button is pressed again"""
    print("[AUDIO] Setting up recording...")
    
    audio = None
    stream = None
    
    try:
        audio = pyaudio.PyAudio()
        
        # Find I2S input device
        device_index = None
        for i in range(audio.get_device_count()):
            try:
                info = audio.get_device_info_by_index(i)
                if info['maxInputChannels'] > 0 and ('googlevoicehat' in info['name'].lower() or 
                                                      'voicehat' in info['name'].lower() or
                                                      'sndrpigooglevoi' in info['name'].lower()):
                    device_index = i
                    print(f"[AUDIO] Using device: {info['name']}")
                    break
            except Exception as e:
                continue
        
        if device_index is None:
            print("[WARNING] Google Voice HAT not found, using default input device")
            device_index = None
        
        # Validate device
        if device_index is not None:
            try:
                device_info = audio.get_device_info_by_index(device_index)
                if device_info['maxInputChannels'] < 1:
                    print("[WARNING] Selected device has no input channels, using default")
                    device_index = None
            except Exception as e:
                print(f"[WARNING] Could not validate device: {e}, using default")
                device_index = None
        
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
        
        # Validate recording length
        if len(frames) == 0:
            print("[ERROR] No audio data recorded")
            return False
        
        # Calculate total recording time
        total_seconds = chunks_recorded / (SAMPLE_RATE / CHUNK_SIZE)
        print(f"[AUDIO] Recording complete ({total_seconds:.1f} seconds)")
        
        # Get sample width before terminating
        sample_width = audio.get_sample_size(AUDIO_FORMAT)
        
        # Amplify audio if gain is not 1.0
        if MICROPHONE_GAIN != 1.0:
            print(f"[AUDIO] Applying gain of {MICROPHONE_GAIN}x...")
            amplified_frames = []
            for frame in frames:
                try:
                    amplified_frames.append(amplify_audio(frame, MICROPHONE_GAIN))
                except Exception as e:
                    print(f"[WARNING] Could not amplify chunk: {e}")
                    amplified_frames.append(frame)
            frames = amplified_frames
        
        # Save to WAV file
        with wave.open(str(RECORDING_FILE), 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(sample_width)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b''.join(frames))
        
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
            print(f"[WARNING] Audio too short for fade effect")
            return
        
        fade_samples = fade_frames * channels
        
        print(f"[DEBUG] Applying {fade_duration_ms}ms fade ({fade_frames} frames)")
        
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
                beginning_array = np.frombuffer(beginning_data, dtype=dtype).copy()
                
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
                ending_array = np.frombuffer(ending_data, dtype=dtype).copy()
                
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

