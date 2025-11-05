# Deployment Guide

This guide covers deploying the voice assistant in a client-server architecture.

## Architecture Overview

- **Raspberry Pi Client**: Records audio, sends to server, plays response
- **Debian Server**: Processes audio via Groq API, returns speech response
- **Cloudflare Tunnel**: Provides automatic SSL/TLS, secure tunneling, DDoS protection

### Why Cloudflare Tunnel?

This deployment uses **Cloudflare Tunnel** (cloudflared) which provides several advantages:

- ✅ **No public IP required** - Works behind NAT/firewall
- ✅ **No port forwarding** - No need to open ports 80/443
- ✅ **Automatic SSL/TLS** - Zero certificate management
- ✅ **Built-in DDoS protection** - Enterprise-grade security
- ✅ **Free tier available** - No cost for basic usage
- ✅ **Simple setup** - 5 commands to get running

Traditional deployments require managing SSL certificates, opening firewall ports, and exposing your server's IP. Cloudflare Tunnel eliminates all of that!

## Deployment Approach

This guide uses a **Git-based deployment** workflow:

1. **Development**: You develop and test code on your local machine (Mac)
2. **Version Control**: Code is pushed to a Git repository (GitHub)
3. **Deployment**: Server/Pi pulls code from Git repository
4. **Updates**: Pull latest changes and restart services

**Repository Structure:**
```
javia/                 # Git repository root
├── server/                      # Server application
│   ├── main.py                  # FastAPI application
│   ├── config.py                # Configuration
│   ├── requirements.txt         # Python dependencies
│   ├── env.example             # Environment template
│   ├── deploy/                  # Deployment scripts
│   │   ├── deploy.sh           # Server deployment script
│   │   ├── nginx/              # Nginx configuration
│   │   └── systemd/            # Systemd service files
│   ├── services/               # Groq API services
│   ├── middleware/             # Authentication
│   └── models/                 # Data models
│
├── pi_client/                   # Raspberry Pi client
│   ├── client.py               # Main client application
│   ├── requirements.txt        # Python dependencies
│   ├── env.example            # Environment template
│   └── deploy/                 # Deployment scripts
│       └── install_client.sh  # Client installation script
│
├── docs/                        # Documentation
└── README.md                    # Main documentation
```

**Deployment Paths:**
- **Server**: Code deployed to `/opt/javia/`
- **Pi Client**: Code deployed to `~/javia_client/`

## Prerequisites

### Debian Server Requirements

- **OS**: Debian 13 (or Ubuntu 22.04+)
- **CPU**: 2+ cores recommended
- **RAM**: 2GB+ recommended
- **Disk**: 10GB+ free space
- **Network**: Internet connection (public IP not required with Cloudflare Tunnel!)
- **Ports**: No inbound ports need to be open (Cloudflare Tunnel uses outbound connections)
- **Git**: Installed
- **FFmpeg**: Required for audio compression (automatically installed by setup script)

**Note:** With Cloudflare Tunnel, your server can be behind NAT/firewall and doesn't need a public IP address or open ports!

### Raspberry Pi Requirements

- **Hardware**: Raspberry Pi 5 (with 40-pin GPIO header)
- **Audio**: INMP441 microphone + MAX98357A amplifier (configured)
- **Network**: WiFi or Ethernet connection
- **OS**: Raspberry Pi OS (64-bit recommended for Pi 5)
- **Git**: Installed

### Domain and DNS

- Custom domain (e.g., yourdomain.com)
- Cloudflare account (free tier is sufficient)
- Domain configured in Cloudflare

## Quick Start Summary

**For the impatient**, here's the entire deployment in brief:

**Server (10 minutes):**
```bash
# On your server
sudo apt update && sudo apt install -y git
cd /tmp && git clone https://github.com/shreyashguptas/javia.git
cd javia/server/deploy && sudo bash deploy.sh
# Script will prompt for GROQ_API_KEY and auto-generate SERVER_API_KEY
# SAVE the generated SERVER_API_KEY!
# Then setup Cloudflare Tunnel (see Part 1, Step 6)
# Commands: cloudflared tunnel login → create → configure → route → start
```

