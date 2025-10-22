# Raspberry Pi Client Deployment Scripts

## Initial Deployment

Use `install_client.sh` for first-time installation:

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
bash ~/javia_client/deploy/update.sh
```

**Or**, if you first need to get the update script itself (if it didn't exist before):

```bash
# Get the latest update script
cd /tmp
git clone https://github.com/shreyashguptas/javia.git javia_temp
cp javia_temp/pi_client/deploy/update.sh ~/javia_client/deploy/
chmod +x ~/javia_client/deploy/update.sh
rm -rf javia_temp

# Now run it
bash ~/javia_client/deploy/update.sh
```

### What the Update Script Does

1. ✅ Backs up your `.env` file (preserves SERVER_URL and API key)
2. ✅ Fetches latest code from GitHub
3. ✅ Stops the client service
4. ✅ Updates all application files
5. ✅ Restores your `.env` file
6. ✅ Updates Python dependencies (ONLY if requirements.txt changed)
7. ✅ Restarts the service
8. ✅ Shows service status and recent logs

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

