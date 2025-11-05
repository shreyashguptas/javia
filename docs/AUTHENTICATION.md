# Authentication Architecture

## Overview

The Javia voice assistant uses a **dual authentication system**:
1. **Device UUID Authentication** (`X-Device-UUID` header) - For device-initiated operations
2. **API Key Authentication** (`X-API-Key` header) - For admin operations

This document describes the authentication flow and which endpoints use which method.

## Authentication Methods

### 1. Device UUID Authentication (`X-Device-UUID`)

**Purpose**: Authenticates individual Pi devices for their own operations.

**How it works**:
- Each Pi device has a unique UUID (stored in `~/.javia_device_uuid`)
- Device must be registered on the server (via admin `register_device.sh` script)
- Device sends its UUID in the `X-Device-UUID` header
- Server validates UUID against database and checks device status

**Used for**:
- Audio processing (`/api/v1/process`)
- Sending heartbeats (`/api/v1/devices/{uuid}/heartbeat`)
- Checking for updates (`/api/v1/devices/{uuid}/updates/check`)
- Downloading updates (`/api/v1/updates/{id}/download`)
- Reporting update status (`/api/v1/updates/{id}/status`)

**Implementation**:
```python
# Client-side
headers = {
    "X-Device-UUID": device_uuid,
    "Content-Type": "application/json"
}
response = requests.post(url, json=data, headers=headers)
```

```python
# Server-side
from middleware.device_auth import verify_device_uuid

@router.post("/{device_uuid}/heartbeat")
async def heartbeat_endpoint(
    device_uuid: str,
    request: DeviceHeartbeatRequest,
    device: DeviceResponse = Depends(verify_device_uuid)
):
    # Device is authenticated and available in 'device' parameter
    pass
```

### 2. API Key Authentication (`X-API-Key`)

**Purpose**: Authenticates server admins for management operations.

**How it works**:
- API key is stored in server's `.env` file (`SERVER_API_KEY` variable)
- Admin scripts send API key in `X-API-Key` header
- Server validates key against configured value

**Used for**:
- Registering devices (`/api/v1/devices/register`)
- Listing devices (`/api/v1/devices/`)
- Getting device info (`/api/v1/devices/{uuid}`)
- Updating device status (`/api/v1/devices/{uuid}/status`)
- Creating updates (`/api/v1/updates/create`)
- Listing updates (`/api/v1/updates/`)

**Implementation**:
```bash
# Admin script
curl -X POST "$SERVER_URL/api/v1/devices/register" \
  -H "X-API-Key: $SERVER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

```python
# Server-side
from middleware.auth import verify_api_key

@router.post("/register", dependencies=[Depends(verify_api_key)])
async def register_device_endpoint(request: DeviceRegisterRequest):
    # API key is verified before this function is called
    pass
```

## Endpoint Authentication Matrix

### Device Management Endpoints (`/api/v1/devices`)

| Endpoint | Method | Auth Method | Purpose |
|----------|--------|-------------|---------|
| `/register` | POST | API Key | Register new device (admin) |
| `/{uuid}/heartbeat` | POST | Device UUID | Device sends heartbeat |
| `/{uuid}/updates/check` | GET | Device UUID | Device checks for updates |
| `/{uuid}` | GET | API Key | Get device info (admin) |
| `/{uuid}/status` | PATCH | API Key | Update device status (admin) |
| `/` | GET | API Key | List all devices (admin) |

### Update Management Endpoints (`/api/v1/updates`)

| Endpoint | Method | Auth Method | Purpose |
|----------|--------|-------------|---------|
| `/create` | POST | API Key | Create new update (admin) |
| `/{id}/download` | GET | Device UUID | Device downloads update |
| `/{id}/status` | POST | Device UUID | Device reports update status |
| `/` | GET | API Key | List all updates (admin) |

### Audio Processing Endpoints (`/api/v1`)

| Endpoint | Method | Auth Method | Purpose |
|----------|--------|-------------|---------|
| `/process` | POST | Device UUID | Process audio query |

## Device Registration Flow

### Step 1: Device Generates UUID

When the Pi client first runs:
```python
# pi_client/device_manager.py
device_uuid = str(uuid7())  # Generate time-sortable UUID
# Save to ~/.javia_device_uuid
```

### Step 2: Admin Registers Device on Server

On the server, admin runs:
```bash
cd /opt/javia/server/scripts/register_device
sudo ./register_device.sh <device-uuid>
```

This creates a database entry with:
- `device_uuid`: The device's UUID
- `device_name`: Optional friendly name
- `status`: Initially "online"
- `timezone`: Device timezone

### Step 3: Device Authenticates

From now on, the device can make authenticated requests:
```python
headers = {"X-Device-UUID": device_uuid}
response = requests.post(f"{server_url}/api/v1/process", headers=headers, files=files)
```

Server validates:
1. UUID format is valid
2. Device exists in database
3. Device status is "online" or "active"

## Security Considerations

### Device UUID Security

**Strengths**:
- ✅ Each device has unique identifier
- ✅ Server can revoke access by changing device status
- ✅ UUIDs are not guessable (UUID7 with timestamp + random bits)
- ✅ Server validates device registration before allowing operations

**Limitations**:
- ⚠️ UUID is sent in plaintext (mitigate with HTTPS)
- ⚠️ No rotation mechanism for compromised UUIDs (manually update device)

**Best Practices**:
1. **Always use HTTPS in production** to encrypt UUID in transit
2. Store device UUID with restricted permissions (`chmod 600 ~/.javia_device_uuid`)
3. Monitor device activity via heartbeats and logs
4. Set device status to "offline" to revoke access

### API Key Security

**Strengths**:
- ✅ Single key for all admin operations
- ✅ Only stored on server (never on devices)
- ✅ Easy to rotate if compromised

**Limitations**:
- ⚠️ All admins share same key (no per-admin permissions)
- ⚠️ Key sent in plaintext (mitigate with HTTPS)

**Best Practices**:
1. **Use a strong random API key** (64+ characters recommended)
2. **Never commit API key to version control**
3. Store in `.env` file with restricted permissions (`chmod 600 .env`)
4. **Rotate API key if compromised** (update all admin scripts)
5. **Always use HTTPS in production**

## Troubleshooting Authentication Issues

### Error: 401 Unauthorized

**Symptoms**: Request returns 401 status code

**Possible Causes**:
1. Missing authentication header
2. Invalid UUID/API key format
3. Wrong authentication method for endpoint

**Solutions**:
```bash
# Check if device UUID is valid
cat ~/.javia_device_uuid

