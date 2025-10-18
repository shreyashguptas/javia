# Groq API Configuration

## Overview

This voice assistant uses Groq's API for three functions:
1. **Speech-to-Text** - Whisper for transcription
2. **Language Model** - LLM for query processing
3. **Text-to-Speech** - TTS for response generation

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
# See voice_assistant.py lines 299-387
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
# See voice_assistant.py lines 391-510
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

**Voice:** `Chip-PlayAI`
- Natural sounding
- Clear pronunciation
- Good for voice assistants

**Configuration:**
- Response Format: WAV
- Streaming: Yes (chunks to file)

**Code Reference:**
```python
# See voice_assistant.py lines 514-620
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
Edit `voice_assistant.py` line 57:
```python
SYSTEM_PROMPT = "Your custom prompt here"
```

### Change Response Length
Edit `voice_assistant.py` line 411:
```python
'max_tokens': 150,  # Increase for longer responses
```

### Change Models
Edit `voice_assistant.py` or use environment variables:
```env
WHISPER_MODEL=whisper-large-v3
LLM_MODEL=llama-3.1-70b-versatile
TTS_MODEL=playai-tts
TTS_VOICE=Nova-PlayAI
```

### Change Temperature
Edit `voice_assistant.py` line 412:
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
    "voice": "Chip-PlayAI"
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

