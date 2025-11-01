# API Documentation

## Overview

The voice assistant uses two API layers:

### 1. Voice Assistant REST API (Server)
The server exposes a REST API for processing audio from Raspberry Pi clients.

### 2. Groq API (Backend)
The server uses Groq's API for three functions:
1. **Speech-to-Text** - Whisper for transcription
2. **Language Model** - LLM for query processing
3. **Text-to-Speech** - TTS for response generation

---

## Voice Assistant REST API

### Base URL
```
https://yourdomain.com
```

### Authentication

**Device UUID Authentication (Pi Clients)**

All API requests from Pi clients (except `/health`) require device UUID authentication.

**Header**: `X-Device-UUID: your_device_uuid`

- Each Pi client has a unique UUID (generated automatically on first boot)
- The device UUID must be registered on the server before making requests
- To register: `./register_device.sh <DEVICE_UUID>` on the server

**Admin API Key (Management Endpoints)**

Device management endpoints require admin API key authentication.

**Header**: `X-API-Key: your_admin_api_key`

- Used only for `/api/v1/devices/*` and `/api/v1/updates/*` endpoints
- Not shared with Pi clients

### Endpoints

#### `GET /health`

Health check endpoint.

**Authentication**: None required

**Response**: `200 OK`
```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

**Example**:
```bash
curl https://yourdomain.com/health
```

---

#### `POST /api/v1/process`

Process audio through complete pipeline: transcription → LLM → TTS.

**Authentication**: Required (X-Device-UUID header)

**Request**:
- **Content-Type**: `multipart/form-data`
- **Headers**: 
  ```
  X-Device-UUID: your_device_uuid_here
  ```
- **Form Data**:
  - `audio` (file): Audio file (**Opus or WAV format**, max 25MB)
  - `session_id` (optional, string): Session identifier for conversation history
  - `microphone_gain` (optional, string): Gain multiplier (default "1.0", e.g., "2.0" for 2x amplification)

**Supported Audio Formats**:
- **Opus** (recommended): `audio/opus` - 90% smaller files, 10x faster transfer
  - Bitrate: 96kbps for excellent voice quality
  - Sample Rate: 48kHz
  - Channels: Mono
- **WAV**: `audio/wav` - Uncompressed format (backward compatibility)

**Response**: `200 OK`
- **Content-Type**: `audio/opus` (compressed for fast download)
- **Headers**:
  - `X-Transcription`: Transcribed text from audio (URL-encoded to support Unicode)
  - `X-LLM-Response`: LLM response text (URL-encoded to support Unicode)
  - `X-Session-ID`: Session ID (if provided, URL-encoded)
- **Body**: Audio file (Opus format) containing TTS response

**Note**: All response headers are URL-encoded to support Unicode characters (e.g., smart quotes, accented characters). Clients should URL-decode these values using `urllib.parse.unquote()` in Python or equivalent in other languages.

**Error Responses**:
- `400 Bad Request`: Invalid file format, size, corrupted audio, or missing/malformed device UUID
- `403 Forbidden`: Device not registered or not authorized
- `413 Request Entity Too Large`: File exceeds 25MB
- `422 Unprocessable Entity`: Validation error
- `500 Internal Server Error`: Server processing error

**Example (Opus format - recommended)**:
```bash
curl -X POST \
  -H "X-Device-UUID: 018c8f5e-8c3a-7890-a1b2-3c4d5e6f7890" \
  -F "audio=@recording.opus;type=audio/opus" \
  -F "session_id=user123_session456" \
  -F "microphone_gain=2.0" \
  https://yourdomain.com/api/v1/process \
  --output response.opus -v
```

**Example (WAV format - legacy)**:
```bash
curl -X POST \
  -H "X-Device-UUID: 018c8f5e-8c3a-7890-a1b2-3c4d5e6f7890" \
  -F "audio=@recording.wav" \
  -F "session_id=user123_session456" \
  https://yourdomain.com/api/v1/process \
  --output response.opus -v
```

**Python Example**:
```python
import requests
from urllib.parse import unquote

headers = {'X-Device-UUID': '018c8f5e-8c3a-7890-a1b2-3c4d5e6f7890'}
files = {'audio': ('recording.wav', open('recording.wav', 'rb'), 'audio/wav')}
data = {'session_id': 'user123_session456'}

