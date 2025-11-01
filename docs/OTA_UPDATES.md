# OTA (Over-The-Air) Update System

This document describes the OTA update system for managing voice assistant Pi clients remotely.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Setup](#setup)
- [Usage](#usage)
- [How It Works](#how-it-works)
- [Troubleshooting](#troubleshooting)

## Overview

The OTA update system allows you to remotely update all your Raspberry Pi voice assistant devices without SSH access. Updates are distributed from a central server and applied automatically based on a schedule or urgency.

### Key Features

- **Automatic Device Registration**: Pi clients auto-register with UUID7 identifiers on first boot
- **Scheduled Updates**: Updates applied at 2 AM local time (configurable per device timezone)
- **Urgent Updates**: Critical patches applied after 1 hour of device inactivity
- **Real-time Tracking**: Monitor update status for all devices via Supabase
- **Rollback Safety**: Failed updates don't brick devices (forward-fix only)
- **System Package Updates**: Can install/update apt packages if needed

## Architecture

### Components

1. **Supabase Database**: Stores device registry, updates, and update status
2. **Server API**: Manages device registration, heartbeats, and update distribution
3. **Pi Client Managers**:
   - `device_manager.py`: Device registration and identification (UUID7)
   - `activity_tracker.py`: Monitors user activity for safe update timing
   - `update_manager.py`: Downloads and applies updates
4. **Update Packaging Script**: `server/scripts/create_update/create_update.sh`

### Database Schema

**devices table**:
- `id` (uuid) - Primary key
- `device_uuid` (text) - UUID7 identifier
- `device_name` (text) - Optional friendly name
- `registered_at` (timestamp) - Registration time
- `last_seen` (timestamp) - Last heartbeat
- `current_version` (text) - Current software version
- `timezone` (text) - Device timezone (e.g., "America/Los_Angeles")
- `status` (text) - online | offline | updating
- `metadata` (jsonb) - Hardware info, OS version, etc.

**updates table**:
- `id` (uuid) - Primary key
- `version` (text) - Version string (e.g., "v1.2.3")
- `created_at` (timestamp) - Creation time
- `update_type` (text) - scheduled | urgent
- `description` (text) - What's in this update
- `package_url` (text) - Download URL for ZIP file
- `requires_system_packages` (bool) - Whether apt packages needed
- `system_packages` (jsonb) - Array of apt package names

**device_updates table**:
- `id` (uuid) - Primary key
- `device_id` (uuid) - Foreign key to devices
- `update_id` (uuid) - Foreign key to updates
- `status` (text) - pending | downloading | installing | completed | failed
- `scheduled_for` (timestamp) - When to apply update
- `started_at` (timestamp) - When update started
- `completed_at` (timestamp) - When update finished
- `error_message` (text) - Error details if failed

### Data Flow

```
1. Admin creates update → Server packages code → Uploads to Supabase Storage
2. Server creates update record → Schedules for all devices
3. Pi clients poll/listen for updates → Detect pending update
4. Pi waits for scheduled time or inactivity → Downloads update
5. Pi installs update → Restarts service → Reports completion
```

## Setup

### Prerequisites

1. **Supabase Project**:
   - Create a project at [supabase.com](https://supabase.com)
   - Run the database migration (automatically done via MCP)
   - Create storage bucket: "update-packages"
   - Enable realtime on `device_updates` table

2. **Server Configuration**:
   Add to `server/.env`:
   ```bash
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_KEY=your-anon-key
   SUPABASE_SERVICE_KEY=your-service-role-key
   ```

3. **Pi Client Configuration**:
   Add to `pi_client/.env`:
   ```bash
   DEVICE_TIMEZONE=America/Los_Angeles  # Your local timezone
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_KEY=your-anon-key
   ```

4. **Install Dependencies**:
   - Server: `pip install -r server/requirements.txt`
   - Pi: `pip install -r pi_client/requirements.txt`

### First-Time Device Setup

On each Pi device:

1. Clone the repository
2. Run the setup script: `bash pi_client/deploy/setup.sh`
3. Enter server URL and API key when prompted
4. Device will auto-register on first boot

The device UUID is saved to `~/.javia_device_uuid` and persists across updates.

## Usage

### Creating an Update

Use the update creation script:

```bash
# Scheduled update (applied at 2 AM local time)
cd /opt/javia/scripts/create_update
./create_update.sh v1.2.3 "Bug fixes and performance improvements" scheduled

# Urgent update (applied after 1 hour inactivity)
./create_update.sh v1.2.4 "Critical security patch" urgent

# Update with system packages
./create_update.sh v1.3.0 "Add new audio codec" scheduled "libopus0,libopus-dev"
```

### Script Parameters

- `version`: Version string (e.g., "v1.2.3")
- `description`: Human-readable description
- `update_type`: "scheduled" or "urgent"
- `system_packages`: Comma-separated apt packages (optional)

### What Gets Packaged

The script automatically packages:
- All Python files from `pi_client/`
- `requirements.txt`
- `VERSION` file (updated with new version)
- `update_metadata.json` (metadata for installer)

### Monitoring Updates

**View all devices**:
```bash
curl -H "X-API-Key: YOUR_KEY" http://your-server:8000/api/v1/devices/
```

**View all updates**:
```bash
curl -H "X-API-Key: YOUR_KEY" http://your-server:8000/api/v1/updates/
```

**Check device's pending updates**:
```bash
curl -H "X-API-Key: YOUR_KEY" \
  http://your-server:8000/api/v1/devices/DEVICE_UUID/updates/check
```

## How It Works

### Device Registration

On first boot, each Pi client:

1. Generates a UUID7 identifier
2. Saves it to `~/.javia_device_uuid`
3. Registers with server via POST `/api/v1/devices/register`
4. Sends periodic heartbeats (every 5 minutes)

### Activity Tracking

The `activity_tracker` monitors:
- Button presses
- Recording sessions
- Playback sessions

Used to determine safe update times (when device is idle).

### Update Scheduling

**Scheduled Updates** (normal):
- Created with `update_type=scheduled`
- Applied at 2 AM in device's local timezone
- Devices convert UTC schedule to local time using `pytz`

**Urgent Updates** (critical patches):
- Created with `update_type=urgent`
- Applied after 1 hour of inactivity
- Device must be idle (no user interaction)

### Update Process

1. **Detection**: Update manager polls server every 5 minutes
2. **Waiting**: Waits for scheduled time or inactivity threshold
3. **Downloading**: Downloads ZIP package from Supabase Storage
4. **Installing**:
   - Extracts files to temp directory
   - Installs system packages (if specified)
   - Updates Python dependencies
   - Copies files to installation directory
   - Updates VERSION file
5. **Restarting**: Restarts systemd service
6. **Completion**: Reports success/failure to server

### Update Package Structure

```
update_v1.2.3.zip
├── pi_client/
│   ├── client.py
│   ├── device_manager.py
│   ├── activity_tracker.py
│   ├── update_manager.py
│   ├── requirements.txt
│   └── VERSION
└── update_metadata.json
```

## Troubleshooting

### Device Not Registering

**Symptoms**: Device not appearing in device list

**Solutions**:
1. Check server URL in `.env`:
   ```bash
   cat ~/javia_client/.env | grep SERVER_URL
   ```
2. Verify API key is correct
3. Check server logs:
   ```bash
   sudo journalctl -u voice-assistant-server -f
   ```
4. Test registration manually:
   ```bash
   python3 -c "from device_manager import DeviceManager; \
     dm = DeviceManager('http://your-server:8000', 'YOUR_API_KEY', 'UTC'); \
     print(dm.register())"
   ```

### Updates Not Detected

**Symptoms**: Update created but device doesn't see it

**Solutions**:
1. Check Supabase connection:
   ```bash
   # In pi_client directory
   python3 -c "from supabase import create_client; \
     client = create_client('URL', 'KEY'); \
     print(client.table('devices').select('*').execute())"
   ```
2. Verify device is registered:
   ```bash
   curl -H "X-API-Key: KEY" http://server:8000/api/v1/devices/
   ```
3. Check update manager is running:
   ```bash
   sudo journalctl -u voice-assistant-client -f | grep "update"
   ```
4. Force update check:
   ```bash
   # Restart service to reinitialize update manager
   sudo systemctl restart voice-assistant-client
   ```

### Update Failed

**Symptoms**: Device shows "failed" status in database

**Solutions**:
1. Check device logs:
   ```bash
   sudo journalctl -u voice-assistant-client -n 100
   ```
2. Look for error messages in device_updates table:
   ```sql
   SELECT error_message FROM device_updates 
   WHERE device_id = 'DEVICE_ID' AND status = 'failed'
   ORDER BY created_at DESC LIMIT 1;
   ```
3. Common issues:
   - **Network timeout**: Increase timeout in `update_manager.py`
   - **Insufficient disk space**: Clear `/tmp` directory
   - **Permission errors**: Check systemd service has correct permissions
   - **Package conflicts**: Review system_packages requirements

### Update Stuck in "downloading"

**Symptoms**: Status shows "downloading" for extended period

**Solutions**:
1. Check network connectivity:
   ```bash
   ping -c 3 google.com
   ```
2. Verify Supabase Storage accessibility:
   ```bash
   curl -I https://your-project.supabase.co/storage/v1/object/public/update-packages/updates/v1.2.3.zip
   ```
3. Restart service to retry:
   ```bash
   sudo systemctl restart voice-assistant-client
   ```

### Device UUID Lost

**Symptoms**: Device re-registers with new UUID after update

**Solutions**:
- UUID is stored in `~/.javia_device_uuid` which persists across updates
- If lost, device will generate new UUID (not ideal but functional)
- Backup UUID file during manual maintenance:
  ```bash
  cp ~/.javia_device_uuid ~/.javia_device_uuid.backup
  ```

### Debugging Tips

**Enable verbose logging**:
```python
# In pi_client/client.py, modify:
logging.basicConfig(level=logging.DEBUG)
```

**Watch update process in real-time**:
```bash
sudo journalctl -u voice-assistant-client -f | grep -E "(UPDATE|OTA|device)"
```

**Query device status from database**:
```python
from supabase import create_client
client = create_client('URL', 'SERVICE_KEY')
result = client.table('device_updates').select('*, updates(*), devices(*)').eq('status', 'pending').execute()
print(result.data)
```

**Manually trigger update (for testing)**:
```bash
# Set scheduled_for to past time
# Device will apply update immediately
```

## Security Considerations

1. **API Authentication**: All endpoints require valid API key
2. **Supabase RLS**: Row-level security policies prevent unauthorized access
3. **Update Verification**: Consider adding checksum verification to ZIP files
4. **Service Role Key**: Keep `SUPABASE_SERVICE_KEY` secure (server-side only)
5. **Network Security**: Use HTTPS for production deployments

## Best Practices

1. **Version Naming**: Use semantic versioning (v1.2.3)
2. **Test Updates**: Test on one device before rolling out to all
3. **Gradual Rollout**: Use `target_devices` to update subset first
4. **Backup Strategy**: Keep backups of working versions
5. **Monitor Rollout**: Check device statuses after creating update
6. **Update Frequency**: Scheduled updates preferred for non-critical changes
7. **Documentation**: Document what changed in each version

## API Reference

### Device Endpoints

- `POST /api/v1/devices/register` - Register new device
- `POST /api/v1/devices/{uuid}/heartbeat` - Update heartbeat
- `GET /api/v1/devices/{uuid}` - Get device info
- `GET /api/v1/devices/` - List all devices
- `GET /api/v1/devices/{uuid}/updates/check` - Check for pending updates
- `PATCH /api/v1/devices/{uuid}/status` - Update device status

### Update Endpoints

- `POST /api/v1/updates/create` - Create new update
- `GET /api/v1/updates/{id}/download` - Download update package
- `POST /api/v1/updates/{id}/status` - Report update status
- `GET /api/v1/updates/` - List all updates

All endpoints require `X-API-Key` header for authentication.

## Future Enhancements

- [ ] Real-time dashboard for monitoring devices
- [ ] Update rollback capability
- [ ] Staged rollouts (percentage-based)
- [ ] Update scheduling UI
- [ ] Notification system for failed updates
- [ ] Automatic version bumping
- [ ] Delta updates (only changed files)
- [ ] Update approval workflow

