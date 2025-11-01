# Server Deployment Guide

This guide covers deploying the Voice Assistant server on a Debian-based system (tested on Debian 13).

## Prerequisites

- Fresh Debian 13 server (or compatible Linux distribution)
- Root or sudo access
- Domain name (for Cloudflare Tunnel setup)
- GROQ API key ([Get one here](https://console.groq.com/keys))

## Quick Start

### Fresh Installation

```bash
# 1. Clone the repository to /tmp
cd /tmp
git clone https://github.com/shreyashguptas/javia.git

# 2. Run the setup script as root
cd javia/server/scripts/setup/
sudo bash setup.sh
```

The script will:
- Install all system dependencies (Python, Nginx, libopus, etc.)
- Create the service user
- Set up the Python virtual environment
- Prompt you for GROQ_API_KEY
- Generate a SERVER_API_KEY (save this for the Pi client!)
- Configure systemd service
- Set up Nginx reverse proxy
- Optionally guide you through Cloudflare Tunnel setup

### Updating Existing Installation

```bash
# 1. Pull latest code to /tmp
cd /tmp
rm -rf javia  # Remove old clone if exists
git clone https://github.com/shreyashguptas/javia.git

# 2. Run the same setup script
cd javia/server/scripts/setup/
sudo bash setup.sh
```

The script will:
- Detect existing installation
- Preserve your `.env` configuration
- Show current GROQ_API_KEY and SERVER_API_KEY
- Let you choose to keep or update values
- Update code and dependencies
- Restart the service

## What Gets Installed

### System Packages
- `python3`, `python3-pip`, `python3-venv` - Python runtime
- `nginx` - Reverse proxy
- `git`, `wget`, `rsync` - Utilities
- `libopus0`, `libopus-dev` - Opus audio codec (for compression)

### Python Packages (in virtual environment)
- `fastapi`, `uvicorn` - Web framework
- `groq` - GROQ API client
- `pydub` - Audio processing
- `python-dotenv` - Environment configuration
- `opuslib` - Opus audio compression
- `uuid6` - UUID7 generation for API keys

### Services
- `voice-assistant-server.service` - Main application service
- `nginx` - HTTP proxy on port 80
- `cloudflared` - Cloudflare Tunnel (optional)

## Installation Details

### Directory Structure

```
/opt/javia/                    # Main installation directory
├── main.py                    # FastAPI application
├── config.py                  # Configuration loader
├── .env                       # Environment variables (created during setup)
├── requirements.txt           # Python dependencies
├── venv/                      # Python virtual environment
├── middleware/                # Auth middleware
│   ├── __init__.py
│   └── auth.py
├── models/                    # Data models
│   ├── __init__.py
│   └── requests.py
└── services/                  # Business logic
    ├── __init__.py
    └── groq_service.py
```

### Environment Variables

The `.env` file contains:

```bash
# GROQ API Key (get from https://console.groq.com/keys)
GROQ_API_KEY=your_groq_api_key_here

# Server API Key (used by Pi client for authentication)
SERVER_API_KEY=generated_uuid7_key

# Server Configuration
HOST=0.0.0.0
PORT=8000
```

## Cloudflare Tunnel Setup

Cloudflare Tunnel allows you to expose your server securely without opening ports or using a VPN.

### Why Cloudflare Tunnel?

- ✅ No port forwarding needed
- ✅ Built-in DDoS protection
- ✅ Automatic HTTPS
- ✅ Hides your server IP
- ✅ Free for personal use

### Setup Steps

The setup script will offer to guide you through Cloudflare Tunnel setup. Here's what happens:

#### 1. Install cloudflared

The script installs `cloudflared` automatically if you choose to set up the tunnel.

#### 2. Authenticate with Cloudflare

```bash
cloudflared tunnel login
```

This opens a browser where you'll authorize the tunnel.

#### 3. Create a Tunnel

```bash
cloudflared tunnel create javia-voice-assistant
```

Save the Tunnel ID shown - you'll need it in the next step.

#### 4. Configure the Tunnel

```bash
cat > /etc/cloudflared/config.yml << 'EOF'
tunnel: <TUNNEL_ID_FROM_STEP_3>
credentials-file: /root/.cloudflared/<TUNNEL_ID>.json
ingress:
  - hostname: yourdomain.com
    service: http://localhost:80
  - service: http_status:404
EOF
```

Replace `<TUNNEL_ID>` and `yourdomain.com` with your actual values.

#### 5. Route DNS

```bash
cloudflared tunnel route dns javia-voice-assistant yourdomain.com
```

This creates a CNAME record in Cloudflare automatically.

#### 6. Start the Tunnel

```bash
cloudflared service install
systemctl start cloudflared
systemctl enable cloudflared
```

#### 7. Test

```bash
# Test local
curl http://localhost:80/health

# Test public
curl https://yourdomain.com/health
```

You should see: `{"status":"healthy","version":"1.0.0"}`

## Verifying Installation

### 1. Check Service Status

```bash
systemctl status voice-assistant-server.service
```

Should show "active (running)"

### 2. Check Nginx

```bash
systemctl status nginx
```

Should show "active (running)"

### 3. Test Health Endpoint

```bash
# Direct to app (port 8000)
curl http://localhost:8000/health

# Through Nginx (port 80)
curl http://localhost:80/health

# Through Cloudflare (HTTPS)
curl https://yourdomain.com/health
```

All should return: `{"status":"healthy","version":"1.0.0"}`

### 4. View Logs

```bash
# Live logs
journalctl -u voice-assistant-server.service -f

# Recent logs
journalctl -u voice-assistant-server.service -n 50
```

## Updating Configuration

### Change GROQ API Key

```bash
# Option 1: Edit .env directly
sudo nano /opt/javia/.env
# Change GROQ_API_KEY value
sudo systemctl restart voice-assistant-server.service

# Option 2: Run setup script again
cd /tmp/javia/server/deploy
sudo bash setup.sh
# Choose "Enter new GROQ_API_KEY" when prompted
```

### Change SERVER API Key

⚠️ **Warning**: Changing `SERVER_API_KEY` requires updating the Pi client!

```bash
# Run setup script
cd /tmp/javia/server/deploy
sudo bash setup.sh
# Choose "Generate new SERVER_API_KEY" when prompted
# Save the new key and update it on the Pi client
```

## Troubleshooting

### Service Won't Start

```bash
# Check logs
journalctl -u voice-assistant-server.service -n 50

# Common issues:
# - Invalid GROQ_API_KEY in .env
# - Port 8000 already in use
# - Missing dependencies
```

### Can't Connect from Pi Client

```bash
# Test health endpoint
curl https://yourdomain.com/health

# Check Cloudflare Tunnel
systemctl status cloudflared
journalctl -u cloudflared -f

# Verify SERVER_API_KEY matches on both server and Pi
cat /opt/javia/.env | grep SERVER_API_KEY
```

### Audio Issues

```bash
# Check libopus installation
dpkg -l | grep libopus

# Should show libopus0 and libopus-dev installed
# If missing, install:
sudo apt install libopus0 libopus-dev
```

## Maintenance

### View Logs

```bash
# Live logs
journalctl -u voice-assistant-server.service -f

# Recent logs
journalctl -u voice-assistant-server.service -n 100

# Filter by time
journalctl -u voice-assistant-server.service --since "1 hour ago"
```

### Restart Service

```bash
sudo systemctl restart voice-assistant-server.service
```

### Stop Service

```bash
sudo systemctl stop voice-assistant-server.service
```

### Check Resource Usage

```bash
# CPU and memory
top -u voiceassistant

# Disk usage
du -sh /opt/javia
```

## Uninstalling

```bash
# Stop and disable services
sudo systemctl stop voice-assistant-server.service
sudo systemctl disable voice-assistant-server.service
sudo systemctl stop cloudflared
sudo systemctl disable cloudflared

# Remove service files
sudo rm /etc/systemd/system/voice-assistant-server.service
sudo systemctl daemon-reload

# Remove installation directory
sudo rm -rf /opt/javia

# Remove nginx config
sudo rm /etc/nginx/sites-enabled/voice-assistant
sudo rm /etc/nginx/sites-available/voice-assistant
sudo systemctl restart nginx

# Optionally remove cloudflared
sudo apt remove cloudflared

# Optionally remove service user
sudo userdel voiceassistant
```

## Security Notes

1. **API Keys**: The `.env` file contains sensitive keys and is set to `600` permissions (owner read/write only)
2. **Service User**: The service runs as `voiceassistant` user (not root) for security
3. **Nginx**: Acts as a reverse proxy and handles HTTPS termination via Cloudflare
4. **Cloudflare**: Provides DDoS protection and hides your server IP
5. **Authentication**: All API requests require `CLIENT_API_KEY` header matching `SERVER_API_KEY`

## Next Steps

After server deployment:

1. ✅ Save your `SERVER_API_KEY` - you'll need it for the Pi client
2. ✅ Test the health endpoint: `curl https://yourdomain.com/health`
3. ✅ Set up your Raspberry Pi client using the Pi client setup guide
4. ✅ Configure the Pi client with your server URL and API key

## Support

For issues or questions, check:
- Application logs: `journalctl -u voice-assistant-server.service -f`
- Cloudflare Tunnel logs: `journalctl -u cloudflared -f`
- Nginx logs: `tail -f /var/log/nginx/error.log`
- Documentation: `/opt/javia/docs/` or the GitHub repository

