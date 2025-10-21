#!/bin/bash
set -e

# Voice Assistant Client Installation Script for Raspberry Pi
# Run as the pi user (not root)

echo "==========================================="
echo "Voice Assistant Client Installation"
echo "==========================================="
echo ""

# Check not running as root
if [[ $EUID -eq 0 ]]; then
   echo "Do not run this script as root. Run as pi user." 
   exit 1
fi

# Configuration
INSTALL_DIR="$HOME/voice_assistant_client"
VENV_DIR="$HOME/venvs/pi_client"

echo "[1/6] Installing system dependencies..."
sudo apt update
sudo apt install -y python3-pyaudio python3-rpi.gpio python3-requests python3-numpy python3-pip

echo ""
echo "[2/6] Creating installation directory..."
mkdir -p $INSTALL_DIR
cd $INSTALL_DIR

echo ""
echo "[3/6] Copying client files..."
# This script expects to be run from the cloned Git repository
# Expected location: /tmp/voice_assistant/pi_client/deploy/
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLIENT_DIR="$(dirname "$SCRIPT_DIR")"

if [ -f "$CLIENT_DIR/client.py" ]; then
    echo "Copying files from: $CLIENT_DIR"
    cp -r "$CLIENT_DIR"/* $INSTALL_DIR/
    echo "Files copied successfully"
else
    echo "ERROR: Cannot find client files!"
    echo "Expected to find client.py at: $CLIENT_DIR/client.py"
    echo ""
    echo "Please ensure you:"
    echo "  1. Cloned the repository: git clone https://github.com/YOUR_USERNAME/voice_assistant.git"
    echo "  2. Are running this script from: /tmp/voice_assistant/pi_client/deploy/"
    echo ""
    exit 1
fi

echo ""
echo "[4/6] Creating Python virtual environment..."
python3 -m venv --system-site-packages $VENV_DIR
source $VENV_DIR/bin/activate
pip install --upgrade pip
pip install python-dotenv

echo ""
echo "[5/6] Setting up environment file..."
if [ ! -f "$INSTALL_DIR/.env" ]; then
    cp env.example .env
    echo ""
    echo "IMPORTANT: Edit $INSTALL_DIR/.env and set:"
    echo "  - SERVER_URL (e.g., https://yourdomain.com)"
    echo "  - CLIENT_API_KEY (must match server's SERVER_API_KEY)"
    echo ""
    read -p "Press Enter after you've edited the .env file..."
else
    echo ".env file already exists"
fi

# Secure the .env file
chmod 600 $INSTALL_DIR/.env

echo ""
echo "[6/6] Setting up systemd service..."
cat > /tmp/voice-assistant-client.service <<EOF
[Unit]
Description=Voice Assistant Client
After=network.target sound.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$VENV_DIR/bin"
ExecStart=$VENV_DIR/bin/python3 $INSTALL_DIR/client.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo mv /tmp/voice-assistant-client.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable voice-assistant-client.service

echo ""
echo "==========================================="
echo "Installation Options:"
echo "==========================================="
echo ""
echo "Option 1: Start service now (runs on boot automatically)"
echo "  sudo systemctl start voice-assistant-client.service"
echo "  sudo systemctl status voice-assistant-client.service"
echo ""
echo "Option 2: Run manually for testing"
echo "  source $VENV_DIR/bin/activate"
echo "  cd $INSTALL_DIR"
echo "  python3 client.py"
echo ""
echo "View logs:"
echo "  sudo journalctl -u voice-assistant-client.service -f"
echo ""
echo "==========================================="
echo "Installation Complete!"
echo "==========================================="

