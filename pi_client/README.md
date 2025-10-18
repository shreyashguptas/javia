# Voice Assistant Raspberry Pi Client

Lightweight client for recording audio and communicating with voice assistant server.

## Quick Start

### 1. Hardware Setup

Ensure hardware is connected (see [../docs/HARDWARE.md](../docs/HARDWARE.md)):
- INMP441 microphone
- MAX98357A amplifier
- Speaker
- Push button

### 2. Install Dependencies

```bash
# Install system packages
sudo apt install -y python3-pyaudio python3-rpi.gpio python3-requests python3-numpy

# Create virtual environment
python3 -m venv --system-site-packages ~/venvs/pi_client
source ~/venvs/pi_client/bin/activate
pip install python-dotenv
```

### 3. Configure Client

```bash
cp env.example .env
nano .env
```

Set the following:
```env
SERVER_URL=https://yourdomain.com
CLIENT_API_KEY=your_api_key_here
```

**Important**: `CLIENT_API_KEY` must match `SERVER_API_KEY` on the server!

Secure the configuration:
```bash
chmod 600 .env
```

### 4. Run Client

```bash
source ~/venvs/pi_client/bin/activate
python3 client.py
```

### 5. Test Client

```bash
python3 test_client.py
```

## Auto-Start on Boot

```bash
cd deploy
bash install_client.sh
sudo systemctl enable voice-assistant-client.service
```

## Documentation

- [Architecture](../docs/ARCHITECTURE.md)
- [Deployment](../docs/DEPLOYMENT.md)
- [Hardware Setup](../docs/HARDWARE.md)
- [Troubleshooting](../docs/TROUBLESHOOTING.md)

## Project Structure

```
pi_client/
├── client.py           # Main application
├── requirements.txt    # Dependencies
├── test_client.py      # Test suite
└── deploy/
    └── install_client.sh  # Installation script
```

