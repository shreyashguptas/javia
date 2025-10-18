#!/usr/bin/env python3
"""
Test script for Voice Assistant Client
Tests audio recording, server communication, and playback
NOTE: This is a non-GPIO test version for development/testing
"""

import os
import sys
import wave
import requests
import numpy as np
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
SERVER_URL = os.getenv('SERVER_URL', 'http://localhost:8000')
CLIENT_API_KEY = os.getenv('CLIENT_API_KEY', 'YOUR_API_KEY_HERE')
AUDIO_DIR = Path(os.path.expanduser("~/voice_assistant/audio"))

def test_audio_directory():
    """Test that audio directory can be created"""
    print("\n" + "="*50)
    print("Test 1: Audio Directory Setup")
    print("="*50)
    
    try:
        AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        print(f"✓ Audio directory created: {AUDIO_DIR}")
        
        # Test write permissions
        test_file = AUDIO_DIR / "test.txt"
        test_file.write_text("test")
        test_file.unlink()
        print(f"✓ Write permissions verified")
        
        return True
    except Exception as e:
        print(f"✗ Audio directory test failed: {e}")
        return False

def test_server_connection():
    """Test connection to server"""
    print("\n" + "="*50)
    print("Test 2: Server Connection")
    print("="*50)
    
    print(f"Server URL: {SERVER_URL}")
    print(f"API Key: {CLIENT_API_KEY[:10]}..." if len(CLIENT_API_KEY) > 10 else f"API Key: {CLIENT_API_KEY}")
    
    if CLIENT_API_KEY == "YOUR_API_KEY_HERE":
        print("✗ API key not configured in .env file")
        return False
    
    try:
        response = requests.get(f"{SERVER_URL}/health", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Server is reachable")
            print(f"  Status: {data.get('status')}")
            print(f"  Version: {data.get('version')}")
            return True
        else:
            print(f"✗ Server returned {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"✗ Cannot connect to server at {SERVER_URL}")
        print("  Make sure the server is running and accessible")
        return False
    except Exception as e:
        print(f"✗ Connection test failed: {e}")
        return False

def create_test_audio(filepath: Path, duration_seconds: float = 2.0, sample_rate: int = 48000):
    """Create a test audio file"""
    print(f"\nCreating test audio: {filepath}")
    
    # Generate sine wave
    frequency = 440
    samples = int(duration_seconds * sample_rate)
    t = np.linspace(0, duration_seconds, samples, False)
    audio_data = np.sin(2 * np.pi * frequency * t)
    audio_data = (audio_data * 32767).astype(np.int16)
    
    # Save as WAV
    with wave.open(str(filepath), 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data.tobytes())
    
    print(f"✓ Created: {filepath.stat().st_size} bytes")
    return filepath

def test_server_processing():
    """Test sending audio to server and receiving response"""
    print("\n" + "="*50)
    print("Test 3: Server Processing")
    print("="*50)
    
    # Create test audio
    recording_file = AUDIO_DIR / "test_recording.wav"
    response_file = AUDIO_DIR / "test_response.wav"
    
    try:
        create_test_audio(recording_file)
    except Exception as e:
        print(f"✗ Failed to create test audio: {e}")
        return False
    
    # Send to server
    print("\nSending to server for processing...")
    try:
        headers = {'X-API-Key': CLIENT_API_KEY}
        
        with open(recording_file, 'rb') as f:
            files = {'audio': ('recording.wav', f, 'audio/wav')}
            data = {'session_id': 'test_client_session'}
            
            response = requests.post(
                f"{SERVER_URL}/api/v1/process",
                headers=headers,
                files=files,
                data=data,
                timeout=120,
                stream=True
            )
            
            print(f"Response code: {response.status_code}")
            
            if response.status_code == 200:
                # Get metadata
                transcription = response.headers.get('X-Transcription', '')
                llm_response = response.headers.get('X-LLM-Response', '')
                
                print(f"✓ Processing successful")
                print(f"  Transcription: {transcription[:100] if transcription else '(empty - expected for test audio)'}")
                print(f"  LLM Response: {llm_response[:100] if llm_response else '(none)'}")
                
                # Save response audio
                total_bytes = 0
                with open(response_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            total_bytes += len(chunk)
                
                print(f"  Response audio: {total_bytes} bytes")
                print(f"  Saved to: {response_file}")
                
                # Clean up
                recording_file.unlink()
                
                return True
            elif response.status_code == 401:
                print(f"✗ Unauthorized - check API key")
                return False
            elif response.status_code == 403:
                print(f"✗ Forbidden - API key invalid")
                return False
            else:
                print(f"✗ Processing failed: {response.status_code}")
                print(f"  Response: {response.text[:200]}")
                return False
                
    except requests.exceptions.Timeout:
        print(f"✗ Request timeout")
        return False
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False
    finally:
        # Cleanup
        if recording_file.exists():
            recording_file.unlink()

def test_audio_validation():
    """Test that response audio is valid"""
    print("\n" + "="*50)
    print("Test 4: Audio Validation")
    print("="*50)
    
    response_file = AUDIO_DIR / "test_response.wav"
    
    if not response_file.exists():
        print("✗ No response audio file found (previous test may have failed)")
        return False
    
    try:
        with wave.open(str(response_file), 'rb') as wf:
            channels = wf.getnchannels()
            sample_rate = wf.getframerate()
            sample_width = wf.getsampwidth()
            frames = wf.getnframes()
            
            print(f"✓ Valid WAV file")
            print(f"  Channels: {channels}")
            print(f"  Sample Rate: {sample_rate} Hz")
            print(f"  Sample Width: {sample_width} bytes")
            print(f"  Frames: {frames}")
            print(f"  Duration: {frames / sample_rate:.2f} seconds")
            
            if frames > 0:
                print(f"✓ Audio file contains data")
                return True
            else:
                print(f"✗ Audio file is empty")
                return False
                
    except Exception as e:
        print(f"✗ Invalid audio file: {e}")
        return False
    finally:
        # Cleanup
        if response_file.exists():
            response_file.unlink()

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("Voice Assistant Client Test Suite")
    print("="*60)
    print("\nNOTE: This is a non-GPIO test for development/testing")
    print("      Run the actual client.py on Raspberry Pi for full testing")
    
    results = []
    
    # Run tests
    results.append(("Audio Directory", test_audio_directory()))
    results.append(("Server Connection", test_server_connection()))
    
    # Only run processing test if previous tests passed
    if all(r[1] for r in results):
        results.append(("Server Processing", test_server_processing()))
        results.append(("Audio Validation", test_audio_validation()))
    else:
        print("\n⚠ Skipping remaining tests due to previous failures")
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    print(f"\nResults: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("\n✓ All tests passed!")
        return 0
    else:
        print("\n✗ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())

