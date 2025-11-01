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
    echo "  1. Cloned the repository: git clone https://github.com/shreyashguptas/javia.git"
    echo "  2. Are running this script from: /tmp/javia/pi_client/deploy/setup.sh"
    echo ""
    exit 1
fi

echo "✓ Found client files at: $CLIENT_DIR"
echo ""

# ==================== STEP 1: SYSTEM DEPENDENCIES ====================
echo "[1/8] Checking system dependencies..."

# Check if packages are already installed to avoid unnecessary updates
PACKAGES_TO_INSTALL=""
for pkg in python3-pyaudio python3-gpiozero python3-requests python3-numpy python3-pip libopus0 libopus-dev; do
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
echo "Installing Python dependencies from requirements.txt..."
pip install -r "$INSTALL_DIR/requirements.txt"
echo "✓ Virtual environment ready with all dependencies"
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
        
        # Read current values from .env file using Python
        read -r CURRENT_SERVER_URL CURRENT_CLIENT_API_KEY CURRENT_DEVICE_TIMEZONE CURRENT_SUPABASE_URL CURRENT_SUPABASE_KEY < <(python3 << 'EOF'
import re

try:
    with open('.env', 'r') as f:
        content = f.read()
    
    def get_value(key):
        match = re.search(f'^{key}=(.*)$', content, re.MULTILINE)
        return match.group(1).strip() if match else ''
    
    server_url = get_value('SERVER_URL')
    client_api_key = get_value('CLIENT_API_KEY')
    device_timezone = get_value('DEVICE_TIMEZONE')
    supabase_url = get_value('SUPABASE_URL')
    supabase_key = get_value('SUPABASE_KEY')
    
    print(f"{server_url} {client_api_key} {device_timezone} {supabase_url} {supabase_key}")
except:
    print("     ")
EOF
)
        
        echo "Enter your SERVER_URL (e.g., https://yourdomain.com):"
        if [ -n "$CURRENT_SERVER_URL" ]; then
            echo "Current value: $CURRENT_SERVER_URL"
        else
            echo "Current value: Not set"
        fi
        read -p "SERVER_URL (press Enter to keep current): " SERVER_URL_INPUT
        if [ -z "$SERVER_URL_INPUT" ]; then
            SERVER_URL_INPUT="$CURRENT_SERVER_URL"
        fi
        
        echo ""
        echo "Enter your CLIENT_API_KEY (must match server's SERVER_API_KEY):"
        if [ -n "$CURRENT_CLIENT_API_KEY" ]; then
            echo "Current value: $CURRENT_CLIENT_API_KEY"
        else
            echo "Current value: Not set"
        fi
        read -p "CLIENT_API_KEY (press Enter to keep current): " CLIENT_API_KEY_INPUT
        if [ -z "$CLIENT_API_KEY_INPUT" ]; then
            CLIENT_API_KEY_INPUT="$CURRENT_CLIENT_API_KEY"
        fi
        
        echo ""
        echo "Select your DEVICE_TIMEZONE:"
        if [ -n "$CURRENT_DEVICE_TIMEZONE" ]; then
            echo "Current value: $CURRENT_DEVICE_TIMEZONE"
        else
            echo "Current value: UTC"
        fi
        echo ""
        
        # Show timezone selector
        TIMEZONE_INPUT=$(CURRENT_DEVICE_TIMEZONE="$CURRENT_DEVICE_TIMEZONE" python3 << 'TZEOF'
import os
import sys

timezones = [
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Phoenix",
    "America/Los_Angeles",
    "America/Anchorage",
    "America/Honolulu",
    "America/Toronto",
    "America/Vancouver",
    "America/Edmonton",
    "America/Winnipeg",
    "America/Halifax",
    "America/Mexico_City",
    "America/Monterrey",
    "America/Tijuana",
    "UTC"
]

current = os.environ.get('CURRENT_DEVICE_TIMEZONE', 'UTC')
if not current:
    current = 'UTC'

try:
    current_index = timezones.index(current)
except ValueError:
    current_index = timezones.index('UTC')

# Simple selection without curses
print("Available Timezones:")
for i, tz in enumerate(timezones):
    marker = " → " if i == current_index else "   "
    print(f"{marker}{i+1}. {tz}")

print(f"\nCurrent: {current}")
choice = input(f"\nEnter number (1-{len(timezones)}), or press Enter to keep current: ")

if choice.strip():
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(timezones):
            print(timezones[idx])
        else:
            print(current)
    except ValueError:
        print(current)
else:
    print(current)
TZEOF
)
        
        echo ""
        echo "Enter your SUPABASE_URL (for OTA updates):"
        if [ -n "$CURRENT_SUPABASE_URL" ]; then
            echo "Current value: $CURRENT_SUPABASE_URL"
        else
            echo "Current value: Not set"
        fi
        read -p "SUPABASE_URL (press Enter to keep current): " SUPABASE_URL_INPUT
        if [ -z "$SUPABASE_URL_INPUT" ]; then
            SUPABASE_URL_INPUT="$CURRENT_SUPABASE_URL"
        fi
        
        echo ""
        echo "Enter your SUPABASE_KEY (anon key for OTA updates):"
        if [ -n "$CURRENT_SUPABASE_KEY" ]; then
            echo "Current value: $CURRENT_SUPABASE_KEY"
        else
            echo "Current value: Not set"
        fi
        read -p "SUPABASE_KEY (press Enter to keep current): " SUPABASE_KEY_INPUT
        if [ -z "$SUPABASE_KEY_INPUT" ]; then
            SUPABASE_KEY_INPUT="$CURRENT_SUPABASE_KEY"
        fi
        
        # Update .env file
        SERVER_URL_INPUT="$SERVER_URL_INPUT" CLIENT_API_KEY_INPUT="$CLIENT_API_KEY_INPUT" TIMEZONE_INPUT="$TIMEZONE_INPUT" SUPABASE_URL_INPUT="$SUPABASE_URL_INPUT" SUPABASE_KEY_INPUT="$SUPABASE_KEY_INPUT" python3 << 'EOF'
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
    
    echo ""
    
    # Select DEVICE_TIMEZONE
    echo "Select your DEVICE_TIMEZONE:"
    echo ""
    TIMEZONE_INPUT=$(python3 << 'TZEOF'
import os
import sys

timezones = [
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Phoenix",
    "America/Los_Angeles",
    "America/Anchorage",
    "America/Honolulu",
    "America/Toronto",
    "America/Vancouver",
    "America/Edmonton",
    "America/Winnipeg",
    "America/Halifax",
    "America/Mexico_City",
    "America/Monterrey",
    "America/Tijuana",
    "UTC"
]

print("Available Timezones:")
for i, tz in enumerate(timezones):
    print(f"  {i+1}. {tz}")

while True:
    choice = input(f"\nEnter number (1-{len(timezones)}): ")
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(timezones):
            print(timezones[idx])
            break
        else:
            print(f"Please enter a number between 1 and {len(timezones)}")
    except ValueError:
        print("Please enter a valid number")
TZEOF
)
    
    echo ""
    
    # Optional: SUPABASE configuration for OTA updates
    echo "==================================="
    echo "OTA Update Configuration (Optional)"
    echo "==================================="
    echo ""
    echo "For over-the-air updates, you need Supabase credentials."
    echo "If you don't have these yet, you can skip and add them later."
    echo ""
    
    echo "Enter your SUPABASE_URL (or press Enter to skip):"
    read -p "SUPABASE_URL: " SUPABASE_URL_INPUT
    
    if [ -n "$SUPABASE_URL_INPUT" ]; then
        echo ""
        echo "Enter your SUPABASE_KEY (anon key):"
        read -p "SUPABASE_KEY: " SUPABASE_KEY_INPUT
    else
        SUPABASE_KEY_INPUT=""
        echo "⊘ Skipped OTA update configuration (can be added later)"
    fi
    
    echo ""
    
    # Update .env file
    SERVER_URL_INPUT="$SERVER_URL_INPUT" CLIENT_API_KEY_INPUT="$CLIENT_API_KEY_INPUT" TIMEZONE_INPUT="$TIMEZONE_INPUT" SUPABASE_URL_INPUT="$SUPABASE_URL_INPUT" SUPABASE_KEY_INPUT="$SUPABASE_KEY_INPUT" python3 << 'EOF'
