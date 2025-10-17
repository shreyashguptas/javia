# Microphone Troubleshooting - Step by Step

## Your Specific Issue: INMP441 Microphone Not Working

Based on your setup, here are the most likely causes and solutions:

### 1. **Most Likely Issue: I2S Configuration**

Your current `/boot/firmware/config.txt` configuration looks correct, but let's verify:

```bash
# Check current configuration
cat /boot/firmware/config.txt | grep -i i2s

# Should show:
# dtparam=i2s=on
# dtoverlay=googlevoicehat-soundcard
```

**If missing, add these lines to `/boot/firmware/config.txt`:**
```bash
sudo nano /boot/firmware/config.txt

# Add at the end:
dtparam=i2s=on
dtoverlay=googlevoicehat-soundcard
```

**Then reboot:**
```bash
sudo reboot
```

### 2. **Check Device Detection**

After reboot, check if the microphone is detected:

```bash
# List recording devices
arecord -l

# Should show something like:
# card 0: googlevoicehat [Google Voice HAT], device 0: ...
```

**If not detected:**
- Check hardware connections
- Verify power supply
- Try different I2S overlay

### 3. **Test Manual Recording**

```bash
# Test recording for 5 seconds
arecord -D plughw:0,0 -c1 -r 16000 -f S16_LE -t wav test.wav

# Check file size
ls -la test.wav

# Should be > 1000 bytes
```

**If file is very small (< 1000 bytes):**
- Microphone not working
- Check hardware connections
- Verify power supply

### 4. **Hardware Connection Check**

Double-check these connections:

```
INMP441 → Raspberry Pi Zero 2 W
VDD     → 3.3V (Pin 1)
GND     → GND (Pin 6)
SCK     → GPIO18 (Pin 12)
WS      → GPIO19 (Pin 35)
SD      → GPIO20 (Pin 38)
L/R     → GND (Pin 6)
```

**Common mistakes:**
- Wrong pin numbers
- Loose breadboard connections
- Power supply issues

### 5. **Power Supply Issues**

Check power supply:

```bash
# Check voltage
vcgencmd measure_volts

# Check for undervoltage
vcgencmd get_throttled
```

**If throttling detected:**
- Use 5V 3A power supply
- Check USB cable quality
- Ensure stable power

### 6. **Python Environment Issues**

Check Python setup:

```bash
# Activate environment
source ~/venvs/pi/bin/activate

# Test PyAudio
python3 -c "import pyaudio; print('PyAudio OK')"

# List audio devices
python3 -c "
import pyaudio
p = pyaudio.PyAudio()
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info['maxInputChannels'] > 0:
        print(f'Device {i}: {info[\"name\"]}')
p.terminate()
"
```

### 7. **Alternative I2S Configuration**

If `googlevoicehat-soundcard` doesn't work, try these alternatives:

**Option 1: HiFiBerry DAC**
```bash
sudo nano /boot/firmware/config.txt

# Replace I2S section with:
dtparam=i2s=on
dtoverlay=hifiberry-dac
```

**Option 2: IQAudio**
```bash
sudo nano /boot/firmware/config.txt

# Replace I2S section with:
dtparam=i2s=on
dtoverlay=iqaudio-codec
```

**Then reboot and test again.**

### 8. **Run Diagnostic Script**

Use the provided diagnostic script:

```bash
cd ~/voice_assistant
python3 scripts/troubleshoot_mic.py
```

This will run comprehensive tests and provide specific recommendations.

### 9. **Test with Different Audio Formats**

Try different sample rates:

```bash
# Test 48kHz
arecord -D plughw:0,0 -c1 -r 48000 -f S16_LE test48k.wav

# Test 44.1kHz
arecord -D plughw:0,0 -c1 -r 44100 -f S16_LE test44k.wav
```

### 10. **Check System Logs**

Look for audio-related errors:

```bash
# Check system logs
dmesg | grep -i audio
dmesg | grep -i i2s
dmesg | grep -i sound

# Check ALSA logs
sudo journalctl -u alsa-state
```

## Quick Fix Checklist

1. **Reboot after config changes** ✓
2. **Check `arecord -l` output** ✓
3. **Test manual recording** ✓
4. **Verify hardware connections** ✓
5. **Check power supply** ✓
6. **Test Python environment** ✓
7. **Run diagnostic script** ✓

## If Nothing Works

1. **Try different INMP441 module** (hardware defect)
2. **Use different Raspberry Pi** (GPIO issues)
3. **Check breadboard connections** (loose wires)
4. **Verify power supply** (undervoltage)

## Expected Behavior

When working correctly:
- `arecord -l` shows "voice-assistant" device
- Manual recording creates files > 1000 bytes
- PyAudio finds I2S device
- Python script can record audio

## Next Steps

1. Run the diagnostic script: `python3 scripts/troubleshoot_mic.py`
2. Follow the specific recommendations
3. Test with: `python3 examples/mic_test.py`
4. If still not working, check hardware connections with multimeter

---

**Remember:** The most common issue is incorrect I2S configuration or hardware connections. Double-check these first!
