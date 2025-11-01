#!/bin/bash
set -e

# Voice Assistant Server Setup Script
# This script handles fresh installs, updates, and fixes
# Run from the cloned Git repository directory

echo "==========================================="
echo "Voice Assistant Server Setup"
echo "==========================================="
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root or with sudo" 
   exit 1
fi

# Configuration
INSTALL_DIR="/opt/javia"
VENV_DIR="$INSTALL_DIR/venv"
SERVICE_USER="voiceassistant"
SERVICE_GROUP="voiceassistant"

# Determine source directory (must be run from git repo)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(dirname "$SCRIPT_DIR")"

# Validate we're in the right place
if [ ! -f "$SERVER_DIR/main.py" ]; then
    echo "❌ ERROR: Cannot find main.py!"
    echo "Expected to find main.py at: $SERVER_DIR/main.py"
    echo ""
    echo "Please ensure you:"
    echo "  1. Cloned the repository: git clone https://github.com/shreyashguptas/javia.git"
    echo "  2. Are running this script from: /tmp/javia/server/deploy/setup.sh"
    echo ""
    exit 1
fi

echo "✓ Found server files at: $SERVER_DIR"
echo ""

# Detect if this is a fresh install or an update
IS_FRESH_INSTALL=false
if [ ! -f "$INSTALL_DIR/.env" ]; then
    IS_FRESH_INSTALL=true
    echo "📦 Detected: FRESH INSTALLATION"
else
    echo "🔄 Detected: UPDATE/RECONFIGURATION"
fi
echo ""

# ==================== STEP 1: SYSTEM DEPENDENCIES ====================
echo "[1/10] Checking system dependencies..."

# Check if packages are already installed to avoid unnecessary updates
PACKAGES_TO_INSTALL=""
for pkg in python3 python3-pip python3-venv nginx git wget rsync libopus0 libopus-dev; do
    if ! dpkg -l | grep -q "^ii  $pkg "; then
        PACKAGES_TO_INSTALL="$PACKAGES_TO_INSTALL $pkg"
    fi
done

if [ -n "$PACKAGES_TO_INSTALL" ]; then
    echo "Installing missing packages:$PACKAGES_TO_INSTALL"
    apt update
    apt install -y $PACKAGES_TO_INSTALL
    echo "✓ System dependencies installed"
else
    echo "✓ All system dependencies already installed"
fi

echo ""

# ==================== STEP 2: CREATE SERVICE USER ====================
echo "[2/10] Setting up service user..."

if ! id -u $SERVICE_USER > /dev/null 2>&1; then
    useradd -r -s /bin/false -d $INSTALL_DIR $SERVICE_USER
    echo "✓ Created user: $SERVICE_USER"
else
    echo "✓ User $SERVICE_USER already exists"
fi

echo ""

# ==================== STEP 3: STOP SERVICE ====================
echo "[3/10] Stopping service (if running)..."
systemctl stop voice-assistant-server.service 2>/dev/null || true
echo "✓ Service stopped"
echo ""

# ==================== STEP 4: CREATE DIRECTORIES ====================
echo "[4/10] Setting up directories..."
mkdir -p "$INSTALL_DIR"
echo "✓ Directories ready"
echo ""

# ==================== STEP 5: COPY/UPDATE FILES ====================
echo "[5/10] Copying latest server files..."

# Backup .env if it exists
ENV_BACKUP=""
if [ -f "$INSTALL_DIR/.env" ]; then
    ENV_BACKUP="/tmp/javia_server_env_backup_$$"
    cp "$INSTALL_DIR/.env" "$ENV_BACKUP"
    echo "✓ Backed up existing .env file"
fi

# Remove old files but preserve venv and .env
if [ -d "$INSTALL_DIR" ]; then
    find "$INSTALL_DIR" -mindepth 1 -maxdepth 1 ! -name 'venv' ! -name '.env' -exec rm -rf {} + 2>/dev/null || true
fi

