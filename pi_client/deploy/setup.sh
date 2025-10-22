#!/bin/bash
set -e

# Voice Assistant Client Setup Script
# This script handles fresh installs, updates, and fixes
# Run from the cloned Git repository directory

echo "==========================================="
echo "Voice Assistant Client Setup"
echo "==========================================="
echo ""

# Check not running as root
if [[ $EUID -eq 0 ]]; then
   echo "❌ Do not run this script as root. Run as pi user." 
   exit 1
fi

# Configuration
INSTALL_DIR="$HOME/javia_client"
VENV_DIR="$HOME/venvs/pi_client"

# Determine source directory (must be run from git repo)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLIENT_DIR="$(dirname "$SCRIPT_DIR")"

# Validate we're in the right place
if [ ! -f "$CLIENT_DIR/client.py" ]; then
    echo "❌ ERROR: Cannot find client.py!"
    echo "Expected to find client.py at: $CLIENT_DIR/client.py"
    echo ""
    echo "Please ensure you:"
    echo "  1. Cloned the repository: git clone https://github.com/YOUR_USERNAME/voice_assistant.git"
    echo "  2. Are running this script from: /tmp/voice_assistant/pi_client/deploy/setup.sh"
    echo ""
    exit 1
fi

echo "✓ Found client files at: $CLIENT_DIR"
echo ""

# ==================== STEP 1: SYSTEM DEPENDENCIES ====================
echo "[1/8] Checking system dependencies..."

# Check if packages are already installed to avoid unnecessary updates
PACKAGES_TO_INSTALL=""
for pkg in python3-pyaudio python3-rpi.gpio python3-requests python3-numpy python3-pip; do
    if ! dpkg -l | grep -q "^ii  $pkg "; then
        PACKAGES_TO_INSTALL="$PACKAGES_TO_INSTALL $pkg"
    fi
done

if [ -n "$PACKAGES_TO_INSTALL" ]; then
    echo "Installing missing packages:$PACKAGES_TO_INSTALL"
    sudo apt update
    sudo apt install -y $PACKAGES_TO_INSTALL
    echo "✓ System dependencies installed"
else
    echo "✓ All system dependencies already installed"
fi

echo ""

# ==================== STEP 2: STOP SERVICE ====================
echo "[2/8] Stopping service (if running)..."
sudo systemctl stop voice-assistant-client.service 2>/dev/null || true
echo "✓ Service stopped"
echo ""

# ==================== STEP 3: CREATE DIRECTORIES ====================
echo "[3/8] Setting up directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$(dirname "$VENV_DIR")"
echo "✓ Directories ready"
echo ""

# ==================== STEP 4: COPY/UPDATE FILES ====================
echo "[4/8] Copying latest client files..."
cd "$INSTALL_DIR"

# Backup .env if it exists
ENV_BACKUP=""
if [ -f "$INSTALL_DIR/.env" ]; then
    ENV_BACKUP="/tmp/javia_client_env_backup_$$"
    cp "$INSTALL_DIR/.env" "$ENV_BACKUP"
    echo "✓ Backed up existing .env file"
fi

# Copy all files from client directory
echo "Copying files from: $CLIENT_DIR"
rsync -av --exclude='deploy' --exclude='__pycache__' --exclude='*.pyc' "$CLIENT_DIR/" "$INSTALL_DIR/"
echo "✓ Files copied successfully"
echo ""

# ==================== STEP 5: VIRTUAL ENVIRONMENT ====================
echo "[5/8] Setting up Python virtual environment..."

if [ -d "$VENV_DIR" ]; then
    echo "✓ Virtual environment already exists, updating..."
else
    echo "Creating new virtual environment..."
    python3 -m venv --system-site-packages "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
pip install --upgrade pip > /dev/null 2>&1
pip install python-dotenv > /dev/null 2>&1
echo "✓ Virtual environment ready"
echo ""

# ==================== STEP 6: CONFIGURE .ENV ====================
echo "[6/8] Configuring environment..."

# Create .env from template if it doesn't exist
if [ ! -f "$INSTALL_DIR/.env" ]; then
    if [ -f "$INSTALL_DIR/env.example" ]; then
        cp "$INSTALL_DIR/env.example" "$INSTALL_DIR/.env"
        echo "✓ Created .env from template"
    else
        echo "❌ ERROR: env.example not found!"
        exit 1
    fi
fi

# Restore backed up .env values if available
if [ -n "$ENV_BACKUP" ] && [ -f "$ENV_BACKUP" ]; then
    echo ""
    echo "Found existing configuration!"
    echo ""
    echo "Options:"
    echo "  1) Keep existing configuration (recommended for updates)"
    echo "  2) Enter new configuration values"
    echo ""
    read -p "Choose option [1-2]: " CONFIG_CHOICE
    
    if [ "$CONFIG_CHOICE" = "1" ]; then
        cp "$ENV_BACKUP" "$INSTALL_DIR/.env"
        echo "✓ Restored existing configuration"
        rm -f "$ENV_BACKUP"
    else
        rm -f "$ENV_BACKUP"
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
        
        # Update .env file
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
    fi
