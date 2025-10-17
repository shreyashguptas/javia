#!/usr/bin/env python3
"""
Raspberry Pi Zero 2 W Voice Assistant with Groq API
Hardware: INMP441 Mic, MAX98357A Amp, Button
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
from dotenv import load_dotenv

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

# Audio Configuration (can be overridden via environment variables)
SAMPLE_RATE = int(os.getenv('SAMPLE_RATE', '16000'))
CHANNELS = 1
RECORD_SECONDS = int(os.getenv('RECORD_SECONDS', '5'))
CHUNK_SIZE = 1024
AUDIO_FORMAT = pyaudio.paInt16

# File paths
AUDIO_DIR = Path("/tmp/voice_assistant")
RECORDING_FILE = AUDIO_DIR / "recording.wav"
RESPONSE_FILE = AUDIO_DIR / "response.wav"

# ==================== INITIALIZATION ====================

def setup():
    """Initialize the system"""
    print("\n" + "="*50)
    print("Raspberry Pi Voice Assistant Starting...")
    print("="*50 + "\n")
    
    # Create audio directory
    AUDIO_DIR.mkdir(exist_ok=True)
    print(f"[INIT] Audio directory: {AUDIO_DIR}")
    
    # Setup GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    print(f"[INIT] Button configured on GPIO{BUTTON_PIN}")
    
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
    """Wait for button press and release"""
    print("[BUTTON] Waiting for button press...")
    
    # Wait for button press (LOW with pull-up)
    while GPIO.input(BUTTON_PIN) == GPIO.HIGH:
        time.sleep(0.01)
    
    print("[BUTTON] *** BUTTON PRESSED! ***")
    time.sleep(0.05)  # Debounce
    
    # Wait for release
    print("[BUTTON] Waiting for release...")
    while GPIO.input(BUTTON_PIN) == GPIO.LOW:
        time.sleep(0.01)
    
    print("[BUTTON] Released. Starting conversation...\n")

# ==================== AUDIO RECORDING ====================

def record_audio():
    """Record audio from I2S microphone"""
    print("[AUDIO] Setting up recording...")
    
    # Initialize PyAudio
    audio = pyaudio.PyAudio()
    
    # Find I2S input device (usually card 0)
    device_index = None
    for i in range(audio.get_device_count()):
        info = audio.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0 and 'sndrpisimplecar' in info['name'].lower():
            device_index = i
            print(f"[AUDIO] Using device: {info['name']}")
            break
    
    if device_index is None:
        print("[WARNING] I2S device not found, using default")
        device_index = None  # Use default
    
    try:
        # Open stream
        stream = audio.open(
            format=AUDIO_FORMAT,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=CHUNK_SIZE
        )
        
        print(f"[AUDIO] Recording for {RECORD_SECONDS} seconds... SPEAK NOW!")
        print("[AUDIO] " + "="*40)
        
        frames = []
        
        # Record
        for i in range(0, int(SAMPLE_RATE / CHUNK_SIZE * RECORD_SECONDS)):
            data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            frames.append(data)
            
            # Progress indicator
            if i % (SAMPLE_RATE // CHUNK_SIZE) == 0:
                second = i // (SAMPLE_RATE // CHUNK_SIZE)
                print(f"[AUDIO] {second}/{RECORD_SECONDS} seconds")
        
        print("[AUDIO] " + "="*40)
        print("[AUDIO] Recording complete")
        
        # Stop and close
        stream.stop_stream()
        stream.close()
        audio.terminate()
        
        # Save to WAV file
        with wave.open(str(RECORDING_FILE), 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(audio.get_sample_size(AUDIO_FORMAT))
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b''.join(frames))
        
        file_size = RECORDING_FILE.stat().st_size
        print(f"[AUDIO] Saved: {RECORDING_FILE} ({file_size} bytes)")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Recording failed: {e}")
        audio.terminate()
        return False

# ==================== TRANSCRIPTION ====================

def transcribe_audio():
    """Transcribe audio using Groq Whisper API"""
    print("[API] Transcribing audio...")
    
    if not RECORDING_FILE.exists():
        print("[ERROR] Recording file not found")
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
            
            print(f"[API] Sending {RECORDING_FILE.stat().st_size} bytes...")
            
            # Make request
            response = requests.post(
                GROQ_WHISPER_URL,
                headers=headers,
                files=files,
                data=data,
                timeout=30
            )
            
            print(f"[API] Response code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                transcription = result.get('text', '')
                print(f"[SUCCESS] Transcription: \"{transcription}\"")
                return transcription
            else:
                print(f"[ERROR] API error: {response.text}")
                return ""
                
    except Exception as e:
        print(f"[ERROR] Transcription failed: {e}")
        return ""

# ==================== LLM QUERY ====================

def query_llm(user_text):
    """Query Groq LLM"""
    print("[API] Querying LLM...")
    
    try:
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {GROQ_API_KEY}'
        }
        
        payload = {
            'model': LLM_MODEL,
            'messages': [
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': user_text}
            ],
            'max_tokens': 150,
            'temperature': 0.7
        }
        
        print(f"[API] Sending query...")
        
        response = requests.post(
            GROQ_LLM_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        print(f"[API] Response code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            llm_response = result['choices'][0]['message']['content']
            print(f"[SUCCESS] LLM Response: \"{llm_response}\"")
            return llm_response
        else:
            print(f"[ERROR] API error: {response.text}")
            return ""
            
    except Exception as e:
        print(f"[ERROR] LLM query failed: {e}")
        return ""

# ==================== TEXT-TO-SPEECH ====================

def generate_speech(text):
    """Generate speech using Groq TTS API"""
    print("[API] Generating speech...")
    
    try:
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {GROQ_API_KEY}'
        }
        
        payload = {
            'model': TTS_MODEL,
            'input': text,
            'voice': TTS_VOICE,
            'response_format': 'wav'
        }
        
        print(f"[API] Requesting TTS...")
        
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
                        if total_bytes % 50000 == 0:
                            print(f"[API] Downloaded: {total_bytes} bytes")
            
            print(f"[SUCCESS] Audio saved: {RESPONSE_FILE} ({total_bytes} bytes)")
            
            # Validate WAV file
            try:
                with wave.open(str(RESPONSE_FILE), 'rb') as wf:
                    print(f"[PLAYBACK] Channels: {wf.getnchannels()}")
                    print(f"[PLAYBACK] Sample Rate: {wf.getframerate()} Hz")
                    print(f"[PLAYBACK] Sample Width: {wf.getsampwidth()} bytes")
                    return True
            except Exception as e:
                print(f"[ERROR] Invalid WAV file: {e}")
                return False
        else:
            print(f"[ERROR] API error: {response.text}")
            return False
            
    except Exception as e:
        print(f"[ERROR] TTS generation failed: {e}")
        return False

# ==================== AUDIO PLAYBACK ====================

def play_audio():
    """Play audio through I2S amplifier"""
    print("[PLAYBACK] Playing response...")
    
    if not RESPONSE_FILE.exists():
        print("[ERROR] Response file not found")
        return
    
    try:
        # Use aplay for I2S playback (most reliable on Pi)
        result = subprocess.run(
            ['aplay', '-D', 'plughw:0,0', str(RESPONSE_FILE)],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print("[PLAYBACK] Complete!")
        else:
            print(f"[ERROR] Playback failed: {result.stderr}")
            
    except Exception as e:
        print(f"[ERROR] Playback error: {e}")

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
            
            # Step 5: Play
            print("\n[PLAYBACK] Playing response...")
            play_audio()
            
            print("\n[COMPLETE] Conversation complete!")
            print("="*50 + "\n")
            
            time.sleep(1)  # Debounce
            
    except KeyboardInterrupt:
        print("\n\n[EXIT] Shutting down...")
    finally:
        GPIO.cleanup()
        print("[EXIT] GPIO cleanup complete")

if __name__ == "__main__":
    main()
