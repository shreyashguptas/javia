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
INSTALL_DIR="$HOME/javia_client"
VENV_DIR="$HOME/venvs/pi_client"

echo "[1/6] Installing system dependencies..."
sudo apt update
sudo apt install -y python3-pyaudio python3-rpi.gpio python3-requests python3-numpy python3-pip

echo ""
echo "[2/6] Determining source directory..."
# This script expects to be run from the cloned Git repository
# Expected location: /tmp/voice_assistant/pi_client/deploy/
# Must resolve paths BEFORE changing directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLIENT_DIR="$(dirname "$SCRIPT_DIR")"

echo ""
echo "[3/6] Creating installation directory..."
mkdir -p $INSTALL_DIR
cd $INSTALL_DIR

echo ""
echo "[4/6] Copying client files..."

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
echo "[5/6] Creating Python virtual environment..."
python3 -m venv --system-site-packages $VENV_DIR
source $VENV_DIR/bin/activate
pip install --upgrade pip
pip install python-dotenv

echo ""
echo "[6/6] Setting up environment file..."

# Create .env from template if it doesn't exist
if [ ! -f "$INSTALL_DIR/.env" ]; then
    echo "Creating .env file from template..."
    cp env.example .env
else
    echo ".env file already exists, will update configuration..."
fi

echo ""
echo "==================================="
echo "Client Configuration"
echo "==================================="
echo ""
echo "Enter your SERVER_URL (e.g., https://yourdomain.com):"
read -p "SERVER_URL: " SERVER_URL_INPUT

echo ""
echo "Enter your CLIENT_API_KEY (must match server's SERVER_API_KEY):"
read -p "CLIENT_API_KEY: " CLIENT_API_KEY_INPUT

# Update .env file with the values
SERVER_URL_INPUT="$SERVER_URL_INPUT" CLIENT_API_KEY_INPUT="$CLIENT_API_KEY_INPUT" python3 << 'EOF'
import os
import re

server_url = os.environ.get('SERVER_URL_INPUT', '').strip()
client_api_key = os.environ.get('CLIENT_API_KEY_INPUT', '').strip()

with open('.env', 'r') as f:
    content = f.read()

# Replace SERVER_URL if provided
if server_url:
    content = re.sub(r'SERVER_URL=.*', f'SERVER_URL={server_url}', content)
    print("✓ Updated SERVER_URL")
else:
    print("⊘ Kept existing SERVER_URL value")

# Replace CLIENT_API_KEY if provided
if client_api_key:
    content = re.sub(r'CLIENT_API_KEY=.*', f'CLIENT_API_KEY={client_api_key}', content)
    print("✓ Updated CLIENT_API_KEY")
else:
    print("⊘ Kept existing CLIENT_API_KEY value")

with open('.env', 'w') as f:
    f.write(content)
EOF

echo ""
echo "Environment file configured successfully!"

# Secure the .env file
chmod 600 $INSTALL_DIR/.env

echo ""
echo "[7/7] Setting up systemd service..."
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