import os
import re

server_url = os.environ.get('SERVER_URL_INPUT', '').strip()
client_api_key = os.environ.get('CLIENT_API_KEY_INPUT', '').strip()
timezone = os.environ.get('TIMEZONE_INPUT', '').strip()
supabase_url = os.environ.get('SUPABASE_URL_INPUT', '').strip()
supabase_key = os.environ.get('SUPABASE_KEY_INPUT', '').strip()

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

# Replace DEVICE_TIMEZONE if provided
if timezone:
    if 'DEVICE_TIMEZONE=' in content:
        content = re.sub(r'DEVICE_TIMEZONE=.*', f'DEVICE_TIMEZONE={timezone}', content)
    else:
        # Add after CLIENT_API_KEY line
        content = re.sub(r'(CLIENT_API_KEY=.*\n)', f'\\1DEVICE_TIMEZONE={timezone}\n', content)
    print("✓ Updated DEVICE_TIMEZONE")

# Replace SUPABASE_URL if provided
if supabase_url:
    if 'SUPABASE_URL=' in content:
        content = re.sub(r'SUPABASE_URL=.*', f'SUPABASE_URL={supabase_url}', content)
    else:
        # Add after DEVICE_TIMEZONE line
        content = re.sub(r'(DEVICE_TIMEZONE=.*\n)', f'\\1SUPABASE_URL={supabase_url}\n', content)
    print("✓ Updated SUPABASE_URL")

