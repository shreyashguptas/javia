# Voice Assistant Architecture

## Overview

The voice assistant has been architected as a client-server system to optimize performance and enable scalability.

## Architecture Diagram

```
┌───────────────────────────────────────────────────────────────────┐
│                         RASPBERRY PI CLIENT                       │
│                                                                   │
│  ┌────────────┐     ┌──────────────┐     ┌────────────────────┐   │
│  │   Button   │────▶│  Audio       │────▶│  Audio Processing  │   │
│  │   Input    │     │  Recording   │     │  (Gain, Fade)      │   │
│  └────────────┘     └──────────────┘     └────────────────────┘   │
│                            │                        │             │
│                            ▼                        ▼             │
│                     ┌──────────────────────────────────┐          │
│                     │   HTTPS Request with Audio       │          │
│                     │   + API Key Authentication       │          │
│                     └──────────────────────────────────┘          │
│                                    │                              │
└────────────────────────────────────┼──────────────────────────────┘
                                     │
                                     │ HTTPS/TLS
                                     │
                      ┌──────────────▼──────────────┐
                      │      CLOUDFLARE CDN         │
                      │  - DDoS Protection          │
                      │  - SSL/TLS Termination      │
                      │  - Rate Limiting            │
                      └──────────────┬──────────────┘
                                     │
┌────────────────────────────────────┼────────────────────────────────┐
│                         DEBIAN SERVER                               │
│                                    │                                │
│                      ┌─────────────▼────────────┐                   │
│                      │      NGINX Reverse Proxy │                   │
│                      │  - SSL Termination       │                   │
│                      │  - Rate Limiting         │                   │
│                      │  - Request Validation    │                   │
│                      └─────────────┬────────────┘                   │
│                                    │                                │
│                      ┌─────────────▼────────────┐                   │
│                      │    FastAPI Application   │                   │
│                      │  - API Key Auth          │                   │
│                      │  - Request Validation    │                   │
│                      │  - Error Handling        │                   │
│                      └─────────────┬────────────┘                   │
│                                    │                                │
│                      ┌─────────────▼────────────┐                   │
│                      │    Groq Service Layer    │                   │
│                      │  - Whisper (STT)         │                   │
│                      │  - LLM (Processing)      │                   │
│                      │  - TTS (Speech Gen)      │                   │
│                      └─────────────┬────────────┘                   │
│                                    │                                │
└────────────────────────────────────┼────────────────────────────────┘
                                     │
                      ┌──────────────▼──────────────┐
                      │       GROQ API CLOUD        │
                      │  - whisper-large-v3-turbo   │
                      │  - openai/gpt-oss-20b       │
                      │  - playai-tts               │
                      └─────────────────────────────┘
```

## Component Responsibilities

### Raspberry Pi Client

**Location**: `pi_client/client.py`

**Responsibilities**:
- GPIO button handling
- Audio recording from I2S microphone
- Audio amplification (gain adjustment)
- Sending audio to server via HTTPS
- Receiving processed audio response
- Audio playback through I2S amplifier
- Fade-in/fade-out and silence padding

**Key Features**:
- Minimal dependencies (PyAudio, RPi.GPIO, requests, numpy)
- Secure API key storage in environment variables
- Automatic reconnection on network issues
- Button interrupt support during playback

**Hardware**:
- INMP441 I2S Microphone
- MAX98357A I2S Amplifier
- Push button for user input
- 3W speaker

### Server (Debian VM)

**Location**: `server/`

**Responsibilities**:
- Accept audio file uploads via REST API
- Authenticate requests using API key
- Process audio through Groq API pipeline:
  1. Transcription (Whisper)
  2. LLM query
  3. Speech generation (TTS)
- Stream audio response back to client
- Session management (future feature)
- Error handling and logging

**Components**:

#### FastAPI Application (`main.py`)
- REST API endpoint: `POST /api/v1/process`
- Health check: `GET /health`
- API documentation: `/docs`, `/redoc`
- Request validation and error handling
- File streaming for efficient memory usage

