# Raspberry Pi Client Deployment

This directory contains the setup script for deploying and maintaining the Voice Assistant client on Raspberry Pi.

## 📁 Directory Structure

```
deploy/
├── README.md      # This file - deployment overview
└── setup.sh       # One script for install/update/fix (idempotent)
```

## 🚀 One Script for Everything

The `setup.sh` script handles **everything**: initial installation, updates, and fixes. You can run it as many times as you want - it's completely idempotent.

### Prerequisites

Before running the script, ensure:
- Hardware is wired correctly (see docs/HARDWARE.md)
- I2S is enabled in `/boot/firmware/config.txt`
- Server is deployed and accessible

### First Time Installation

```bash
# SSH to your Raspberry Pi
ssh user@raspberrypi.local
```

**Step 1: Enable I2S Audio**

```bash
# Edit the config file
sudo nano /boot/firmware/config.txt

# Find this line (around the bottom):
#dtparam=i2s=on

# Remove the '#' to UNCOMMENT it, and add the overlay:
dtparam=i2s=on
dtoverlay=googlevoicehat-soundcard

# Save: Ctrl+O, Enter, Ctrl+X
```

**Step 2: Reboot (CRITICAL)**

```bash
# MUST reboot for I2S changes to take effect
sudo reboot
```

Wait for the Pi to restart, then SSH back in:

```bash
ssh user@raspberrypi.local
```

**Step 3: Clone and Run Setup**

```bash
# Clone the repository
cd /tmp
sudo apt update && sudo apt install -y git
# Clone only if /tmp/javia does not exist
if [ -d "javia" ]; then
  echo "Directory 'javia' already exists. Skipping clone."
else
  git clone https://github.com/shreyashguptas/javia.git javia
fi

cd javia

# Run setup
bash pi_client/deploy/setup.sh
```

The script will:
- ✅ Install system dependencies (PyAudio, gpiozero, etc.)
- ✅ Create Python virtual environment
- ✅ Copy client files to `~/javia_client`
- ✅ Prompt for SERVER_URL and CLIENT_API_KEY (first time only)
- ✅ Validate configuration
- ✅ Create systemd service (Pi 5 compatible)
- ✅ Add user to `audio` and `gpio` groups (required for hardware access)
- ✅ Enable autostart on boot
- ✅ Start the service and verify it's running

**If the service fails to start**, the script will:
- ❌ Show error logs explaining why
- 💡 Provide troubleshooting steps
- 🔄 Allow you to fix and re-run the script

**⚠️ IMPORTANT - Group Permissions**:
- The script requires you to be in `audio` and `gpio` groups
- If you're not in these groups, the script will add you and **EXIT**
- If you're assigned to the groups but they're not active in your current session, the script will **EXIT**
- **You MUST log out and log back in**, then run the script again
- The script will NOT start the service until group permissions are active

**⚠️ CRITICAL - I2S Must Be Enabled Before Running Setup**:
- You **MUST** enable I2S in `/boot/firmware/config.txt` and **reboot** BEFORE running setup
- If you skip the reboot, the audio device won't be available and the service will fail
- See "Step 1: Enable I2S Audio" above for instructions

### Updating After Code Changes

When you make changes to the code on your Mac and push to GitHub:

```bash
# SSH to your Raspberry Pi
ssh user@raspberrypi.local
```

```bash
# 1. Pull latest code to /tmp
cd /tmp
rm -rf javia  # Remove old clone if exists
git clone https://github.com/shreyashguptas/javia.git
cd javia

# 2. Run the SAME script again
bash pi_client/deploy/setup.sh
```

The script will:
- ✅ Install any missing dependencies
- ✅ Offer to rebuild virtual environment (choose option 2 for major updates)
- ✅ Copy latest client files
- ✅ Give you option to keep or update configuration
- ✅ Update virtual environment packages
- ✅ Restart the service

**Update Strategy:**
- **Minor updates** (bug fixes, small changes): Choose option 1 to keep existing venv
- **Major updates** (new dependencies, package version changes): Choose option 2 to rebuild venv

**Why rebuild the venv?**
- Removes old/conflicting packages
- Ensures clean dependency installation
- Fixes import errors from stale packages
- Only takes 1-2 minutes

**It's that simple!** No need to remember which script to run - it's always the same one.

### Fixing Issues

If you encounter any issues (audio not working, service not starting, etc.), just run the setup script again:

```bash
cd /tmp/javia
bash pi_client/deploy/setup.sh
```

## ✅ Verify Client is Working

After running the setup script, check if the client is running:

```bash
# Quick check - is the service running?
systemctl is-active voice-assistant-client.service && echo "✅ Running!" || echo "❌ Not running"

# Detailed status
sudo systemctl status voice-assistant-client.service

# View live logs (press Ctrl+C to exit)
sudo journalctl -u voice-assistant-client.service -f
```

**If running successfully**, you'll see:
- Status: `active (running)`
- Log message: `[READY] System ready! Press button to start...`
- **You can now press your button and speak!**