# Replace SUPABASE_KEY if provided
if supabase_key:
    if 'SUPABASE_KEY=' in content:
        content = re.sub(r'SUPABASE_KEY=.*', f'SUPABASE_KEY={supabase_key}', content)
    else:
        # Add after SUPABASE_URL line
        content = re.sub(r'(SUPABASE_URL=.*\n)', f'\\1SUPABASE_KEY={supabase_key}\n', content)
    print("✓ Updated SUPABASE_KEY")

with open('.env', 'w') as f:
    f.write(content)
EOF
fi

# Clean inline comments from .env file (systemd EnvironmentFile doesn't support them)
echo ""
echo "Cleaning .env file (removing inline comments for systemd compatibility)..."
python3 << 'EOF'
import re

with open('.env', 'r') as f:
    lines = f.readlines()

cleaned_lines = []
for line in lines:
    # Skip empty lines and comment-only lines
    if not line.strip() or line.strip().startswith('#'):
        cleaned_lines.append(line)
        continue
    
    # Check if line has a variable assignment
    if '=' in line:
        # Split on first '=' to preserve '=' in values
        key, value = line.split('=', 1)
        
        # Strip inline comments (anything after # that's not in quotes)
        # Simple approach: remove everything after # (assumes no # in values)
        if '#' in value:
            value = value.split('#')[0]
        
        # Clean up whitespace but preserve newline
        value = value.rstrip() + '\n'
        
        cleaned_lines.append(f"{key}={value}")
    else:
        # Keep line as-is
        cleaned_lines.append(line)

with open('.env', 'w') as f:
    f.writelines(cleaned_lines)

print("✓ Cleaned inline comments from .env file")
EOF

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

# ==================== STEP 7: AUDIO & GPIO GROUPS & SYSTEMD ====================
echo "[7/8] Setting up system permissions and service..."

NEEDS_LOGOUT=false
GROUPS_ASSIGNED_BUT_NOT_ACTIVE=false

# Check if groups are ACTIVE in current session (not just assigned)
CURRENT_GROUPS=$(id -Gn)

# Add user to audio group if not already assigned
if ! groups $USER | grep -q "\baudio\b"; then
    sudo usermod -a -G audio $USER
    echo "✓ User added to audio group"
    NEEDS_LOGOUT=true
