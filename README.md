# Raspberry Pi Zero 2 W Voice Assistant

A complete voice assistant project using Raspberry Pi Zero 2 W with INMP441 microphone, MAX98357A amplifier, and Groq API integration.

## 🎯 Project Overview

This project creates a voice assistant that:
- Records audio using **INMP441 I2S microphone**
- **Press button once to start recording, press again to stop** (no time limit!)
- Transcribes speech using Groq Whisper API
- Processes queries with Groq LLM
- Generates speech responses using Groq TTS
- Plays audio through **MAX98357A I2S amplifier**
- Controlled via GPIO button

## 🔧 Hardware Requirements

### Components
- **Raspberry Pi Zero 2 W** - Mainboard with 40-pin GPIO
- **INMP441 MEMS Microphone** - I2S digital microphone (24-bit, up to 64kHz)
- **MAX98357A I2S Amplifier** - 3W Class D amplifier with DAC
- **3W 4Ω Speaker** - Connected to amplifier output
- **Push Button** - Momentary switch for recording control
- **Breadboard and Jumper Wires** - For connections
- **5V 3A Power Supply** - USB power adapter with quality cable

### Quick Wiring Reference

```
INMP441 Microphone:
├── VDD  → Pi 3.3V (Pin 1)
├── GND  → Pi GND (Pin 6)
├── SCK  → Pi GPIO18 (Pin 12)
├── WS   → Pi GPIO19 (Pin 35)
├── SD   → Pi GPIO20 (Pin 38)
└── L/R  → Pi GND (Pin 6)

MAX98357A Amplifier:
├── VDD  → Pi 3.3V (Pin 1)
├── GND  → Pi GND (Pin 6)
├── BCLK → Pi GPIO18 (Pin 12)
├── LRC  → Pi GPIO19 (Pin 35)
├── DIN  → Pi GPIO21 (Pin 40)
└── SD   → Pi GPIO27 (Pin 13) ← Prevents audio clicks

Speaker:
├── Red   → Amplifier OUT+
└── Black → Amplifier OUT-

Button:
├── Terminal 1 → Pi GPIO17 (Pin 11)
└── Terminal 2 → Pi GND (Pin 6)
```

**Detailed wiring diagrams:** See `docs/HARDWARE.md`

## 🚀 Quick Start

### 1. Hardware Setup
1. **Power off** the Raspberry Pi
2. **Wire INMP441 microphone** according to diagram above
3. **Wire MAX98357A amplifier** according to diagram above
4. **Connect speaker** to amplifier (red to +, black to -)
5. **Connect button** to GPIO17 and GND
6. **Power on** with 3A power supply

**Detailed setup:** See `docs/HARDWARE.md`

### 2. Software Configuration

#### Enable I2S Audio
Add to `/boot/firmware/config.txt`:
```bash
sudo nano /boot/firmware/config.txt
```

Then add this at the bottom of the file

```bash
# I2S Configuration (INMP441 + MAX98357A)
dtparam=i2s=on
dtoverlay=googlevoicehat-soundcard
```

**Note:** We use the `googlevoicehat-soundcard` driver (it works great with INMP441+MAX98357A).

**Then reboot:**
```bash
sudo reboot
```

#### Install Dependencies

- Make sure this repo is git cloned then run the following

```bash
cd J.A.R.V.I.S.
```

**Option 1: Use System Packages (Recommended for Pi Zero 2 W)**

This avoids compilation issues and memory constraints:

```bash
# Install system packages
sudo apt update
sudo apt install -y python3-pyaudio python3-rpi.gpio python3-requests python3-numpy python3-pip

# Create virtual environment with system packages
python3 -m venv --system-site-packages ~/venvs/pi
source ~/venvs/pi/bin/activate

# Install remaining packages
pip install python-dotenv
```

**Option 2: Build from Source (if you have time and patience)**

Only use this if Option 1 doesn't work:

```bash
# Install build dependencies
sudo apt install -y python3-dev portaudio19-dev libatlas-base-dev

# Create virtual environment
python3 -m venv ~/venvs/pi
source ~/venvs/pi/bin/activate

# Install packages (this may take 30-60 minutes on Pi Zero 2 W)
pip install -r config/requirements.txt
```

#### Configure API Key
Copy the environment template and add your API key:
```bash
cp env.example .env
nano .env
```

Edit the `.env` file and replace:
```
GROQ_API_KEY=YOUR_GROQ_API_KEY_HERE
```

### 3. Test Setup
```bash
# Test microphone (5 seconds, 48000 Hz required)
arecord -D plughw:0,0 -c1 -r 48000 -f S16_LE -t wav -d 5 test.wav

# Test speaker
aplay -D plughw:0,0 test.wav

# Run voice assistant
python3 voice_assistant.py
```

**Troubleshooting:** See `docs/TROUBLESHOOTING.md`

## 🎙️ How to Use