**Pi Client (5 minutes):**
```bash
# On your Raspberry Pi
cd /tmp && git clone https://github.com/shreyashguptas/javia.git
cd javia/pi_client/deploy && bash install_client.sh
# Edit ~/javia_client/.env with server URL and API key
sudo systemctl start voice-assistant-client.service
```

**Updates (30 seconds):**
```bash
# Push from local → Pull on server/Pi → Restart service
```

Read on for detailed step-by-step instructions...

## Git Repository Setup

Before deploying, ensure your code is in a Git repository:

**If you don't have a GitHub repository yet:**

1. Create a new repository on GitHub (can be private)
2. On your local machine (Mac):
   ```bash
   cd /Users/shreyashgupta/Documents/Github/javia
   git init  # If not already initialized
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/shreyashguptas/javia.git
   git push -u origin main
   ```

**For Private Repositories:**

You'll need to authenticate when cloning. Options:
1. **Personal Access Token** (recommended):
   - GitHub → Settings → Developer settings → Personal access tokens
   - Generate new token with `repo` scope
   - Use: `git clone https://YOUR_TOKEN@github.com/shreyashguptas/javia.git`

2. **SSH Keys** (more secure):
   - Generate SSH key on server/Pi: `ssh-keygen -t ed25519`
   - Add public key to GitHub: Settings → SSH keys
   - Use: `git clone git@github.com:shreyashguptas/javia.git`

**For Public Repositories:**
- Simply use: `git clone https://github.com/shreyashguptas/javia.git`

## Part 1: Server Deployment

### Step 1: Prepare Server

SSH into your Debian server:

```bash
ssh user@your-server-ip
```

Update system:

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y git
```

### Step 2: Clone Repository

Clone this repository to your server:

```bash
cd /tmp
git clone https://github.com/shreyashguptas/javia.git
```

> **Note**: Replace `YOUR_USERNAME` with your actual GitHub username. If you have a private repo, you'll need to setup SSH keys or use a personal access token.

### Step 3: Run Deployment Script

```bash
cd /tmp/javia/server/deploy
sudo bash deploy.sh
```

The script will:
- Install Python, pip, nginx, wget
- Create service user (`voiceassistant`)
- Copy server files to `/opt/javia/`
- Setup virtual environment
- Install Python dependencies
- **Prompt you for your GROQ_API_KEY**
- **Automatically generate a SERVER_API_KEY using UUID7**
- Configure `.env` file automatically
- Create systemd service
- Start the service
- **Configure Nginx as a reverse proxy (HTTP on port 80)**
- **Install Cloudflare Tunnel (cloudflared) for automatic SSL**

**Note**: The deployment script expects files in `/tmp/javia/server/`. It will copy all server files to `/opt/javia/` where the application will run.

### Step 4: API Configuration (Automated)

During deployment (Step 7 of the script), you will be prompted to:

1. **Enter your GROQ_API_KEY**: Paste your Groq API key when prompted
2. **Save the generated SERVER_API_KEY**: The script will automatically generate a secure UUID7-based API key and display it prominently

**Important**: When the script displays the `SERVER_API_KEY`, **copy and save it immediately**! You will need this exact key to configure the Raspberry Pi client later.

The script automatically updates the `.env` file with both keys, so you don't need to manually edit it.

**If you need to change the API keys later**, edit:

```bash
sudo nano /opt/javia/.env
```

After manual edits, restart the service:

```bash
sudo systemctl restart voice-assistant-server.service
```

**Optional configuration** (advanced users):

You can customize model settings and other parameters in `/opt/javia/.env`:

```env
# Optional: Customize models
WHISPER_MODEL=whisper-large-v3-turbo
LLM_MODEL=openai/gpt-oss-20b
TTS_MODEL=playai-tts
TTS_VOICE=Cheyenne-PlayAI
```

### Step 5: Verify Service is Running

Check service status:

```bash
sudo systemctl status voice-assistant-server.service
```

Test health endpoint:

```bash
curl http://localhost:8000/health
```

You should see:

```json
{"status":"healthy","version":"1.0.0"}
```

View logs:

```bash
sudo journalctl -u voice-assistant-server.service -f
```

### Step 6: Setup Cloudflare Tunnel (Automatic SSL)

The deployment script has already:
- ✅ Configured Nginx as a reverse proxy on port 80
- ✅ Installed Cloudflare Tunnel (cloudflared)
   - If not then go here - https://pkg.cloudflareclient.com/#debian

Now you need to configure the tunnel to connect your domain to the server.

**Prerequisites:**
- Your domain must already be added to Cloudflare
- Your domain's nameservers must point to Cloudflare

#### 6.1: Authenticate with Cloudflare

Run the following command:

```bash
cloudflared tunnel login
```

This will:
1. Display a URL in the terminal
2. Open your browser (or copy the URL to a browser)
3. Ask you to select your domain and authorize the tunnel
4. Save authentication credentials to `~/.cloudflared/cert.pem`

#### 6.2: Create a Tunnel

Create a named tunnel:

```bash
cloudflared tunnel create javia-voice-assistant
```

This will:
- Create a tunnel with the name `javia-voice-assistant`
- Display a **Tunnel ID** (UUID) - **save this!**
- Create a credentials file at `~/.cloudflared/<TUNNEL_ID>.json`

Example output:
```
Tunnel credentials written to /root/.cloudflared/12345678-abcd-efgh-ijkl-123456789012.json
Created tunnel javia-voice-assistant with id 12345678-abcd-efgh-ijkl-123456789012
```

#### 6.3: Configure the Tunnel

Create the tunnel configuration file (replace `YOUR_DOMAIN` with your actual domain and `<TUNNEL_ID>` with the ID from step 6.2):

```bash
sudo mkdir -p /etc/cloudflared