# Copy all files from server directory
echo "Copying files from: $SERVER_DIR"
rsync -av --exclude='deploy' --exclude='__pycache__' --exclude='*.pyc' "$SERVER_DIR/" "$INSTALL_DIR/"
echo "✓ Files copied successfully"
echo ""

# ==================== STEP 6: VIRTUAL ENVIRONMENT ====================
echo "[6/10] Setting up Python virtual environment..."

if [ -d "$VENV_DIR" ]; then
    echo "✓ Virtual environment already exists, updating..."
else
    echo "Creating new virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
pip install --upgrade pip > /dev/null 2>&1
pip install -r "$INSTALL_DIR/requirements.txt"
echo "✓ Virtual environment ready"
echo ""

# ==================== STEP 7: CONFIGURE .ENV ====================
echo "[7/10] Configuring environment..."

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

cd "$INSTALL_DIR"

# Handle configuration based on fresh install vs update
if [ "$IS_FRESH_INSTALL" = true ]; then
    # FRESH INSTALL - Require all values
    echo ""
    echo "==================================="
    echo "Server Configuration (REQUIRED)"
    echo "==================================="
    echo ""
    
    # Require GROQ_API_KEY
    while true; do
        echo "Enter your GROQ_API_KEY:"
        read -p "GROQ_API_KEY: " GROQ_KEY_INPUT
        if [ -n "$GROQ_KEY_INPUT" ]; then
            break
        else
            echo "❌ GROQ_API_KEY cannot be empty. Please enter a valid API key."
            echo ""
        fi
    done
    
    echo ""
    echo "Generating SERVER_API_KEY using UUID7..."
    # Install uuid6 package (provides uuid7 support) if needed
    pip install -q uuid6 > /dev/null 2>&1 || true
    SERVER_KEY_INPUT=$(python3 -c "from uuid6 import uuid7; print(str(uuid7()))")
    
    echo ""
    echo "==================================="
    echo "GENERATED SERVER_API_KEY (SAVE THIS!):"
    echo "$SERVER_KEY_INPUT"
    echo "==================================="
    echo ""
    echo "IMPORTANT: Copy and save the SERVER_API_KEY above!"
    echo "You will need it to configure the Raspberry Pi client."
    echo ""
    read -p "Press Enter after you've saved the SERVER_API_KEY..."
    
    echo ""
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
        
        echo ""
        echo "Enter your SUPABASE_SERVICE_KEY (service role key):"
        read -p "SUPABASE_SERVICE_KEY: " SUPABASE_SERVICE_KEY_INPUT
    else
        SUPABASE_KEY_INPUT=""
        SUPABASE_SERVICE_KEY_INPUT=""
        echo "⊘ Skipped OTA update configuration (can be added later)"
    fi
    
