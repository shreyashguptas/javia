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

# Check if this is an update (venv exists) and offer to rebuild it
if [ -d "$VENV_DIR" ]; then
    echo "⚠️  Existing virtual environment detected at: $VENV_DIR"
    echo ""
    echo "For major updates, it's recommended to rebuild the virtual environment"
    echo "to avoid package conflicts and ensure clean dependencies."
    echo ""
    echo "Options:"
    echo "  1) Keep existing venv and update packages (faster)"
    echo "  2) Delete and rebuild venv from scratch (recommended for updates)"
    echo ""
    read -p "Choose option [1-2] (default: 1): " VENV_CHOICE
    
    if [ "$VENV_CHOICE" = "2" ]; then
        echo ""
        echo "Removing existing virtual environment..."
        rm -rf "$VENV_DIR"
        echo "✓ Existing venv removed (will create fresh one)"
    else
        echo "✓ Keeping existing venv"
    fi
    echo ""
fi

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

# Strategy: Use --system-site-packages for hardware libs (pyaudio, gpiozero, numpy)
# but force-install OTA dependencies to venv for isolation
if [ -d "$VENV_DIR" ]; then
    echo "✓ Virtual environment exists, checking configuration..."
    
    # Ensure system-site-packages is enabled
    if [ -f "$VENV_DIR/pyvenv.cfg" ]; then
        if ! grep -q "include-system-site-packages = true" "$VENV_DIR/pyvenv.cfg"; then
            echo "⚠️  Enabling system-site-packages for hardware library access..."
            sed -i 's/include-system-site-packages = false/include-system-site-packages = true/' "$VENV_DIR/pyvenv.cfg"
        fi
    fi
else
    echo "Creating new virtual environment with system-site-packages..."
    python3 -m venv --system-site-packages "$VENV_DIR"
fi

# Upgrade pip first
echo "Upgrading pip in virtual environment..."
"$VENV_DIR/bin/pip" install --upgrade pip setuptools wheel > /dev/null 2>&1

# Install OTA dependencies with --ignore-installed to force them into venv
echo "Installing OTA dependencies into virtual environment..."
echo "This ensures clean, isolated package installations..."
"$VENV_DIR/bin/pip" install --no-cache-dir --ignore-installed --no-deps uuid6
"$VENV_DIR/bin/pip" install --no-cache-dir --ignore-installed pytz
"$VENV_DIR/bin/pip" install --no-cache-dir realtime
"$VENV_DIR/bin/pip" install --no-cache-dir supabase

# Install other dependencies normally (can use system packages where available)
echo "Installing remaining dependencies..."
"$VENV_DIR/bin/pip" install --no-cache-dir requests python-dotenv opuslib numpy

# Clear any Python bytecode cache to ensure clean imports
echo "Clearing Python cache..."
find "$VENV_DIR" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find "$INSTALL_DIR" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find "$INSTALL_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true

# Force Python to clear import cache
"$VENV_DIR/bin/python3" -c "import sys; sys.dont_write_bytecode = True" 2>/dev/null || true

# Verify all dependencies are accessible
echo ""
echo "Verifying dependencies..."

# Test each dependency individually for better diagnostics
declare -A DEPS_STATUS
declare -A DEPS_LOCATION

# All dependencies we need to check (both venv and system)
DEPS_TO_CHECK="uuid6 supabase pytz realtime requests dotenv opuslib numpy pyaudio gpiozero"

for dep in $DEPS_TO_CHECK; do
    if "$VENV_DIR/bin/python3" -c "import $dep" 2>/dev/null; then
        DEPS_STATUS[$dep]="✓"
        # Check if it's from system or venv
        location=$("$VENV_DIR/bin/python3" -c "import $dep; import os; print('venv' if '$VENV_DIR' in os.path.dirname($dep.__file__) else 'system')" 2>/dev/null)
        DEPS_LOCATION[$dep]=$location
    else
        DEPS_STATUS[$dep]="✗"
        DEPS_LOCATION[$dep]="missing"
    fi
done

