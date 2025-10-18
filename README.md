# Raspberry Pi Voice Assistant

A distributed voice assistant with client-server architecture: Raspberry Pi handles audio I/O, server processes via Groq API.

## 🎯 Project Overview

This project creates a production-ready voice assistant with:

### Architecture
- **Raspberry Pi Client**: Records audio, sends to server, plays response
- **Server (Debian VM)**: Processes audio via Groq API (Whisper, LLM, TTS)
- **Cloudflare**: Provides DNS, SSL/TLS, DDoS protection

### Features
- Records audio using **INMP441 I2S microphone**
- **Press button once to start recording, press again to stop** (no time limit!)
- Sends audio to server over HTTPS
- Server transcribes speech using Groq Whisper API
- Server processes queries with Groq LLM
- Server generates speech responses using Groq TTS
- Plays audio through **MAX98357A I2S amplifier**
- Controlled via GPIO button
- Secure API key authentication
- Session support (future feature)

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

**Note**: This project now uses a client-server architecture. You need to:
1. Deploy the server (Debian VM)
2. Install the client (Raspberry Pi)

**Quick Links**:
- 📖 **[Full Deployment Guide](docs/DEPLOYMENT.md)** - Step-by-step server + client setup
- 🏗️ **[Architecture Documentation](docs/ARCHITECTURE.md)** - System design and components
- 🔌 **[API Documentation](docs/API.md)** - REST API and Groq API details

### Option 1: Quick Deploy (Recommended)

See **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** for complete instructions.

**Server Setup** (5-10 minutes):
```bash
# On Debian server
sudo bash server/deploy/deploy.sh
# Configure .env with GROQ_API_KEY and SERVER_API_KEY
# Setup Cloudflare DNS and SSL
```

**Pi Client Setup** (5 minutes):
```bash
# On Raspberry Pi
bash pi_client/deploy/install_client.sh
# Configure .env with SERVER_URL and CLIENT_API_KEY
```

### Option 2: Manual Setup

Follow the sections below for detailed manual setup.

---

## 🖥️ Server Deployment

### Prerequisites
- Debian 13 (or Ubuntu 22.04+) server
- Static public IP address
- Custom domain with Cloudflare
- Groq API key

### Quick Deploy

1. **Copy server files to your server**:
```bash
scp -r server/ user@your-server:/opt/voice_assistant/
```

2. **Run deployment script**:
```bash
ssh user@your-server
cd /opt/voice_assistant/deploy
sudo bash deploy.sh
```

3. **Configure environment**:
```bash
sudo nano /opt/voice_assistant/.env
# Set GROQ_API_KEY and SERVER_API_KEY
```

4. **Setup Cloudflare** (see [DEPLOYMENT.md](docs/DEPLOYMENT.md) for details):
- Configure DNS
- Setup SSL/TLS
- Create origin certificate

5. **Test server**:
```bash
curl https://yourdomain.com/health
```

**Full instructions**: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

---

## 📱 Raspberry Pi Client Setup

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

### 3. Client Software Installation

#### Quick Install

```bash
# Copy client files to Pi
scp -r pi_client/ pi@raspberrypi.local:/tmp/voice_assistant_client/

# SSH to Pi
ssh pi@raspberrypi.local

# Run installation script
cd /tmp/voice_assistant_client/deploy
bash install_client.sh
```

#### Configure Client

Edit configuration file:
```bash
nano ~/voice_assistant_client/.env
```

Set the following:
```env
# Your server URL (must use https://)
SERVER_URL=https://yourdomain.com

# API key (must match server's SERVER_API_KEY)
CLIENT_API_KEY=your_secure_api_key_here

# Hardware pins
BUTTON_PIN=17
AMPLIFIER_SD_PIN=27

# Audio settings
MICROPHONE_GAIN=2.0
```

Secure the file:
```bash
chmod 600 ~/voice_assistant_client/.env
```

### 4. Test Client

Test hardware:
```bash
# Test microphone (5 seconds, 48000 Hz required)
arecord -D plughw:0,0 -c1 -r 48000 -f S16_LE -t wav -d 5 test.wav

# Test speaker
aplay -D plughw:0,0 test.wav
```

Test client:
```bash
cd ~/voice_assistant_client
source ~/venvs/pi_client/bin/activate
python3 client.py
```

Press button and speak. Verify recording, server communication, and playback all work.

### 5. Run as Service (Optional)

```bash
sudo systemctl start voice-assistant-client.service
sudo systemctl enable voice-assistant-client.service
```

View logs:
```bash
sudo journalctl -u voice-assistant-client.service -f
```

