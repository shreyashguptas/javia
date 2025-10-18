# Documentation Guide

## Quick Navigation

### Getting Started
- **`../README.md`** - Project overview, quick start, basic usage

### Hardware & Setup
- **`HARDWARE.md`** - Complete wiring diagrams and assembly instructions
- **`PYTHON.md`** - Python 3.13 compatibility and installation guide

### Configuration
- **`API.md`** - Groq API setup and configuration
- **`MICROPHONE_GAIN.md`** - Microphone volume/sensitivity adjustment

### Troubleshooting
- **`TROUBLESHOOTING.md`** - Common issues and solutions
- **`AUDIO_CLICKS.md`** - Fixing audio clicks and pops

### Project Info
- **`CHANGELOG.md`** - Improvements and bug fixes log

## Documentation Organization

### By Topic

**Hardware Issues** → `HARDWARE.md` or `TROUBLESHOOTING.md`
**Audio Quality** → `MICROPHONE_GAIN.md` or `AUDIO_CLICKS.md`
**API Problems** → `API.md` or `TROUBLESHOOTING.md`
**Installation** → `PYTHON.md` or `../README.md`

### Quick Reference

| Need to... | See |
|------------|-----|
| Wire hardware | `HARDWARE.md` |
| Fix microphone not working | `TROUBLESHOOTING.md` → Section 2 |
| Adjust microphone volume | `MICROPHONE_GAIN.md` |
| Fix audio clicks | `AUDIO_CLICKS.md` |
| Configure API key | `API.md` |
| Install Python packages | `PYTHON.md` |
| Fix sample rate error | `TROUBLESHOOTING.md` → Section 1 |
| Check what's changed | `CHANGELOG.md` |

## File Descriptions

### HARDWARE.md
- Complete component list
- Pin-by-pin wiring diagrams
- Assembly steps
- Power requirements
- Verification checklist

### TROUBLESHOOTING.md
- Quick diagnostic commands
- Common error solutions
- Audio device testing
- System checks
- Log collection

### API.md
- Groq API setup
- Model configuration
- Rate limits
- Error handling
- Testing endpoints

### AUDIO_CLICKS.md
- Why clicks happen
- Three-layer solution
- Hardware SD pin control
- Software padding
- Troubleshooting persistent clicks

### MICROPHONE_GAIN.md
- Software gain configuration
- Recommended values (1.0-4.0)
- ALSA volume control
- Testing procedures
- Troubleshooting quiet recordings

### PYTHON.md
- Python 3.13 compatibility
- System package installation
- Virtual environment setup
- Avoiding compilation issues

### CHANGELOG.md
- Critical bug fixes
- Feature improvements
- Performance optimizations
- Documentation updates

## Code as Source of Truth

All documentation reflects the actual implementation in `voice_assistant.py`:

**Hardware:**
- INMP441 microphone (I2S)
- MAX98357A amplifier (I2S)
- Uses `googlevoicehat-soundcard` driver

**Configuration:**
- Sample Rate: 48000 Hz (required)
- Microphone Gain: 2.0x default
- Button: GPIO17
- Amplifier SD: GPIO27

**Features:**
- Button press to start/stop recording
- Automatic retry on API errors
- Memory-efficient audio padding
- Comprehensive error handling