else
    # UPDATE - Show current values and allow keeping or changing
    echo ""
    echo "Found existing configuration!"
    echo ""
    
    # Load current values using Python (safer than sourcing)
    CURRENT_VALUES=$(python3 << 'EOF'
import os
import re

env_file = '.env'
groq_key = 'NOT_SET'
server_key = 'NOT_SET'
supabase_url = 'NOT_SET'
supabase_key = 'NOT_SET'
supabase_service_key = 'NOT_SET'

try:
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                if line.startswith('GROQ_API_KEY='):
                    groq_key = line.split('=', 1)[1].strip()
                elif line.startswith('SERVER_API_KEY='):
                    server_key = line.split('=', 1)[1].strip()
                elif line.startswith('SUPABASE_URL='):
                    supabase_url = line.split('=', 1)[1].strip()
                elif line.startswith('SUPABASE_KEY='):
                    supabase_key = line.split('=', 1)[1].strip()
                elif line.startswith('SUPABASE_SERVICE_KEY='):
                    supabase_service_key = line.split('=', 1)[1].strip()
    print(f"GROQ_KEY={groq_key}")
    print(f"SERVER_KEY={server_key}")
    print(f"SUPABASE_URL={supabase_url}")
    print(f"SUPABASE_KEY={supabase_key}")
    print(f"SUPABASE_SERVICE_KEY={supabase_service_key}")
except Exception as e:
    print(f"GROQ_KEY=NOT_SET")
    print(f"SERVER_KEY=NOT_SET")
    print(f"SUPABASE_URL=NOT_SET")
    print(f"SUPABASE_KEY=NOT_SET")
    print(f"SUPABASE_SERVICE_KEY=NOT_SET")
EOF
)
    
    # Parse the output
    CURRENT_GROQ_KEY=$(echo "$CURRENT_VALUES" | grep "^GROQ_KEY=" | cut -d'=' -f2)
    CURRENT_SERVER_KEY=$(echo "$CURRENT_VALUES" | grep "^SERVER_KEY=" | cut -d'=' -f2)
    CURRENT_SUPABASE_URL=$(echo "$CURRENT_VALUES" | grep "^SUPABASE_URL=" | cut -d'=' -f2)
    CURRENT_SUPABASE_KEY=$(echo "$CURRENT_VALUES" | grep "^SUPABASE_KEY=" | cut -d'=' -f2)
    CURRENT_SUPABASE_SERVICE_KEY=$(echo "$CURRENT_VALUES" | grep "^SUPABASE_SERVICE_KEY=" | cut -d'=' -f2)
    
    echo "==================================="
    echo "Current Configuration"
    echo "==================================="
    echo ""
    echo "GROQ_API_KEY"
    echo "------------"
    echo "Current value: ${CURRENT_GROQ_KEY:0:20}... (hidden)"
    echo ""
    echo "Enter new GROQ_API_KEY (or press Enter to keep current):"
    read -p "GROQ_API_KEY: " GROQ_KEY_INPUT
    
    if [ -z "$GROQ_KEY_INPUT" ]; then
        GROQ_KEY_INPUT="$CURRENT_GROQ_KEY"
        echo "✓ Keeping existing GROQ_API_KEY"
    else
        echo "✓ Will update GROQ_API_KEY"
    fi
    
    echo ""
    echo "==================================="
    echo "SERVER_API_KEY"
    echo "------------"
    echo "Current value: $CURRENT_SERVER_KEY"
    echo ""
    echo "⚠️  WARNING: Changing SERVER_API_KEY requires updating ALL Pi clients!"
    echo ""
    echo "Options:"
    echo "  1) Keep current SERVER_API_KEY (press Enter)"
    echo "  2) Generate new SERVER_API_KEY (type 'new')"
    echo ""
    read -p "Choice (Enter or 'new'): " SERVER_KEY_CHOICE
    
    if [ "$SERVER_KEY_CHOICE" = "new" ]; then
        echo ""
        echo "Generating new SERVER_API_KEY using UUID7..."
        pip install -q uuid6 > /dev/null 2>&1 || true
        SERVER_KEY_INPUT=$(python3 -c "from uuid6 import uuid7; print(str(uuid7()))")
        echo ""
        echo "==================================="
        echo "NEW SERVER_API_KEY (SAVE THIS!):"
        echo "$SERVER_KEY_INPUT"
        echo "==================================="
        echo ""
        echo "IMPORTANT: Copy and save the SERVER_API_KEY above!"
        echo "You MUST update your Raspberry Pi client with this new key."
        echo ""
        read -p "Press Enter after you've saved the SERVER_API_KEY..."
    else
        SERVER_KEY_INPUT="$CURRENT_SERVER_KEY"
        echo "✓ Keeping existing SERVER_API_KEY"
    fi
    
    echo ""
    echo "==================================="
    echo "OTA Update Configuration (Supabase)"
    echo "==================================="
    echo ""
    echo "SUPABASE_URL"
    echo "------------"
    if [ "$CURRENT_SUPABASE_URL" != "NOT_SET" ] && [ "$CURRENT_SUPABASE_URL" != "https://your-project.supabase.co" ]; then
        echo "Current value: $CURRENT_SUPABASE_URL"
    else
        echo "Current value: Not configured"
    fi
    echo ""
    read -p "SUPABASE_URL (press Enter to keep current): " SUPABASE_URL_INPUT
    
    if [ -z "$SUPABASE_URL_INPUT" ]; then
        SUPABASE_URL_INPUT="$CURRENT_SUPABASE_URL"
        echo "✓ Keeping existing SUPABASE_URL"
    else
        echo "✓ Will update SUPABASE_URL"
    fi
    
    echo ""
    echo "SUPABASE_KEY (anon key)"
    echo "------------"
    if [ "$CURRENT_SUPABASE_KEY" != "NOT_SET" ] && [ "$CURRENT_SUPABASE_KEY" != "your-anon-key" ]; then
        echo "Current value: ${CURRENT_SUPABASE_KEY:0:20}... (hidden)"
    else
        echo "Current value: Not configured"
    fi
    echo ""
    read -p "SUPABASE_KEY (press Enter to keep current): " SUPABASE_KEY_INPUT
    
    if [ -z "$SUPABASE_KEY_INPUT" ]; then
        SUPABASE_KEY_INPUT="$CURRENT_SUPABASE_KEY"
        echo "✓ Keeping existing SUPABASE_KEY"
    else
        echo "✓ Will update SUPABASE_KEY"
    fi
    
    echo ""
    echo "SUPABASE_SERVICE_KEY (service role key)"
    echo "------------"
    if [ "$CURRENT_SUPABASE_SERVICE_KEY" != "NOT_SET" ] && [ "$CURRENT_SUPABASE_SERVICE_KEY" != "your-service-role-key" ]; then
        echo "Current value: ${CURRENT_SUPABASE_SERVICE_KEY:0:20}... (hidden)"
    else
        echo "Current value: Not configured"
    fi
    echo ""
    read -p "SUPABASE_SERVICE_KEY (press Enter to keep current): " SUPABASE_SERVICE_KEY_INPUT
    
    if [ -z "$SUPABASE_SERVICE_KEY_INPUT" ]; then
        SUPABASE_SERVICE_KEY_INPUT="$CURRENT_SUPABASE_SERVICE_KEY"
        echo "✓ Keeping existing SUPABASE_SERVICE_KEY"
    else
        echo "✓ Will update SUPABASE_SERVICE_KEY"
    fi