**Full instructions**: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
**Troubleshooting**: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

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
├── voice_assistant.py        # Legacy monolithic version (deprecated)
├── server/                   # Server application
│   ├── main.py               # FastAPI application
│   ├── config.py             # Configuration management
│   ├── requirements.txt      # Server dependencies
│   ├── env.example           # Server environment template
│   ├── services/
│   │   └── groq_service.py   # Groq API integration
│   ├── middleware/
│   │   └── auth.py           # API key authentication
│   ├── models/
│   │   └── requests.py       # Request/response models
│   ├── deploy/
│   │   ├── deploy.sh         # Server deployment script
│   │   ├── systemd/          # Systemd service files
│   │   └── nginx/            # Nginx configuration
│   └── test_server.py        # Server test suite
├── pi_client/                # Raspberry Pi client
│   ├── client.py             # Main client application
│   ├── requirements.txt      # Client dependencies
│   ├── env.example           # Client environment template
│   ├── deploy/
│   │   └── install_client.sh # Client installation script
│   └── test_client.py        # Client test suite
├── docs/
│   ├── ARCHITECTURE.md       # System architecture
│   ├── DEPLOYMENT.md         # Deployment guide
│   ├── API.md                # API documentation
│   ├── HARDWARE.md           # Hardware wiring guide
│   ├── TROUBLESHOOTING.md    # Common issues and solutions
│   ├── AUDIO_CLICKS.md       # Fixing audio clicks/pops
│   ├── MICROPHONE_GAIN.MD    # Microphone volume configuration
│   ├── PYTHON.md             # Python compatibility
│   └── CHANGELOG.md          # Project improvements log
├── config/                   # Legacy configuration
├── scripts/                  # Legacy scripts
└── examples/                 # Legacy examples
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
- **Audio Clicks/Pops**: 
  - The system uses **fade-in/fade-out** and **silence padding** to eliminate clicks
  - If clicks persist, try increasing `FADE_DURATION_MS` in `.env` (default: 50ms, try 100ms)
  - See `docs/AUDIO_CLICKS.md` for detailed troubleshooting
- **No Audio**: Test with `aplay` command first

**Full troubleshooting:** See `docs/TROUBLESHOOTING.md`

### API Issues

- **Authentication**: Verify Groq API key
- **Network**: Check internet connectivity
- **Rate Limits**: Monitor API usage

## 🛠️ Development

### Testing

**Test Server**:
```bash
cd server
source venv/bin/activate
python3 test_server.py
```

**Test Client**:
```bash
cd pi_client
source ~/venvs/pi_client/bin/activate
python3 test_client.py
```

### Customization

**Server Configuration** (`server/.env`):
```env
GROQ_API_KEY=your_groq_api_key
SERVER_API_KEY=your_secure_api_key
WHISPER_MODEL=whisper-large-v3-turbo
LLM_MODEL=openai/gpt-oss-20b
TTS_MODEL=playai-tts
TTS_VOICE=Chip-PlayAI
SYSTEM_PROMPT=You are a helpful voice assistant...
```

**Client Configuration** (`pi_client/.env`):
```env
SERVER_URL=https://yourdomain.com
CLIENT_API_KEY=matches_server_api_key
BUTTON_PIN=17
AMPLIFIER_SD_PIN=27
MICROPHONE_GAIN=2.0
FADE_DURATION_MS=50
```

**Audio Settings**:
- `MICROPHONE_GAIN`: 1.0 = no change, 2.0 = double volume (recommended)
- `FADE_DURATION_MS`: Fade duration to eliminate clicks (50ms recommended)

### Monitoring

**Server Logs**:
```bash
sudo journalctl -u voice-assistant-server.service -f
sudo tail -f /var/log/nginx/voice-assistant-access.log
```

**Client Logs**:
```bash
sudo journalctl -u voice-assistant-client.service -f
```

## 📚 Documentation

### Quick Links
- 🏗️ **[Architecture](docs/ARCHITECTURE.md)** - System design, data flow, components
- 🚀 **[Deployment](docs/DEPLOYMENT.md)** - Complete deployment guide
- 🔌 **[API Reference](docs/API.md)** - REST API and Groq API documentation
- 🔧 **[Hardware](docs/HARDWARE.md)** - Wiring diagrams and connections
- 🐛 **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions

### API Overview

**Voice Assistant REST API** (Server):
- `POST /api/v1/process` - Process audio (transcribe → LLM → TTS)
- `GET /health` - Health check
- Authentication: API key in `X-API-Key` header

**Groq API** (Backend):
- **Whisper**: `whisper-large-v3-turbo` - Speech transcription
- **LLM**: `openai/gpt-oss-20b` - Query processing
- **TTS**: `playai-tts` - Speech generation

See **[docs/API.md](docs/API.md)** for complete API reference.

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Make changes
4. Test thoroughly
5. Submit pull request

## 📄 License

MIT License - see LICENSE file for details

## 🔒 Security

- ✅ API key authentication between client and server
- ✅ HTTPS/TLS for all communication
- ✅ Cloudflare DDoS protection
- ✅ Rate limiting (10 req/min per IP)
- ✅ File size and format validation
- ✅ Secure environment variable storage

See **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** for security hardening steps.

## 🆘 Support

For issues and questions:
1. Check **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)**
2. Review **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**
3. Check server and client logs
4. Create GitHub issue with logs

## 🎯 Roadmap

- [x] Client-server architecture
- [x] Secure API authentication
- [x] Production deployment guide
- [ ] Session-based conversation history
- [ ] User personalization and learning
- [ ] Multi-client support
- [ ] Audio streaming (reduce latency)
- [ ] Wake word detection
- [ ] Mobile app client

---

**Happy Voice Assisting! 🎤🤖**
