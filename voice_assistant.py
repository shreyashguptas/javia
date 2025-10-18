#!/usr/bin/env python3
"""
Raspberry Pi Zero 2 W Voice Assistant with Groq API
Hardware: Google Voice HAT (microphone + speaker)
"""

import os
import sys
import time
import wave
import requests
import json
import subprocess
from pathlib import Path
import RPi.GPIO as GPIO
import pyaudio
import numpy as np
from dotenv import load_dotenv

# Suppress ALSA warnings - these are harmless but cluttering
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
    pass  # If we can't suppress, that's okay

# Load environment variables from .env file
load_dotenv()

# ==================== CONFIGURATION ====================

# WiFi Credentials (configured via raspi-config)
# No need to set here - Pi should already be connected

# Groq API Configuration
GROQ_API_KEY = os.getenv('GROQ_API_KEY', 'YOUR_GROQ_API_KEY_HERE')
GROQ_WHISPER_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_LLM_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_TTS_URL = "https://api.groq.com/openai/v1/audio/speech"

# Model Names (can be overridden via environment variables)
WHISPER_MODEL = os.getenv('WHISPER_MODEL', 'whisper-large-v3-turbo')
LLM_MODEL = os.getenv('LLM_MODEL', 'openai/gpt-oss-20b')
TTS_MODEL = os.getenv('TTS_MODEL', 'playai-tts')
TTS_VOICE = os.getenv('TTS_VOICE', 'Chip-PlayAI')

# System Prompt
SYSTEM_PROMPT = "You are a helpful voice assistant that gives concise, factual answers. Keep responses brief and conversational, under 3 sentences."

# GPIO Configuration (can be overridden via environment variables)
BUTTON_PIN = int(os.getenv('BUTTON_PIN', '17'))  # BCM GPIO17 (Physical Pin 11)
AMPLIFIER_SD_PIN = int(os.getenv('AMPLIFIER_SD_PIN', '27'))  # BCM GPIO27 (Physical Pin 13) - Controls amplifier shutdown

# Audio Configuration (can be overridden via environment variables)
# Note: Google Voice HAT requires 48000 Hz sample rate
SAMPLE_RATE = int(os.getenv('SAMPLE_RATE', '48000'))
CHANNELS = 1
RECORD_SECONDS = int(os.getenv('RECORD_SECONDS', '5'))
CHUNK_SIZE = 1024
AUDIO_FORMAT = pyaudio.paInt16
MICROPHONE_GAIN = float(os.getenv('MICROPHONE_GAIN', '2.0'))  # Amplification factor (1.0 = no change, 2.0 = double volume)

# File paths
AUDIO_DIR = Path(os.path.expanduser("~/voice_assistant/audio"))
RECORDING_FILE = AUDIO_DIR / "recording.wav"
RESPONSE_FILE = AUDIO_DIR / "response.wav"

# ==================== INITIALIZATION ====================

def setup():
    """Initialize the system"""
    print("\n" + "="*50)
    print("Raspberry Pi Voice Assistant Starting...")
    print("="*50 + "\n")
    
    # Create audio directory
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[INIT] Audio directory: {AUDIO_DIR}")
    
    # Clean up old recordings to prevent disk space issues
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
    
    # Setup amplifier shutdown pin (keeps amp powered, controls muting)
    GPIO.setup(AMPLIFIER_SD_PIN, GPIO.OUT)
    GPIO.output(AMPLIFIER_SD_PIN, GPIO.LOW)  # Start with amp muted
    print(f"[INIT] Amplifier SD pin configured on GPIO{AMPLIFIER_SD_PIN}")
    
    # Check API key
    if GROQ_API_KEY == "YOUR_GROQ_API_KEY_HERE":
        print("\n[ERROR] GROQ API KEY NOT SET!")
        print("[ERROR] Please set your API key in the code.")
        sys.exit(1)
    
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
    
    # Wait for button press (LOW with pull-up)
    while GPIO.input(BUTTON_PIN) == GPIO.HIGH:
        time.sleep(0.01)
    
    print("[BUTTON] *** BUTTON PRESSED! Starting recording... ***")
    time.sleep(0.05)  # Debounce

def wait_for_button_release():
    """Wait for button press again to stop recording"""
    print("[BUTTON] Press button again to stop recording...")
    
    # Wait for button to be released first (if still pressed)
    while GPIO.input(BUTTON_PIN) == GPIO.LOW:
        time.sleep(0.01)
    
    # Now wait for button press again (to stop)
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
    """
    Amplify audio data by the specified gain factor
    
    Args:
        audio_data: Raw audio bytes
        gain: Amplification factor (1.0 = no change, 2.0 = double volume)
    
    Returns:
        Amplified audio bytes
    """
    # Convert bytes to numpy array
    audio_array = np.frombuffer(audio_data, dtype=np.int16)
    
    # Apply gain
    amplified = audio_array * gain
    
    # Clip to prevent overflow
    amplified = np.clip(amplified, -32768, 32767)
    
    # Convert back to int16
    amplified = amplified.astype(np.int16)
    
    return amplified.tobytes()

