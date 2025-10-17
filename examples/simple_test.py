#!/usr/bin/env python3
"""
Simple Test Script for Voice Assistant
Basic functionality test without full voice assistant
"""

import sys
import time
import subprocess
from pathlib import Path

def test_basic_imports():
    """Test basic Python imports"""
    print("Testing basic imports...")
    
    try:
        import pyaudio
        print("✓ PyAudio imported successfully")
    except ImportError as e:
        print(f"✗ PyAudio import failed: {e}")
        return False
    
    try:
        import RPi.GPIO as GPIO
        print("✓ RPi.GPIO imported successfully")
    except ImportError as e:
        print(f"✗ RPi.GPIO import failed: {e}")
        return False
    
    try:
        import requests
        print("✓ Requests imported successfully")
    except ImportError as e:
        print(f"✗ Requests import failed: {e}")
        return False
    
    return True

def test_audio_system():
    """Test basic audio system"""
    print("\nTesting audio system...")
    
    # Test arecord
    try:
        result = subprocess.run(['arecord', '-l'], 
                              capture_output=True, text=True, check=True)
        if "voice-assistant" in result.stdout:
            print("✓ I2S microphone detected")
        else:
            print("⚠ I2S microphone not detected")
        print(f"Recording devices:\n{result.stdout}")
    except Exception as e:
        print(f"✗ arecord failed: {e}")
        return False
    
    # Test aplay
    try:
        result = subprocess.run(['aplay', '-l'], 
                              capture_output=True, text=True, check=True)
        if "voice-assistant" in result.stdout:
            print("✓ I2S amplifier detected")
        else:
            print("⚠ I2S amplifier not detected")
        print(f"Playback devices:\n{result.stdout}")
    except Exception as e:
        print(f"✗ aplay failed: {e}")
        return False
    
    return True

def test_gpio():
    """Test GPIO functionality"""
    print("\nTesting GPIO...")
    
    try:
        import RPi.GPIO as GPIO
        
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        state = GPIO.input(17)
        print(f"✓ GPIO17 (button) state: {state}")
        
        GPIO.cleanup()
        return True
        
    except Exception as e:
        print(f"✗ GPIO test failed: {e}")
        return False

def test_network():
    """Test network connectivity"""
    print("\nTesting network connectivity...")
    
    try:
        import requests
        
        # Test Groq API connectivity
        response = requests.get("https://api.groq.com", timeout=5)
        if response.status_code == 200:
            print("✓ Groq API reachable")
        else:
            print(f"⚠ Groq API returned status: {response.status_code}")
        
        return True
        
    except Exception as e:
        print(f"✗ Network test failed: {e}")
        return False

def test_file_permissions():
    """Test file permissions"""
    print("\nTesting file permissions...")
    
    # Test /tmp directory
    try:
        test_file = Path("/tmp/voice_assistant_test.txt")
        test_file.write_text("test")
        test_file.unlink()
        print("✓ /tmp directory writable")
    except Exception as e:
        print(f"✗ /tmp directory not writable: {e}")
        return False
    
    return True

def main():
    """Run all tests"""
    print("=" * 50)
    print("Voice Assistant Basic Test")
    print("=" * 50)
    
    tests = [
        ("Basic Imports", test_basic_imports),
        ("Audio System", test_audio_system),
        ("GPIO", test_gpio),
        ("Network", test_network),
        ("File Permissions", test_file_permissions)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        print("-" * 20)
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"✗ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("Test Results:")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Your system is ready for the voice assistant.")
    else:
        print(f"\n⚠ {total - passed} tests failed. Check the output above for details.")
        print("\nCommon solutions:")
        print("1. Reboot the system")
        print("2. Check hardware connections")
        print("3. Verify configuration files")
        print("4. Run the full test suite: python3 scripts/test_audio.py")

if __name__ == "__main__":
    main()