response = requests.post(
    'https://yourdomain.com/api/v1/process',
    headers=headers,
    files=files,
    data=data,
    stream=True
)

if response.status_code == 200:
    # Get metadata (URL-decode to handle Unicode characters)
    transcription = unquote(response.headers.get('X-Transcription', ''))
    llm_response = unquote(response.headers.get('X-LLM-Response', ''))
    
    # Save audio
    with open('response.wav', 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
```

---

#### `GET /docs`

Interactive API documentation (Swagger UI).

**Authentication**: None required

**Access**: Open in browser: `https://yourdomain.com/docs`

---

#### `GET /redoc`

Alternative API documentation (ReDoc).

**Authentication**: None required

**Access**: Open in browser: `https://yourdomain.com/redoc`

---

### Rate Limiting

**Nginx Level**:
- 10 requests per minute per IP
- Burst: 5 additional requests allowed

**Status Code**: `429 Too Many Requests` when exceeded

**Headers**: 
```
Retry-After: 60
```

---

### Security

**Authentication**: API key in custom header
- Keys stored in environment variables only
- Transmitted over HTTPS only
- Validated on every request

**Transport**: 
- All requests must use HTTPS
- TLS 1.2+ required
- Cloudflare DDoS protection

**File Validation**:
- Content-Type must be `audio/wav`
- Size: 100 bytes minimum, 25MB maximum
- File structure validated as WAV format

---

## Groq API Configuration

## Getting Your API Key

### 1. Create Account
1. Visit [console.groq.com](https://console.groq.com)
2. Sign up (free tier available)
3. Verify your email

### 2. Generate API Key
1. Go to API Keys section in console
2. Click "Create API Key"
3. Copy the key (starts with `gsk_`)
4. Store securely

## Configuration

### Using .env File (Recommended)
```bash
# Create .env file
cp env.example .env
nano .env
```

Add your API key:
```env
GROQ_API_KEY=gsk_your_actual_api_key_here
```

### Using Environment Variable
```bash
export GROQ_API_KEY="gsk_your_actual_api_key_here"
```

### Verify Configuration
```bash
# Test API key
curl -H "Authorization: Bearer YOUR_API_KEY" \
     https://api.groq.com/openai/v1/models
```

## API Details

### Whisper (Speech-to-Text)
**Endpoint:** `https://api.groq.com/openai/v1/audio/transcriptions`

**Model:** `whisper-large-v3-turbo`
- Fast and accurate
- Supports multiple languages
- Optimized for real-time use

**Input:**
- Format: WAV audio file
- Sample Rate: 48000 Hz (mono)
- Max Size: 25 MB

**Output:**
- Text transcription
- Language detection (automatic)

**Code Reference:**
```python
# See javia.py lines 299-387
def transcribe_audio():
    # Validates file size
    # Handles retries on timeout/rate limit
    # Returns transcribed text
```

### LLM (Language Processing)
**Endpoint:** `https://api.groq.com/openai/v1/chat/completions`

**Model:** `openai/gpt-oss-20b`
- Fast inference
- Good for conversational queries
- Concise responses

**System Prompt:**
```
"You are a helpful voice assistant that gives concise, factual answers. 
Keep responses brief and conversational, under 3 sentences."
```

**Configuration:**
- Max Tokens: 150
- Temperature: 0.7 (balanced creativity)

**Code Reference:**
```python
# See javia.py lines 391-510
def query_llm(user_text):
    # Input validation
    # Retry logic
    # Response structure validation
```

**Alternative Models:**
- `llama-3.1-70b-versatile` - More capable, slower
- `mixtral-8x7b-32768` - Large context window

### TTS (Text-to-Speech)
**Endpoint:** `https://api.groq.com/openai/v1/audio/speech`

**Model:** `playai-tts`

**Voice:** `Cheyenne-PlayAI`
- Natural sounding
- Clear pronunciation
- Good for voice assistants

**Configuration:**
- Response Format: WAV
- Streaming: Yes (chunks to file)

**Code Reference:**
```python
# See javia.py lines 514-620
def generate_speech(text):
    # Text length validation (max 4096 chars)
    # Streaming download
    # WAV file validation
```

**Alternative Voices:**
- `Alloy-PlayAI`
- `Echo-PlayAI`
- `Fable-PlayAI`
- `Nova-PlayAI`
- `Shimmer-PlayAI`

## Rate Limits

### Free Tier
- **Requests/min**: 30
- **Tokens/min**: 30,000
- **Concurrent**: 2

### Handling Rate Limits
The code automatically handles rate limiting:
```python
# Retry logic with backoff
if response.status_code == 429:
    print("[WARNING] Rate limited, waiting before retry...")
    time.sleep(2)
    continue  # Retry
```

**Code:** See retry loops in:
- `transcribe_audio()` line 334
- `query_llm()` line 419
- `generate_speech()` line 544

## Error Handling

### Built-in Error Recovery
The code includes comprehensive error handling:

**1. Retries**
- 2 automatic retries on timeout
- Exponential backoff on rate limits
- Connection error detection

**2. Validation**
- File size checks (100 bytes min, 25MB max)
- Empty response detection
- API response structure validation
- Text length limits (4096 chars for TTS)

**3. Timeouts**
- Transcription: 60 seconds
- LLM: 30 seconds
- TTS: 60 seconds (streaming)

### Common Errors

**401 Unauthorized**
```
Cause: Invalid API key
Solution: Verify key in .env file starts with gsk_
```

**429 Rate Limit**
```
Cause: Too many requests
Solution: Code retries automatically, or wait 60 seconds
```

**Timeout**
```
Cause: Network slow or large file
Solution: Code retries twice, check internet connection
```

**Empty Response**
```
Cause: API returned no data
Solution: Code detects and reports, check API status
```

## Customization

### Change System Prompt
Edit `javia.py` line 57:
```python
SYSTEM_PROMPT = "Your custom prompt here"
```

### Change Response Length
Edit `javia.py` line 411:
```python
'max_tokens': 150,  # Increase for longer responses
```

### Change Models
Edit `javia.py` or use environment variables:
```env
WHISPER_MODEL=whisper-large-v3
LLM_MODEL=llama-3.1-70b-versatile
TTS_MODEL=playai-tts
TTS_VOICE=Cheyenne-PlayAI
```

### Change Temperature
Edit `javia.py` line 412:
```python
'temperature': 0.7,  # 0.0 = deterministic, 1.0 = creative
```

## Monitoring

### Check Usage
```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
     https://api.groq.com/openai/v1/usage
```

### Monitor Logs
The voice assistant logs all API calls:
```
[API] Transcribing audio...
[API] Sending 378924 bytes...
[API] Response code: 200
[SUCCESS] Transcription: "..."
```

### Debug Mode
For detailed debugging, check traceback on errors:
```
[ERROR] Transcription failed: ...
[DEBUG] Traceback (most recent call last):
  ...
```

## Security Best Practices

### API Key Security
1. ✅ Use `.env` file (not hardcoded)
2. ✅ Add `.env` to `.gitignore`
3. ✅ Never commit API keys to git
4. ✅ Rotate keys if compromised
5. ✅ Use environment-specific keys

### Network Security
1. ✅ All requests use HTTPS (code uses https://)
2. ✅ Timeouts prevent hanging (configured in code)
3. ✅ SSL certificate verification (default in requests)

## Testing APIs

### Test Whisper
```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "file=@test.wav" \
  -F "model=whisper-large-v3-turbo" \
  https://api.groq.com/openai/v1/audio/transcriptions
```

### Test LLM
```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-oss-20b",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 150
  }' \
  https://api.groq.com/openai/v1/chat/completions
```

### Test TTS
```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "playai-tts",
    "input": "Hello, this is a test.",
    "voice": "Cheyenne-PlayAI"
  }' \
  https://api.groq.com/openai/v1/audio/speech \
  --output test_response.wav
```

## Troubleshooting

### API Key Not Working
1. Verify format: `gsk_...`
2. Check `.env` file syntax
3. Restart script after changing `.env`
4. Test with curl (see Testing APIs above)

### Network Issues
1. Test connectivity: `ping api.groq.com`
2. Check DNS: `nslookup api.groq.com`
3. Verify HTTPS: `curl -I https://api.groq.com`
4. Check firewall settings

### Rate Limiting
1. Monitor usage at console.groq.com
2. Code automatically retries (no action needed)
3. Consider upgrading if frequent
4. Implement caching for repeated queries

## Resources

- [Groq API Documentation](https://console.groq.com/docs)
- [Groq Discord Community](https://discord.gg/groq)
- [API Status Page](https://status.groq.com)
- [Console Dashboard](https://console.groq.com)