def record_audio():
    """Record audio from I2S microphone until button is pressed again"""
    print("[AUDIO] Setting up recording...")
    
    audio = None
    stream = None
    
    try:
        # Initialize PyAudio
        audio = pyaudio.PyAudio()
        
        # Find I2S input device (Google Voice HAT)
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
                continue  # Skip problematic devices
        
        if device_index is None:
            print("[WARNING] Google Voice HAT not found, using default input device")
            device_index = None  # Use default
        
        # Validate device before opening stream
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
                continue  # Try to continue recording despite errors
        
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
                    amplified_frames.append(frame)  # Use original if amplification fails
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
        if file_size < 1000:  # Less than 1KB is suspiciously small
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

# ==================== TRANSCRIPTION ====================

def transcribe_audio():
    """Transcribe audio using Groq Whisper API"""
    print("[API] Transcribing audio...")
    
    if not RECORDING_FILE.exists():
        print("[ERROR] Recording file not found")
        return ""
    
    # Validate file size
    file_size = RECORDING_FILE.stat().st_size
    if file_size < 100:
        print(f"[ERROR] Recording file too small ({file_size} bytes) - likely empty")
        return ""
    
    if file_size > 25 * 1024 * 1024:  # 25MB limit for Groq API
        print(f"[ERROR] Recording file too large ({file_size} bytes) - exceeds 25MB limit")
        return ""
    
    try:
        # Open file
        with open(RECORDING_FILE, 'rb') as audio_file:
            files = {
                'file': ('audio.wav', audio_file, 'audio/wav')
            }
            data = {
                'model': WHISPER_MODEL
            }
            headers = {
                'Authorization': f'Bearer {GROQ_API_KEY}'
            }
            
            print(f"[API] Sending {file_size} bytes...")
            
            # Make request with retries
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    response = requests.post(
                        GROQ_WHISPER_URL,
                        headers=headers,
                        files=files,
                        data=data,
                        timeout=60  # Increased timeout for larger files
                    )
                    
                    print(f"[API] Response code: {response.status_code}")
                    
                    if response.status_code == 200:
                        result = response.json()
                        transcription = result.get('text', '').strip()
                        
                        if not transcription:
                            print("[WARNING] Transcription returned empty text")
                            return ""
                        
                        print(f"[SUCCESS] Transcription: \"{transcription}\"")
                        return transcription
                    elif response.status_code == 429:
                        print("[WARNING] Rate limited, waiting before retry...")
                        time.sleep(2)
                        continue
                    else:
                        print(f"[ERROR] API error {response.status_code}: {response.text}")
                        return ""
                        
                except requests.exceptions.Timeout:
                    if attempt < max_retries - 1:
                        print(f"[WARNING] Request timeout, retrying... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(1)
                        continue
                    else:
                        print("[ERROR] Request timeout after retries")
                        return ""
                        
                except requests.exceptions.ConnectionError as e:
                    print(f"[ERROR] Connection error: {e}")
                    return ""
                
            print("[ERROR] Failed after all retry attempts")
            return ""
                
    except FileNotFoundError:
        print(f"[ERROR] Recording file not found: {RECORDING_FILE}")
        return ""
    except Exception as e:
        print(f"[ERROR] Transcription failed: {e}")
        import traceback
        print(f"[DEBUG] {traceback.format_exc()}")
        return ""

# ==================== LLM QUERY ====================

def query_llm(user_text):
    """Query Groq LLM"""
    print("[API] Querying LLM...")
    
    if not user_text or not user_text.strip():
        print("[ERROR] Cannot query LLM with empty text")
        return ""
    
    try:
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {GROQ_API_KEY}'
        }
        
        payload = {
            'model': LLM_MODEL,
            'messages': [
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': user_text.strip()}
            ],
            'max_tokens': 150,
            'temperature': 0.7
        }
        
        print(f"[API] Sending query...")
        
        # Make request with retries
        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    GROQ_LLM_URL,
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                
                print(f"[API] Response code: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Validate response structure
                    if 'choices' not in result or len(result['choices']) == 0:
                        print(f"[ERROR] Invalid LLM response structure")
                        return ""
                    
                    llm_response = result['choices'][0]['message']['content']
                    
                    # Check if response is empty or just whitespace
                    if not llm_response or llm_response.strip() == "":
                        print(f"[ERROR] LLM returned empty response")
                        return ""
                    
                    print(f"[SUCCESS] LLM Response: \"{llm_response}\"")
                    return llm_response.strip()
                    
                elif response.status_code == 429:
                    print("[WARNING] Rate limited, waiting before retry...")
                    time.sleep(2)
                    continue
                else:
                    print(f"[ERROR] API error {response.status_code}: {response.text}")
                    return ""
                    
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    print(f"[WARNING] Request timeout, retrying... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(1)
                    continue
                else:
                    print("[ERROR] Request timeout after retries")
                    return ""
                    
            except requests.exceptions.ConnectionError as e:
                print(f"[ERROR] Connection error: {e}")
                return ""
        
        print("[ERROR] Failed after all retry attempts")
        return ""
            
    except KeyError as e:
        print(f"[ERROR] Missing expected field in API response: {e}")
        return ""
    except Exception as e:
        print(f"[ERROR] LLM query failed: {e}")
        import traceback
        print(f"[DEBUG] {traceback.format_exc()}")
        return ""

# ==================== TEXT-TO-SPEECH ====================

def generate_speech(text):
    """Generate speech using Groq TTS API"""
    print("[API] Generating speech...")
    
    if not text or not text.strip():
        print("[ERROR] Cannot generate speech from empty text")
        return False
    
    # Validate text length
    if len(text) > 4096:
        print(f"[WARNING] Text too long ({len(text)} chars), truncating to 4096")
        text = text[:4096]
    
    try:
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {GROQ_API_KEY}'
        }
        
        payload = {
            'model': TTS_MODEL,
            'input': text.strip(),
            'voice': TTS_VOICE,
            'response_format': 'wav'
        }
        
        print(f"[API] Requesting TTS...")
        
        # Make request with retries
        max_retries = 2
        for attempt in range(max_retries):
            try:
                # Stream response to file
                response = requests.post(
                    GROQ_TTS_URL,
                    headers=headers,
                    json=payload,
                    timeout=60,
                    stream=True
                )
                
                print(f"[API] Response code: {response.status_code}")
                
                if response.status_code == 200:
                    # Save to file
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
                    
                    # Validate WAV file
                    try:
                        with wave.open(str(RESPONSE_FILE), 'rb') as wf:
                            channels = wf.getnchannels()
                            sample_rate = wf.getframerate()
                            sample_width = wf.getsampwidth()
                            frames = wf.getnframes()
                            
                            if frames == 0:
                                print("[ERROR] WAV file has no audio frames")
                                return False
                            
                            print(f"[PLAYBACK] Channels: {channels}")
                            print(f"[PLAYBACK] Sample Rate: {sample_rate} Hz")
                            print(f"[PLAYBACK] Sample Width: {sample_width} bytes")
                            return True
                    except Exception as e:
                        print(f"[ERROR] Invalid WAV file: {e}")
                        return False
                        
                elif response.status_code == 429:
                    print("[WARNING] Rate limited, waiting before retry...")
                    time.sleep(2)
                    continue
                else:
                    print(f"[ERROR] API error {response.status_code}: {response.text}")
                    return False
                    
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    print(f"[WARNING] Request timeout, retrying... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(1)
                    continue
                else:
                    print("[ERROR] Request timeout after retries")
                    return False
                    
            except requests.exceptions.ConnectionError as e:
                print(f"[ERROR] Connection error: {e}")
                return False
        
        print("[ERROR] Failed after all retry attempts")
        return False
            
    except Exception as e:
        print(f"[ERROR] TTS generation failed: {e}")
        import traceback
        print(f"[DEBUG] {traceback.format_exc()}")
        return False

# ==================== AUDIO PLAYBACK ====================

def add_silence_padding(wav_file, padding_ms=150):
    """
    Add silence padding to beginning and end of WAV file to prevent clicks/pops
    Memory-efficient approach using temporary file
    
    Args:
        wav_file: Path to WAV file
        padding_ms: Milliseconds of silence to add (default 150ms)
    """
    try:
        import tempfile
        
        # Create temporary file for padded audio
        temp_file = wav_file.parent / f"{wav_file.stem}_temp.wav"
        
        # Read original file parameters
        with wave.open(str(wav_file), 'rb') as wf:
            params = wf.getparams()
            channels = params.nchannels
            sampwidth = params.sampwidth
            framerate = params.framerate
            
            # Determine dtype based on sample width
            if sampwidth == 1:
                dtype = np.uint8
            elif sampwidth == 2:
                dtype = np.int16
            elif sampwidth == 4:
                dtype = np.int32
            else:
                print(f"[WARNING] Unsupported sample width: {sampwidth} bytes")
                return
            
            # Calculate padding length (samples = time * sample_rate * channels)
            padding_samples = int((padding_ms / 1000.0) * framerate * channels)
            silence = np.zeros(padding_samples, dtype=dtype)
            
            # Write to temporary file with padding
            with wave.open(str(temp_file), 'wb') as wf_out:
                wf_out.setparams(params)
                
                # Write leading silence
                wf_out.writeframes(silence.tobytes())
                
                # Copy original audio in chunks to avoid memory issues
                chunk_size = 8192
                while True:
                    frames = wf.readframes(chunk_size)
                    if not frames:
                        break
                    wf_out.writeframes(frames)
                
                # Write trailing silence
                wf_out.writeframes(silence.tobytes())
        
        # Replace original file with padded version
        temp_file.replace(wav_file)
        
        print(f"[AUDIO] Added {padding_ms}ms silence padding ({framerate}Hz, {channels}ch)")
        
    except Exception as e:
        print(f"[WARNING] Could not add silence padding: {e}")
        # Clean up temp file if it exists
        if 'temp_file' in locals() and temp_file.exists():
            temp_file.unlink()

def play_audio():
    """
    Play audio through I2S amplifier with SD pin control
    Returns True if playback completed normally, False if interrupted by button press
    """
    if not RESPONSE_FILE.exists():
        print("[ERROR] Response file not found")
        return False
    
    process = None
    try:
        # Add silence padding FIRST (before enabling amp)
        print("[PLAYBACK] Preparing audio...")
        add_silence_padding(RESPONSE_FILE, padding_ms=150)
        
        # Enable amplifier (unmute) - give it time to stabilize
        GPIO.output(AMPLIFIER_SD_PIN, GPIO.HIGH)
        time.sleep(0.200)  # 200ms for amplifier to fully power on and stabilize
        
        # Use aplay for I2S playback (most reliable on Pi)
        print("[PLAYBACK] Playing response... (Press button to interrupt)")
        process = subprocess.Popen(
            ['aplay', '-D', 'plughw:0,0', str(RESPONSE_FILE)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Monitor button during playback
        interrupted = False
        while process.poll() is None:  # While process is still running
            if GPIO.input(BUTTON_PIN) == GPIO.LOW:  # Button pressed
                print("\n[INTERRUPT] *** BUTTON PRESSED! Stopping playback... ***")
                process.terminate()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                interrupted = True
                break
            time.sleep(0.01)  # Check every 10ms
        
        # Wait for audio to fully complete before muting
        time.sleep(0.200)  # 200ms for audio to fully finish
        
        # Disable amplifier (mute) after playback
        GPIO.output(AMPLIFIER_SD_PIN, GPIO.LOW)
        
        if interrupted:
            print("[INTERRUPT] Playback cancelled!")
            # Wait for button release
            while GPIO.input(BUTTON_PIN) == GPIO.LOW:
                time.sleep(0.01)
            return False
        else:
            print("[PLAYBACK] Complete!")
            return True
            
    except Exception as e:
        print(f"[ERROR] Playback error: {e}")
        # Make sure amp is muted on error
        GPIO.output(AMPLIFIER_SD_PIN, GPIO.LOW)
        # Clean up process if it exists
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
            print("[STEP 1/4] Recording audio...")
            if not record_audio():
                print("[ERROR] Recording failed. Restarting...")
                time.sleep(2)
                continue
            
            # Step 2: Transcribe
            print("\n[STEP 2/4] Transcribing...")
            transcription = transcribe_audio()
            if not transcription:
                print("[ERROR] Transcription failed. Restarting...")
                time.sleep(2)
                continue
            
            # Step 3: Query LLM
            print("\n[STEP 3/4] Querying LLM...")
            response = query_llm(transcription)
            if not response:
                print("[ERROR] LLM query failed. Restarting...")
                time.sleep(2)
                continue
            
            # Step 4: Generate Speech
            print("\n[STEP 4/4] Generating speech...")
            if not generate_speech(response):
                print("[ERROR] TTS failed. Restarting...")
                time.sleep(2)
                continue
            
            # Step 5: Play (with interrupt support)
            print("\n[STEP 5/5] Playing response...")
            playback_completed = play_audio()
            
            if playback_completed:
                print("\n[COMPLETE] Conversation complete!")
                print("="*50 + "\n")
                time.sleep(1)  # Debounce
            else:
                # Playback was interrupted
                print("\n[INTERRUPT] Waiting for next button press to start new recording...")
                print("="*50 + "\n")
                time.sleep(0.5)  # Brief pause for clarity
                # Loop will continue and wait_for_button_press() will be called
            
    except KeyboardInterrupt:
        print("\n\n[EXIT] Shutting down...")
    finally:
        GPIO.cleanup()
        print("[EXIT] GPIO cleanup complete")

if __name__ == "__main__":
    main()
