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
INSTALL_DIR="/opt/javia"
VENV_DIR="$INSTALL_DIR/venv"
SERVICE_USER="voiceassistant"
SERVICE_GROUP="voiceassistant"

echo "[1/9] Installing system dependencies..."
apt update
apt install -y python3 python3-pip python3-venv nginx git

echo ""
echo "[2/9] Creating service user..."
if ! id -u $SERVICE_USER > /dev/null 2>&1; then
    useradd -r -s /bin/false -d $INSTALL_DIR $SERVICE_USER
    echo "Created user: $SERVICE_USER"
else
    echo "User $SERVICE_USER already exists"
fi

echo ""
echo "[3/9] Determining source directory..."
# This script expects to be run from the cloned Git repository
# Expected location: /tmp/javia/server/deploy/
# Must resolve paths BEFORE changing directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(dirname "$SCRIPT_DIR")"

echo ""
echo "[4/9] Creating installation directory..."
mkdir -p $INSTALL_DIR
cd $INSTALL_DIR

echo ""
echo "[5/9] Copying application files..."

if [ -f "$SERVER_DIR/main.py" ]; then
    echo "Copying files from: $SERVER_DIR"
    cp -r "$SERVER_DIR"/* $INSTALL_DIR/
    echo "Files copied successfully"
else
    echo "ERROR: Cannot find server files!"
    echo "Expected to find main.py at: $SERVER_DIR/main.py"
    echo ""
    echo "Please ensure you:"
    echo "  1. Cloned the repository: git clone https://github.com/shreyashguptas/javia.git"
    echo "  2. Are running this script from: /tmp/javia/server/deploy/"
    echo ""
    exit 1
fi

echo ""
echo "[6/9] Creating Python virtual environment..."
python3 -m venv $VENV_DIR
source $VENV_DIR/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "[7/9] Setting up environment file..."

# Create .env from template if it doesn't exist
if [ ! -f "$INSTALL_DIR/.env" ]; then
    echo "Creating .env file from template..."
    cp env.example .env
else
    echo ".env file already exists, will update configuration..."
fi

echo ""
# Prompt for GROQ API Key
echo "==================================="
echo "API Configuration"
echo "==================================="
echo ""
echo "Enter your GROQ_API_KEY (or press Enter to keep existing value):"
read -p "GROQ_API_KEY: " GROQ_KEY

# Generate SERVER_API_KEY using uuid7
echo ""
echo "Generating SERVER_API_KEY using UUID7..."
# Install uuid6 package (provides uuid7 support) in a temporary way
python3 -c "import sys; import subprocess; subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', 'uuid6'])" 2>/dev/null || true
SERVER_KEY=$(python3 -c "from uuid6 import uuid7; print(str(uuid7()))")

echo ""
echo "==================================="
echo "GENERATED SERVER_API_KEY (SAVE THIS!):"
echo "$SERVER_KEY"
echo "==================================="
echo ""
echo "IMPORTANT: Copy and save the SERVER_API_KEY above!"
echo "You will need it to configure the Raspberry Pi client."
echo ""
read -p "Press Enter after you've saved the SERVER_API_KEY..."

# Update .env file with the values
GROQ_KEY="$GROQ_KEY" SERVER_KEY="$SERVER_KEY" python3 << 'EOF'
import os
import re

groq_key = os.environ.get('GROQ_KEY', '').strip()
server_key = os.environ['SERVER_KEY']

with open('.env', 'r') as f:
    content = f.read()

# Replace GROQ_API_KEY only if user provided one
if groq_key:
    content = re.sub(r'GROQ_API_KEY=.*', f'GROQ_API_KEY={groq_key}', content)
    print("✓ Updated GROQ_API_KEY")
else:
    print("⊘ Kept existing GROQ_API_KEY value")

# Always replace SERVER_API_KEY
content = re.sub(r'SERVER_API_KEY=.*', f'SERVER_API_KEY={server_key}', content)
print("✓ Updated SERVER_API_KEY")

with open('.env', 'w') as f:
    f.write(content)
EOF

echo ""
echo "Environment file configured successfully!"

echo ""
echo "[8/9] Setting permissions..."
chown -R $SERVICE_USER:$SERVICE_GROUP $INSTALL_DIR
chmod 600 $INSTALL_DIR/.env

echo ""
echo "[9/9] Installing systemd service..."
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

