#!/bin/bash
set -e

# Voice Assistant Client Update Script for Raspberry Pi
# Run as the pi user (NOT as root)

echo "========================================="
echo "Voice Assistant Client Update"
echo "========================================="
echo ""

# Check NOT running as root
if [[ $EUID -eq 0 ]]; then
   echo "Do not run this script as root. Run as pi user." 
   exit 1
fi

# Configuration
INSTALL_DIR="$HOME/javia_client"
VENV_DIR="$HOME/venvs/pi_client"
TEMP_DIR="/tmp/javia_update_$$"  # Use PID for unique temp dir
REPO_URL="https://github.com/shreyashguptas/javia.git"

echo "[1/7] Backing up current .env file..."
if [ -f "$INSTALL_DIR/.env" ]; then
    cp "$INSTALL_DIR/.env" "/tmp/javia_client_env_backup_$$"
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
sudo systemctl stop voice-assistant-client.service
echo "✓ Service stopped"

echo ""
echo "[4/7] Updating application files..."
# Copy client files from the repo (exclude .env)
cd "$TEMP_DIR/pi_client"

# Remove old files but preserve .env
find "$INSTALL_DIR" -mindepth 1 -maxdepth 1 ! -name '.env' -exec rm -rf {} +

# Copy new files
cp -r * "$INSTALL_DIR/" 2>/dev/null || true
# Copy hidden files except .git
for file in .[!.]*; do
    if [ -f "$file" ] && [ "$file" != ".git" ]; then
        cp "$file" "$INSTALL_DIR/" 2>/dev/null || true
    fi
done

echo "✓ Files updated"

echo ""
echo "[5/7] Restoring .env file..."
if [ -f "/tmp/javia_client_env_backup_$$" ]; then
    cp "/tmp/javia_client_env_backup_$$" "$INSTALL_DIR/.env"
    chmod 600 "$INSTALL_DIR/.env"
    echo "✓ .env file restored"
else
    echo "⚠ No backup .env found - you may need to reconfigure"
fi

echo ""
echo "[6/7] Updating Python dependencies..."
cd "$INSTALL_DIR"

# Check if requirements.txt changed
NEEDS_UPDATE=false
if [ -f "$VENV_DIR/requirements_installed.txt" ]; then
    if ! diff -q requirements.txt "$VENV_DIR/requirements_installed.txt" > /dev/null 2>&1; then
        NEEDS_UPDATE=true
        echo "Requirements changed, updating virtual environment..."
    fi
else
    NEEDS_UPDATE=true
    echo "First time setup or requirements tracking missing, updating..."
fi

if [ "$NEEDS_UPDATE" = true ]; then
    # Activate virtual environment
    source "$VENV_DIR/bin/activate"
    
    # Update pip
    pip install --upgrade pip
    
    # Install/update dependencies
    pip install -r requirements.txt
    
    # Save current requirements for future comparison
    cp requirements.txt "$VENV_DIR/requirements_installed.txt"
    
    echo "✓ Dependencies updated"
else
    echo "✓ Dependencies up to date (no changes)"
fi

echo ""
echo "[7/7] Starting service..."
sudo systemctl start voice-assistant-client.service
echo "✓ Service started"

echo ""
echo "Cleaning up..."
rm -rf "$TEMP_DIR"
rm -f "/tmp/javia_client_env_backup_$$"

echo ""
echo "========================================="
echo "Update Complete!"
echo "========================================="
echo ""
echo "Service Status:"
sudo systemctl status voice-assistant-client.service --no-pager

echo ""
echo "Recent Logs:"
sudo journalctl -u voice-assistant-client.service -n 20 --no-pager

echo ""
echo "To view live logs, run:"
echo "  sudo journalctl -u voice-assistant-client.service -f"
echo ""
echo "To test the client manually:"
echo "  source $VENV_DIR/bin/activate"
echo "  cd $INSTALL_DIR"
echo "  python3 client.py"
echo ""

