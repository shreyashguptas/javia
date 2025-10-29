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
- Terminal 2 → GND (Pin 6)

**Test:**
```python
import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)

print("Press button (Ctrl+C to exit)...")
try:
    while True:
        print(f"Button: {'PRESSED' if GPIO.input(17) == 0 else 'RELEASED'}")
        time.sleep(0.1)
except KeyboardInterrupt:
    GPIO.cleanup()
```

### 7. ALSA Warnings (Harmless)

These warnings are normal and can be ignored:
```
ALSA lib pcm.c: Unknown PCM cards.pcm.front
jack server is not running
```

They occur during PyAudio initialization. As long as recording and playback work, ignore them.

### 8. API Errors

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

### 11. LLM Response Truncation

**Symptom:**
- Answers feel cut off mid-sentence
- Response ends abruptly
- Server log shows: `finish_reason=length`

**Cause:**
Response hit the `max_tokens` limit for its complexity tier.

**Check Server Logs:**
```bash
journalctl -u voice-assistant-server.service -n 50 | grep "finish_reason"
```

**Solutions:**

**A. Increase Token Limits**
Edit `.env` on server:
```env
# For simple questions (default: 100)
LLM_TOKENS_SIMPLE=150

# For moderate questions (default: 300)
LLM_TOKENS_MODERATE=500

# For complex questions (default: 800)
LLM_TOKENS_COMPLEX=1200
```

**B. Check Complexity Detection**
Server logs show detected complexity:
```
Complexity analysis: level=simple, score=1, chars=35, words=7
```

If misclassified, adjust thresholds in `.env`:
```env
# Classify queries ≤50 chars as simple (default: 50)
COMPLEXITY_LEN_SIMPLE_MAX=40

# Classify queries ≥150 chars as complex (default: 150)
COMPLEXITY_LEN_COMPLEX_MIN=120
```

**C. Restart Server After Changes**
```bash
sudo systemctl restart voice-assistant-server.service
```

**Warning:** Keep token limits reasonable to avoid TTS truncation (see next issue).

### 12. TTS Truncation (Long Responses)

**Symptom:**
- Server log shows: `Text exceeds TTS limit (5234 chars > 4096)`
- Response audio cuts off before complete answer

**Cause:**
Groq TTS has a 4096-character limit. LLM response was too long.

**Check Server Logs:**
```bash
journalctl -u voice-assistant-server.service -n 50 | grep "TTS"
```

**Solutions:**

**A. Reduce Token Limits**
Ensure token limits stay within TTS character limit:
```env
# Rule of thumb: 1 token ≈ 4 characters
# 800 tokens ≈ 3200 chars (safe for 4096 limit)

LLM_TOKENS_SIMPLE=100   # ~400 chars
LLM_TOKENS_MODERATE=300 # ~1200 chars
LLM_TOKENS_COMPLEX=800  # ~3200 chars (safe)
```

**B. Adjust System Prompt**
Make the system prompt encourage more concise responses in `.env`:
```env
SYSTEM_PROMPT="You are a helpful voice assistant. Keep all responses under 600 words. For simple questions, answer in one sentence. For complex questions, provide thorough but concise answers."
```

**C. Monitor Truncation**
Check logs for truncation warnings:
```bash
journalctl -u voice-assistant-server.service -f | grep "truncat"
```

### 13. Request Timeouts

**Symptom:**
- Pi client shows: `[ERROR] Request timeout`
- Server log shows: `Request timeout after 45s`

**Causes:**
1. LLM timeout too short for complex queries
2. TTS timeout too short for long responses
3. Network latency

**Check Which Timeout:**
```bash
journalctl -u voice-assistant-server.service -n 50 | grep "timeout"
```

**Solutions:**

**A. Increase LLM Timeout**
For complex queries that need more processing time:
```env
# Default: 45 seconds
LLM_TIMEOUT_S=60
```

**B. Increase TTS Timeout**
For longer text-to-speech generation:
```env
# Default: 90 seconds
TTS_TIMEOUT_S=120
```

**C. Check Network**
On Pi:
```bash
ping yourdomain.com
curl -I https://yourdomain.com/health
```

**D. Restart Server After Changes**
```bash
sudo systemctl restart voice-assistant-server.service
```

### 14. Audio Playback Issues for Long Responses

**Symptom:**
- Short answers play fine
- Long, detailed answers cut off or don't play
- Pi client shows playback errors

**Check:**
1. Verify Opus file size in server logs:
   ```bash
   journalctl -u voice-assistant-server.service -n 50 | grep "Compressed"
   ```

2. Check Pi client can decompress:
   ```bash
   # Test Opus decompression
   python3 -c "import opuslib; print('Opus OK')"
   ```

**Solutions:**

**A. Verify Pi Has Enough Disk Space**
```bash
df -h ~/javia/audio
# Should have at least 100MB free
```

**B. Check Audio File Integrity**
On Pi:
```bash
ls -lh ~/javia/audio/response.wav
# Should show reasonable size (not 0 bytes)
```

**C. Increase aplay Buffer** (if audio stutters)
Client code automatically handles this, but if issues persist:
```bash
# Manually test with larger buffer
aplay -D plughw:0,0 --buffer-size=8192 ~/javia/audio/response.wav
```

**D. Monitor Logs During Playback**
```bash
# On Pi
journalctl -f | grep -i "playback\|audio"
```

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
