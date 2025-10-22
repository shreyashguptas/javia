# Server Deployment

This directory contains scripts for deploying and maintaining the Voice Assistant server.

## 📁 Directory Structure

```
deploy/
├── README.md                 # This file - deployment overview
├── deploy.sh                 # Initial server deployment (run once)
├── update/                   # Update scripts (run after code changes)
│   ├── update.sh            # Server update script
│   └── README.md            # Update documentation
├── systemd/                  # Systemd service files
│   └── voice-assistant-server.service
└── nginx/                    # Nginx configuration (optional)
```

## 🚀 Initial Deployment

**Run this ONCE when first setting up the server:**

```bash
# On your Debian server
cd /tmp
git clone https://github.com/shreyashguptas/javia.git
cd javia/server/deploy
sudo bash deploy.sh
```

This script will:
- Install system dependencies (Python, nginx, git)
- Create service user
- Set up Python virtual environment
- Configure .env file (prompts for GROQ_API_KEY)
- Generate SERVER_API_KEY (save this for Pi client!)
- Install systemd service
- Configure nginx
- Install Cloudflare tunnel

**After initial deployment, continue with Cloudflare setup** (see output instructions).

## 🔄 Updating After Code Changes

**Run this whenever you push code changes to GitHub:**

```bash
# SSH to your server
ssh user@your-server-ip

# Run the update script
sudo bash /opt/javia/deploy/update/update.sh
```

See **[update/README.md](update/README.md)** for detailed update documentation.

## 📝 Quick Reference

### When to Use Each Script

| Script | When to Use | Frequency |
|--------|-------------|-----------|
| `deploy.sh` | First-time server setup | Once |
| `update/update.sh` | After pushing code changes | Every update |

### Important Paths

- **Installation directory**: `/opt/javia`
- **Service user**: `voiceassistant`
- **Virtual environment**: `/opt/javia/venv`
- **Configuration**: `/opt/javia/.env`
- **Service file**: `/etc/systemd/system/voice-assistant-server.service`
- **Nginx config**: `/etc/nginx/sites-available/voice-assistant`

### Common Commands

```bash
# View service status
sudo systemctl status voice-assistant-server.service

# View logs
sudo journalctl -u voice-assistant-server.service -f

# Restart service
sudo systemctl restart voice-assistant-server.service

# Test server locally
curl http://localhost:8000/health

# Test server publicly
curl https://yourdomain.com/health
```

## 🔒 Security Notes

- ✅ `.env` file contains sensitive API keys
- ✅ File permissions set to 600 (owner read/write only)
- ✅ Service runs as non-root user `voiceassistant`
- ✅ API keys never committed to git

## 📚 Documentation

- **[update/README.md](update/README.md)** - Detailed update instructions
- **[../../docs/DEPLOYMENT.md](../../docs/DEPLOYMENT.md)** - Complete deployment guide
- **[../../docs/TROUBLESHOOTING.md](../../docs/TROUBLESHOOTING.md)** - Common issues

