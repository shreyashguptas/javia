# Deployment Guide

This guide covers deploying the voice assistant in a client-server architecture.

## Architecture Overview

- **Raspberry Pi Client**: Records audio, sends to server, plays response
- **Debian Server**: Processes audio via Groq API, returns speech response
- **Cloudflare**: Provides DNS, SSL/TLS, DDoS protection

## Prerequisites

### Debian Server Requirements

- **OS**: Debian 13 (or Ubuntu 22.04+)
- **CPU**: 2+ cores recommended
- **RAM**: 2GB+ recommended
- **Disk**: 10GB+ free space
- **Network**: Static public IP address
- **Ports**: 80, 443 open to internet

### Raspberry Pi Requirements

- **Hardware**: Raspberry Pi Zero 2 W (or newer)
- **Audio**: INMP441 microphone + MAX98357A amplifier (configured)
- **Network**: WiFi connection
- **OS**: Raspberry Pi OS

### Domain and DNS

- Custom domain (e.g., yourdomain.com)
- Cloudflare account (free tier is sufficient)
- Domain configured in Cloudflare

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
```

### Step 2: Copy Files to Server

On your local machine, prepare deployment package:

```bash
cd voice_assistant/
tar -czf server-deploy.tar.gz server/
```

Upload to server:

```bash
scp server-deploy.tar.gz user@your-server-ip:/tmp/
```

On the server, extract files:

```bash
cd /tmp
tar -xzf server-deploy.tar.gz
mv server voice_assistant_deploy
```

### Step 3: Run Deployment Script

```bash
cd /tmp/voice_assistant_deploy/deploy
sudo bash deploy.sh
```

The script will:
- Install Python, pip, nginx
- Create service user
- Setup virtual environment
- Install Python dependencies
- Create systemd service
- Start the service

### Step 4: Configure Environment Variables

Edit the server configuration:

```bash
sudo nano /opt/voice_assistant/.env
```

Set the following values:

```env
# Required: Your Groq API key
GROQ_API_KEY=your_actual_groq_api_key_here

# Required: Generate a secure random key for authentication
SERVER_API_KEY=your_secure_random_key_here

# Optional: Customize models
WHISPER_MODEL=whisper-large-v3-turbo
LLM_MODEL=openai/gpt-oss-20b
TTS_MODEL=playai-tts
TTS_VOICE=Chip-PlayAI
```

**Generate a secure API key**:

```bash
# Option 1: Use openssl
openssl rand -hex 32

# Option 2: Use Python
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Save your `SERVER_API_KEY` - you'll need it for the Pi client!

After editing, restart the service:

```bash
sudo systemctl restart voice-assistant-server.service
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

### Step 6: Configure Nginx

Edit the Nginx configuration:

```bash
sudo nano /opt/voice_assistant/deploy/nginx/voice-assistant.conf
```

Update the following:

1. Replace `yourdomain.com` with your actual domain (appears multiple times)
2. Update SSL certificate paths (we'll set these up with Cloudflare)

Copy to Nginx:

```bash
sudo cp /opt/voice_assistant/deploy/nginx/voice-assistant.conf /etc/nginx/sites-available/voice-assistant
sudo ln -s /etc/nginx/sites-available/voice-assistant /etc/nginx/sites-enabled/
```

Remove default site:

```bash
sudo rm /etc/nginx/sites-enabled/default
```

### Step 7: Setup Cloudflare SSL Certificates

#### 7.1: Create Origin Certificate in Cloudflare

1. Log into Cloudflare dashboard
2. Select your domain
3. Go to **SSL/TLS** → **Origin Server**
4. Click **Create Certificate**
5. Select:
   - **Generate private key and CSR with Cloudflare**
   - **RSA** key
   - **Valid for 15 years**
   - Hostnames: `yourdomain.com` and `*.yourdomain.com`
6. Click **Create**
7. Copy both:
   - **Origin Certificate** (save as `cloudflare-origin.pem`)
   - **Private Key** (save as `cloudflare-origin.key`)

#### 7.2: Install Certificate on Server

Create SSL directory:

```bash
sudo mkdir -p /etc/ssl/private
sudo chmod 700 /etc/ssl/private
```

Save origin certificate:

```bash
sudo nano /etc/ssl/certs/cloudflare-origin.pem
# Paste the origin certificate, save and exit
```

Save private key:

```bash
sudo nano /etc/ssl/private/cloudflare-origin.key
# Paste the private key, save and exit
```

Set permissions:

```bash
sudo chmod 644 /etc/ssl/certs/cloudflare-origin.pem
sudo chmod 600 /etc/ssl/private/cloudflare-origin.key
```

#### 7.3: Configure SSL Mode in Cloudflare

1. Go to **SSL/TLS** → **Overview**
2. Set encryption mode to **Full (strict)**
3. This ensures end-to-end encryption

### Step 8: Configure Cloudflare DNS

1. Go to **DNS** → **Records**
2. Add an A record:
   - **Type**: A
   - **Name**: @ (or your subdomain)
   - **IPv4 address**: Your server's public IP
   - **Proxy status**: ✅ Proxied (orange cloud)
   - **TTL**: Auto
3. Click **Save**

DNS propagation typically takes a few minutes.

### Step 9: Start Nginx

Test Nginx configuration:

```bash
sudo nginx -t
```

If successful, start Nginx:

```bash
sudo systemctl enable nginx
sudo systemctl start nginx
```

### Step 10: Test Server

Test from outside:

```bash
# From your local machine
curl https://yourdomain.com/health
```

You should see:

```json
{"status":"healthy","version":"1.0.0"}
```

Test API documentation:

Open in browser: `https://yourdomain.com/docs`

