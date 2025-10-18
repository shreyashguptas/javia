# Voice Assistant Server

FastAPI-based server for processing voice assistant requests via Groq API.

## Quick Start

### 1. Install Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp env.example .env
nano .env
```

Set the following:
```env
GROQ_API_KEY=your_groq_api_key_here
SERVER_API_KEY=your_secure_api_key_here
```

Generate a secure API key:
```bash
openssl rand -hex 32
```

### 3. Run Server

**Development**:
```bash
python3 main.py
```

**Production** (see [../docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md)):
```bash
cd deploy
sudo bash deploy.sh
```

### 4. Test Server

```bash
python3 test_server.py
```

Or manually:
```bash
curl http://localhost:8000/health
```

## API Endpoints

- `GET /health` - Health check
- `GET /docs` - API documentation
- `POST /api/v1/process` - Process audio (requires X-API-Key header)

## Documentation

- [Architecture](../docs/ARCHITECTURE.md)
- [Deployment](../docs/DEPLOYMENT.md)
- [API Reference](../docs/API.md)

## Project Structure

```
server/
├── main.py              # FastAPI application
├── config.py            # Configuration
├── requirements.txt     # Dependencies
├── services/
│   └── groq_service.py  # Groq API integration
├── middleware/
│   └── auth.py          # Authentication
├── models/
│   └── requests.py      # Request/response models
└── deploy/              # Deployment files
```

