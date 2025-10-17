#!/usr/bin/env python3
"""
Audio Testing Utilities for Voice Assistant
"""

import os
import sys
import time
import wave
import subprocess
import pyaudio
from pathlib import Path

# Audio Configuration
SAMPLE_RATE = 16000
CHANNELS = 1
RECORD_SECONDS = 3
CHUNK_SIZE = 1024
AUDIO_FORMAT = pyaudio.paInt16

def list_audio_devices():
    """List all available audio devices"""
    print("=" * 60)
    print("AUDIO DEVICE DETECTION")
    print("=" * 60)
    
    # Test arecord
    print("\n1. Recording Devices (arecord -l):")
    print("-" * 40)
    try:
        result = subprocess.run(['arecord', '-l'], 
                              capture_output=True, text=True, check=True)
        print(result.stdout)
    except Exception as e:
        print(f"Error: {e}")
    
    # Test aplay
    print("\n2. Playback Devices (aplay -l):")
    print("-" * 40)
    try:
        result = subprocess.run(['aplay', '-l'], 
                              capture_output=True, text=True, check=True)
        print(result.stdout)
    except Exception as e:
        print(f"Error: {e}")
    
    # Test PyAudio
    print("\n3. PyAudio Devices:")
    print("-" * 40)
    try:
        p = pyaudio.PyAudio()
        print(f"PyAudio version: {pyaudio.__version__}")
        print(f"Total devices: {p.get_device_count()}")
        
        print("\nInput devices:")
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                print(f"  Device {i}: {info['name']}")
                print(f"    Channels: {info['maxInputChannels']}")
                print(f"    Sample Rate: {info['defaultSampleRate']}")
        
        print("\nOutput devices:")
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info['maxOutputChannels'] > 0:
                print(f"  Device {i}: {info['name']}")
                print(f"    Channels: {info['maxOutputChannels']}")
                print(f"    Sample Rate: {info['defaultSampleRate']}")
        
        p.terminate()
    except Exception as e:
        print(f"Error: {e}")

def test_microphone_recording():
    """Test microphone recording"""
    print("\n" + "=" * 60)
    print("MICROPHONE RECORDING TEST")
    print("=" * 60)
    
    # Find I2S input device
    device_index = None
    audio = pyaudio.PyAudio()
    
    for i in range(audio.get_device_count()):
        info = audio.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0 and 'sndrpisimplecar' in info['name'].lower():
            device_index = i
            print(f"Using I2S device: {info['name']}")
            break
    
    if device_index is None:
        print("I2S device not found, using default device")
        device_index = None
    
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
        
        print(f"Recording for {RECORD_SECONDS} seconds...")
        print("SPEAK NOW!")
        
        frames = []
        for i in range(0, int(SAMPLE_RATE / CHUNK_SIZE * RECORD_SECONDS)):
            data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            frames.append(data)
            
            # Progress indicator
            if i % (SAMPLE_RATE // CHUNK_SIZE) == 0:
                second = i // (SAMPLE_RATE // CHUNK_SIZE)
                print(f"Recording: {second}/{RECORD_SECONDS} seconds")
        
        print("Recording complete!")
        
        # Stop and close
        stream.stop_stream()
        stream.close()
        audio.terminate()
        
        # Save to file
        test_file = Path("/tmp/mic_test.wav")
        with wave.open(str(test_file), 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(audio.get_sample_size(AUDIO_FORMAT))
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b''.join(frames))
        
        file_size = test_file.stat().st_size
        print(f"Test recording saved: {test_file} ({file_size} bytes)")
        
        return test_file
        
    except Exception as e:
        print(f"Recording failed: {e}")
        audio.terminate()
        return None

def test_speaker_playback(test_file):
    """Test speaker playback"""
    print("\n" + "=" * 60)
    print("SPEAKER PLAYBACK TEST")
    print("=" * 60)
    
    if not test_file or not test_file.exists():
        print("No test file available for playback")
        return False
    
    try:
        print(f"Playing test file: {test_file}")
        
        # Use aplay for playback
        result = subprocess.run(
            ['aplay', '-D', 'plughw:0,0', str(test_file)],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print("Playback successful!")
            return True
        else:
            print(f"Playback failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"Playback error: {e}")
        return False

def test_audio_levels():
    """Test audio input levels"""
    print("\n" + "=" * 60)
    print("AUDIO LEVEL TEST")
    print("=" * 60)
    
    print("Testing audio levels with arecord...")
    print("Speak into the microphone for 5 seconds...")
    
    try:
        result = subprocess.run([
            'arecord', '-D', 'plughw:0,0', '-c1', '-r16000', 
            '-f', 'S16_LE', '-t', 'wav', '-V', 'mono', 
            '/tmp/level_test.wav'
        ], timeout=5)
        
        if result.returncode == 0:
            print("Level test completed successfully")
            return True
        else:
            print("Level test failed")
            return False
            
    except subprocess.TimeoutExpired:
        print("Level test completed (timeout)")
        return True
    except Exception as e:
        print(f"Level test error: {e}")
        return False

def test_gpio_button():
    """Test GPIO button functionality"""
    print("\n" + "=" * 60)
    print("GPIO BUTTON TEST")
    print("=" * 60)
    
    try:
        import RPi.GPIO as GPIO
        
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        print("GPIO17 (button) configured")
        print("Current button state:", GPIO.input(17))
        print("Press and hold the button...")
        
        # Monitor button for 10 seconds
        start_time = time.time()
        pressed = False
        
        while time.time() - start_time < 10:
            if GPIO.input(17) == GPIO.LOW:
                if not pressed:
                    print("Button PRESSED!")
                    pressed = True
            else:
                if pressed:
                    print("Button RELEASED!")
                    pressed = False
            time.sleep(0.01)
        
        GPIO.cleanup()
        print("GPIO test completed")
        return True
        
    except Exception as e:
        print(f"GPIO test error: {e}")
        return False

def run_comprehensive_test():
    """Run all tests"""
    print("=" * 60)
    print("COMPREHENSIVE AUDIO TEST")
    print("=" * 60)
    
    # Test 1: List devices
    list_audio_devices()
    
    # Test 2: Record audio
    test_file = test_microphone_recording()
    
    # Test 3: Play audio
    if test_file:
        test_speaker_playback(test_file)
    
    # Test 4: Audio levels
    test_audio_levels()
    
    # Test 5: GPIO button
    test_gpio_button()
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print("All tests completed. Check the output above for any errors.")
    print("If tests failed:")
    print("1. Check hardware connections")
    print("2. Verify /boot/firmware/config.txt settings")
    print("3. Reboot the system")
    print("4. Check system logs")

def main():
    """Main function"""
    if len(sys.argv) > 1:
        test_type = sys.argv[1].lower()
        
        if test_type == "devices":
            list_audio_devices()
        elif test_type == "mic":
            test_microphone_recording()
        elif test_type == "speaker":
            test_file = Path("/tmp/mic_test.wav")
            test_speaker_playback(test_file)
        elif test_type == "levels":
            test_audio_levels()
        elif test_type == "gpio":
            test_gpio_button()
        elif test_type == "all":
            run_comprehensive_test()
        else:
            print("Usage: python3 test_audio.py [devices|mic|speaker|levels|gpio|all]")
    else:
        run_comprehensive_test()

if __name__ == "__main__":
    main()