sudo tee /etc/cloudflared/config.yml > /dev/null <<EOF
tunnel: <TUNNEL_ID>
credentials-file: /root/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: YOUR_DOMAIN.com
    service: http://localhost:80
  - service: http_status:404
EOF
```

**Example** (if your tunnel ID is `12345678-abcd-efgh-ijkl-123456789012` and domain is `voice.example.com`):

```bash
sudo tee /etc/cloudflared/config.yml > /dev/null <<EOF
tunnel: 12345678-abcd-efgh-ijkl-123456789012
credentials-file: /root/.cloudflared/12345678-abcd-efgh-ijkl-123456789012.json

ingress:
  - hostname: voice.example.com
    service: http://localhost:80
  - service: http_status:404
EOF
```

#### 6.4: Route Your Domain to the Tunnel

This command automatically creates a CNAME record in your Cloudflare DNS:

```bash
cloudflared tunnel route dns javia-voice-assistant YOUR_DOMAIN.com
```

Replace `YOUR_DOMAIN.com` with your actual domain (e.g., `voice.example.com`).

You should see:
```
Created CNAME record for YOUR_DOMAIN.com which will route to tunnel ...
```

#### 6.5: Install and Start the Tunnel Service

Install the tunnel as a system service:

```bash
sudo cloudflared service install
```

Start and enable the service:

```bash
sudo systemctl start cloudflared
sudo systemctl enable cloudflared
```

Check the status:

```bash
sudo systemctl status cloudflared
```

You should see "active (running)".

### Step 7: Test Server

Test locally first:

```bash
# Test the application directly
curl http://localhost:8000/health

# Test through Nginx
curl http://localhost:80/health
```

Test from your local machine (after tunnel is running):

```bash
# From your Mac or another computer
curl https://yourdomain.com/health
```

You should see:

```json
{"status":"healthy","version":"1.0.0"}
```

Test API documentation:

Open in browser: `https://yourdomain.com/docs`

You should see the FastAPI documentation interface.

**Note:** SSL/TLS is handled automatically by Cloudflare Tunnel! Your connection is encrypted end-to-end without any manual certificate management.

## Part 2: Raspberry Pi Client Deployment

### Step 1: Prepare Pi

SSH into your Raspberry Pi:

```bash
ssh pi@raspberrypi.local
```

Ensure audio hardware is configured (see main README.md in the root of the repository).

### Step 2: Clone Repository

Clone this repository to your Pi:

```bash
cd /tmp
git clone https://github.com/shreyashguptas/javia.git
```

