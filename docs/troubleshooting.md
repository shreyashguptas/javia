# Troubleshooting Guide

## Common Issues and Solutions

### 1. Microphone Not Working

#### Symptoms
- No audio input detected
- `arecord -l` shows no I2S devices
- Recording produces silent files
- Python script fails to find audio device

#### Possible Causes & Solutions

**A. Hardware Connections**
```bash
# Check if microphone is detected
arecord -l

# Expected output:
# card 0: voice-assistant [voice-assistant], device 0: simple-card_codec_link [simple-card_codec_link]
```

**Solutions:**
1. **Verify Wiring**: Check all INMP441 connections
   - VDD → 3.3V (Pin 1)
   - GND → GND (Pin 6)
   - SCK → GPIO18 (Pin 12)
   - WS → GPIO19 (Pin 35)
   - SD → GPIO20 (Pin 38)
   - L/R → GND (Pin 6)

2. **Check Power**: Measure 3.3V at microphone
   ```bash
   # Check 3.3V rail
   sudo raspi-config nonint do_serial 0
   ```

3. **Test Continuity**: Use multimeter to verify connections

**B. I2S Configuration**
```bash
# Check current config
cat /boot/firmware/config.txt | grep -i i2s

# Expected lines:
# dtparam=i2s=on
# dtoverlay=i2s-mmap
# dtoverlay=rpi-simple-soundcard,card-name=voice-assistant
```

**Solutions:**
1. **Add Missing Configuration**:
   ```bash
   sudo nano /boot/firmware/config.txt
   
   # Add these lines at the end:
   dtparam=i2s=on
   dtoverlay=i2s-mmap
   dtoverlay=rpi-simple-soundcard,card-name=voice-assistant
   dtparam=simple_card_name="voice-assistant"
   dtparam=i2s_master=on
   dtparam=i2s_sample_rate=16000
   ```

2. **Reboot After Changes**:
   ```bash
   sudo reboot
   ```

3. **Verify Device Detection**:
   ```bash
   # After reboot, check devices
   arecord -l
   aplay -l
   ```

**C. Python Environment Issues**
```bash
# Check PyAudio installation
python3 -c "import pyaudio; print('PyAudio OK')"

# Check device enumeration
python3 -c "
import pyaudio
p = pyaudio.PyAudio()
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info['maxInputChannels'] > 0:
        print(f'Device {i}: {info[\"name\"]}')
"
```

**Solutions:**
1. **Reinstall PyAudio**:
   ```bash
   pip uninstall pyaudio
   pip install pyaudio
   ```

2. **Check ALSA Configuration**:
   ```bash
   # Test recording manually
   arecord -D plughw:0,0 -c1 -r 16000 -f S16_LE -t wav test.wav
   ```

### 2. Speaker Not Working

#### Symptoms
- No audio output
- `aplay -l` shows no I2S devices
- Audio files play silently
- Amplifier gets hot

#### Possible Causes & Solutions

**A. Hardware Connections**
```bash
# Check if amplifier is detected
aplay -l

# Expected output:
# card 0: voice-assistant [voice-assistant], device 0: simple-card_codec_link [simple-card_codec_link]
```

**Solutions:**
1. **Verify MAX98357A Wiring**:
   - VDD → 3.3V (Pin 1)
   - GND → GND (Pin 6)
   - BCLK → GPIO18 (Pin 12)
   - LRC → GPIO19 (Pin 35)
   - DIN → GPIO20 (Pin 40)

2. **Check Speaker Connections**:
   - Red wire → OUT+ terminal
   - Black wire → OUT- terminal

3. **Test Amplifier**:
   ```bash
   # Generate test tone
   speaker-test -D plughw:0,0 -c1 -t sine -f 1000
   ```

**B. Audio Configuration**
```bash
# Check audio settings
amixer -c 0

# Set volume
amixer -c 0 set Master 80%
```

### 3. Button Not Working

#### Symptoms
- Button press not detected
- GPIO pin not responding
- Script hangs waiting for button

#### Possible Causes & Solutions

**A. Hardware Issues**
```bash
# Check GPIO pin state
gpio readall

# Test button manually
python3 -c "
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)
print('Button state:', GPIO.input(17))
GPIO.cleanup()
"
```

**Solutions:**
1. **Verify Button Wiring**:
   - One terminal → GPIO17 (Pin 11)
   - Other terminal → GND (Pin 6)

2. **Check Button Function**:
   - Use multimeter to test continuity
   - Verify button makes/breaks contact

3. **Test GPIO Configuration**:
   ```bash
   # Add to config.txt
   gpio=17=ip,pu
   ```

### 4. API Issues

#### Symptoms
- Transcription fails
- LLM queries timeout
- TTS generation fails
- Network errors

#### Possible Causes & Solutions

**A. API Key Issues**
```python
# Check API key format
GROQ_API_KEY = "gsk_..."  # Should start with gsk_
```

**Solutions:**
1. **Verify API Key**:
   - Check key format (starts with `gsk_`)
   - Ensure key is active
   - Test with curl:
   ```bash
   curl -H "Authorization: Bearer YOUR_API_KEY" \
        https://api.groq.com/openai/v1/models
   ```

