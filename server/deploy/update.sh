#!/bin/bash
set -e

# Voice Assistant Server Update Script
# Run as root or with sudo on the server

echo "========================================="
echo "Voice Assistant Server Update"
echo "========================================="
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root or with sudo" 
   exit 1
fi

# Configuration
INSTALL_DIR="/opt/javia"
VENV_DIR="$INSTALL_DIR/venv"
TEMP_DIR="/tmp/javia_update"
REPO_URL="https://github.com/shreyashguptas/javia.git"

echo "[1/7] Backing up current .env file..."
if [ -f "$INSTALL_DIR/.env" ]; then
    cp "$INSTALL_DIR/.env" "/tmp/javia_env_backup"
    echo "✓ Backed up .env file"
else
    echo "⚠ No .env file found (will need to configure)"
fi

echo ""
echo "[2/7] Fetching latest code from GitHub..."
# Remove old temp directory if it exists
rm -rf "$TEMP_DIR"

# Clone fresh copy
git clone "$REPO_URL" "$TEMP_DIR"
echo "✓ Code fetched successfully"

echo ""
echo "[3/7] Stopping service..."
systemctl stop voice-assistant-server.service
echo "✓ Service stopped"

echo ""
echo "[4/7] Updating application files..."
# Copy server files from the repo (exclude venv and .env)
cd "$TEMP_DIR/server"
rsync -av --exclude='venv' --exclude='.env' --exclude='__pycache__' ./ "$INSTALL_DIR/"
echo "✓ Files updated"

echo ""
echo "[5/7] Restoring .env file..."
if [ -f "/tmp/javia_env_backup" ]; then
    cp "/tmp/javia_env_backup" "$INSTALL_DIR/.env"
    chmod 600 "$INSTALL_DIR/.env"
    echo "✓ .env file restored"
else
    echo "⚠ No backup .env found - you may need to reconfigure"
fi

echo ""
echo "[6/7] Updating Python dependencies..."
cd "$INSTALL_DIR"
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r requirements.txt
echo "✓ Dependencies updated"

echo ""
echo "[7/7] Starting service..."
chown -R voiceassistant:voiceassistant "$INSTALL_DIR"
systemctl start voice-assistant-server.service
echo "✓ Service started"

echo ""
echo "Cleaning up..."
rm -rf "$TEMP_DIR"
rm -f "/tmp/javia_env_backup"

echo ""
echo "========================================="
echo "Update Complete!"
echo "========================================="
echo ""
echo "Service Status:"
systemctl status voice-assistant-server.service --no-pager

echo ""
echo "Recent Logs:"
journalctl -u voice-assistant-server.service -n 20 --no-pager

echo ""
echo "To view live logs, run:"
echo "  journalctl -u voice-assistant-server.service -f"
echo ""