1. **Press the button** - Recording starts
2. **Speak your question** - Take as long as you need (no time limit)
3. **Press the button again** - Recording stops
4. **Wait for response** - Processing and playback happens automatically
5. **Listen to the answer** - Response plays through speaker
6. **Interrupt if needed** - Press button during playback to cancel, then press again to start new recording
7. **Repeat** - Press button to ask another question

### Interrupt Feature
While the assistant is speaking (playing audio response):
- **Press button once**: Immediately stops the audio playback
- **Press button again**: Starts recording a new question (normal flow resumes)

## 📁 Project Structure

```
voice_assistant/
├── README.md                 # This file
├── voice_assistant.py        # Main application
├── env.example              # Environment variables template
├── config/
│   ├── config.txt.example    # Example Pi configuration
│   └── requirements.txt      # Python dependencies
├── docs/
│   ├── HARDWARE.md           # Detailed hardware wiring guide
│   ├── TROUBLESHOOTING.md    # Common issues and solutions
│   ├── API.md                # Groq API configuration
│   ├── AUDIO_CLICKS.md       # Fixing audio clicks/pops
│   ├── MICROPHONE_GAIN.md    # Microphone volume configuration
│   ├── PYTHON.md             # Python 3.13 compatibility
│   └── CHANGELOG.md          # Project improvements log
├── scripts/
│   ├── setup.sh              # Automated setup script
│   ├── test_audio.py         # Audio testing utilities
│   └── install_deps.sh       # Dependency installer
└── examples/
    ├── simple_test.py        # Basic functionality test
    └── mic_test.py           # Microphone testing
```

## 🔍 Troubleshooting

### Microphone Not Working

**Common Issues:**

1. **Hardware Connections**
   - Verify all wiring matches diagram
   - Check for loose breadboard connections
   - Ensure proper power supply

2. **I2S Configuration**
   - Verify `/boot/firmware/config.txt` settings
   - Reboot after configuration changes
   - Check with `arecord -l`

3. **Device Detection**
   ```bash
   # List audio devices
   arecord -l
   aplay -l
   
   # Test recording (5 seconds, 48000 Hz required)
   arecord -D plughw:0,0 -c1 -r 48000 -f S16_LE -d 5 test.wav
   ```

4. **Python Environment**
   - Ensure virtual environment is activated
   - Check PyAudio installation
   - Verify device permissions

### Audio Quality Issues

- **Microphone Too Quiet**: 
  - Increase `MICROPHONE_GAIN` in `.env` file (try 2.0, 3.0, or 4.0)
  - Check ALSA capture volume: `amixer -c 0 set Capture 100%`
  - Verify microphone is close enough (6-12 inches)
- **Speaker Volume Low**: Check speaker connections and amplifier power
- **Distorted Audio**: 
  - Reduce `MICROPHONE_GAIN` if too high
  - Verify sample rate is 48000 Hz
- **Audio Clicks**: See `docs/AUDIO_CLICKS.md`
- **No Audio**: Test with `aplay` command first

**Full troubleshooting:** See `docs/TROUBLESHOOTING.md`

### API Issues

- **Authentication**: Verify Groq API key
- **Network**: Check internet connectivity
- **Rate Limits**: Monitor API usage

## 🛠️ Development

### Testing Audio Components
```bash
# Test microphone recording
python3 scripts/test_audio.py

# Test individual components
python3 examples/mic_test.py
```

### Customization

You can customize settings via the `.env` file:

```bash
# Edit .env file
nano .env
```

**Available Settings:**
- `MICROPHONE_GAIN` - Amplify microphone input (default: 2.0)
  - `1.0` = No amplification
  - `2.0` = Double volume (recommended)
  - `3.0` = Triple volume
  - `4.0` = Quadruple volume (may distort)
- `RECORD_SECONDS` - Recording duration in seconds (default: 5)
- `BUTTON_PIN` - GPIO pin for button (default: 17)
- `SAMPLE_RATE` - Audio sample rate (default: 48000, required by driver)

**Example `.env`:**
```env
GROQ_API_KEY=your_api_key_here
MICROPHONE_GAIN=2.5
RECORD_SECONDS=7
```

## 📚 API Documentation

### Groq API Endpoints
- **Whisper**: `https://api.groq.com/openai/v1/audio/transcriptions`
- **LLM**: `https://api.groq.com/openai/v1/chat/completions`
- **TTS**: `https://api.groq.com/openai/v1/audio/speech`

### Models Used
- **Whisper**: `whisper-large-v3-turbo` (fastest, most accurate)
- **LLM**: `openai/gpt-oss-20b`
- **TTS**: `playai-tts` with `Chip-PlayAI` voice

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Make changes
4. Test thoroughly
5. Submit pull request

## 📄 License

MIT License - see LICENSE file for details

## 🆘 Support

For issues and questions:
1. Check troubleshooting guide
2. Review hardware setup
3. Test individual components
4. Create GitHub issue with logs

---

**Happy Voice Assisting! 🎤🤖**