# Check if device is registered (on server)
psql -d javia -c "SELECT * FROM devices WHERE device_uuid = '<uuid>';"

# Verify API key (on server)
grep SERVER_API_KEY /opt/javia/.env
```

### Error: 403 Forbidden

**Symptoms**: Request returns 403 status code

**Possible Causes**:
1. Device not registered in database
2. Device status is not "online" or "active"
3. Device UUID in path doesn't match authenticated UUID

**Solutions**:
```bash
# Register device (on server)
cd /opt/javia/server/scripts/register_device
sudo ./register_device.sh <device-uuid>

# Check device status (on server)
psql -d javia -c "UPDATE devices SET status = 'online' WHERE device_uuid = '<uuid>';"
```

### Error: Heartbeat Failed (401)

**Symptom**: Pi client logs show `Heartbeat failed: 401`

**Root Cause**: Client is using old authentication (X-API-Key instead of X-Device-UUID)

**Solution**: Update Pi client code to use device UUID authentication:
```python
# OLD (WRONG)
headers = {"X-API-Key": api_key}

# NEW (CORRECT)
headers = {"X-Device-UUID": device_uuid}
```

## Migration from Old Authentication

### Before (Broken)

**Problem**: All device endpoints required API key, but devices only had UUID.

```python
# pi_client/device_manager.py (OLD)
def send_heartbeat(self):
    headers = {"X-API-Key": self.api_key}  # ❌ Device doesn't have API key!
    response = requests.post(url, headers=headers)
```

**Result**: 401 Unauthorized errors

### After (Fixed)

**Solution**: Split endpoints by authentication type.

```python
# pi_client/device_manager.py (NEW)
def send_heartbeat(self):
    headers = {"X-Device-UUID": self.device_uuid}  # ✅ Device uses UUID
    response = requests.post(url, headers=headers)
```

```python
# server/routers/devices.py (NEW)
@router.post("/{device_uuid}/heartbeat")
async def heartbeat_endpoint(
    device_uuid: str,
    request: DeviceHeartbeatRequest,
    device: DeviceResponse = Depends(verify_device_uuid)  # ✅ Device auth
):
    pass
```

**Result**: Authentication works correctly

## Testing Authentication

### Test Device Authentication

```bash
# Get device UUID
DEVICE_UUID=$(cat ~/.javia_device_uuid)

# Test heartbeat endpoint
curl -X POST "http://server:8000/api/v1/devices/$DEVICE_UUID/heartbeat" \
  -H "X-Device-UUID: $DEVICE_UUID" \
  -H "Content-Type: application/json" \
  -d '{
    "current_version": "v1.0.0",
    "status": "online",
    "metadata": {}
  }'
```

Expected: 200 OK with device info

### Test API Key Authentication

```bash
# Test register endpoint (admin only)
curl -X POST "http://server:8000/api/v1/devices/register" \
  -H "X-API-Key: $SERVER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "device_uuid": "test-uuid-123",
    "timezone": "America/Los_Angeles"
  }'
```

Expected: 200 OK with device info

## Conclusion

The dual authentication system provides:
- ✅ **Security**: Devices can only access their own operations
- ✅ **Scalability**: Each device has unique credentials
- ✅ **Manageability**: Admins can manage all devices with API key
- ✅ **Auditability**: Device UUIDs enable tracking per-device activity

**Key Takeaway**: Device-initiated operations use `X-Device-UUID`, admin operations use `X-API-Key`.