fi

# Update .env file with the values
GROQ_KEY_INPUT="$GROQ_KEY_INPUT" SERVER_KEY_INPUT="$SERVER_KEY_INPUT" SUPABASE_URL_INPUT="$SUPABASE_URL_INPUT" SUPABASE_KEY_INPUT="$SUPABASE_KEY_INPUT" SUPABASE_SERVICE_KEY_INPUT="$SUPABASE_SERVICE_KEY_INPUT" python3 << 'EOF'
import os
import re

groq_key = os.environ.get('GROQ_KEY_INPUT', '').strip()
server_key = os.environ.get('SERVER_KEY_INPUT', '').strip()
supabase_url = os.environ.get('SUPABASE_URL_INPUT', '').strip()
supabase_key = os.environ.get('SUPABASE_KEY_INPUT', '').strip()
supabase_service_key = os.environ.get('SUPABASE_SERVICE_KEY_INPUT', '').strip()

with open('.env', 'r') as f:
    content = f.read()

# Replace GROQ_API_KEY
if groq_key and groq_key != 'NOT_SET':
    content = re.sub(r'GROQ_API_KEY=.*', f'GROQ_API_KEY={groq_key}', content)
    print("✓ Updated GROQ_API_KEY")

# Replace SERVER_API_KEY
if server_key and server_key != 'NOT_SET':
    content = re.sub(r'SERVER_API_KEY=.*', f'SERVER_API_KEY={server_key}', content)
    print("✓ Updated SERVER_API_KEY")

