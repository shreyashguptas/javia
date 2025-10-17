#!/usr/bin/env python3
"""
Microphone Testing Script
Comprehensive microphone testing for INMP441
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
RECORD_SECONDS = 5
CHUNK_SIZE = 1024
AUDIO_FORMAT = pyaudio.paInt16

def find_i2s_device():
    """Find I2S input device"""
    print("Searching for I2S microphone device...")
    
    audio = pyaudio.PyAudio()
    device_index = None
    
    for i in range(audio.get_device_count()):
        info = audio.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0:
            print(f"Device {i}: {info['name']}")
            if 'sndrpisimplecar' in info['name'].lower():
                device_index = i
                print(f"✓ Found I2S device: {info['name']}")
                break
    
    audio.terminate()
    
    if device_index is None:
        print("⚠ I2S device not found, will use default device")
    
    return device_index

def test_microphone_recording():
    """Test microphone recording"""
    print("\n" + "=" * 50)
    print("MICROPHONE RECORDING TEST")
    print("=" * 50)
    
    # Find device
    device_index = find_i2s_device()
    
    # Initialize PyAudio
    audio = pyaudio.PyAudio()
    
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
        print("SPEAK INTO THE MICROPHONE NOW!")
        print("=" * 40)
        
        frames = []
        start_time = time.time()
        
        # Record with progress indicator
        for i in range(0, int(SAMPLE_RATE / CHUNK_SIZE * RECORD_SECONDS)):
            data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            frames.append(data)
            
            # Progress indicator
            if i % (SAMPLE_RATE // CHUNK_SIZE) == 0:
                elapsed = time.time() - start_time
                print(f"Recording: {elapsed:.1f}/{RECORD_SECONDS} seconds")
        
        print("=" * 40)
        print("Recording complete!")
        
        # Stop and close
        stream.stop_stream()
        stream.close()
        
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
        print(f"✗ Recording failed: {e}")
        return None
    finally:
        audio.terminate()

def test_audio_levels():
    """Test audio input levels"""
    print("\n" + "=" * 50)
    print("AUDIO LEVEL TEST")
    print("=" * 50)
    
    print("Testing audio levels with arecord...")
    print("Speak into the microphone for 5 seconds...")
    print("You should see level indicators (VU meter)")
    
    try:
        result = subprocess.run([
            'arecord', '-D', 'plughw:0,0', '-c1', '-r16000', 
            '-f', 'S16_LE', '-t', 'wav', '-V', 'mono', 
            '/tmp/level_test.wav'
        ], timeout=5)
        
        if result.returncode == 0:
            print("✓ Level test completed successfully")
            return True
        else:
            print("✗ Level test failed")
            return False
            
    except subprocess.TimeoutExpired:
        print("✓ Level test completed (timeout)")
        return True
    except Exception as e:
        print(f"✗ Level test error: {e}")
        return False

def test_playback(test_file):
    """Test playback of recorded audio"""
    print("\n" + "=" * 50)
    print("PLAYBACK TEST")
    print("=" * 50)
    
    if not test_file or not test_file.exists():
        print("No test file available for playback")
        return False
    
    try:
        print(f"Playing test file: {test_file}")
        print("You should hear your recorded voice...")
        
        # Use aplay for playback
        result = subprocess.run(
            ['aplay', '-D', 'plughw:0,0', str(test_file)],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print("✓ Playback successful!")
            return True
        else:
            print(f"✗ Playback failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"✗ Playback error: {e}")
        return False

def test_different_formats():
    """Test different audio formats"""
    print("\n" + "=" * 50)
    print("FORMAT TESTING")
    print("=" * 50)
    
    formats = [
        ("16kHz, 16-bit", 16000, pyaudio.paInt16),
        ("48kHz, 16-bit", 48000, pyaudio.paInt16),
        ("16kHz, 24-bit", 16000, pyaudio.paInt24),
    ]
    
    results = []
    
    for format_name, sample_rate, audio_format in formats:
        print(f"\nTesting {format_name}...")
        
        try:
            audio = pyaudio.PyAudio()
            
            # Check if format is supported
            if audio.is_format_supported(
                rate=sample_rate,
                input_device=None,
                input_channels=CHANNELS,
                input_format=audio_format
            ):
                print(f"✓ {format_name} supported")
                results.append((format_name, True))
            else:
                print(f"✗ {format_name} not supported")
                results.append((format_name, False))
            
            audio.terminate()
            
        except Exception as e:
            print(f"✗ {format_name} test failed: {e}")
            results.append((format_name, False))
    
    return results

def analyze_audio_file(test_file):
    """Analyze recorded audio file"""
    print("\n" + "=" * 50)
    print("AUDIO FILE ANALYSIS")
    print("=" * 50)
    
    if not test_file or not test_file.exists():
        print("No test file to analyze")
        return
    
    try:
        with wave.open(str(test_file), 'rb') as wf:
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            sample_rate = wf.getframerate()
            frames = wf.getnframes()
            duration = frames / sample_rate
            
            print(f"Channels: {channels}")
            print(f"Sample Width: {sample_width} bytes")
            print(f"Sample Rate: {sample_rate} Hz")
            print(f"Frames: {frames}")
            print(f"Duration: {duration:.2f} seconds")
            
            # Check for silence
            wf.rewind()
            audio_data = wf.readframes(frames)
            
            # Calculate RMS (Root Mean Square) for volume analysis
            import struct
            if sample_width == 2:  # 16-bit
                audio_samples = struct.unpack(f'{frames * channels}h', audio_data)
            elif sample_width == 3:  # 24-bit
                audio_samples = struct.unpack(f'{frames * channels}i', audio_data)
            else:
                print("Unsupported sample width for analysis")
                return
            
            # Calculate RMS
            rms = (sum(x * x for x in audio_samples) / len(audio_samples)) ** 0.5
            print(f"RMS Level: {rms:.2f}")
            
            if rms < 100:
                print("⚠ Audio level is very low - check microphone connection")
            elif rms > 10000:
                print("⚠ Audio level is very high - check for clipping")
            else:
                print("✓ Audio level appears normal")
                
    except Exception as e:
        print(f"✗ Audio analysis failed: {e}")

def main():
    """Main test function"""
    print("=" * 60)
    print("INMP441 MICROPHONE TESTING")
    print("=" * 60)
    
    print("This script will test your INMP441 microphone setup.")
    print("Make sure your microphone is properly connected!")
    print()
    
    # Test 1: Recording
    test_file = test_microphone_recording()
    
    # Test 2: Audio levels
    test_audio_levels()
    
    # Test 3: Playback
    if test_file:
        test_playback(test_file)
    
    # Test 4: Format testing
    format_results = test_different_formats()
    
    # Test 5: Audio analysis
    if test_file:
        analyze_audio_file(test_file)
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    if test_file:
        print("✓ Microphone recording test completed")
    else:
        print("✗ Microphone recording test failed")
    
    print("\nFormat Support:")
    for format_name, supported in format_results:
        status = "✓" if supported else "✗"
        print(f"  {status} {format_name}")
    
    print("\nIf tests failed:")
    print("1. Check hardware connections")
    print("2. Verify /boot/firmware/config.txt settings")
    print("3. Reboot the system")
    print("4. Check system logs")
    print("5. Run: arecord -l (should show voice-assistant device)")

if __name__ == "__main__":
    main()