# Display status with source information
ALL_OK=true
echo ""
echo "Dependency Status:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
for dep in $DEPS_TO_CHECK; do
    if [ "${DEPS_STATUS[$dep]}" = "✗" ]; then
        echo "  ${DEPS_STATUS[$dep]} $dep - FAILED"
        ALL_OK=false
    else
        location_label="${DEPS_LOCATION[$dep]}"
        echo "  ${DEPS_STATUS[$dep]} $dep ($location_label)"
    fi
done
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ "$ALL_OK" = false ]; then
    echo ""
    echo "❌ Some dependencies failed verification."
    echo ""
    echo "Diagnostic information:"
    echo "Python version: $("$VENV_DIR/bin/python3" --version)"
    echo "Pip version: $("$VENV_DIR/bin/pip" --version)"
    echo "Site packages: $("$VENV_DIR/bin/python3" -c "import site; print(site.getsitepackages())")"
    echo ""
    echo "Installed packages:"
    "$VENV_DIR/bin/pip" list | grep -E "(uuid6|supabase|pytz|realtime|requests|dotenv|opuslib)"
    echo ""
    
    read -p "Attempt to reinstall failed packages? (Y/n): " RETRY_INSTALL
    if [ "$RETRY_INSTALL" != "n" ] && [ "$RETRY_INSTALL" != "N" ]; then
        echo "Reinstalling all requirements..."
        "$VENV_DIR/bin/pip" install --no-cache-dir --force-reinstall -r "$INSTALL_DIR/requirements.txt"
        
        # Clear cache again
        find "$VENV_DIR" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
        
        # Test again
        echo "Re-verifying..."
        STILL_FAILING=false
        for dep in $DEPS_TO_CHECK; do
            import_name="$dep"
            case "$dep" in
                "python-dotenv") import_name="dotenv" ;;
            esac
            
            if ! "$VENV_DIR/bin/python3" -c "import $import_name" 2>/dev/null; then
                echo "  ✗ $dep - STILL FAILING"
                STILL_FAILING=true
            fi
        done
        
        if [ "$STILL_FAILING" = true ]; then
            echo ""
            echo "❌ Some packages still cannot be imported."
            echo "The service may not work correctly."
            echo ""
            read -p "Continue anyway? (y/N): " FORCE_CONTINUE
            if [ "$FORCE_CONTINUE" != "y" ] && [ "$FORCE_CONTINUE" != "Y" ]; then
                exit 1
            fi
        else
            echo "✓ All dependencies verified after reinstall"
        fi
    else
        echo ""
        read -p "Continue without fixing? Service may not work. (y/N): " FORCE_CONTINUE
        if [ "$FORCE_CONTINUE" != "y" ] && [ "$FORCE_CONTINUE" != "Y" ]; then
            exit 1
        fi
    fi
else
    echo "✓ All dependencies verified successfully"
fi

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

# Restore backed up .env if available, then prompt for configuration
if [ -n "$ENV_BACKUP" ] && [ -f "$ENV_BACKUP" ]; then
    # Restore the backup first so we can read current values
    cp "$ENV_BACKUP" "$INSTALL_DIR/.env"
    rm -f "$ENV_BACKUP"
fi

# Always show configuration prompts with current values
echo ""
echo "==================================="
echo "Client Configuration"
echo "==================================="
echo ""