else
    # First time setup - require values
    echo ""
    echo "==================================="
    echo "Client Configuration (REQUIRED)"
    echo "==================================="
    echo ""
    
    # Require SERVER_URL
    while true; do
        echo "Enter your SERVER_URL (e.g., https://yourdomain.com):"
        read -p "SERVER_URL: " SERVER_URL_INPUT
        if [ -n "$SERVER_URL_INPUT" ]; then
            break
        else
            echo "❌ SERVER_URL cannot be empty. Please enter a valid URL."
            echo ""
        fi
    done
    
    echo ""
    
    # Require CLIENT_API_KEY
    while true; do
        echo "Enter your CLIENT_API_KEY (must match server's SERVER_API_KEY):"
        read -p "CLIENT_API_KEY: " CLIENT_API_KEY_INPUT
        if [ -n "$CLIENT_API_KEY_INPUT" ]; then
            break
        else
            echo "❌ CLIENT_API_KEY cannot be empty. Please enter a valid API key."
            echo ""
        fi
    done
    
    # Update .env file
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
fi

# Secure the .env file
chmod 600 "$INSTALL_DIR/.env"

# Validate configuration
echo ""
echo "Validating configuration..."
cd "$INSTALL_DIR"
python3 << 'EOF'
import os
from dotenv import load_dotenv

# Load the .env file from current directory
load_dotenv('.env')

server_url = os.getenv('SERVER_URL', '')
client_api_key = os.getenv('CLIENT_API_KEY', '')

errors = []

# Check SERVER_URL
if not server_url or server_url in ['https://yourdomain.com', 'http://localhost:8000']:
    errors.append("SERVER_URL is not configured or using default value")

# Check CLIENT_API_KEY  
if not client_api_key or client_api_key in ['YOUR_API_KEY_HERE', 'YOUR_SECURE_API_KEY_HERE']:
    errors.append("CLIENT_API_KEY is not configured or using default value")

if errors:
    print("❌ Configuration errors found:")
    for error in errors:
        print(f"  - {error}")
    exit(1)
else:
    print("✓ Configuration validated successfully")
EOF

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Configuration validation failed!"
    echo "Please check your .env file: $INSTALL_DIR/.env"
    exit 1
fi

echo "✓ Environment configured"
echo ""

# ==================== STEP 7: AUDIO GROUP & SYSTEMD ====================
echo "[7/8] Setting up system permissions and service..."

# Add user to audio group if not already
if ! groups $USER | grep -q "\baudio\b"; then
    sudo usermod -a -G audio $USER
    echo "✓ User added to audio group"
    NEEDS_LOGOUT=true
else
    echo "✓ User already in audio group"
    NEEDS_LOGOUT=false
fi

# Create systemd service file
echo "Creating systemd service..."
cat > /tmp/voice-assistant-client.service <<EOF
[Unit]
Description=Voice Assistant Client
After=network.target sound.target

[Service]
Type=simple
User=$USER
Group=audio
SupplementaryGroups=audio gpio
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$VENV_DIR/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="PYTHONUNBUFFERED=1"
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$VENV_DIR/bin/python3 $INSTALL_DIR/client.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Audio device access
DeviceAllow=/dev/snd

[Install]
WantedBy=multi-user.target
EOF

sudo mv /tmp/voice-assistant-client.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable voice-assistant-client.service
echo "✓ Systemd service configured"
echo ""

# ==================== STEP 8: START SERVICE ====================
echo "[8/8] Starting service..."
sudo systemctl start voice-assistant-client.service

# Wait for service to initialize
sleep 2

# Check if service is actually running
echo ""
echo "Checking service status..."
if systemctl is-active --quiet voice-assistant-client.service; then
    echo "✅ Service is RUNNING successfully!"
    echo ""
    echo "==========================================="
    echo "Setup Complete!"
    echo "==========================================="
    echo ""
    
    if [ "$NEEDS_LOGOUT" = true ]; then
        echo "⚠️  IMPORTANT: You must log out and log back in for audio group permissions to take effect!"
        echo ""
    fi
    
    echo "✅ Client is ready! You can now press the button to use the voice assistant."
    echo ""
else
    echo "❌ Service FAILED to start!"
    echo ""
    echo "==========================================="
    echo "Setup Failed - Service Not Running"
    echo "==========================================="
    echo ""
    echo "Error logs (last 20 lines):"
    echo "-------------------------------------"
    sudo journalctl -u voice-assistant-client.service -n 20 --no-pager
    echo "-------------------------------------"
    echo ""
    echo "Common issues:"
    echo "  - Invalid SERVER_URL or CLIENT_API_KEY in .env"
    echo "  - Missing audio group permissions (log out and back in)"
    echo "  - Hardware issues (GPIO, audio devices)"
    echo ""
    echo "To fix:"
    echo "  1. Check the error logs above"
    echo "  2. Edit .env if needed: nano $INSTALL_DIR/.env"
    echo "  3. Run this script again: bash $SCRIPT_DIR/setup.sh"
    echo ""
    exit 1
fi

echo "Service Status:"
sudo systemctl status voice-assistant-client.service --no-pager -l
echo ""

echo "View live logs:"
echo "  sudo journalctl -u voice-assistant-client.service -f"
echo ""

echo "Check recent logs:"
echo "  sudo journalctl -u voice-assistant-client.service -n 50"
echo ""

echo "Restart service:"
echo "  sudo systemctl restart voice-assistant-client.service"
echo ""

echo "Stop service:"
echo "  sudo systemctl stop voice-assistant-client.service"
echo ""

echo "Manual testing (if needed):"
echo "  source $VENV_DIR/bin/activate"
echo "  cd $INSTALL_DIR"
echo "  python3 client.py"
echo ""

echo "==========================================="
echo "You can run this script again anytime to update!"
echo "==========================================="
echo ""

