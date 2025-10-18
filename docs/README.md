# Documentation Guide

Welcome to the Voice Assistant documentation! This guide helps you navigate the documentation for the client-server architecture.

## Quick Navigation

### Getting Started
- **[../GETTING_STARTED.md](../GETTING_STARTED.md)** - Quick deployment guide for server and client
- **[../README.md](../README.md)** - Project overview and introduction
- **[../MIGRATION.md](../MIGRATION.md)** - Migration guide from old monolithic architecture

### Architecture & Deployment
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System design, data flow, and components
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Complete deployment guide for server and Pi client
- **[API.md](API.md)** - REST API and Groq API documentation

### Hardware & Setup
- **[HARDWARE.md](HARDWARE.md)** - Raspberry Pi wiring diagrams and assembly
- **[PYTHON.md](PYTHON.md)** - Python installation and system packages

### Configuration & Tuning
- **[MICROPHONE_GAIN.md](MICROPHONE_GAIN.md)** - Microphone volume adjustment
- **[AUDIO_CLICKS.md](AUDIO_CLICKS.md)** - Fixing audio clicks and pops

### Troubleshooting
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Common issues and solutions

### Project History
- **[CHANGELOG.md](CHANGELOG.md)** - Historical improvements log

## Documentation Organization

### By Component

**Server Setup:**
1. [DEPLOYMENT.md](DEPLOYMENT.md) → Server deployment section
2. [API.md](API.md) → REST API documentation
3. [ARCHITECTURE.md](ARCHITECTURE.md) → Server architecture

**Raspberry Pi Client:**
1. [DEPLOYMENT.md](DEPLOYMENT.md) → Client deployment section
2. [HARDWARE.md](HARDWARE.md) → Hardware wiring
3. [PYTHON.md](PYTHON.md) → Python setup
4. [MICROPHONE_GAIN.md](MICROPHONE_GAIN.md) → Audio tuning
5. [AUDIO_CLICKS.md](AUDIO_CLICKS.md) → Audio quality

**Understanding the System:**
1. [ARCHITECTURE.md](ARCHITECTURE.md) → How it all works
2. [API.md](API.md) → Communication protocol
3. [../MIGRATION.md](../MIGRATION.md) → What changed from old version

### By Task

| Need to... | See |
|------------|-----|
| Deploy server | [DEPLOYMENT.md](DEPLOYMENT.md) → Part 1 |
| Setup Cloudflare | [DEPLOYMENT.md](DEPLOYMENT.md) → Part 1, Step 7-9 |
| Install Pi client | [DEPLOYMENT.md](DEPLOYMENT.md) → Part 2 |
| Wire hardware | [HARDWARE.md](HARDWARE.md) |
| Fix microphone not working | [TROUBLESHOOTING.md](TROUBLESHOOTING.md) |
| Adjust microphone volume | [MICROPHONE_GAIN.md](MICROPHONE_GAIN.md) |
| Fix audio clicks | [AUDIO_CLICKS.md](AUDIO_CLICKS.md) |
| Understand architecture | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Setup API keys | [DEPLOYMENT.md](DEPLOYMENT.md) |
| Configure Nginx | [DEPLOYMENT.md](DEPLOYMENT.md) → Part 1, Step 6-8 |
| Test deployment | [DEPLOYMENT.md](DEPLOYMENT.md) → Part 3 |
| Secure system | [DEPLOYMENT.md](DEPLOYMENT.md) → Part 4 |
| Monitor logs | [DEPLOYMENT.md](DEPLOYMENT.md) → Part 5 |

## File Descriptions

### Core Documentation

#### ARCHITECTURE.md
- Client-server design overview
- Data flow diagrams
- Component responsibilities
- API specifications
- Security architecture
- Performance characteristics
- Deployment topology

#### DEPLOYMENT.md
- Complete deployment guide
- Server setup on Debian
- Cloudflare configuration
- Raspberry Pi client installation
- Security hardening
- Monitoring and maintenance
- Troubleshooting deployment issues

#### API.md
- Voice Assistant REST API endpoints
- Authentication methods
- Request/response formats
- Groq API configuration
- Rate limiting
- Error codes
- Testing examples

### Hardware Documentation