else
    echo "✓ User assigned to audio group"
    # Check if it's active in current session
    if ! echo "$CURRENT_GROUPS" | grep -q "\baudio\b"; then
        echo "  ⚠️  But audio group is NOT active in this session!"
        GROUPS_ASSIGNED_BUT_NOT_ACTIVE=true
    fi
fi

# Add user to gpio group if not already assigned
if ! groups $USER | grep -q "\bgpio\b"; then
    sudo usermod -a -G gpio $USER
    echo "✓ User added to gpio group"
    NEEDS_LOGOUT=true
else
    echo "✓ User assigned to gpio group"
    # Check if it's active in current session
    if ! echo "$CURRENT_GROUPS" | grep -q "\bgpio\b"; then
        echo "  ⚠️  But gpio group is NOT active in this session!"
        GROUPS_ASSIGNED_BUT_NOT_ACTIVE=true
    fi
fi

# If groups are assigned but not active, we must exit
if [ "$GROUPS_ASSIGNED_BUT_NOT_ACTIVE" = true ]; then
    echo ""
    echo "================================================================"
    echo "❌ CRITICAL: Group Permissions Not Active"
    echo "================================================================"
    echo ""
    echo "You are assigned to the audio/gpio groups, but they are NOT"
    echo "active in your current session. This WILL cause the service to fail."
    echo ""
    echo "YOU MUST LOG OUT AND LOG BACK IN for group permissions to work."
    echo ""
    echo "Steps:"
    echo "  1. Exit this SSH session: exit"
    echo "  2. SSH back in: ssh $USER@$(hostname)"
    echo "  3. Run this script again: bash /tmp/javia/pi_client/deploy/setup.sh"
    echo ""
    echo "================================================================"
    exit 1
fi

if [ "$NEEDS_LOGOUT" = true ]; then
    echo ""
    echo "================================================================"
    echo "⚠️  Groups Added - Logout Required"
    echo "================================================================"
    echo ""
    echo "You have been added to audio/gpio groups."
    echo ""
    echo "YOU MUST LOG OUT AND LOG BACK IN for changes to take effect."
    echo ""
    echo "Steps:"
    echo "  1. Exit this SSH session: exit"
    echo "  2. SSH back in: ssh $USER@$(hostname)"
    echo "  3. Run this script again: bash /tmp/javia/pi_client/deploy/setup.sh"
    echo ""
    echo "================================================================"
    exit 0
fi

echo "✓ All required groups are active in this session"

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

# Device access permissions - Pi 5 compatible GPIO and audio
DeviceAllow=/dev/snd
DeviceAllow=/dev/gpiochip0 rw
DeviceAllow=/dev/gpiochip1 rw
DeviceAllow=/dev/gpiochip2 rw
DeviceAllow=/dev/gpiochip3 rw
DeviceAllow=/dev/gpiochip4 rw
DeviceAllow=/dev/gpiomem rw
DeviceAllow=char-alsa rw
DevicePolicy=auto

# Disable restrictive sandboxing for hardware access
PrivateDevices=no
ProtectHome=no

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
        echo "⚠️  IMPORTANT: You must log out and log back in for group permissions to take effect!"
        echo ""
        echo "After logging back in, the client will work when you press the button."
        echo ""
    else
        echo "✅ Client is ready! You can now press the button to use the voice assistant."
        echo ""
    fi
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
    echo "  - Missing gpio/audio group permissions (need to log out and back in)"
    echo "  - Hardware issues (GPIO pins, audio devices)"
    echo "  - Pi 5 requires gpiozero library (not RPi.GPIO)"
    echo ""
    echo "To fix:"
    echo "  1. Check the error logs above"
    echo "  2. If you see 'No access to /dev/mem': Log out and log back in (group membership)"
    echo "  3. Edit .env if needed: nano $INSTALL_DIR/.env"
    echo "  4. Run this script again: bash $SCRIPT_DIR/setup.sh"
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

