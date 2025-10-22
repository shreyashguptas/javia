# Raspberry Pi Client Update Scripts

**Location:** `pi_client/deploy/update/`

This directory contains scripts for updating the Voice Assistant client on Raspberry Pi after code changes.

## Initial Deployment

For first-time installation, use `../install_client.sh` (in the parent directory):

```bash
# On your Raspberry Pi
cd /tmp
git clone https://github.com/shreyashguptas/javia.git
cd javia/pi_client/deploy
bash install_client.sh
```

This will:
- Install system dependencies
- Create Python virtual environment with system site packages (for PyAudio, GPIO)
- Set up client files
- Configure .env file (prompts for SERVER_URL and API key)
- Install systemd service
- Enable autostart on boot

## Updating the Client

After you've pushed code changes to GitHub, use `update.sh`:

```bash
# SSH to your Raspberry Pi
ssh shreyashgupta@pi-zero-2-w-1.local

# Run the update script (as regular user, NOT sudo)
bash ~/javia_client/deploy/update/update.sh
```

**Or**, if you first need to get the update script itself (if it didn't exist before):

```bash
# Get the latest update script
cd /tmp
git clone https://github.com/shreyashguptas/javia.git javia_temp
mkdir -p ~/javia_client/deploy/update
cp javia_temp/pi_client/deploy/update/update.sh ~/javia_client/deploy/update/
chmod +x ~/javia_client/deploy/update/update.sh
rm -rf javia_temp

# Now run it
bash ~/javia_client/deploy/update/update.sh
```

### What the Update Script Does

1. ✅ Backs up your `.env` file (preserves SERVER_URL and API key)
2. ✅ Fetches latest code from GitHub
3. ✅ Stops the client service
4. ✅ Updates all application files
5. ✅ Restores your `.env` file
6. ✅ **Prompts for new SERVER_API_KEY** (in case it changed on server)
7. ✅ Updates Python dependencies (ONLY if requirements.txt changed)
8. ✅ Restarts the service
9. ✅ Shows service status and recent logs

### SERVER_API_KEY Synchronization

The update script will prompt you to enter the SERVER_API_KEY from your server. This is important because:
- If you updated the server and regenerated API keys, the Pi needs to be updated
- It ensures authentication between client and server stays in sync

**To get your SERVER_API_KEY from the server:**
```bash
ssh user@your-server-ip
sudo cat /opt/javia/.env | grep SERVER_API_KEY
# Copy the value shown
```

When the Pi update script prompts you, paste this key. If the key hasn't changed, you can press Enter to keep the existing one.

### Important Notes

- **Run as regular user** - Do NOT use sudo to run the update script
- **Your `.env` file is preserved** - SERVER_URL and API keys won't be lost
- **Virtual environment is smart** - Only rebuilds if dependencies change
- **Service is automatically restarted** - No manual intervention needed
- **Brief interruption** - Voice assistant will be offline for ~5-10 seconds during update

## Troubleshooting

### View Logs
```bash
# Live logs
sudo journalctl -u voice-assistant-client.service -f

# Last 50 lines
sudo journalctl -u voice-assistant-client.service -n 50
```

### Check Service Status
```bash
sudo systemctl status voice-assistant-client.service
```

### Restart Service Manually
```bash
sudo systemctl restart voice-assistant-client.service
```

### Test Client Manually (without service)
```bash
# Stop the service first
sudo systemctl stop voice-assistant-client.service

# Run manually
source ~/venvs/pi_client/bin/activate
cd ~/javia_client
python3 client.py

# When done, restart service
sudo systemctl start voice-assistant-client.service
```

### Check Audio Devices
```bash
arecord -l  # List recording devices
aplay -l    # List playback devices
```

### Test Recording
```bash
arecord -D plughw:0,0 -c1 -r 48000 -f S16_LE -d 5 test.wav
aplay -D plughw:0,0 test.wav
```

### Roll Back to Previous Version

If the update breaks something:

```bash
# Stop the service
sudo systemctl stop voice-assistant-client.service

# Clone a specific previous commit
cd /tmp
git clone https://github.com/shreyashguptas/javia.git javia_rollback
cd javia_rollback
git checkout <PREVIOUS_COMMIT_HASH>

# Copy files (preserve .env)
cd pi_client
find ~/javia_client -mindepth 1 -maxdepth 1 ! -name '.env' -exec rm -rf {} +
cp -r * ~/javia_client/

# Restart
sudo systemctl start voice-assistant-client.service
```

### Common Issues After Update

**Import errors / Module not found:**
```bash
# Reinstall dependencies
source ~/venvs/pi_client/bin/activate
cd ~/javia_client
pip install -r requirements.txt
```

**Permission errors:**
```bash
# Fix ownership
sudo chown -R $USER:$USER ~/javia_client
```

**Service won't start:**
```bash
# Check logs for specific error
sudo journalctl -u voice-assistant-client.service -n 50

# Check if audio devices are available
arecord -l
```

## Files

- `install_client.sh` - Initial installation script
- `update.sh` - Update script for code changes

## Configuration

Edit `~/javia_client/.env` to configure:

```env
SERVER_URL=https://yourdomain.com
CLIENT_API_KEY=your_api_key_here
BUTTON_PIN=17
AMPLIFIER_SD_PIN=27
MICROPHONE_GAIN=2.0
FADE_DURATION_MS=50
SAMPLE_RATE=48000
```

After editing `.env`, restart the service:
```bash
sudo systemctl restart voice-assistant-client.service
```

## Autostart on Boot

The installation script automatically configures the client to start on boot:

```bash
# Check if enabled
systemctl is-enabled voice-assistant-client.service

# Disable autostart
sudo systemctl disable voice-assistant-client.service

# Enable autostart
sudo systemctl enable voice-assistant-client.service
```

