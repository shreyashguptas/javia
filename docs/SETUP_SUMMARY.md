# Voice Assistant Repository - Complete Setup

## 🎯 Project Summary

I've created a comprehensive repository for your Raspberry Pi Zero 2 W voice assistant project. The repository includes everything needed to get your INMP441 microphone working with the MAX98357A amplifier.

## 📁 Repository Structure

```
voice_assistant/
├── README.md                    # Main documentation
├── README_SHORT.md              # Quick start guide
├── MICROPHONE_FIX.md            # Specific microphone troubleshooting
├── voice_assistant.py           # Main application
├── LICENSE                      # MIT license
├── config/
│   ├── config.txt.example       # Pi configuration template
│   └── requirements.txt         # Python dependencies
├── docs/
│   ├── hardware_setup.md         # Detailed hardware guide
│   ├── troubleshooting.md       # Comprehensive troubleshooting
│   └── api_setup.md             # Groq API configuration
├── scripts/
│   ├── setup.sh                 # Automated setup script
│   ├── install_deps.sh           # Dependency installer
│   ├── test_audio.py            # Audio testing utilities
│   └── troubleshoot_mic.py      # Microphone diagnostic tool
└── examples/
    ├── simple_test.py            # Basic functionality test
    └── mic_test.py               # Microphone testing
```

## 🔧 Your Microphone Issue - Quick Fix

Based on your setup, the most likely issue is **I2S configuration**. Here's the quick fix:

### 1. Check Current Configuration
```bash
cat /boot/firmware/config.txt | grep -i i2s
```

### 2. If Missing, Add These Lines
```bash
sudo nano /boot/firmware/config.txt

# Add at the end:
dtparam=i2s=on
dtoverlay=i2s-mmap
dtoverlay=rpi-simple-soundcard,card-name=voice-assistant
dtparam=simple_card_name="voice-assistant"
dtparam=i2s_master=on
dtparam=i2s_sample_rate=16000
```

### 3. Reboot
```bash
sudo reboot
```

### 4. Test
```bash
# Check if microphone is detected
arecord -l

# Test recording
arecord -D plughw:0,0 -c1 -r 16000 -f S16_LE test.wav
```

## 🚀 Quick Start Guide

### 1. Hardware Setup
- Connect INMP441 microphone according to wiring diagram
- Connect MAX98357A amplifier
- Connect speaker and button
- Power on Raspberry Pi

### 2. Software Setup
```bash
# Run automated setup
chmod +x scripts/setup.sh
./scripts/setup.sh

# Reboot
sudo reboot
```

### 3. Configure API Key
Edit `voice_assistant.py` and replace:
```python
GROQ_API_KEY = "YOUR_GROQ_API_KEY_HERE"
```

### 4. Test Setup
```bash
# Test basic functionality
python3 examples/simple_test.py

# Test microphone specifically
python3 examples/mic_test.py

# Run comprehensive diagnostics
python3 scripts/troubleshoot_mic.py
```

### 5. Run Voice Assistant
```bash
python3 voice_assistant.py
```

## 🔍 Troubleshooting Tools

### Diagnostic Script
```bash
python3 scripts/troubleshoot_mic.py
```
This will:
- Check I2S configuration
- Test audio devices
- Verify hardware connections
- Test recording functionality
- Provide specific recommendations

### Audio Testing
```bash
python3 scripts/test_audio.py
```
This will:
- List all audio devices
- Test microphone recording
- Test speaker playback
- Check audio levels
- Test GPIO button

### Simple Test
```bash
python3 examples/simple_test.py
```
This will:
- Test Python imports
- Check audio system
- Test GPIO
- Verify network connectivity

## 📚 Documentation

### Hardware Setup (`docs/hardware_setup.md`)
- Detailed wiring diagrams
- Pin reference
- Power requirements
- Breadboard layout
- Connection tips

### Troubleshooting (`docs/troubleshooting.md`)
- Common issues and solutions
- Diagnostic commands
- System optimization
- Getting help

### API Setup (`docs/api_setup.md`)
- Groq API configuration
- Rate limits
- Error handling
- Testing connections

## 🛠️ Scripts Available

### Setup Script (`scripts/setup.sh`)
- Installs system dependencies
- Creates virtual environment
- Configures I2S audio
- Sets up systemd service
- Creates test scripts

### Dependency Installer (`scripts/install_deps.sh`)
- Installs Python packages
- Sets up audio permissions
- Creates activation scripts
- Verifies installations

### Audio Tester (`scripts/test_audio.py`)
- Comprehensive audio testing
- Device enumeration
- Recording/playback tests
- Level monitoring
- GPIO testing

### Microphone Troubleshooter (`scripts/troubleshoot_mic.py`)
- Specific microphone diagnostics
- Configuration checking
- Hardware verification
- Power supply testing
- Detailed recommendations

## 🎯 Most Common Issues

### 1. Microphone Not Detected
- **Cause**: Missing I2S configuration
- **Fix**: Add I2S settings to config.txt and reboot

### 2. No Audio Input
- **Cause**: Hardware connections
- **Fix**: Check wiring diagram and connections

### 3. Silent Recordings
- **Cause**: Power supply or microphone defect
- **Fix**: Check power supply, try different microphone

### 4. Python Import Errors
- **Cause**: Missing packages
- **Fix**: Run `scripts/install_deps.sh`

### 5. Permission Errors
- **Cause**: User not in audio group
- **Fix**: Run `sudo usermod -a -G audio $USER`

## 🔧 Hardware Verification

### Wiring Checklist
- [ ] INMP441 VDD → Pi 3.3V (Pin 1)
- [ ] INMP441 GND → Pi GND (Pin 6)
- [ ] INMP441 SCK → Pi GPIO18 (Pin 12)
- [ ] INMP441 WS → Pi GPIO19 (Pin 35)
- [ ] INMP441 SD → Pi GPIO20 (Pin 38)
- [ ] INMP441 L/R → Pi GND (Pin 6)
- [ ] MAX98357A VDD → Pi 3.3V (Pin 1)
- [ ] MAX98357A GND → Pi GND (Pin 6)
- [ ] MAX98357A BCLK → Pi GPIO18 (Pin 12)
- [ ] MAX98357A LRC → Pi GPIO19 (Pin 35)
- [ ] MAX98357A DIN → Pi GPIO20 (Pin 40)
- [ ] Button → Pi GPIO17 (Pin 11) and GND

### Power Supply
- [ ] 5V 3A USB power adapter
- [ ] High-quality USB cable
- [ ] Stable power (no undervoltage)

## 🎉 Success Indicators

When everything is working correctly:
- `arecord -l` shows "voice-assistant" device
- Manual recording creates files > 1000 bytes
- PyAudio finds I2S device
- Python script can record audio
- Voice assistant responds to button presses

## 📞 Getting Help

1. **Run diagnostic script**: `python3 scripts/troubleshoot_mic.py`
2. **Check troubleshooting guide**: `docs/troubleshooting.md`
3. **Verify hardware setup**: `docs/hardware_setup.md`
4. **Test individual components**: `examples/mic_test.py`

---

**Your microphone should work after following the I2S configuration steps above. If not, run the diagnostic script for specific recommendations!**