> **Note**: Replace `YOUR_USERNAME` with your actual GitHub username. If you have a private repo, you'll need to setup SSH keys or use a personal access token.

### Step 3: Run Installation Script

```bash
cd /tmp/javia/pi_client/deploy
bash install_client.sh
```

Follow the prompts. The script will:
- Install system dependencies (python3-pyaudio, python3-rpi.gpio, etc.)
- Create virtual environment at `~/venvs/pi_client`
- Copy client files to `~/javia_client/`
- Create systemd service (`voice-assistant-client.service`)

**Note**: The installation script expects files in `/tmp/javia/pi_client/`. It will copy all client files to `~/javia_client/` where the application will run.

### Step 4: Configure Environment Variables

Edit the client configuration:

```bash
nano ~/javia_client/.env
```

Set the following values:

```env
# Required: Your server URL (with https://)
SERVER_URL=https://yourdomain.com

# Device timezone (required for scheduled operations)
DEVICE_TIMEZONE=America/Los_Angeles

# Hardware configuration
BUTTON_PIN=17
AMPLIFIER_SD_PIN=27

# Audio configuration
SAMPLE_RATE=48000
MICROPHONE_GAIN=2.0
FADE_DURATION_MS=50
```

**Note**: Pi clients use device UUID authentication (`X-Device-UUID` header), not API keys. The device UUID is automatically generated and stored in `~/.javia_device_uuid` when the client first runs. You must register this UUID on the server using the `register_device.sh` script before the device can connect.

### Step 5: Secure the Configuration

```bash
chmod 600 ~/javia_client/.env
```

This ensures only your user can read the configuration file.

### Step 6: Test Client Manually

Before enabling the service, test manually:

```bash
cd ~/javia_client
source ~/venvs/pi_client/bin/activate
python3 client.py
```

Press the button and speak. Verify:
1. ✅ Recording works
2. ✅ Server communication succeeds
3. ✅ Audio playback works

Press `Ctrl+C` to stop.

### Step 7: Enable Service (Optional)

To run automatically on boot:

```bash
sudo systemctl start voice-assistant-client.service
sudo systemctl status voice-assistant-client.service
```

View logs:

```bash
sudo journalctl -u voice-assistant-client.service -f
```

To stop auto-start:

```bash
sudo systemctl stop voice-assistant-client.service
sudo systemctl disable voice-assistant-client.service
```

## Part 3: Testing and Validation

### Test Server

Use the test script:

```bash
cd /opt/javia
source venv/bin/activate
python3 test_server.py
```

This will:
- ✅ Test health check
- ✅ Test authentication
- ✅ Test audio processing (if GROQ_API_KEY is valid)

### Test Client

