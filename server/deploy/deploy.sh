#!/bin/bash
set -e

# Voice Assistant Server Deployment Script for Debian 13
# Run as root or with sudo

echo "=================================="
echo "Voice Assistant Server Deployment"
echo "=================================="
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root or with sudo" 
   exit 1
fi

# Configuration
INSTALL_DIR="/opt/voice_assistant"
VENV_DIR="$INSTALL_DIR/venv"
SERVICE_USER="voiceassistant"
SERVICE_GROUP="voiceassistant"

echo "[1/8] Installing system dependencies..."
apt update
apt install -y python3 python3-pip python3-venv nginx git

echo ""
echo "[2/8] Creating service user..."
if ! id -u $SERVICE_USER > /dev/null 2>&1; then
    useradd -r -s /bin/false -d $INSTALL_DIR $SERVICE_USER
    echo "Created user: $SERVICE_USER"
else
    echo "User $SERVICE_USER already exists"
fi

echo ""
echo "[3/8] Creating installation directory..."
mkdir -p $INSTALL_DIR
cd $INSTALL_DIR

echo ""
echo "[4/8] Copying application files..."
# Note: This assumes the script is run from the deployment directory
# Adjust paths as needed for your deployment method
if [ -d "/tmp/voice_assistant_deploy" ]; then
    cp -r /tmp/voice_assistant_deploy/server/* $INSTALL_DIR/
else
    echo "WARNING: Source files not found in /tmp/voice_assistant_deploy"
    echo "Please manually copy the server files to $INSTALL_DIR"
    echo "Expected structure:"
    echo "  $INSTALL_DIR/main.py"
    echo "  $INSTALL_DIR/config.py"
    echo "  $INSTALL_DIR/requirements.txt"
    echo "  $INSTALL_DIR/services/"
    echo "  $INSTALL_DIR/middleware/"
    echo "  $INSTALL_DIR/models/"
fi

echo ""
echo "[5/8] Creating Python virtual environment..."
python3 -m venv $VENV_DIR
source $VENV_DIR/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "[6/8] Setting up environment file..."
if [ ! -f "$INSTALL_DIR/.env" ]; then
    echo "Creating .env file from template..."
    cp env.example .env
    echo ""
    echo "IMPORTANT: Edit $INSTALL_DIR/.env and set:"
    echo "  - GROQ_API_KEY"
    echo "  - SERVER_API_KEY (generate a secure random key)"
    echo ""
    read -p "Press Enter after you've edited the .env file..."
else
    echo ".env file already exists"
fi

echo ""
echo "[7/8] Setting permissions..."
chown -R $SERVICE_USER:$SERVICE_GROUP $INSTALL_DIR
chmod 600 $INSTALL_DIR/.env

echo ""
echo "[8/8] Installing systemd service..."
cp deploy/systemd/voice-assistant-server.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable voice-assistant-server.service
systemctl start voice-assistant-server.service

echo ""
echo "=================================="
echo "Service Status:"
echo "=================================="
systemctl status voice-assistant-server.service --no-pager

echo ""
echo "=================================="
echo "Next Steps:"
echo "=================================="
echo ""
echo "1. Configure Nginx:"
echo "   - Edit deploy/nginx/voice-assistant.conf"
echo "   - Update server_name to your domain"
echo "   - Update SSL certificate paths"
echo "   - Copy to Nginx: cp deploy/nginx/voice-assistant.conf /etc/nginx/sites-available/"
echo "   - Enable site: ln -s /etc/nginx/sites-available/voice-assistant.conf /etc/nginx/sites-enabled/"
echo "   - Test config: nginx -t"
echo "   - Reload Nginx: systemctl reload nginx"
echo ""
echo "2. Configure Cloudflare:"
echo "   - Set DNS A record pointing to this server's IP"
echo "   - Enable SSL/TLS Full (strict) mode"
echo "   - Create Origin Certificate and install on server"
echo "   - Enable DDoS protection"
echo ""
echo "3. Test the server:"
echo "   - curl http://localhost:8000/health"
echo "   - Check logs: journalctl -u voice-assistant-server.service -f"
echo ""
echo "4. Update Raspberry Pi client:"
echo "   - Set SERVER_URL to https://yourdomain.com"
echo "   - Set CLIENT_API_KEY to match SERVER_API_KEY"
echo ""
echo "=================================="
echo "Deployment Complete!"
echo "=================================="