2. **Check Network Connectivity**:
   ```bash
   ping api.groq.com
   curl -I https://api.groq.com
   ```

**B. Rate Limiting**
```bash
# Check API usage
curl -H "Authorization: Bearer YOUR_API_KEY" \
     https://api.groq.com/openai/v1/usage
```

**Solutions:**
1. **Implement Retry Logic**:
   ```python
   import time
   import requests
   
   def api_call_with_retry(url, headers, data, max_retries=3):
       for attempt in range(max_retries):
           try:
               response = requests.post(url, headers=headers, data=data)
               if response.status_code == 200:
                   return response
               elif response.status_code == 429:  # Rate limited
                   time.sleep(2 ** attempt)  # Exponential backoff
               else:
                   return response
           except Exception as e:
               if attempt == max_retries - 1:
                   raise e
               time.sleep(1)
   ```

### 5. Audio Quality Issues

#### Symptoms
- Distorted audio
- Low volume
- Background noise
- Echo or feedback

#### Possible Causes & Solutions

**A. Sample Rate Mismatch**
```bash
# Check current sample rate
cat /proc/asound/card0/pcm0p/sub0/hw_params
```

**Solutions:**
1. **Set Correct Sample Rate**:
   ```bash
   # In config.txt
   dtparam=i2s_sample_rate=16000
   ```

2. **Test Different Rates**:
   ```bash
   # Test 16kHz
   arecord -D plughw:0,0 -c1 -r 16000 -f S16_LE test16k.wav
   
   # Test 48kHz
   arecord -D plughw:0,0 -c1 -r 48000 -f S16_LE test48k.wav
   ```

**B. Audio Levels**
```bash
# Check input levels
arecord -D plughw:0,0 -c1 -r 16000 -f S16_LE -V mono test.wav

# Check output levels
amixer -c 0 set Master 80%
```

### 6. System Performance Issues

#### Symptoms
- Slow response times
- Audio dropouts
- System freezes
- High CPU usage

#### Possible Causes & Solutions

**A. Power Supply Issues**
```bash
# Check power supply voltage
vcgencmd measure_volts

# Check for undervoltage
vcgencmd get_throttled
```

**Solutions:**
1. **Use Adequate Power Supply**:
   - Minimum: 5V 2A
   - Recommended: 5V 3A
   - For high volume: 5V 4A

2. **Check Power Connections**:
   - Verify USB cable quality
   - Check for loose connections
   - Monitor voltage under load

**B. CPU Overload**
```bash
# Check CPU usage
top
htop

# Check memory usage
free -h
```

**Solutions:**
1. **Optimize Audio Settings**:
   - Reduce sample rate if possible
   - Use smaller chunk sizes
   - Implement audio buffering

2. **System Optimization**:
   ```bash
   # Disable unnecessary services
   sudo systemctl disable bluetooth
   sudo systemctl disable wifi-powersave
   
   # Increase GPU memory split
   sudo raspi-config
   # Advanced Options → Memory Split → 16
   ```

## Diagnostic Commands

### Audio System Diagnostics
```bash
# List all audio devices
arecord -l
aplay -l

# Test microphone
arecord -D plughw:0,0 -c1 -r 16000 -f S16_LE -t wav test.wav

# Test speaker
aplay -D plughw:0,0 test.wav

# Check audio configuration
cat /proc/asound/cards
cat /proc/asound/pcm

# Monitor audio levels
arecord -D plughw:0,0 -c1 -r 16000 -f S16_LE -V mono test.wav
```

### System Diagnostics
```bash
# Check GPIO
gpio readall

# Check I2S configuration
cat /boot/firmware/config.txt | grep -i i2s

# Check system resources
free -h
df -h
vcgencmd measure_temp
vcgencmd measure_volts
vcgencmd get_throttled

# Check network
ping -c 4 api.groq.com
curl -I https://api.groq.com
```

### Python Environment Diagnostics
```bash
# Check Python packages
pip list | grep -E "(pyaudio|RPi|requests)"

# Test PyAudio
python3 -c "
import pyaudio
p = pyaudio.PyAudio()
print('PyAudio version:', pyaudio.__version__)
print('Device count:', p.get_device_count())
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    print(f'Device {i}: {info[\"name\"]}')
p.terminate()
"

# Test GPIO
python3 -c "
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)
print('Button state:', GPIO.input(17))
GPIO.cleanup()
"
```

## Getting Help

### Before Asking for Help
1. Run all diagnostic commands
2. Check hardware connections
3. Verify configuration files
4. Test individual components
5. Check system logs

### Useful Resources
- [Raspberry Pi Audio Documentation](https://www.raspberrypi.org/documentation/configuration/audio-config.md)
- [ALSA Configuration Guide](https://alsa.opensrc.org/)
- [Groq API Documentation](https://console.groq.com/docs)
- [PyAudio Documentation](https://people.csail.mit.edu/hubert/pyaudio/docs/)

### Log Collection
```bash
# Collect system logs
sudo journalctl -u alsa-state > alsa.log
dmesg | grep -i audio > audio_dmesg.log
cat /boot/firmware/config.txt > config.txt
arecord -l > audio_devices.log
aplay -l >> audio_devices.log
```