#### Groq Service Layer (`services/groq_service.py`)
- Encapsulates all Groq API calls
- Retry logic with exponential backoff
- Rate limit handling
- Error handling and logging

#### Authentication Middleware (`middleware/auth.py`)
- API key validation from `X-API-Key` header
- Fast, stateless authentication

#### Configuration (`config.py`)
- Pydantic settings management
- Environment variable loading
- Type validation

## API Specification

### Authentication

All API requests (except `/health`) require authentication via API key.

**Header**: `X-API-Key: <your-api-key>`

### Endpoints

#### `GET /health`

Health check endpoint.

**Response**:
```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

#### `POST /api/v1/process`

Process audio through the complete pipeline.

**Request**:
- **Content-Type**: `multipart/form-data`
- **Headers**: 
  - `X-API-Key`: Authentication key
- **Form Data**:
  - `audio`: Audio file (WAV format, max 25MB)
  - `session_id`: Optional session identifier (string)

**Response**:
- **Content-Type**: `audio/wav`
- **Headers**:
  - `X-Transcription`: Transcribed text
  - `X-LLM-Response`: LLM response text
  - `X-Session-ID`: Session ID (if provided)
- **Body**: Audio file (WAV format)

**Status Codes**:
- `200`: Success
- `400`: Bad request (invalid file, wrong format)
- `401`: Unauthorized (missing API key)
- `403`: Forbidden (invalid API key)
- `413`: Request too large (file exceeds 25MB)
- `422`: Validation error
- `500`: Internal server error

## Data Flow

### Complete Request Flow

1. **User presses button** on Raspberry Pi
2. **Pi records audio** from microphone
3. **Pi applies gain** to recorded audio
4. **Pi saves audio** as WAV file
5. **Pi sends HTTPS request** to server:
   - Includes `X-API-Key` header
   - Uploads audio file
   - Optionally includes session ID
6. **Cloudflare processes** request:
   - DDoS protection
   - Rate limiting
   - SSL/TLS handling
7. **Nginx receives** request:
   - Additional rate limiting
   - Proxies to FastAPI
8. **FastAPI validates** request:
   - Checks API key
   - Validates file size and format
   - Saves temporary file
9. **Groq Service processes** audio:
   - **Step 1**: Transcribe audio (Whisper API)
   - **Step 2**: Query LLM with transcription
   - **Step 3**: Generate speech from LLM response (TTS API)
10. **Server returns** audio response:
    - Streams audio file
    - Includes metadata in headers
11. **Pi receives** response:
    - Saves audio file
    - Displays transcription and response
12. **Pi plays** audio:
    - Applies fade-in/fade-out
    - Adds silence padding
    - Plays through speaker

## Security Architecture

### Authentication

- **API Key**: Shared secret between Pi and server
- **Storage**: Environment variables only (never in code)
- **Transmission**: HTTPS only (encrypted in transit)
- **Validation**: Every request validated server-side

### Transport Security

- **HTTPS/TLS**: All communication encrypted
- **Cloudflare**: SSL/TLS termination, DDoS protection
- **Nginx**: SSL/TLS termination (origin certificates)

### Rate Limiting

- **Cloudflare**: Configured per domain
- **Nginx**: 10 requests per minute per IP
- **Burst**: 5 additional requests allowed

### File Validation

- **Size limit**: 25MB maximum
- **Content-Type**: Must be `audio/wav`
- **File structure**: Validated as WAV format
- **Minimum size**: 100 bytes

### Pi Security

- **API key permissions**: `chmod 600 .env` (read by pi user only)
- **No secrets in code**: All credentials in environment variables
- **No remote access**: Optional (can be disabled)

## Session Management (Future)

### Design

Session management is planned for future implementation to enable:
- Conversation history tracking
- Context-aware responses
- User personalization
- Learning user preferences

### Architecture

```
Server:
  ├── sessions/
  │   ├── session_store.py    # Session storage (Redis/DB)
  │   ├── session_manager.py  # Session lifecycle
  │   └── conversation.py     # Conversation history