# Read current values from .env file using Python
read -r CURRENT_SERVER_URL CURRENT_DEVICE_TIMEZONE CURRENT_SUPABASE_URL CURRENT_SUPABASE_KEY < <(python3 << 'EOF'
import re

try:
    with open('.env', 'r') as f:
        content = f.read()
    
    def get_value(key):
        match = re.search(f'^{key}=(.*)$', content, re.MULTILINE)
        return match.group(1).strip() if match else ''
    
    server_url = get_value('SERVER_URL')
    device_timezone = get_value('DEVICE_TIMEZONE')
    supabase_url = get_value('SUPABASE_URL')
    supabase_key = get_value('SUPABASE_KEY')
    
    print(f"{server_url} {device_timezone} {supabase_url} {supabase_key}")
except:
    print("    ")
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
echo "NOTE: CLIENT_API_KEY is no longer used. Authentication is now via device UUID."
echo "You will register your device UUID on the server after this setup completes."
echo ""
# Skip CLIENT_API_KEY - not needed anymore
CLIENT_API_KEY_INPUT=""

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
# Write prompts to stderr so they appear, but result goes to stdout
print("Available Timezones:", file=sys.stderr)
for i, tz in enumerate(timezones):
    marker = " → " if i == current_index else "   "
    print(f"{marker}{i+1}. {tz}", file=sys.stderr)

print(f"\nCurrent: {current}", file=sys.stderr)

# Read from /dev/tty directly for user input
try:
    with open('/dev/tty', 'r') as tty:
        sys.stderr.write(f"\nEnter number (1-{len(timezones)}), or press Enter to keep current: ")
        sys.stderr.flush()
        choice = tty.readline().strip()
except:
    # Fallback if /dev/tty is not available
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
SERVER_URL_INPUT="$SERVER_URL_INPUT" TIMEZONE_INPUT="$TIMEZONE_INPUT" SUPABASE_URL_INPUT="$SUPABASE_URL_INPUT" SUPABASE_KEY_INPUT="$SUPABASE_KEY_INPUT" python3 << 'EOF'
import os
import re

server_url = os.environ.get('SERVER_URL_INPUT', '').strip()
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

# CLIENT_API_KEY is deprecated - remove it from .env if present
if 'CLIENT_API_KEY=' in content:
    # Comment out the old CLIENT_API_KEY line
    content = re.sub(r'CLIENT_API_KEY=.*', '# CLIENT_API_KEY=DEPRECATED (authentication now uses device UUID)', content)
    print("✓ Removed CLIENT_API_KEY (deprecated)")

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
"$VENV_DIR/bin/python3" << 'EOF'
import os
from dotenv import load_dotenv

# Load the .env file from current directory
load_dotenv('.env')

server_url = os.getenv('SERVER_URL', '')

errors = []

# Check SERVER_URL
if not server_url or server_url in ['https://yourdomain.com', 'http://localhost:8000']:
    errors.append("SERVER_URL is not configured or using default value")

# CLIENT_API_KEY is no longer required - authentication is via device UUID

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
    
    # Display device UUID for registration
    echo "==========================================="
    echo "⚠️  IMPORTANT: Device Registration Required"
    echo "==========================================="
    echo ""
    
    # Get the device UUID from the UUID file
    DEVICE_UUID_FILE="$HOME/.javia_device_uuid"
    if [ -f "$DEVICE_UUID_FILE" ]; then
        DEVICE_UUID=$(cat "$DEVICE_UUID_FILE")
        echo "Your Device UUID:"
        echo ""
        echo "  ┌────────────────────────────────────────────┐"
        echo "  │  $DEVICE_UUID  │"
        echo "  └────────────────────────────────────────────┘"
        echo ""
        echo "This device MUST be registered on the server before it can connect."
        echo ""
        echo "On your server, SSH in and run:"
        echo ""
        echo "  cd /opt/javia/scripts/register_device"
        echo "  sudo ./register_device.sh $DEVICE_UUID \"$(hostname)\" \"$DEVICE_TIMEZONE\""
        echo ""
        echo "After registration, the device can make requests to the server."
        echo ""
    else
        echo "⚠️  Device UUID file not found."
        echo "The device will generate a UUID on first run."
        echo "Check logs after starting to get the UUID:"
        echo "  sudo journalctl -u voice-assistant-client.service -n 50"
        echo ""
    fi
    
    echo "==========================================="
    echo "Setup Complete!"
    echo "==========================================="
    echo ""
    
    if [ "$NEEDS_LOGOUT" = true ]; then
        echo "⚠️  IMPORTANT: You must log out and log back in for group permissions to take effect!"
        echo ""
        echo "After logging back in, register the device UUID on the server."
        echo ""
    else
        echo "✅ Next Steps:"
        echo "  1. Register the device UUID on the server (see above)"
        echo "  2. Press the button to test the voice assistant"
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

