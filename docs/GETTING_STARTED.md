# Getting Started with Voice Assistant

This guide will help you deploy and run the voice assistant system.

## What You Need

### Hardware
- ✅ Raspberry Pi Zero 2 W (with audio hardware configured)
- ✅ Debian 13 server (or Ubuntu 22.04+) with static public IP
- ✅ Custom domain configured in Cloudflare

### Accounts & Keys
- ✅ Groq API account and API key ([console.groq.com](https://console.groq.com))
- ✅ Cloudflare account (free tier is fine)

## Deployment Steps

### Step 1: Deploy Server (10-15 minutes)

**On your Debian server:**

```bash
# 1. SSH to server
ssh user@your-server

# 2. Install Git and clone repository
sudo apt update && sudo apt install -y git
cd /tmp
git clone https://github.com/YOUR_USERNAME/voice_assistant.git

# 3. Run deployment script
cd /tmp/voice_assistant/server/deploy
sudo bash deploy.sh

# 4. Configure environment
sudo nano /opt/voice_assistant/.env
```

> **Note**: Replace `YOUR_USERNAME` with your GitHub username. For private repos, use a personal access token or SSH key (see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for details).

**Set in .env:**
```env
GROQ_API_KEY=gsk_your_groq_key_here
SERVER_API_KEY=<generate with: openssl rand -hex 32>
```

**Save the SERVER_API_KEY** - you'll need it for the Pi client!

```bash
# 4. Restart service
sudo systemctl restart voice-assistant-server.service

# 5. Verify it's running
curl http://localhost:8000/health
```

### Step 2: Setup Cloudflare (5-10 minutes)

**Configure DNS:**
1. Go to Cloudflare dashboard → DNS → Records
2. Add A record pointing to your server's public IP
3. Enable proxy (orange cloud)

**Setup SSL:**
1. Go to SSL/TLS → Origin Server
2. Create origin certificate
3. Copy certificate and private key to server:
   ```bash
   sudo nano /etc/ssl/certs/cloudflare-origin.pem
   # Paste certificate
   
   sudo nano /etc/ssl/private/cloudflare-origin.key
   # Paste private key
   ```
4. Set SSL/TLS mode to "Full (strict)"

**Configure Nginx:**
```bash
# On server
sudo nano /opt/voice_assistant/deploy/nginx/voice-assistant.conf
# Update server_name to your domain

sudo cp /opt/voice_assistant/deploy/nginx/voice-assistant.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/voice-assistant.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

**Test:**
```bash
curl https://yourdomain.com/health
```

### Step 3: Deploy Pi Client (5 minutes)

**On Raspberry Pi:**
```bash
# 1. SSH to Pi
ssh pi@raspberrypi.local

# 2. Clone repository
cd /tmp
git clone https://github.com/YOUR_USERNAME/voice_assistant.git

# 3. Run installation script
cd /tmp/voice_assistant/pi_client/deploy
bash install_client.sh

# 4. Configure
nano ~/voice_assistant_client/.env
```

> **Note**: Replace `YOUR_USERNAME` with your GitHub username. For private repos, setup authentication (see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)).

**Set in .env:**
```env
SERVER_URL=https://yourdomain.com
CLIENT_API_KEY=<same as SERVER_API_KEY from server>
BUTTON_PIN=17
AMPLIFIER_SD_PIN=27
MICROPHONE_GAIN=2.0
```

```bash
# Secure it
chmod 600 ~/voice_assistant_client/.env

# Test
cd ~/voice_assistant_client
source ~/venvs/pi_client/bin/activate
python3 client.py
```

**Press button and speak!**

### Step 4: Enable Auto-Start (Optional)

**On Raspberry Pi:**
```bash
sudo systemctl start voice-assistant-client.service
sudo systemctl enable voice-assistant-client.service
sudo systemctl status voice-assistant-client.service
```

## Testing

### Test Server
```bash
# On server
cd /opt/voice_assistant
source venv/bin/activate
python3 test_server.py
```

### Test Client
```bash
# On Pi
cd ~/voice_assistant_client
source ~/venvs/pi_client/bin/activate
python3 test_client.py
```

## Monitoring

### Server Logs
```bash
# Application logs
sudo journalctl -u voice-assistant-server.service -f

# Nginx logs
sudo tail -f /var/log/nginx/voice-assistant-access.log
```

### Client Logs
```bash
# If running as service
sudo journalctl -u voice-assistant-client.service -f

# If running manually, logs appear in console
```

## Troubleshooting

### Server Won't Start
- Check logs: `sudo journalctl -u voice-assistant-server.service -xe`
- Verify .env file has GROQ_API_KEY and SERVER_API_KEY
- Check port 8000 isn't in use: `sudo netstat -tlnp | grep 8000`

### Can't Connect to Server from Pi
- Test DNS: `nslookup yourdomain.com`
- Test HTTPS: `curl https://yourdomain.com/health`
- Verify CLIENT_API_KEY matches SERVER_API_KEY
- Check Cloudflare SSL mode is "Full (strict)"

### Audio Not Working
- See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- Verify hardware connections
- Test with: `arecord -D plughw:0,0 -c1 -r 48000 -f S16_LE -t wav -d 5 test.wav`

### API Errors
- Verify GROQ_API_KEY is valid
- Check API usage at console.groq.com
- Look for rate limiting (429 errors)

## Next Steps

✅ **You're all set!** Press the button to use your voice assistant.

### Optional Enhancements
- Configure rate limiting in Cloudflare
- Setup monitoring/alerting
- Implement conversation history (future feature)
- Add wake word detection

## Documentation

- 📖 [Complete Deployment Guide](docs/DEPLOYMENT.md)
- 🏗️ [Architecture Documentation](docs/ARCHITECTURE.md)
- 🔌 [API Reference](docs/API.md)
- 🔧 [Hardware Setup](docs/HARDWARE.md)
- 🐛 [Troubleshooting](docs/TROUBLESHOOTING.md)

## Support

Having issues? Check:
1. [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for common problems
2. Server and client logs for error messages
3. [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for detailed instructions

## Security Checklist

- ✅ API keys stored in .env files only
- ✅ .env files have 600 permissions
- ✅ HTTPS enabled (not HTTP)
- ✅ Cloudflare proxy enabled (orange cloud)
- ✅ Firewall configured on server
- ✅ Strong API keys (32+ characters)
- ✅ Rate limiting configured

---

**Enjoy your production-ready voice assistant!** 🎤🤖

