# Groq API Setup Guide

## Overview

This voice assistant uses Groq's API for three main functions:
1. **Speech-to-Text**: Whisper model for transcription
2. **Language Processing**: LLM for understanding and responding
3. **Text-to-Speech**: TTS for generating audio responses

## Getting Started

### 1. Create Groq Account
1. Visit [console.groq.com](https://console.groq.com)
2. Sign up for a free account
3. Verify your email address

### 2. Generate API Key
1. Log into the Groq console
2. Navigate to "API Keys" section
3. Click "Create API Key"
4. Copy the generated key (starts with `gsk_`)
5. Store it securely

### 3. Configure API Key
Edit `voice_assistant.py` and replace:
```python
GROQ_API_KEY = "YOUR_GROQ_API_KEY_HERE"
```

With your actual API key:
```python
GROQ_API_KEY = "gsk_your_actual_api_key_here"
```

## API Endpoints

### Speech-to-Text (Whisper)
- **Endpoint**: `https://api.groq.com/openai/v1/audio/transcriptions`
- **Model**: `whisper-large-v3-turbo`
- **Input**: WAV audio file
- **Output**: Text transcription

### Language Processing (LLM)
- **Endpoint**: `https://api.groq.com/openai/v1/chat/completions`
- **Model**: `openai/gpt-oss-20b`
- **Input**: Text conversation
- **Output**: Text response

### Text-to-Speech (TTS)
- **Endpoint**: `https://api.groq.com/openai/v1/audio/speech`
- **Model**: `playai-tts`
- **Voice**: `Chip-PlayAI`
- **Input**: Text
- **Output**: WAV audio file

## Rate Limits

### Free Tier Limits
- **Requests per minute**: 30
- **Tokens per minute**: 30,000
- **Concurrent requests**: 2

### Paid Tier Limits
- **Requests per minute**: 1,000
- **Tokens per minute**: 1,000,000
- **Concurrent requests**: 10

## Error Handling

### Common Error Codes
- **401**: Invalid API key
- **429**: Rate limit exceeded
- **500**: Server error
- **503**: Service unavailable

### Retry Logic
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
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"Rate limited, waiting {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                return response
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(1)
    return None
```

## Testing API Connection

### Test API Key
```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
     https://api.groq.com/openai/v1/models
```

### Test Whisper API
```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "file=@test.wav" \
  -F "model=whisper-large-v3-turbo" \
  https://api.groq.com/openai/v1/audio/transcriptions
```

### Test LLM API
```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-oss-20b",
    "messages": [
      {"role": "user", "content": "Hello, how are you?"}
    ],
    "max_tokens": 150
  }' \
  https://api.groq.com/openai/v1/chat/completions
```

### Test TTS API
```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "playai-tts",
    "input": "Hello, this is a test.",
    "voice": "Chip-PlayAI",
    "response_format": "wav"
  }' \
  https://api.groq.com/openai/v1/audio/speech \
  --output test_response.wav
```

## Configuration Options

### Whisper Model Options
- `whisper-large-v3-turbo`: Fast, accurate transcription
- `whisper-large-v3`: Highest accuracy, slower

### LLM Model Options
- `openai/gpt-oss-20b`: Fast, good for simple queries
- `llama-3.1-70b-versatile`: More capable, slower
- `mixtral-8x7b-32768`: Balanced performance

### TTS Voice Options
- `Chip-PlayAI`: Default voice
- `Alloy-PlayAI`: Alternative voice
- `Echo-PlayAI`: Alternative voice
- `Fable-PlayAI`: Alternative voice
- `Onyx-PlayAI`: Alternative voice
- `Nova-PlayAI`: Alternative voice
- `Shimmer-PlayAI`: Alternative voice

## Customization

### System Prompt
Modify the system prompt in `voice_assistant.py`:
```python
SYSTEM_PROMPT = "You are a helpful voice assistant that gives concise, factual answers. Keep responses brief and conversational, under 3 sentences."
```

### Response Length
Adjust the `max_tokens` parameter:
```python
payload = {
    'model': LLM_MODEL,
    'messages': [
        {'role': 'system', 'content': SYSTEM_PROMPT},
        {'role': 'user', 'content': user_text}
    ],
    'max_tokens': 150,  # Adjust this value
    'temperature': 0.7
}
```

### Audio Settings
Modify audio parameters:
```python
# Audio Configuration
SAMPLE_RATE = 16000  # 16kHz for Whisper
CHANNELS = 1         # Mono audio
RECORD_SECONDS = 5   # Recording duration
CHUNK_SIZE = 1024    # Buffer size
```

## Monitoring Usage

### Check API Usage
```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
     https://api.groq.com/openai/v1/usage
```

### Monitor Rate Limits
```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
     https://api.groq.com/openai/v1/rate_limits
```

## Security Best Practices

### API Key Security
1. **Never commit API keys to version control**
2. **Use environment variables**:
   ```bash
   export GROQ_API_KEY="your_api_key_here"
   ```
3. **Rotate keys regularly**
4. **Monitor usage for anomalies**

### Environment Variables
```python
import os

# Load from environment variable
GROQ_API_KEY = os.getenv('GROQ_API_KEY', 'YOUR_GROQ_API_KEY_HERE')

if GROQ_API_KEY == 'YOUR_GROQ_API_KEY_HERE':
    print("Error: GROQ_API_KEY environment variable not set")
    sys.exit(1)
```

### Network Security
1. **Use HTTPS only**
2. **Verify SSL certificates**
3. **Implement request timeouts**
4. **Log API calls for monitoring**

## Troubleshooting

### API Key Issues
- **Invalid key**: Check key format (starts with `gsk_`)
- **Expired key**: Generate new key
- **Wrong permissions**: Verify key has required permissions

### Network Issues
- **Connection timeout**: Check internet connectivity
- **DNS resolution**: Verify `api.groq.com` resolves
- **Firewall**: Ensure outbound HTTPS traffic allowed

### Rate Limiting
- **429 errors**: Implement exponential backoff
- **High usage**: Monitor API usage dashboard
- **Upgrade plan**: Consider paid tier for higher limits

### Audio Issues
- **File format**: Ensure WAV format for Whisper
- **File size**: Check file size limits
- **Audio quality**: Verify sample rate and bit depth

## Support Resources

### Documentation
- [Groq API Documentation](https://console.groq.com/docs)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [Whisper Documentation](https://platform.openai.com/docs/guides/speech-to-text)

### Community
- [Groq Discord](https://discord.gg/groq)
- [GitHub Issues](https://github.com/groq/groq/issues)
- [Stack Overflow](https://stackoverflow.com/questions/tagged/groq)

### Contact Support
- **Email**: support@groq.com
- **Console**: Use the support form in the Groq console
- **Status Page**: [status.groq.com](https://status.groq.com)