# Replace SUPABASE_URL if provided
if supabase_url and supabase_url != 'NOT_SET':
    if 'SUPABASE_URL=' in content:
        content = re.sub(r'SUPABASE_URL=.*', f'SUPABASE_URL={supabase_url}', content)
    else:
        # Add after SERVER_API_KEY line
        content = re.sub(r'(SERVER_API_KEY=.*\n)', f'\\1SUPABASE_URL={supabase_url}\n', content)
    print("✓ Updated SUPABASE_URL")

# Replace SUPABASE_KEY if provided
if supabase_key and supabase_key != 'NOT_SET':
    if 'SUPABASE_KEY=' in content:
        content = re.sub(r'SUPABASE_KEY=.*', f'SUPABASE_KEY={supabase_key}', content)
    else:
        # Add after SUPABASE_URL line
        content = re.sub(r'(SUPABASE_URL=.*\n)', f'\\1SUPABASE_KEY={supabase_key}\n', content)
    print("✓ Updated SUPABASE_KEY")

# Replace SUPABASE_SERVICE_KEY if provided
if supabase_service_key and supabase_service_key != 'NOT_SET':
    if 'SUPABASE_SERVICE_KEY=' in content:
        content = re.sub(r'SUPABASE_SERVICE_KEY=.*', f'SUPABASE_SERVICE_KEY={supabase_service_key}', content)
    else:
        # Add after SUPABASE_KEY line
        content = re.sub(r'(SUPABASE_KEY=.*\n)', f'\\1SUPABASE_SERVICE_KEY={supabase_service_key}\n', content)
    print("✓ Updated SUPABASE_SERVICE_KEY")

with open('.env', 'w') as f:
    f.write(content)
EOF

# Secure the .env file
chmod 600 "$INSTALL_DIR/.env"

echo ""
echo "✓ Environment configured"
echo ""

# ==================== STEP 8: SET PERMISSIONS ====================
echo "[8/10] Setting permissions..."
chown -R $SERVICE_USER:$SERVICE_GROUP "$INSTALL_DIR"
chmod 600 "$INSTALL_DIR/.env"
echo "✓ Permissions set"
echo ""

# ==================== STEP 9: SYSTEMD SERVICE ====================
echo "[9/10] Setting up systemd service..."

# Create systemd service file
cat > /tmp/voice-assistant-server.service <<EOF
[Unit]
Description=Voice Assistant Server
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_GROUP
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$VENV_DIR/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="PYTHONUNBUFFERED=1"
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$VENV_DIR/bin/python3 $INSTALL_DIR/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

mv /tmp/voice-assistant-server.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable voice-assistant-server.service
echo "✓ Systemd service configured"
echo ""

# ==================== STEP 10: NGINX CONFIGURATION ====================
echo "[10/10] Configuring Nginx..."

# Create nginx configuration
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

# ==================== START SERVICE ====================
echo "Starting service..."
systemctl start voice-assistant-server.service

# Wait for service to initialize
sleep 2

