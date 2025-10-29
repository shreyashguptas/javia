# Troubleshooting Guide

## Quick Diagnostics

### Check Audio Devices
```bash
arecord -l  # Should show: sndrpigooglevoi
aplay -l    # Should show: sndrpigooglevoi
```

### Test Recording (5 seconds, 48000 Hz)
```bash
arecord -D plughw:0,0 -c1 -r 48000 -f S16_LE -d 5 test.wav
ls -lh test.wav  # Should be ~900KB
aplay -D plughw:0,0 test.wav
```

## Common Issues

### 1. Invalid Sample Rate Error

**Error:**
```
OSError: [Errno -9997] Invalid sample rate
```

**Cause:** googlevoicehat-soundcard driver requires 48000 Hz

**Solution:** Code is already set to 48000 Hz. If you see this:
1. Check `/boot/firmware/config.txt` has `dtoverlay=googlevoicehat-soundcard`
2. Reboot after config changes
3. Verify with `cat /boot/firmware/config.txt | grep i2s`

### 2. Microphone Not Detected

**Solutions:**

**A. Check I2S Configuration**
```bash
sudo nano /boot/firmware/config.txt

# Add these lines:
dtparam=i2s=on
dtoverlay=googlevoicehat-soundcard

# Then reboot
sudo reboot
```

**B. Verify INMP441 Wiring** (see `HARDWARE.md`):s
- VDD → 3.3V (Pin 1)
- GND → GND (Pin 6)
- SCK → GPIO18 (Pin 12)
- WS → GPIO19 (Pin 35)
- SD → GPIO20 (Pin 38)
- L/R → GND (Pin 6)

**C. Check Power**
```bash
vcgencmd get_throttled  # Should be: 0x0
vcgencmd measure_volts   # Should be ~1.35V
```

### 3. Speaker Not Working

**Check MAX98357A Wiring** (see `HARDWARE.md`):
- VDD → 3.3V (Pin 1)
- GND → GND (Pin 6)
- BCLK → GPIO18 (Pin 12)
- LRC → GPIO19 (Pin 35)
- DIN → GPIO21 (Pin 40)
- SD → GPIO27 (Pin 13)

**Test:**
```bash
speaker-test -D plughw:0,0 -c1 -t sine -f 1000 -l 1
```

### 4. Audio Clicks/Pops

**Solution:**
- Ensure GPIO27 connected to MAX98357A SD pin
- See `AUDIO_CLICKS.md` for details
- If persists, increase padding in code (line 523): `padding_ms=200`

### 5. Microphone Too Quiet

**Solutions:**

**A. Increase Gain**
Edit `.env`:
```env
MICROPHONE_GAIN=3.0
```

**B. Set ALSA Volume**
```bash
amixer -c 0 set Capture 100%
```

**C. Check Distance**
- Optimal: 6-12 inches from microphone
- Speak at normal volume

See `MICROPHONE_GAIN.md` for detailed configuration.

### 6. Button Not Working

**Wiring:**
- Terminal 1 → GPIO17 (Pin 11)
- Terminal 2 → GND (breadboard negative rail)

**Test:**
```python
from gpiozero import Button
import time

button = Button(17, pull_up=True)

print("Press button (Ctrl+C to exit)...")
try:
    while True:
        print(f"Button: {'PRESSED' if button.is_pressed else 'RELEASED'}")
        time.sleep(0.1)
except KeyboardInterrupt:
    button.close()
    print("\nCleanup complete")
```

### 7. ALSA Warnings (Harmless)

These warnings are normal and can be ignored:
```
ALSA lib pcm.c: Unknown PCM cards.pcm.front
jack server is not running
```

They occur during PyAudio initialization. As long as recording and playback work, ignore them.

### 8. GPIO Errors (Pi 5 Specific)

**Error: RuntimeError: Cannot determine SOC peripheral base address**

**Cause:** Using old `RPi.GPIO` library on Pi 5 (incompatible)

**Solution:** This project uses `gpiozero` for Pi 5 compatibility. If you see this error:
1. Verify you're running the latest code
2. Check `requirements.txt` has `gpiozero>=2.0` (not `RPi.GPIO`)
3. Reinstall dependencies:
   ```bash
   cd ~/javia_client
   source ~/venvs/pi_client/bin/activate
   pip install -r requirements.txt
   ```

**Error: PermissionError: [Errno 13] Permission denied: '/dev/gpiochip0'**

**Cause:** User not in `gpio` group or systemd service missing permissions

**Solution:**
```bash
# Add user to gpio group
sudo usermod -a -G gpio $USER

# Log out and back in (REQUIRED for group to activate)
exit
# SSH back in

# Verify group membership
groups  # Should show: audio gpio
```

If running as systemd service, verify service file has:
```ini
DeviceAllow=/dev/gpiochip0 rw
DeviceAllow=/dev/gpiochip1 rw
DeviceAllow=/dev/gpiochip2 rw
DeviceAllow=/dev/gpiochip3 rw
DeviceAllow=/dev/gpiochip4 rw
```

### 9. API Errors

**401 Unauthorized:**
- Check `.env` file has `GROQ_API_KEY=gsk_...`
- Verify key starts with `gsk_`

**429 Rate Limited:**
- Code retries automatically
- Free tier: 30 requests/minute

**Network:**
```bash
ping api.groq.com
curl -I https://api.groq.com
```

**500 Internal Server Error - Character Encoding:**
- Error: `'latin-1' codec can't encode character...`
- Cause: LLM response contains Unicode characters (e.g., smart quotes, special characters)
- Solution: Fixed in latest version - server now URL-encodes headers
- Ensure both server and client code are up to date

### 9. Power Issues

**Check:**
```bash
vcgencmd get_throttled  # Should be: 0x0
vcgencmd measure_volts
vcgencmd measure_temp
```

**Solution:**
- Use 5V 3A power supply
- Short, quality USB cable
- No USB hubs

### 10. Memory Errors

**Solution:**
Code now uses streaming (no MemoryError). If you see this, update to latest code.

## Diagnostic Commands

```bash
# Audio system
arecord -l
aplay -l
amixer -c 0

# GPIO
gpio readall

# System
free -h
df -h
vcgencmd get_throttled

# I2S config
cat /boot/firmware/config.txt | grep i2s

# Python devices
python3 -c "import pyaudio; p=pyaudio.PyAudio(); print(f'{p.get_device_count()} devices'); p.terminate()"
```

## Getting Help

### Information to Provide
1. Error messages (full text)
2. Output of `arecord -l`
3. I2S config from `/boot/firmware/config.txt`
4. Output of `vcgencmd get_throttled`
5. Python version: `python3 --version`

### Log Collection
```bash
dmesg | grep -i audio > audio.log
arecord -l > devices.log
cat /boot/firmware/config.txt > config.log
```

## Related Documentation

- Hardware Setup: `HARDWARE.md`
- Audio Clicks: `AUDIO_CLICKS.md`
- Microphone Gain: `MICROPHONE_GAIN.md`
- API Configuration: `API.md`
- Python Setup: `PYTHON.md`
