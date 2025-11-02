#!/bin/bash
set -e

# Quick update script for server files
# This updates the code without reconfiguring environment/services
# Use this when you only need to update scripts or code, not full setup

echo "==========================================="
echo "Voice Assistant - Update Server Files"
echo "==========================================="
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root or with sudo" 
   exit 1
fi

INSTALL_DIR="/opt/javia"

# Determine source directory (must be run from git repo)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Validate we're in the right place
if [ ! -f "$SERVER_DIR/main.py" ]; then
    echo "❌ ERROR: Cannot find main.py!"
    echo "Expected to find main.py at: $SERVER_DIR/main.py"
    echo ""
    echo "Please ensure you:"
    echo "  1. Cloned the repository: git clone https://github.com/shreyashguptas/javia.git"
    echo "  2. Are running this script from: /tmp/javia/server/scripts/update_server_files.sh"
    echo ""
    exit 1
fi

echo "✓ Found server files at: $SERVER_DIR"
echo ""

# Check if production install exists
if [ ! -d "$INSTALL_DIR" ]; then
    echo "❌ ERROR: Production installation not found at $INSTALL_DIR"
    echo ""
    echo "Please run the full setup first:"
    echo "  cd /tmp/javia/server/scripts/setup"
    echo "  sudo ./setup.sh"
    echo ""
    exit 1
fi

echo "📦 Updating files from repository to production..."
echo ""

# Stop service
echo "[1/4] Stopping service..."
systemctl stop voice-assistant-server.service 2>/dev/null || true
echo "✓ Service stopped"
echo ""

# Backup .env
echo "[2/4] Backing up configuration..."
ENV_BACKUP="/tmp/javia_server_env_backup_$$"
if [ -f "$INSTALL_DIR/.env" ]; then
    cp "$INSTALL_DIR/.env" "$ENV_BACKUP"
    echo "✓ Backed up .env file"
else
    echo "⚠️  No .env file found (fresh install?)"
fi
echo ""

# Update files (preserve venv and .env)
echo "[3/4] Updating files..."
echo "Copying from: $SERVER_DIR"
echo "Copying to:   $INSTALL_DIR"
echo ""

# Remove old files but preserve venv and .env
if [ -d "$INSTALL_DIR" ]; then
    find "$INSTALL_DIR" -mindepth 1 -maxdepth 1 ! -name 'venv' ! -name '.env' -exec rm -rf {} + 2>/dev/null || true
fi

# Copy all files
rsync -av --exclude='__pycache__' --exclude='*.pyc' "$SERVER_DIR/" "$INSTALL_DIR/"

# Restore .env if backed up
if [ -f "$ENV_BACKUP" ]; then
    cp "$ENV_BACKUP" "$INSTALL_DIR/.env"
    rm "$ENV_BACKUP"
    echo "✓ Restored .env file"
fi

# Set permissions
chown -R voiceassistant:voiceassistant "$INSTALL_DIR"
chmod 600 "$INSTALL_DIR/.env"

# Make scripts executable
if [ -f "$INSTALL_DIR/scripts/register_device/register_device.sh" ]; then
    chmod 755 "$INSTALL_DIR/scripts/register_device/register_device.sh"
fi
if [ -f "$INSTALL_DIR/scripts/create_update/create_update.sh" ]; then
    chmod 755 "$INSTALL_DIR/scripts/create_update/create_update.sh"
fi

echo "✓ Files updated"
echo ""

# Update Python dependencies
echo "[4/4] Updating Python dependencies..."
VENV_DIR="$INSTALL_DIR/venv"
if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
    pip install --upgrade pip > /dev/null 2>&1
    pip install -r "$INSTALL_DIR/requirements.txt" --quiet
    echo "✓ Dependencies updated"
else
    echo "⚠️  Virtual environment not found, skipping dependency update"
fi
echo ""

# Restart service
echo "Restarting service..."
systemctl start voice-assistant-server.service
sleep 2

# Check status
if systemctl is-active --quiet voice-assistant-server.service; then
    echo "✅ Service restarted successfully!"
    echo ""
    
    # Test health
    HEALTH_CHECK=$(curl -s http://localhost:8000/health || echo "FAILED")
    if [[ "$HEALTH_CHECK" == *"healthy"* ]]; then
        echo "✅ Health check passed: $HEALTH_CHECK"
    else
        echo "⚠️  Health check failed (service may still be starting)"
    fi
else
    echo "❌ Service failed to start!"
    echo ""
    echo "Recent logs:"
    journalctl -u voice-assistant-server.service -n 20 --no-pager
    exit 1
fi

echo ""
echo "==========================================="
echo "Update Complete!"
echo "==========================================="
echo ""
echo "Updated files in: $INSTALL_DIR"
echo ""
echo "View logs:"
echo "  journalctl -u voice-assistant-server.service -f"
echo ""

