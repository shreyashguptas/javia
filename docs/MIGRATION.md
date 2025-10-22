# Migration Guide: Monolithic to Client-Server

This guide explains the changes from the original monolithic `javia.py` to the new client-server architecture.

## What Changed?

### Before (Monolithic)
```
Raspberry Pi (javia.py)
  ├── Records audio
  ├── Calls Groq Whisper API
  ├── Calls Groq LLM API
  ├── Calls Groq TTS API
  └── Plays audio
```

**Issues:**
- Pi does all processing (slow)
- API keys exposed on Pi
- Difficult to scale
- Single point of failure

### After (Client-Server)
```
Raspberry Pi (pi_client/client.py)     Server (server/main.py)
  ├── Records audio                       ├── Receives audio
  ├── Sends to server         ─────>      ├── Calls Groq APIs
  ├── Receives response       <─────      ├── Processes everything
  └── Plays audio                         └── Returns audio
```

**Benefits:**
- ✅ Pi only handles audio I/O (fast)
- ✅ Server does heavy processing (faster CPU)
- ✅ API keys secure on server
- ✅ Can support multiple Pis
- ✅ Easy to update/maintain

## What Stayed the Same?

### On Raspberry Pi
- ✅ Hardware setup (microphone, amplifier, button)
- ✅ Audio recording and playback
- ✅ Button controls (start/stop, interrupt)
- ✅ Gain adjustment
- ✅ Fade effects to eliminate clicks

### Processing Pipeline
- ✅ Whisper for transcription
- ✅ LLM for query processing
- ✅ TTS for speech generation
- ✅ Same models and voices

## File Mapping

### Old → New

| Old File | New Location | Purpose |
|----------|-------------|---------|
| `javia.py` | `pi_client/client.py` | Audio I/O only |
| N/A | `server/main.py` | Server application |
| N/A | `server/services/groq_service.py` | Groq API calls |
| `.env` | `server/.env` | Server config |
| `.env` | `pi_client/.env` | Client config |

## Code Changes

### What Moved to Server

**From `javia.py` lines 337-425:**
```python
def transcribe_audio():
    # ... Groq Whisper API call ...
```
**Now in:** `server/services/groq_service.py`

**From `javia.py` lines 429-517:**
```python
def query_llm(user_text):
    # ... Groq LLM API call ...
```
**Now in:** `server/services/groq_service.py`

**From `javia.py` lines 521-627:**
```python
def generate_speech(text):
    # ... Groq TTS API call ...
```
**Now in:** `server/services/groq_service.py`

### What Stayed on Pi

**Audio recording (lines 195-333):**
- Still in `pi_client/client.py`
- Same logic, same functions

**Audio playback (lines 631-919):**
- Still in `pi_client/client.py`
- Same fade effects, same amplifier control

**GPIO handling (lines 134-166):**
- Still in `pi_client/client.py`
- Same button logic

### What's New

**Server communication** (`pi_client/client.py`):
```python
def send_to_server():
    """Send audio to server and receive response"""
    # HTTPS POST with API key
    # Stream audio response
```

**FastAPI server** (`server/main.py`):
```python
@app.post("/api/v1/process")
async def process_audio():
    # Receive audio
    # Process through Groq APIs
    # Return audio response
```

**Authentication** (`server/middleware/auth.py`):
```python
async def verify_api_key():
    # Validate API key from header
```

## Configuration Changes

### Old `.env` (Monolithic)
```env
GROQ_API_KEY=your_key
BUTTON_PIN=17
MICROPHONE_GAIN=2.0
```

### New Server `.env`
```env
GROQ_API_KEY=your_groq_key
SERVER_API_KEY=your_secure_key
WHISPER_MODEL=whisper-large-v3-turbo
LLM_MODEL=openai/gpt-oss-20b
TTS_MODEL=playai-tts
```

### New Client `.env`
```env
SERVER_URL=https://yourdomain.com
CLIENT_API_KEY=matches_server_api_key
BUTTON_PIN=17
AMPLIFIER_SD_PIN=27
MICROPHONE_GAIN=2.0
```

## Migration Steps

### If You're Currently Running the Old System

1. **Keep Pi running** with old `javia.py` (don't break it yet!)

2. **Deploy server first:**
   ```bash
   # Follow server deployment in docs/DEPLOYMENT.md
   ```

3. **Test server independently:**
   ```bash
   python3 server/test_server.py
   ```

4. **Deploy client:**
   ```bash
   # Follow client deployment in docs/DEPLOYMENT.md
   ```

5. **Test client:**
   ```bash
   python3 pi_client/test_client.py
   ```

6. **Switch to new client:**
   ```bash
   # Stop old service
   sudo systemctl stop old-voice-assistant.service
   
   # Start new client
   sudo systemctl start voice-assistant-client.service
   ```

7. **Backup old files** (keep for reference):
   ```bash
   mv javia.py javia.py.backup
   ```

## Performance Comparison

### Old System (Monolithic)
```
Recording: User controlled
Processing: 5-15 seconds (Pi CPU limited)
Playback: Variable
Total: Slow
```

### New System (Client-Server)
```
Recording: User controlled
Upload: 0.5-2s
Processing: 3-8 seconds (Server is fast!)
Download: 0.5-1s
Playback: Variable
Total: Much faster!
```

## Troubleshooting Migration

### Old System Still Working?
Keep it! You can run both in parallel:
- Old: Use original GPIO pins
- New: Use same GPIO pins (just stop old service first)

### Server Not Accessible?
- Check Cloudflare DNS
- Verify nginx is running
- Test with: `curl https://yourdomain.com/health`

### API Key Mismatch?
- Verify `CLIENT_API_KEY` matches `SERVER_API_KEY`
- Both should be in respective `.env` files

### Missing Dependencies?
```bash
# Server
pip install -r server/requirements.txt

# Client
pip install -r pi_client/requirements.txt
```

## Rollback Plan

If you need to go back to the old system:

```bash
# 1. Stop new client
sudo systemctl stop voice-assistant-client.service

# 2. Restore old file
mv javia.py.backup javia.py

# 3. Run old system
cd ~/javia
source ~/venvs/pi/bin/activate
python3 javia.py
```

## Version Updates

### v1.1.0 - Unicode Character Encoding Fix

**Issue:** Server returned 500 error when LLM response contained Unicode characters (e.g., smart quotes, accented characters).

**Error message:**
```
'latin-1' codec can't encode character '\u2019' in position 186: ordinal not in range(256)
```

**Solution:** HTTP response headers are now URL-encoded to support Unicode characters.

**Files changed:**
- `server/main.py` - Added URL encoding for response headers
- `pi_client/client.py` - Added URL decoding for response headers
- `server/test_server.py` - Added URL decoding for test compatibility
- `pi_client/test_client.py` - Added URL decoding for test compatibility

**Migration:**
If you're running an older version, update both server and client:

```bash
# Update server
cd ~/voice_assistant/server
git pull
sudo systemctl restart voice-assistant-server

# Update client
cd ~/voice_assistant/pi_client
git pull
sudo systemctl restart voice-assistant-client
```

**Backward compatibility:** This change is backward compatible. The URL encoding only affects special characters; regular ASCII text remains unchanged.

## Questions?

See:
- [GETTING_STARTED.md](GETTING_STARTED.md) for quick setup
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for detailed deployment
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for system design
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for common issues

---

**The migration is worth it!** You'll get better performance, security, and scalability. 🚀