# Check if service is actually running
echo ""
echo "Checking service status..."
if systemctl is-active --quiet voice-assistant-server.service; then
    echo "✅ Service is RUNNING successfully!"
    echo ""
    echo "==========================================="
    echo "Setup Complete!"
    echo "==========================================="
    echo ""
    
    # Test local connectivity
    echo "Testing local connectivity..."
    HEALTH_CHECK=$(curl -s http://localhost:8000/health || echo "FAILED")
    if [[ "$HEALTH_CHECK" == *"healthy"* ]]; then
        echo "✅ Local health check passed: $HEALTH_CHECK"
    else
        echo "⚠️  Local health check failed (service may still be starting)"
    fi
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
    journalctl -u voice-assistant-server.service -n 20 --no-pager
    echo "-------------------------------------"
    echo ""
    echo "To fix:"
    echo "  1. Check the error logs above"
    echo "  2. Edit .env if needed: nano $INSTALL_DIR/.env"
    echo "  3. Run this script again: bash $SCRIPT_DIR/setup.sh"
    echo ""
    exit 1
fi

# ==================== CLOUDFLARE TUNNEL SETUP ====================
# Check if cloudflared is already configured
CLOUDFLARED_CONFIGURED=false
if systemctl is-active --quiet cloudflared 2>/dev/null; then
    CLOUDFLARED_CONFIGURED=true
fi

if [ "$IS_FRESH_INSTALL" = true ] || [ "$CLOUDFLARED_CONFIGURED" = false ]; then
    # Fresh install or cloudflared not configured - offer setup
    echo ""
    echo "==================================="
    echo "Cloudflare Tunnel Setup"
    echo "==================================="
    echo ""
    
    if [ "$CLOUDFLARED_CONFIGURED" = false ]; then
        echo "Cloudflare Tunnel is NOT configured."
    fi
    
    echo "Do you want to set up Cloudflare Tunnel now?"
    echo "  1) Yes - Install and configure Cloudflare Tunnel"
    echo "  2) No - Skip (you can run this script again later)"
    echo ""
    read -p "Choose option [1-2]: " CLOUDFLARE_CHOICE
    
    if [ "$CLOUDFLARE_CHOICE" = "1" ]; then
        # Install cloudflared if not present
        if ! command -v cloudflared &> /dev/null; then
            echo ""
            echo "Installing cloudflared..."
            wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
            dpkg -i cloudflared-linux-amd64.deb
            rm cloudflared-linux-amd64.deb
            echo "✓ cloudflared installed"
        else
            echo "✓ cloudflared already installed"
        fi
        
        echo ""
        echo "==================================="
        echo "Cloudflare Tunnel Configuration Steps"
        echo "==================================="
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
        echo "  Set CLIENT_API_KEY to the SERVER_API_KEY shown earlier"
        echo ""
    else
        echo "✓ Skipped Cloudflare Tunnel setup"
    fi
else
    # Update scenario and cloudflared is already configured
    echo ""
    echo "==================================="
    echo "Cloudflare Tunnel Status"
    echo "==================================="
    echo ""
    echo "✅ Cloudflare Tunnel is already configured and running"
    echo ""
    echo "Do you want to reconfigure Cloudflare Tunnel?"
    echo "  1) No - Keep current configuration (recommended)"
    echo "  2) Yes - Show reconfiguration instructions"
    echo ""
    read -p "Choose option [1-2]: " CLOUDFLARE_RECONFIG_CHOICE
    
    if [ "$CLOUDFLARE_RECONFIG_CHOICE" = "2" ]; then
        echo ""
        echo "==================================="
        echo "Cloudflare Tunnel Reconfiguration"
        echo "==================================="
        echo ""
        echo "To reconfigure your tunnel:"
        echo ""
        echo "View current config: cat /etc/cloudflared/config.yml"
        echo "Edit config: nano /etc/cloudflared/config.yml"
        echo "Restart tunnel: systemctl restart cloudflared"
        echo "View tunnel status: systemctl status cloudflared"
        echo "View tunnel logs: journalctl -u cloudflared -f"
        echo ""
    else
        echo "✓ Keeping current Cloudflare Tunnel configuration"
    fi
fi

echo ""
echo "==========================================="
echo "Useful Commands"
echo "==========================================="
echo ""
echo "Service Status:"
echo "  systemctl status voice-assistant-server.service"
echo ""
echo "View live logs:"
echo "  journalctl -u voice-assistant-server.service -f"
echo ""
echo "Check recent logs:"
echo "  journalctl -u voice-assistant-server.service -n 50"
echo ""
echo "Restart service:"
echo "  systemctl restart voice-assistant-server.service"
echo ""
echo "Stop service:"
echo "  systemctl stop voice-assistant-server.service"
echo ""
echo "Test endpoints:"
echo "  curl http://localhost:8000/health"
echo "  curl http://localhost:80/health"
echo ""
echo "Edit configuration:"
echo "  nano $INSTALL_DIR/.env"
echo "  # Then restart: systemctl restart voice-assistant-server.service"
echo ""
echo "==========================================="
echo "You can run this script again anytime to update!"
echo "==========================================="
echo ""

