# Conversational Memory System with Mem0

## Overview

Integrate self-hosted Mem0 to enable context-aware conversations where the voice assistant remembers previous exchanges within a session, detects topic changes, and maintains long-term user preferences across sessions.

## Architecture

### Data Flow

1. **Device sends request** → Server receives with device_uuid (identifies device)
2. **Session detection** → Check if active session exists (< 5min since last interaction)
3. **Memory retrieval** → Fetch relevant memories from Mem0 (session context + long-term facts)
4. **Topic detection** → Use Mem0 semantic search to determine if new topic
5. **LLM query** → Send enriched context to Groq LLM
6. **Memory update** → Compress and store conversation (real-time, async)
7. **Session timeout** → After 5min silence, persist session to Supabase

### Storage Architecture

- **Supabase Postgres + pgvector**: Vector embeddings and conversation history
- **Mem0 self-hosted**: Memory management and intelligent compression
- **Server RAM**: Active session cache for fast access during conversation

## Implementation Steps

### 1. Database Schema (Supabase)

Create tables in Supabase:

**`devices`** - Track each physical device

- `id` (uuid, primary key)
- `created_at` (timestamp)
- `last_active_at` (timestamp)
- `metadata` (jsonb) - device info

**`sessions`** - Conversation sessions

- `id` (uuid, primary key)
- `device_id` (uuid, foreign key)
- `started_at` (timestamp)
- `ended_at` (timestamp, nullable)
- `topic_summary` (text, nullable)
- `status` (enum: active, ended)

**`conversations`** - Raw message history

- `id` (uuid, primary key)
- `session_id` (uuid, foreign key)
- `device_id` (uuid, foreign key)
- `user_message` (text)
- `assistant_response` (text)
- `created_at` (timestamp)

**`memories`** - Mem0-managed memories (synced from Mem0)

- Mem0 will manage this internally, we'll use its API

### 2. Mem0 Setup

**Install Mem0** on server:

- Add `mem0ai` to `server/requirements.txt`
- Configure Mem0 to use Supabase as vector store
- Create `server/services/memory_service.py` for Mem0 integration

**Mem0 Configuration:**

```python
from mem0 import Memory

config = {
    "vector_store": {
        "provider": "postgres",
        "config": {
            "url": SUPABASE_CONNECTION_STRING,
            "collection_name": "memories"
        }
    },
    "llm": {
        "provider": "groq",
        "config": {
            "model": "openai/gpt-oss-20b",
            "api_key": GROQ_API_KEY
        }
    }
}
```

### 3. Session Management Service

Create `server/services/session_service.py`:

**Key Functions:**

- `get_or_create_session(device_uuid)` - Check for active session (< 5min)
- `is_topic_related(new_query, session_context)` - Semantic similarity check
- `end_session(session_id)` - Mark session as ended, persist to DB
- `update_session_activity(session_id)` - Reset timeout timer

**Session Logic:**

1. Check last interaction timestamp
2. If > 5min → end old session, start new one
3. If < 5min → check topic relevance using Mem0 semantic search
4. If topic unrelated (similarity < 0.3) → start new session
5. Otherwise → continue existing session

### 4. Memory Service Integration

Create `server/services/memory_service.py`:

**Core Functions:**

- `add_conversation(device_uuid, session_id, user_msg, assistant_msg)` - Store and compress
- `get_session_context(session_id)` - Retrieve recent conversation
- `get_device_memories(device_uuid)` - Fetch long-term facts/preferences
- `search_memories(query, device_uuid)` - Semantic search
- `compress_context_async(session_id)` - Background compression

**Memory Types:**

- **Session memories**: Temporary, cleared after session ends
- **Device memories**: Long-term facts, preferences (persist across sessions)
- **Compressed context**: Mem0's intelligent summary of conversation

### 5. Update LLM Query Flow

Modify `server/services/groq_service.py`:

**Current flow:**

```python
query_llm(user_text, session_id=None)
```

**New flow:**

```python
query_llm_with_context(user_text, device_uuid, session_id):
    1. Get/create session
    2. Retrieve memories:
       - Session context (recent conversation)
       - Device memories (long-term facts)
    3. Build enriched prompt:
       - System prompt
       - Long-term memories
       - Session context
       - Current user message
    4. Query Groq LLM
    5. Async: Store conversation + compress
    6. Return response
```

### 6. Update Server Endpoint

Modify `server/main.py`:

**Changes:**

- Add `device_uuid` to `/api/v1/process` endpoint
- Generate UUID if not provided (new device)
- Pass device_uuid to LLM service
- Handle session management in background

**New parameters:**

```python
async def process_audio(
    audio: UploadFile,
    device_uuid: Optional[str] = Form(None),  # NEW
    session_id: Optional[str] = Form(None),   # Keep for compatibility
    microphone_gain: Optional[str] = Form("1.0"),
    api_key: str = Depends(verify_api_key)
)
```

### 7. Update Pi Client

Modify `pi_client/client.py`:

**Changes:**

- Generate persistent device UUID on first run
- Store UUID in config file (`~/.javia_device_uuid`)
- Send device_uuid with every request

**Implementation:**

```python
def get_or_create_device_uuid():
    uuid_file = Path.home() / ".javia_device_uuid"
    if uuid_file.exists():
        return uuid_file.read_text().strip()
    device_uuid = str(uuid7())
    uuid_file.write_text(device_uuid)
    return device_uuid
```

### 8. Background Session Cleanup

Create `server/services/session_cleanup.py`:

**Periodic task (runs every minute):**

- Find sessions with last_activity > 5min
- Mark as ended
- Trigger final memory compression
- Archive to database

### 9. Configuration & Environment

**Add to `server/.env`:**

```
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
SUPABASE_DB_URL=postgresql://...
MEM0_EMBEDDING_MODEL=text-embedding-3-small
```

**Add to `server/config.py`:**

- Supabase connection settings
- Mem0 configuration
- Session timeout duration (default: 300 seconds)
- Topic similarity threshold (default: 0.3)

### 10. Testing & Optimization

**Test scenarios:**

1. Single topic conversation (multiple follow-ups)
2. Topic change detection (medical → math)
3. Session timeout (5min silence)
4. Multiple devices (UUID isolation)
5. Long conversation (token limit handling)

**Performance optimizations:**

- Cache active sessions in server RAM
- Async memory compression (non-blocking)
- Batch DB writes
- Connection pooling for Supabase

## Key Files to Create/Modify

**New Files:**

- `server/services/memory_service.py` - Mem0 integration
- `server/services/session_service.py` - Session management
- `server/services/session_cleanup.py` - Background cleanup
- `server/migrations/001_create_tables.sql` - Database schema
- `docs/MEMORY.md` - Memory system documentation

**Modified Files:**

- `server/main.py` - Add device_uuid parameter
- `server/services/groq_service.py` - Integrate memory context
- `server/config.py` - Add Supabase/Mem0 settings
- `server/requirements.txt` - Add mem0ai, asyncpg
- `pi_client/client.py` - Add device UUID

## Benefits

1. **Contextual conversations** - Follow-up questions work naturally
2. **Smart topic detection** - Automatically starts fresh when topic changes
3. **Long-term memory** - Remembers device-specific preferences
4. **Cost optimization** - Mem0 compresses context (up to 80% token reduction)
5. **Fast performance** - RAM caching + async compression
6. **Scalable** - Each device isolated, multiple devices supported