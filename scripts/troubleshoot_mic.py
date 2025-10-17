#!/usr/bin/env python3
"""
Microphone Troubleshooting Script
Specifically designed to diagnose INMP441 microphone issues
"""

import os
import sys
import time
import subprocess
import pyaudio
from pathlib import Path

def check_config_file():
    """Check /boot/firmware/config.txt for I2S configuration"""
    print("=" * 60)
    print("CHECKING CONFIG.TXT")
    print("=" * 60)
    
    config_file = Path("/boot/firmware/config.txt")
    if not config_file.exists():
        print("✗ /boot/firmware/config.txt not found")
        return False
    
    print("✓ /boot/firmware/config.txt exists")
    
    # Read config file
    with open(config_file, 'r') as f:
        content = f.read()
    
    # Check for required I2S settings
    required_settings = [
        "dtparam=i2s=on",
        "dtoverlay=googlevoicehat-soundcard"
    ]
    
    missing_settings = []
    for setting in required_settings:
        if setting in content:
            print(f"✓ Found: {setting}")
        else:
            print(f"✗ Missing: {setting}")
            missing_settings.append(setting)
    
    if missing_settings:
        print(f"\n⚠ Missing {len(missing_settings)} required settings")
        print("Add these lines to /boot/firmware/config.txt:")
        for setting in missing_settings:
            print(f"  {setting}")
        return False
    else:
        print("\n✓ All required I2S settings found")
        return True

def check_audio_devices():
    """Check if audio devices are detected"""
    print("\n" + "=" * 60)
    print("CHECKING AUDIO DEVICES")
    print("=" * 60)
    
    # Check arecord
    print("1. Recording devices (arecord -l):")
    try:
        result = subprocess.run(['arecord', '-l'], 
                              capture_output=True, text=True, check=True)
        print(result.stdout)
        
        if "googlevoicehat" in result.stdout or "voice-assistant" in result.stdout:
            print("✓ I2S microphone detected")
            return True
        else:
            print("✗ I2S microphone NOT detected")
            return False
            
    except Exception as e:
        print(f"✗ arecord failed: {e}")
        return False

def check_pyaudio_devices():
    """Check PyAudio device enumeration"""
    print("\n2. PyAudio devices:")
    try:
        p = pyaudio.PyAudio()
        print(f"PyAudio version: {pyaudio.__version__}")
        print(f"Total devices: {p.get_device_count()}")
        
        i2s_found = False
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                print(f"  Device {i}: {info['name']}")
                if 'sndrpisimplecar' in info['name'].lower():
                    i2s_found = True
                    print(f"    ✓ I2S device found!")
        
        p.terminate()
        
        if i2s_found:
            print("✓ PyAudio found I2S device")
            return True
        else:
            print("✗ PyAudio did not find I2S device")
            return False
            
    except Exception as e:
        print(f"✗ PyAudio check failed: {e}")
        return False