**If not running**, check the logs for errors and re-run the setup script.

## 📝 Quick Reference

### Important Paths

- **Installation directory**: `~/javia_client`
- **Virtual environment**: `~/venvs/pi_client`
- **Configuration**: `~/javia_client/.env`
- **Service file**: `/etc/systemd/system/voice-assistant-client.service`

### Common Commands

```bash
# View service status
sudo systemctl status voice-assistant-client.service

# View logs (live)
sudo journalctl -u voice-assistant-client.service -f

# View last 50 log lines
sudo journalctl -u voice-assistant-client.service -n 50

# Restart service
sudo systemctl restart voice-assistant-client.service

# Stop service
sudo systemctl stop voice-assistant-client.service

# Start service
sudo systemctl start voice-assistant-client.service

# Test manually (stop service first)
sudo systemctl stop voice-assistant-client.service
source ~/venvs/pi_client/bin/activate
cd ~/javia_client
python3 client.py
```

### Test Audio Hardware

```bash
# List audio devices
arecord -l
aplay -l

# Test recording (3 seconds) - Use full CARD name for reliability
arecord -D plughw:CARD=sndrpigooglevoi,DEV=0 -f S16_LE -r 48000 -c 1 -d 3 /tmp/test.wav

# Verify file was created
ls -lh /tmp/test.wav

# Test playback
aplay /tmp/test.wav

# Check audio group membership
groups $USER
# Should include: audio gpio

# Check if beep files exist
ls -lh ~/javia/audio/*.wav
```

**If audio tests fail:**
1. Verify I2S is enabled in `/boot/firmware/config.txt`:
   ```bash
   grep -E "dtparam=i2s|dtoverlay=googlevoicehat" /boot/firmware/config.txt
   ```
   Should show both lines uncommented.

2. If I2S is enabled but audio still doesn't work, **reboot the Pi**:
   ```bash
   sudo reboot
   ```
   Then test again after logging back in.

3. If still not working, check hardware connections (see docs/HARDWARE.md)

## 🔑 Configuration Management

When you run `setup.sh` on an already-configured system, it will:
1. Detect existing configuration
2. Ask if you want to keep it or enter new values
3. For updates, just choose option 1 to keep existing config

**To find your SERVER_API_KEY on the server:**
```bash
ssh user@your-server-ip
sudo cat /opt/javia/.env | grep SERVER_API_KEY
```

The CLIENT_API_KEY on the Pi must match the SERVER_API_KEY on the server.

## 🔒 Security Notes

- ✅ `.env` file contains SERVER_URL and API key
- ✅ File permissions set to 600 (owner read/write only)
- ✅ Service runs as your user (not root)
- ✅ API keys never committed to git

## 🔧 Troubleshooting Common Issues

### Error: "ValueError: invalid literal for int() with base 10"

**Symptom:**
```
ValueError: invalid literal for int() with base 10: '17          # Rotary encoder SW (push button) pin'
```

**Cause:** The `.env` file contains inline comments (e.g., `BUTTON_PIN=17 # comment`). Systemd's `EnvironmentFile` doesn't strip inline comments like Python's `dotenv` library does.

**Fix:**

```bash
# SSH to your Raspberry Pi
ssh user@raspberrypi.local

# Pull latest code (includes the fix)
cd /tmp/javia
git pull

# Re-run setup script (it will clean the .env file automatically)
bash pi_client/deploy/setup.sh
```

The setup script will now automatically remove inline comments from your `.env` file.

**Manual Fix (if needed):**

If you prefer to fix it manually:

```bash
# Edit the .env file
nano ~/javia_client/.env

# Remove all inline comments. Change this:
BUTTON_PIN=17          # Rotary encoder SW (push button) pin

# To this:
BUTTON_PIN=17

# Save: Ctrl+O, Enter, Ctrl+X

# Restart the service
sudo systemctl restart voice-assistant-client.service
```

### Error: Audio device not found

**Symptom:** Service fails with "No input devices found" or audio tests fail.

**Cause:** I2S not enabled or Pi not rebooted after enabling I2S.

**Fix:**
1. Verify I2S is enabled:
   ```bash
   grep -E "dtparam=i2s|dtoverlay=googlevoicehat" /boot/firmware/config.txt
   ```
   Should show both lines uncommented.

2. If I2S is enabled but audio doesn't work, **reboot**:
   ```bash
   sudo reboot
   ```

3. Test again after reboot:
   ```bash
   arecord -l  # Should show googlevoicehat device
   ```

## 📚 Additional Documentation

- **[../../docs/DEPLOYMENT.md](../../docs/DEPLOYMENT.md)** - Complete deployment guide
- **[../../docs/HARDWARE.md](../../docs/HARDWARE.md)** - Hardware wiring guide
- **[../../docs/TROUBLESHOOTING.md](../../docs/TROUBLESHOOTING.md)** - Common issues
- **[../../docs/GETTING_STARTED.md](../../docs/GETTING_STARTED.md)** - Getting started guide