#### HARDWARE.md
- Complete component list
- INMP441 microphone wiring
- MAX98357A amplifier wiring
- Button connections
- Power requirements
- Verification checklist

### Setup & Configuration

#### PYTHON.md
- Python 3.13 compatibility
- System package installation
- Virtual environment setup
- Avoiding compilation issues on Pi

#### MICROPHONE_GAIN.md
- Software gain configuration (1.0-4.0x)
- Recommended values
- ALSA volume control
- Testing procedures
- Troubleshooting quiet recordings

#### AUDIO_CLICKS.md
- Why clicks happen
- Hardware SD pin control
- Software padding and fade effects
- Troubleshooting persistent clicks

### Support

#### TROUBLESHOOTING.md
- Quick diagnostic commands
- Common error solutions
- Audio device testing
- System checks
- Server connection issues
- Log collection

#### CHANGELOG.md
- Historical improvements
- Bug fixes from original version
- Feature additions

## Architecture Overview

The voice assistant uses a **client-server architecture**:

### Raspberry Pi Client
- Records audio from microphone
- Sends to server via HTTPS
- Receives processed audio response
- Plays through speaker
- **Documentation:** [Hardware](HARDWARE.md), [Client Setup](DEPLOYMENT.md#part-2-raspberry-pi-client-deployment)

### Server (Debian VM)
- Receives audio files
- Processes via Groq API (Whisper, LLM, TTS)
- Returns audio response
- **Documentation:** [Server Setup](DEPLOYMENT.md#part-1-server-deployment), [API](API.md)

### Cloudflare
- DNS management
- SSL/TLS encryption
- DDoS protection
- **Documentation:** [Cloudflare Setup](DEPLOYMENT.md#step-7-setup-cloudflare-ssl-certificates)

## Component Documentation

### Server Components
| Component | Location | Documentation |
|-----------|----------|---------------|
| FastAPI App | `../server/main.py` | [API.md](API.md) |
| Groq Service | `../server/services/groq_service.py` | [API.md](API.md) |
| Authentication | `../server/middleware/auth.py` | [API.md](API.md) |
| Configuration | `../server/config.py` | [DEPLOYMENT.md](DEPLOYMENT.md) |
| Deployment | `../server/deploy/` | [DEPLOYMENT.md](DEPLOYMENT.md) |

### Client Components
| Component | Location | Documentation |
|-----------|----------|---------------|
| Main Client | `../pi_client/client.py` | Hardware I/O |
| Audio Recording | `../pi_client/client.py` | [HARDWARE.md](HARDWARE.md) |
| Audio Playback | `../pi_client/client.py` | [AUDIO_CLICKS.md](AUDIO_CLICKS.md) |
| Deployment | `../pi_client/deploy/` | [DEPLOYMENT.md](DEPLOYMENT.md) |

## Deployment Quick Start

1. **Read** [GETTING_STARTED.md](../GETTING_STARTED.md) for overview
2. **Deploy Server** using [DEPLOYMENT.md](DEPLOYMENT.md) Part 1
3. **Setup Cloudflare** using [DEPLOYMENT.md](DEPLOYMENT.md) Step 7-9
4. **Install Client** using [DEPLOYMENT.md](DEPLOYMENT.md) Part 2
5. **Test** using test scripts in Part 3

## Need Help?

1. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues
2. Review [DEPLOYMENT.md](DEPLOYMENT.md) for deployment problems
3. Check logs (documented in [DEPLOYMENT.md](DEPLOYMENT.md) Part 5)
4. Review [ARCHITECTURE.md](ARCHITECTURE.md) to understand the system
5. Create GitHub issue with logs

## Technical Stack

**Server:**
- FastAPI (Python web framework)
- Uvicorn (ASGI server)
- Nginx (reverse proxy)
- Groq API (Whisper, LLM, TTS)

**Client:**
- Python 3
- PyAudio (audio I/O)
- RPi.GPIO (hardware control)
- INMP441 microphone (I2S)
- MAX98357A amplifier (I2S)

**Infrastructure:**
- Debian 13 (server OS)
- Raspberry Pi OS (client OS)
- Cloudflare (CDN/SSL/DNS)
- systemd (process management)

---

**All documentation reflects the current client-server architecture.** For migration from the old monolithic version, see [MIGRATION.md](../MIGRATION.md).