def test_manual_recording():
    """Test manual recording with arecord"""
    print("\n" + "=" * 60)
    print("TESTING MANUAL RECORDING")
    print("=" * 60)
    
    print("Testing manual recording with arecord...")
    print("Speak into the microphone for 3 seconds...")
    
    try:
        # Test recording
        result = subprocess.run([
            'arecord', '-D', 'plughw:0,0', '-c1', '-r16000', 
            '-f', 'S16_LE', '-t', 'wav', '-d', '3',
            '/tmp/manual_test.wav'
        ], capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            print("✓ Manual recording successful")
            
            # Check file size
            test_file = Path("/tmp/manual_test.wav")
            if test_file.exists():
                file_size = test_file.stat().st_size
                print(f"✓ Test file created: {file_size} bytes")
                
                if file_size > 1000:  # Should be more than 1KB
                    print("✓ File size looks reasonable")
                    return True
                else:
                    print("⚠ File size is very small - may be silent")
                    return False
            else:
                print("✗ Test file not created")
                return False
        else:
            print(f"✗ Manual recording failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("✓ Manual recording completed (timeout)")
        return True
    except Exception as e:
        print(f"✗ Manual recording error: {e}")
        return False

def test_pyaudio_recording():
    """Test PyAudio recording"""
    print("\n" + "=" * 60)
    print("TESTING PYAUDIO RECORDING")
    print("=" * 60)
    
    try:
        audio = pyaudio.PyAudio()
        
        # Find I2S device
        device_index = None
        for i in range(audio.get_device_count()):
            info = audio.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0 and 'sndrpisimplecar' in info['name'].lower():
                device_index = i
                print(f"Using I2S device: {info['name']}")
                break
        
        if device_index is None:
            print("⚠ I2S device not found, using default")
            device_index = None
        
        # Test recording
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=1024
        )
        
        print("Recording for 3 seconds... SPEAK NOW!")
        
        frames = []
        for i in range(48):  # 3 seconds at 16kHz/1024 chunks
            data = stream.read(1024, exception_on_overflow=False)
            frames.append(data)
        
        stream.stop_stream()
        stream.close()
        audio.terminate()
        
        # Save test file
        import wave
        test_file = Path("/tmp/pyaudio_test.wav")
        with wave.open(str(test_file), 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b''.join(frames))
        
        file_size = test_file.stat().st_size
        print(f"✓ PyAudio test file created: {file_size} bytes")
        
        if file_size > 1000:
            print("✓ PyAudio recording successful")
            return True
        else:
            print("⚠ PyAudio file size is small - may be silent")
            return False
            
    except Exception as e:
        print(f"✗ PyAudio recording failed: {e}")
        return False

def check_hardware_connections():
    """Check hardware connections"""
    print("\n" + "=" * 60)
    print("HARDWARE CONNECTION CHECK")
    print("=" * 60)
    
    print("Please verify these connections:")
    print()
    print("INMP441 Microphone:")
    print("  VDD  → Pi 3.3V (Pin 1)")
    print("  GND  → Pi GND (Pin 6)")
    print("  SCK  → Pi GPIO18 (Pin 12)")
    print("  WS   → Pi GPIO19 (Pin 35)")
    print("  SD   → Pi GPIO20 (Pin 38)")
    print("  L/R  → Pi GND (Pin 6)")
    print()
    print("MAX98357A Amplifier:")
    print("  VDD  → Pi 3.3V (Pin 1)")
    print("  GND  → Pi GND (Pin 6)")
    print("  BCLK → Pi GPIO18 (Pin 12)")
    print("  LRC  → Pi GPIO19 (Pin 35)")
    print("  DIN  → Pi GPIO20 (Pin 40)")
    print()
    print("Button:")
    print("  Terminal 1 → Pi GPIO17 (Pin 11)")
    print("  Terminal 2 → Pi GND (Pin 6)")
    print()
    
    response = input("Are all connections correct? (y/N): ")
    return response.lower() in ['y', 'yes']

def check_power_supply():
    """Check power supply"""
    print("\n" + "=" * 60)
    print("POWER SUPPLY CHECK")
    print("=" * 60)
    
    try:
        # Check voltage
        result = subprocess.run(['vcgencmd', 'measure_volts'], 
                              capture_output=True, text=True, check=True)
        voltage = result.stdout.strip()
        print(f"Current voltage: {voltage}")
        
        # Check for undervoltage
        result = subprocess.run(['vcgencmd', 'get_throttled'], 
                              capture_output=True, text=True, check=True)
        throttled = result.stdout.strip()
        print(f"Throttling status: {throttled}")
        
        if "0x0" in throttled:
            print("✓ No power issues detected")
            return True
        else:
            print("⚠ Power issues detected - check power supply")
            return False
            
    except Exception as e:
        print(f"✗ Power check failed: {e}")
        return False

def generate_diagnostic_report():
    """Generate comprehensive diagnostic report"""
    print("\n" + "=" * 60)
    print("DIAGNOSTIC REPORT")
    print("=" * 60)
    
    # Run all checks
    config_ok = check_config_file()
    devices_ok = check_audio_devices()
    pyaudio_ok = check_pyaudio_devices()
    manual_ok = test_manual_recording()
    pyaudio_rec_ok = test_pyaudio_recording()
    hardware_ok = check_hardware_connections()
    power_ok = check_power_supply()
    
    # Summary
    print("\n" + "=" * 60)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 60)
    
    checks = [
        ("Config File", config_ok),
        ("Audio Devices", devices_ok),
        ("PyAudio Devices", pyaudio_ok),
        ("Manual Recording", manual_ok),
        ("PyAudio Recording", pyaudio_rec_ok),
        ("Hardware Connections", hardware_ok),
        ("Power Supply", power_ok)
    ]
    
    passed = 0
    total = len(checks)
    
    for check_name, result in checks:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{check_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} checks passed")
    
    # Recommendations
    print("\n" + "=" * 60)
    print("RECOMMENDATIONS")
    print("=" * 60)
    
    if not config_ok:
        print("1. Add missing I2S configuration to /boot/firmware/config.txt")
        print("2. Reboot the system after making changes")
    
    if not devices_ok:
        print("3. Check hardware connections")
        print("4. Verify I2S configuration")
        print("5. Reboot the system")
    
    if not pyaudio_ok:
        print("6. Reinstall PyAudio: pip uninstall pyaudio && pip install pyaudio")
        print("7. Check ALSA configuration")
    
    if not manual_ok:
        print("8. Test with different audio formats")
        print("9. Check microphone power supply")
    
    if not pyaudio_rec_ok:
        print("10. Check PyAudio device enumeration")
        print("11. Verify audio permissions")
    
    if not hardware_ok:
        print("12. Double-check all wiring connections")
        print("13. Use multimeter to test continuity")
    
    if not power_ok:
        print("14. Use a higher capacity power supply (5V 3A+)")
        print("15. Check USB cable quality")
    
    if passed == total:
        print("\n🎉 All checks passed! Your microphone should be working.")
        print("If you're still having issues, try:")
        print("- Reboot the system")
        print("- Check the troubleshooting guide")
        print("- Test with different audio formats")
    else:
        print(f"\n⚠ {total - passed} checks failed. Follow the recommendations above.")

def main():
    """Main function"""
    print("=" * 60)
    print("INMP441 MICROPHONE TROUBLESHOOTING")
    print("=" * 60)
    print()
    print("This script will diagnose common microphone issues.")
    print("Make sure your INMP441 is properly connected!")
    print()
    
    # Run diagnostic
    generate_diagnostic_report()
    
    print("\n" + "=" * 60)
    print("NEXT STEPS")
    print("=" * 60)
    print("1. Follow the recommendations above")
    print("2. Reboot the system if configuration was changed")
    print("3. Run this script again to verify fixes")
    print("4. Test with: python3 examples/mic_test.py")
    print("5. Check docs/troubleshooting.md for more help")

if __name__ == "__main__":
    main()