```

### Flow

1. Client includes `session_id` in request
2. Server loads conversation history for session
3. LLM receives context from previous messages
4. Server saves new message to session
5. Sessions expire after inactivity (e.g., 1 hour)

## Scalability Considerations

### Current Architecture

- **Single server**: Handles all requests
- **Stateless**: No session state (easy to scale)
- **FastAPI**: Async support for concurrency

### Future Scaling

**Horizontal Scaling**:
- Add more server instances
- Use load balancer (Nginx, HAProxy, Cloudflare)
- Shared session storage (Redis, PostgreSQL)

**Vertical Scaling**:
- Increase CPU/RAM on server
- Multiple workers in uvicorn
- Connection pooling for Groq API

**Optimization**:
- Cache common responses
- Compress audio in transit
- Use faster audio codecs (Opus)
- Parallel API calls where possible

## Monitoring and Logging

### Server Logging

- **Application logs**: `journalctl -u voice-assistant-server.service`
- **Nginx access logs**: `/var/log/nginx/voice-assistant-access.log`
- **Nginx error logs**: `/var/log/nginx/voice-assistant-error.log`

### Client Logging

- **Application logs**: `journalctl -u voice-assistant-client.service`
- **Console output**: Visible when running manually

### Metrics to Monitor

- Request latency (end-to-end)
- Error rates (4xx, 5xx)
- API key usage
- Audio file sizes
- Groq API response times
- Disk usage (temp files)

## Deployment Topology

```
┌────────────────────────────────────────────────────────────┐
│                    Production Deployment                   │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Raspberry Pi (Home)                                       │
│  ├── IP: Dynamic (residential)                             │
│  ├── Network: WiFi                                         │
│  └── Connects to: Server via HTTPS                         │
│                                                            │
│  Cloudflare                                                │
│  ├── DNS: yourdomain.com                                   │
│  ├── SSL: Full (strict) mode                               │
│  └── Features: DDoS protection, caching                    │
│                                                            │
│  Debian Server (VPS/Cloud)                                 │
│  ├── IP: Static public IP                                  │
│  ├── Ports: 80, 443 (open)                                 │
│  ├── Services:                                             │
│  │   ├── Nginx (reverse proxy)                             │
│  │   ├── FastAPI (application)                             │
│  │   └── Systemd (process management)                      │
│  └── Connects to: Groq API via HTTPS                       │
│                                                            │
│  Groq Cloud                                                │
│  ├── API: api.groq.com                                     │
│  └── Models: Whisper, LLM, TTS                             │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

## Technology Stack

### Raspberry Pi Client

- **Language**: Python 3
- **Framework**: None (pure Python)
- **Libraries**: PyAudio, RPi.GPIO, requests, numpy
- **OS**: Raspberry Pi OS

### Server

- **Language**: Python 3.11+
- **Framework**: FastAPI
- **Server**: Uvicorn (ASGI)
- **Reverse Proxy**: Nginx
- **OS**: Debian 13

### Infrastructure

- **CDN**: Cloudflare
- **SSL/TLS**: Cloudflare + Origin Certificates
- **Process Manager**: systemd
- **Deployment**: Shell scripts + systemd services

## Performance Characteristics

### Latency Breakdown (Typical)

```
Recording: Variable (user-controlled)
Upload: 0.5-2s (depends on audio length, network)
Transcription: 1-3s (Groq Whisper)
LLM Query: 0.5-2s (Groq LLM)
TTS Generation: 1-3s (Groq TTS)
Download: 0.5-1s (depends on response length)
Playback: Variable (response length)
─────────────────────────────────────
Total (excluding recording/playback): 3-11 seconds
```

### Bottlenecks

1. **Network latency**: Pi to server (can't optimize much)
2. **Groq API processing**: Depends on Groq infrastructure
3. **Audio file size**: Larger files = longer upload

### Optimization Opportunities

1. **Audio compression**: Use compressed formats (Opus, MP3)
2. **Streaming**: Stream audio as it's generated
3. **Caching**: Cache common responses
4. **Local processing**: Move some processing to Pi (if fast enough)

