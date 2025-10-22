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

echo "[1/11] Installing system dependencies..."
apt update
apt install -y python3 python3-pip python3-venv nginx git wget

echo ""
echo "[2/11] Creating service user..."
if ! id -u $SERVICE_USER > /dev/null 2>&1; then
    useradd -r -s /bin/false -d $INSTALL_DIR $SERVICE_USER
    echo "Created user: $SERVICE_USER"
else
    echo "User $SERVICE_USER already exists"
fi

echo ""
echo "[3/11] Determining source directory..."
# This script expects to be run from the cloned Git repository
# Expected location: /tmp/javia/server/deploy/
# Must resolve paths BEFORE changing directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(dirname "$SCRIPT_DIR")"

echo ""
echo "[4/11] Creating installation directory..."
mkdir -p $INSTALL_DIR
cd $INSTALL_DIR

echo ""
echo "[5/11] Copying application files..."

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
echo "[6/11] Creating Python virtual environment..."
python3 -m venv $VENV_DIR
source $VENV_DIR/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "[7/11] Setting up environment file..."

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
echo "[8/11] Setting permissions..."
chown -R $SERVICE_USER:$SERVICE_GROUP $INSTALL_DIR
chmod 600 $INSTALL_DIR/.env

echo ""
echo "[9/11] Installing systemd service..."
cp deploy/systemd/voice-assistant-server.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable voice-assistant-server.service
systemctl start voice-assistant-server.service

echo ""
echo "[10/11] Configuring Nginx..."
# Create simple nginx configuration
cat > /etc/nginx/sites-available/voice-assistant << 'NGINX_EOF'
server {
    listen 80;
    server_name _;
    
    # Health check endpoint
    location /health {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Main API endpoints
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Increase timeout for long-running requests
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
    
    # Increase max upload size for audio files
    client_max_body_size 26M;
}
NGINX_EOF

# Enable the site
ln -sf /etc/nginx/sites-available/voice-assistant /etc/nginx/sites-enabled/voice-assistant
rm -f /etc/nginx/sites-enabled/default

# Test and reload nginx
nginx -t && systemctl restart nginx

echo "✓ Nginx configured and running on port 80"

echo ""
echo "[11/11] Installing Cloudflare Tunnel (cloudflared)..."
# Download and install cloudflared
if ! command -v cloudflared &> /dev/null; then
    echo "Downloading cloudflared..."
    wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
    dpkg -i cloudflared-linux-amd64.deb
    rm cloudflared-linux-amd64.deb
    echo "✓ cloudflared installed"
else
    echo "✓ cloudflared already installed"
fi

echo ""
echo "=================================="
echo "Service Status:"
echo "=================================="
systemctl status voice-assistant-server.service --no-pager

echo ""
echo "=================================="
echo "Next Steps: Setup Cloudflare Tunnel"
echo "=================================="
echo ""
echo "Prerequisites:"
echo "  ✓ You must have already added your domain to Cloudflare"
echo "  ✓ Your domain's nameservers must be pointed to Cloudflare"
echo ""
echo "Step 1: Authenticate with Cloudflare"
echo "  Run: cloudflared tunnel login"
echo "  This will open a browser - login and authorize the tunnel"
echo ""
echo "Step 2: Create a tunnel"
echo "  Run: cloudflared tunnel create javia-voice-assistant"
echo "  Save the Tunnel ID that is displayed"
echo ""
echo "Step 3: Configure the tunnel"
echo "  Run the following command (replace YOUR_DOMAIN with your actual domain):"
echo "  cat > /etc/cloudflared/config.yml << 'TUNNEL_EOF'"
echo "  tunnel: <TUNNEL_ID_FROM_STEP_2>"
echo "  credentials-file: /root/.cloudflared/<TUNNEL_ID>.json"
echo "  ingress:"
echo "    - hostname: YOUR_DOMAIN.com"
echo "      service: http://localhost:80"
echo "    - service: http_status:404"
echo "  TUNNEL_EOF"
echo ""
echo "Step 4: Route your domain to the tunnel"
echo "  Run: cloudflared tunnel route dns javia-voice-assistant YOUR_DOMAIN.com"
echo "  This automatically creates a CNAME record in Cloudflare DNS"
echo ""
echo "Step 5: Start the tunnel as a service"
echo "  Run: cloudflared service install"
echo "  Run: systemctl start cloudflared"
echo "  Run: systemctl enable cloudflared"
echo ""
echo "Step 6: Test your setup"
echo "  Local test: curl http://localhost:80/health"
echo "  Public test: curl https://YOUR_DOMAIN.com/health"
echo "  You should see: {\"status\":\"healthy\",\"version\":\"1.0.0\"}"
echo ""
echo "Step 7: Configure Raspberry Pi client"
echo "  Set SERVER_URL to https://YOUR_DOMAIN.com"
echo "  Set CLIENT_API_KEY to the SERVER_API_KEY shown above"
echo ""
echo "Troubleshooting:"
echo "  - View tunnel logs: journalctl -u cloudflared -f"
echo "  - View app logs: journalctl -u voice-assistant-server.service -f"
echo "  - Test local app: curl http://localhost:8000/health"
echo "  - Test nginx: curl http://localhost:80/health"
echo ""
echo "=================================="
echo "Deployment Complete!"
echo "=================================="
echo ""
echo "Documentation: See /opt/javia/docs/ for more information"
echo ""