Use the test script (doesn't require GPIO):

```bash
cd ~/javia_client
source ~/venvs/pi_client/bin/activate
python3 test_client.py
```

This will:
- ✅ Test audio directory
- ✅ Test server connection
- ✅ Test server processing
- ✅ Test audio validation

## Part 4: Security Hardening

### Server Security

#### 4.1: Firewall (UFW)

With Cloudflare Tunnel, you only need SSH open (and even that can be restricted):

```bash
sudo apt install ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH only
sudo ufw enable
```

**Note:** With Cloudflare Tunnel, you don't need to open ports 80 or 443! The tunnel creates outbound connections to Cloudflare, making your server more secure.

**Optional - Restrict SSH:** For even better security, restrict SSH to your IP:
```bash
sudo ufw allow from YOUR_IP_ADDRESS to any port 22
```

#### 4.2: Fail2Ban (Optional)

Protect against brute force:

```bash
sudo apt install fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

#### 4.3: Automatic Updates

```bash
sudo apt install unattended-upgrades
sudo dpkg-reconfigure --priority=low unattended-upgrades
```

### Pi Security

#### 4.1: Change Default Password

```bash
passwd
```

#### 4.2: Disable SSH Password Authentication (Use SSH Keys)

```bash
sudo nano /etc/ssh/sshd_config
```

Set:
```
PasswordAuthentication no
```

Restart SSH:
```bash
sudo systemctl restart ssh
```

### Cloudflare Security

Cloudflare Tunnel provides built-in security benefits:

- ✅ **No exposed ports** - Tunnel creates outbound connections only
- ✅ **Automatic SSL/TLS** - End-to-end encryption with no certificate management
- ✅ **DDoS Protection** - Already enabled by default
- ✅ **No public IP exposure** - Server IP is hidden from attackers

#### Additional Cloudflare Security (Optional)

**4.1: Configure Rate Limiting**

1. Go to **Security** → **WAF**
2. Create rate limiting rule:
   - **Name**: Voice API Rate Limit
   - **If**: URI Path contains `/api/v1/process`
   - **Then**: Block
   - **Threshold**: 60 requests per minute per IP

**4.2: Enable Bot Protection**

1. Go to **Security** → **Bots**
2. Enable **Bot Fight Mode** (free tier)

**4.3: Enable Cloudflare Access (Optional)**

For additional authentication layer:
1. Go to **Zero Trust** → **Access**
2. Create access policies to restrict who can access your domain

## Part 5: Monitoring and Maintenance

### Server Monitoring

#### View Logs

Application logs:
```bash
sudo journalctl -u voice-assistant-server.service -f
```

Nginx access logs:
```bash
sudo tail -f /var/log/nginx/voice-assistant-access.log
```

Nginx error logs:
```bash
sudo tail -f /var/log/nginx/voice-assistant-error.log
```

#### Check Service Status

```bash
sudo systemctl status voice-assistant-server.service
```

#### Restart Service

```bash
sudo systemctl restart voice-assistant-server.service
```

### Client Monitoring

#### View Logs

```bash
sudo journalctl -u voice-assistant-client.service -f
```

#### Check Service Status

```bash
sudo systemctl status voice-assistant-client.service
```

#### Restart Service

```bash
sudo systemctl restart voice-assistant-client.service
```

### Disk Space Management

Server automatically cleans up temp files, but monitor:

```bash
df -h
du -sh /tmp
```

### Update Server Code

When you update the code in your Git repository:

**On your local machine:**
```bash
# 1. Commit and push your changes
git add .
git commit -m "Update server code"
git push origin main
```

**On the server:**
```bash
# 1. Navigate to a temporary location
cd /tmp
rm -rf javia  # Remove old clone if exists
git clone https://github.com/shreyashguptas/javia.git

# 2. Copy updated files to installation directory
sudo cp -r /tmp/javia/server/* /opt/javia/

# 3. Update dependencies if needed
sudo -u voiceassistant /opt/javia/venv/bin/pip install -r /opt/javia/requirements.txt

# 4. Restart service
sudo systemctl restart voice-assistant-server.service

# 5. Clean up
rm -rf /tmp/javia
```

**Alternative (if you keep a Git clone on the server):**
```bash
# If you've kept the repo on the server
cd /path/to/javia
git pull origin main
sudo cp -r server/* /opt/javia/
sudo systemctl restart voice-assistant-server.service
```

### Update Client Code

When you update the code in your Git repository:

**On your local machine:**
```bash
# 1. Commit and push your changes
git add .
git commit -m "Update client code"
git push origin main
```

**On the Pi:**
```bash
# 1. Navigate to a temporary location
cd /tmp
rm -rf javia  # Remove old clone if exists
git clone https://github.com/shreyashguptas/javia.git

# 2. Copy updated files
cp -r /tmp/javia/pi_client/* ~/javia_client/

# 3. Restart service
sudo systemctl restart voice-assistant-client.service

# 4. Clean up
rm -rf /tmp/javia
```

**Alternative (if you keep a Git clone on the Pi):**
```bash
# If you've kept the repo on the Pi
cd /path/to/javia
git pull origin main
cp -r pi_client/* ~/javia_client/
sudo systemctl restart voice-assistant-client.service
```

## Part 6: Troubleshooting

### Server Issues

#### Service Won't Start

Check logs:
```bash
sudo journalctl -u voice-assistant-server.service -xe
```

Common issues:
- Missing environment variables in `.env`
- Port 8000 already in use
- Python dependencies not installed
- **FFmpeg not installed** - Audio compression will fail with "No such file or directory: 'ffmpeg'"

#### Audio Processing Errors

If you see errors like "Audio compression failed: [Errno 2] No such file or directory: 'ffmpeg'":

**Solution:**
```bash
# Install ffmpeg manually
sudo apt update && sudo apt install ffmpeg

# Restart the service
sudo systemctl restart voice-assistant-server.service
```

**Note:** The deployment script should automatically install ffmpeg. If it didn't, you can install it manually as shown above.

#### Nginx 502 Bad Gateway

Check if application is running:
```bash
curl http://localhost:8000/health
```

If not, check application logs.

#### Cloudflare Tunnel Issues

**Tunnel not connecting:**

Check tunnel status:
```bash
sudo systemctl status cloudflared
```

View tunnel logs:
```bash
sudo journalctl -u cloudflared -f
```

Common issues:
- Tunnel configuration file has wrong tunnel ID
- Credentials file path is incorrect
- Domain not routed to tunnel

**Verify tunnel configuration:**
```bash
cat /etc/cloudflared/config.yml
```

**List your tunnels:**
```bash
cloudflared tunnel list
```

**Test tunnel manually:**
```bash
sudo cloudflared tunnel run javia-voice-assistant
```

### Client Issues

#### Cannot Connect to Server

Test DNS:
```bash
nslookup yourdomain.com
```

Test connectivity:
```bash
ping yourdomain.com
curl https://yourdomain.com/health
```

Check API key is correct in `.env`.

#### Recording Not Working

See main TROUBLESHOOTING.md for audio issues.

#### Service Crashes

Check logs:
```bash
sudo journalctl -u voice-assistant-client.service -xe
```

Run manually to see errors:
```bash
cd ~/javia_client
source ~/venvs/pi_client/bin/activate
python3 client.py
```

### Network Issues

#### High Latency

Test latency:
```bash
time curl https://yourdomain.com/health
```

Check:
- Server location (closer is better)
- Network congestion
- Cloudflare routing

#### Rate Limiting

If you get 429 errors:
- Wait a minute and try again
- Check Cloudflare rate limits
- Check Nginx rate limits

### Git and Deployment Issues

#### Git Clone Fails - Authentication Required

If you get "repository not found" or authentication errors:

**For HTTPS (Private Repos):**
```bash
# Use personal access token
git clone https://YOUR_TOKEN@github.com/shreyashguptas/javia.git
```

**For SSH (Recommended for Private Repos):**
```bash
# Generate SSH key (if not exists)
ssh-keygen -t ed25519 -C "your_email@example.com"

# Display public key
cat ~/.ssh/id_ed25519.pub

# Add this key to GitHub → Settings → SSH and GPG keys
# Then clone using SSH
git clone git@github.com:shreyashguptas/javia.git
```

#### Deployment Script Can't Find Files

Error: `Cannot find server files!` or `Expected to find main.py at...`

**Solution:**
1. Ensure you're running the script from the correct location:
   - Server: `/tmp/javia/server/deploy/`
   - Client: `/tmp/javia/pi_client/deploy/`
2. Check the repository was cloned completely:
   ```bash
   ls -la /tmp/javia/
   ls -la /tmp/javia/server/
   ls -la /tmp/javia/pi_client/
   ```

#### Permission Denied When Copying Files

Error: `Permission denied` when running deploy.sh

**Solution:**
```bash
# Ensure you're running with sudo (server only)
sudo bash deploy.sh

# For client, run as regular user (NOT sudo)
bash install_client.sh
```

## Part 7: Backup and Recovery

### What to Backup

Since code is in Git, you only need to backup **configuration and secrets**:

**Server - Configuration Files:**
- `.env` file (contains API keys)
- Cloudflare Tunnel configuration (`/etc/cloudflared/config.yml`)
- Cloudflare Tunnel credentials (`/root/.cloudflared/*.json`)

**Note:** Nginx configuration is automatically generated by the deployment script

**Client - Configuration Files:**
- `.env` file (contains API key and settings)

### Backup Server Configuration

```bash
# On server
sudo tar -czf ~/voice-assistant-backup-$(date +%Y%m%d).tar.gz \
  /opt/javia/.env \
  /etc/cloudflared/config.yml \
  /root/.cloudflared/

# Make it readable by your user
sudo chown $USER:$USER ~/voice-assistant-backup-*.tar.gz
```

Download backup to your local machine:
```bash
# On your local machine
scp user@server:~/voice-assistant-backup-*.tar.gz ~/backups/
```

### Backup Client Configuration

```bash
# On Pi
tar -czf ~/client-backup-$(date +%Y%m%d).tar.gz \
  ~/javia_client/.env

# Download to local machine (from your Mac)
scp pi@raspberrypi.local:~/client-backup-*.tar.gz ~/backups/
```

### Recovery

**To restore after a server failure:**

1. Deploy fresh installation following Part 1 (Steps 1-5)
2. Extract and restore backup:
   ```bash
   tar -xzf voice-assistant-backup-YYYYMMDD.tar.gz
   
   # Restore .env
   sudo cp opt/javia/.env /opt/javia/.env
   sudo chown voiceassistant:voiceassistant /opt/javia/.env
   sudo chmod 600 /opt/javia/.env
   
   # Restore Cloudflare Tunnel config
   sudo cp -r root/.cloudflared /root/
   sudo cp etc/cloudflared/config.yml /etc/cloudflared/config.yml
   ```
3. Restart services:
   ```bash
   sudo systemctl restart voice-assistant-server.service
   sudo systemctl restart cloudflared
   ```

**To restore client after Pi failure:**

1. Deploy fresh installation following Part 2
2. Extract backup:
   ```bash
   tar -xzf client-backup-YYYYMMDD.tar.gz
   cp javia_client/.env ~/javia_client/.env
   chmod 600 ~/javia_client/.env
   ```
3. Restart service: `sudo systemctl restart voice-assistant-client.service`

### Git Repository Backup

Your code is already backed up in Git, but ensure you:
- Push all changes regularly: `git push origin main`
- Consider creating a private repository if you haven't already
- Keep backups of your Git repository (GitHub already does this)

## Part 8: Cost Considerations

### Server Costs

- **VPS/Cloud**: $5-10/month (DigitalOcean, Linode, Vultr)
- **Cloudflare**: Free tier is sufficient
- **Groq API**: Check current pricing at groq.com

### Optimization Tips

1. **Choose server location close to your Pi** for lower latency
2. **Use Cloudflare free tier** - provides excellent DDoS protection
3. **Monitor Groq API usage** to stay within budget
4. **Consider cheaper VPS providers** (Hetzner, OVH) if available in your region

## Conclusion

Your voice assistant is now deployed in a secure, scalable client-server architecture!

**What You've Achieved:**
- ✅ Raspberry Pi handles local audio I/O
- ✅ Server processes via fast Groq API
- ✅ Cloudflare provides security and SSL
- ✅ Everything is encrypted and authenticated
- ✅ Systemd ensures services stay running
- ✅ Git-based deployment for easy updates
- ✅ Production-ready configuration

**Quick Reference Commands:**

**Server Management:**
```bash
# Check status
sudo systemctl status voice-assistant-server.service

# View logs
sudo journalctl -u voice-assistant-server.service -f

# Restart
sudo systemctl restart voice-assistant-server.service

# Update code
cd /tmp && git clone https://github.com/shreyashguptas/javia.git
sudo cp -r javia/server/* /opt/javia/
sudo systemctl restart voice-assistant-server.service
```

**Client Management:**
```bash
# Check status
sudo systemctl status voice-assistant-client.service

# View logs
sudo journalctl -u voice-assistant-client.service -f

# Restart
sudo systemctl restart voice-assistant-client.service

# Update code
cd /tmp && git clone https://github.com/shreyashguptas/javia.git
cp -r javia/pi_client/* ~/javia_client/
sudo systemctl restart voice-assistant-client.service
```

**Testing:**
```bash
# Test server health
curl https://yourdomain.com/health

# Test from client
curl https://yourdomain.com/health
```

Enjoy your voice assistant! 🎤🤖

## Additional Resources

- **Documentation**: See `/docs` folder for detailed guides
- **Troubleshooting**: See `docs/TROUBLESHOOTING.md`
- **Hardware Setup**: See `docs/HARDWARE.md`
- **API Reference**: Visit `https://yourdomain.com/docs` after deployment