You should see the FastAPI documentation interface.

## Part 2: Raspberry Pi Client Deployment

### Step 1: Prepare Pi

SSH into your Raspberry Pi:

```bash
ssh pi@raspberrypi.local
```

Ensure audio hardware is configured (see main README.md).

### Step 2: Copy Client Files

On your local machine:

```bash
cd voice_assistant/
tar -czf client-deploy.tar.gz pi_client/
```

Upload to Pi:

```bash
scp client-deploy.tar.gz pi@raspberrypi.local:/tmp/
```

On the Pi:

```bash
cd /tmp
tar -xzf client-deploy.tar.gz
mv pi_client voice_assistant_client
```

### Step 3: Run Installation Script

```bash
cd /tmp/voice_assistant_client/deploy
bash install_client.sh
```

Follow the prompts. The script will:
- Install system dependencies
- Create virtual environment
- Setup directory structure
- Create systemd service

### Step 4: Configure Environment Variables

Edit the client configuration:

```bash
nano ~/voice_assistant_client/.env
```

Set the following values:

```env
# Required: Your server URL (with https://)
SERVER_URL=https://yourdomain.com

# Required: Must match SERVER_API_KEY from server
CLIENT_API_KEY=your_secure_random_key_here

# Hardware configuration
BUTTON_PIN=17
AMPLIFIER_SD_PIN=27

# Audio configuration
SAMPLE_RATE=48000
MICROPHONE_GAIN=2.0
FADE_DURATION_MS=50
```

**Important**: The `CLIENT_API_KEY` must exactly match the `SERVER_API_KEY` you set on the server!

### Step 5: Secure the Configuration

```bash
chmod 600 ~/voice_assistant_client/.env
```

This ensures only your user can read the API key.

### Step 6: Test Client Manually

Before enabling the service, test manually:

```bash
cd ~/voice_assistant_client
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
cd /opt/voice_assistant
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
cd ~/voice_assistant_client
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

```bash
sudo apt install ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
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

#### 4.1: Enable DDoS Protection

Already enabled by default with proxied DNS.

#### 4.2: Configure Rate Limiting

1. Go to **Security** → **WAF**
2. Create rate limiting rule:
   - **Name**: Voice API Rate Limit
   - **If**: URI Path contains `/api/v1/process`
   - **Then**: Block
   - **Threshold**: 60 requests per minute per IP

#### 4.3: Enable Bot Protection

1. Go to **Security** → **Bots**
2. Enable **Bot Fight Mode** (free tier)

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

When you update the code:

```bash
# 1. Upload new files
scp -r server/* user@server:/opt/voice_assistant/

# 2. On server, update dependencies if needed
sudo -u voiceassistant /opt/voice_assistant/venv/bin/pip install -r /opt/voice_assistant/requirements.txt

# 3. Restart service
sudo systemctl restart voice-assistant-server.service
```

### Update Client Code

```bash
# 1. Upload new files
scp -r pi_client/* pi@raspberrypi.local:~/voice_assistant_client/

# 2. On Pi, restart service
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

#### Nginx 502 Bad Gateway

Check if application is running:
```bash
curl http://localhost:8000/health
```

If not, check application logs.

#### SSL Certificate Errors

Verify certificate files exist:
```bash
ls -l /etc/ssl/certs/cloudflare-origin.pem
ls -l /etc/ssl/private/cloudflare-origin.key
```

Test Nginx config:
```bash
sudo nginx -t
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
cd ~/voice_assistant_client
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

## Part 7: Backup and Recovery

### Backup Server Configuration

```bash
# On server
sudo tar -czf ~/voice-assistant-backup.tar.gz \
  /opt/voice_assistant/.env \
  /opt/voice_assistant/deploy/ \
  /etc/nginx/sites-available/voice-assistant \
  /etc/ssl/certs/cloudflare-origin.pem \
  /etc/ssl/private/cloudflare-origin.key
```

Download backup:
```bash
scp user@server:~/voice-assistant-backup.tar.gz .
```

### Backup Client Configuration

```bash
# On Pi
tar -czf ~/client-backup.tar.gz \
  ~/voice_assistant_client/.env
```

### Recovery

To restore, extract backups and follow deployment steps, copying configuration files instead of creating new ones.

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

- ✅ Raspberry Pi handles local audio I/O
- ✅ Server processes via fast Groq API
- ✅ Cloudflare provides security and SSL
- ✅ Everything is encrypted and authenticated
- ✅ Systemd ensures services stay running

Enjoy your voice assistant! 🎤🤖

