# Raspberry Pi Client Deployment

This directory contains scripts for deploying and maintaining the Voice Assistant client on Raspberry Pi.

## 📁 Directory Structure

```
deploy/
├── README.md                 # This file - deployment overview
├── install_client.sh         # Initial client installation (run once)
└── update/                   # Update scripts (run after code changes)
    ├── update.sh            # Client update script
    └── README.md            # Update documentation
```

## 🚀 Initial Installation

**Run this ONCE when first setting up the Raspberry Pi:**

```bash
# On your Raspberry Pi
cd /tmp
git clone https://github.com/shreyashguptas/javia.git
cd javia/pi_client/deploy
bash install_client.sh
```

This script will:
- Install system dependencies (PyAudio, GPIO, etc.)
- Create Python virtual environment
- Copy client files to `~/javia_client`
- Configure .env file (prompts for SERVER_URL and CLIENT_API_KEY)
- Install systemd service
- Enable autostart on boot

**Prerequisites:**
- Hardware must be wired correctly (see docs/HARDWARE.md)
- I2S must be enabled in `/boot/firmware/config.txt`
- Server must be deployed and accessible

## 🔄 Updating After Code Changes

**Run this whenever you push code changes to GitHub:**

```bash
# SSH to your Raspberry Pi
ssh user@pi-zero-2-w-1.local

# Run the update script (as regular user, NOT sudo)
bash ~/javia_client/deploy/update/update.sh
```

The update script will:
- Fetch latest code from GitHub
- Update all application files
- Preserve your `.env` configuration
- **Prompt for new SERVER_API_KEY** (in case it changed on server)
- Update Python dependencies (only if requirements.txt changed)
- Restart the service

See **[update/README.md](update/README.md)** for detailed update documentation.

## 📝 Quick Reference

### When to Use Each Script

| Script | When to Use | Frequency |
|--------|-------------|-----------|
| `install_client.sh` | First-time Pi setup | Once |
| `update/update.sh` | After pushing code changes | Every update |

### Important Paths

- **Installation directory**: `~/javia_client`
- **Virtual environment**: `~/venvs/pi_client`
- **Configuration**: `~/javia_client/.env`
- **Service file**: `/etc/systemd/system/voice-assistant-client.service`

### Common Commands

```bash
# View service status
sudo systemctl status voice-assistant-client.service

# View logs (live)
sudo journalctl -u voice-assistant-client.service -f

# View last 50 log lines
sudo journalctl -u voice-assistant-client.service -n 50

# Restart service
sudo systemctl restart voice-assistant-client.service

# Stop service
sudo systemctl stop voice-assistant-client.service

# Start service
sudo systemctl start voice-assistant-client.service

# Test manually (stop service first)
sudo systemctl stop voice-assistant-client.service
source ~/venvs/pi_client/bin/activate
cd ~/javia_client
python3 client.py
```

### Test Audio Hardware

```bash
# List audio devices
arecord -l
aplay -l

# Test recording (5 seconds)
arecord -D plughw:0,0 -c1 -r 48000 -f S16_LE -d 5 test.wav

# Test playback
aplay -D plughw:0,0 test.wav
```

## 🔑 API Key Synchronization

The update script will prompt you to enter the SERVER_API_KEY from your server. This ensures the Pi client can authenticate with the server.

**To find your SERVER_API_KEY on the server:**
```bash
ssh user@your-server-ip
sudo cat /opt/javia/.env | grep SERVER_API_KEY
```

Copy the key and paste it when the Pi update script prompts you.

## 🔒 Security Notes

- ✅ `.env` file contains SERVER_URL and API key
- ✅ File permissions set to 600 (owner read/write only)
- ✅ Service runs as your user (not root)
- ✅ API keys never committed to git

## 📚 Documentation

- **[update/README.md](update/README.md)** - Detailed update instructions
- **[../../docs/DEPLOYMENT.md](../../docs/DEPLOYMENT.md)** - Complete deployment guide
- **[../../docs/HARDWARE.md](../../docs/HARDWARE.md)** - Hardware wiring guide
- **[../../docs/TROUBLESHOOTING.md](../../docs/TROUBLESHOOTING.md)** - Common issues

