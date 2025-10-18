#!/usr/bin/env python3
"""
Test script for Voice Assistant Server
Tests health check, authentication, and audio processing
"""

import os
import sys
import requests
import wave
import numpy as np
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
SERVER_URL = os.getenv('SERVER_URL', 'http://localhost:8000')
API_KEY = os.getenv('SERVER_API_KEY', 'test_key')

def create_test_audio(filepath: Path, duration_seconds: float = 2.0, sample_rate: int = 48000):
    """Create a test audio file with a sine wave"""
    print(f"Creating test audio file: {filepath}")
    
    # Generate sine wave at 440 Hz (A4 note)
    frequency = 440
    samples = int(duration_seconds * sample_rate)
    t = np.linspace(0, duration_seconds, samples, False)
    audio_data = np.sin(2 * np.pi * frequency * t)
    
    # Convert to 16-bit PCM
    audio_data = (audio_data * 32767).astype(np.int16)
    
    # Save as WAV
    with wave.open(str(filepath), 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data.tobytes())
    
    print(f"✓ Created test audio: {filepath.stat().st_size} bytes")
    return filepath

def test_health_check():
    """Test the health check endpoint"""
    print("\n" + "="*50)
    print("Test 1: Health Check")
    print("="*50)
    
    try:
        response = requests.get(f"{SERVER_URL}/health", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Health check passed")
            print(f"  Status: {data.get('status')}")
            print(f"  Version: {data.get('version')}")
            return True
        else:
            print(f"✗ Health check failed: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"✗ Connection failed - is the server running at {SERVER_URL}?")
        return False
    except Exception as e:
        print(f"✗ Health check error: {e}")
        return False

def test_authentication():
    """Test API key authentication"""
    print("\n" + "="*50)
    print("Test 2: Authentication")
    print("="*50)
    
    # Test without API key
    print("\n[2.1] Testing without API key...")
    try:
        response = requests.get(f"{SERVER_URL}/api/v1/process", timeout=5)
        if response.status_code == 401:
            print("✓ Correctly rejected request without API key")
        else:
            print(f"✗ Expected 401, got {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Test error: {e}")
        return False
    
    # Test with invalid API key
    print("\n[2.2] Testing with invalid API key...")
    try:
        headers = {'X-API-Key': 'invalid_key_12345'}
        response = requests.get(f"{SERVER_URL}/api/v1/process", headers=headers, timeout=5)
        if response.status_code == 403:
            print("✓ Correctly rejected request with invalid API key")
        else:
            print(f"✗ Expected 403, got {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Test error: {e}")
        return False
    
    # Test with valid API key
    print("\n[2.3] Testing with valid API key...")
    try:
        headers = {'X-API-Key': API_KEY}
        # Note: This will fail because we're not sending audio, but auth should pass
        response = requests.post(f"{SERVER_URL}/api/v1/process", headers=headers, timeout=5)
        # 422 = validation error (missing audio file), which means auth passed
        if response.status_code == 422:
            print("✓ Authentication successful (validation error expected)")
            return True
        elif response.status_code == 401 or response.status_code == 403:
            print(f"✗ Authentication failed with valid key")
            return False
        else:
            print(f"✓ Authentication passed (got {response.status_code})")
            return True
    except Exception as e:
        print(f"✗ Test error: {e}")
        return False

def test_audio_processing():
    """Test audio processing endpoint"""
    print("\n" + "="*50)
    print("Test 3: Audio Processing")
    print("="*50)
    
    # Create test audio file
    test_audio_path = Path("/tmp/test_audio.wav")
    try:
        create_test_audio(test_audio_path)
    except Exception as e:
        print(f"✗ Failed to create test audio: {e}")
        return False
    
    # Send to server
    print("\nSending test audio to server...")
    print("NOTE: This test requires valid GROQ_API_KEY in server .env")
    print("The audio is synthetic, so transcription will likely be empty or noise.")
    
    try:
        headers = {'X-API-Key': API_KEY}
        
        with open(test_audio_path, 'rb') as f:
            files = {'audio': ('test.wav', f, 'audio/wav')}
            data = {'session_id': 'test_session_123'}
            
            print(f"Uploading {test_audio_path.stat().st_size} bytes...")
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
                # Get metadata from headers
                transcription = response.headers.get('X-Transcription', '')
                llm_response = response.headers.get('X-LLM-Response', '')
                
                print(f"✓ Audio processing successful")
                print(f"  Transcription: {transcription[:100] if transcription else '(empty - expected for test audio)'}")
                print(f"  LLM Response: {llm_response[:100] if llm_response else '(none)'}")
                
                # Save response audio
                response_path = Path("/tmp/test_response.wav")
                with open(response_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                print(f"  Response audio: {response_path.stat().st_size} bytes")
                print(f"  Saved to: {response_path}")
                
                # Clean up
                test_audio_path.unlink()
                
                return True
            else:
                print(f"✗ Processing failed: {response.status_code}")
                print(f"  Response: {response.text[:200]}")
                test_audio_path.unlink()
                return False
                
    except requests.exceptions.Timeout:
        print(f"✗ Request timeout (server may be processing)")
        return False
    except Exception as e:
        print(f"✗ Test error: {e}")
        if test_audio_path.exists():
            test_audio_path.unlink()
        return False

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("Voice Assistant Server Test Suite")
    print("="*60)
    print(f"Server URL: {SERVER_URL}")
    print(f"API Key: {API_KEY[:10]}..." if len(API_KEY) > 10 else f"API Key: {API_KEY}")
    
    results = []
    
    # Run tests
    results.append(("Health Check", test_health_check()))
    results.append(("Authentication", test_authentication()))
    
    # Only run audio processing test if previous tests passed
    if all(r[1] for r in results):
        results.append(("Audio Processing", test_audio_processing()))
    else:
        print("\n⚠ Skipping audio processing test due to previous failures")
    
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

