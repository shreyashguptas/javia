# Update Mechanisms

This document describes the three update mechanisms available for pushing updates to Pi client devices.

## Overview

The Javia voice assistant system supports **three types of updates**:

1. **Scheduled Updates** - Updates installed at 2 AM local time
2. **Urgent Updates** - Updates installed after 1 hour of inactivity
3. **Instant Updates** - Updates installed immediately for recently active devices

## Device Heartbeat System

All Pi clients send a heartbeat ping to the server **every 5 minutes** to report their status.

### What Happens During Heartbeat

- Device reports it is "online"
- Server updates the `last_seen` timestamp in the database
- Server updates the `current_version` field
- Server updates the `updated_at` timestamp
- Device metadata is refreshed (IP address, OS version, etc.)

### Database Updates

The heartbeat updates the following fields in the `devices` table:
- `last_seen`: Current timestamp
- `current_version`: Software version running on device
- `status`: Set to "online"
- `metadata`: Hardware and system information
- `updated_at`: Current timestamp (automatic)

## Update Types

### 1. Scheduled Update (Default)

**Use Case**: Feature updates, improvements, non-critical bug fixes

**Behavior**:
- Update is scheduled for **2 AM local time** (device timezone)
- Device checks for updates daily
- Update installs during the scheduled maintenance window
- Non-disruptive to normal device usage

**Example**:
```bash
cd /opt/javia/scripts/create_update
sudo ./create_update.sh
# Select option 1: Scheduled Update
```

### 2. Instant Update

**Use Case**: Breaking changes requiring immediate deployment, critical functionality updates

**Behavior**:
- Only targets devices that were **online in the last 5 minutes**
- Update begins **immediately** when device checks for updates
- **Device will NOT function until update completes**
- Other devices will receive update at their next heartbeat (within 5 minutes)

**Warning**: Use this only when absolutely necessary! The device will be non-functional during the update process.

**Example**:
```bash
cd /opt/javia/scripts/create_update
sudo ./create_update.sh
# Select option 2: Instant Update
```

**How It Works**:
1. Server checks `last_seen` timestamp for each device
2. Only devices seen within last 300 seconds (5 minutes) get the update
3. Update is scheduled with `scheduled_for = NOW`
4. Device applies update immediately on next check
5. Device becomes unavailable during installation
6. Device restarts with new version

### 3. Urgent Update

**Use Case**: Critical security patches, urgent bug fixes that need quick deployment

**Behavior**:
- Device checks for updates every 5 minutes
- Update installs after **1 hour of continuous inactivity**
- Ensures update happens soon without disrupting active usage
- More aggressive than scheduled but safer than instant

**Example**:
```bash
cd /opt/javia/scripts/create_update
sudo ./create_update.sh
# Select option 3: Urgent Update
```

## Version Management

### VERSION File

The `pi_client/VERSION` file contains the current software version:
```
v0.0.1
```

### Version Format

All versions must follow semantic versioning:
```
vX.Y.Z
```

Where:
- **X** = Major version (breaking changes)
- **Y** = Minor version (new features, backward compatible)
- **Z** = Patch version (bug fixes, small improvements)

### Version Update Flow

1. Developer updates code in `pi_client/` directory
2. Developer runs `create_update.sh`
3. Script reads current version from `pi_client/VERSION`
4. Developer provides new version number
5. Script packages code with new version number
6. Script uploads package to server
7. Server schedules update for all devices
8. Devices download and install update
9. Device's `current_version` is updated in database

## Creating an Update

### Interactive Mode (Recommended)

```bash
cd /opt/javia/scripts/create_update
sudo ./create_update.sh
```

Follow the interactive prompts to:
1. Specify version number
2. Enter description
3. Choose update type (scheduled/instant/urgent)
4. Add system packages if needed
5. Confirm and upload

### Command-Line Mode

```bash
cd /opt/javia/scripts/create_update
sudo ./create_update.sh "v1.2.3" "Bug fixes" "scheduled" ""
```

Arguments:
1. Version (e.g., "v1.2.3")
2. Description
3. Update type: "scheduled", "instant", or "urgent"
4. System packages (comma-separated, or empty string)

## Monitoring Updates

### Check Device Status

```bash
# View all devices
curl -H "X-API-Key: $SERVER_API_KEY" http://localhost:8000/api/v1/devices/

# View specific device
curl -H "X-API-Key: $SERVER_API_KEY" http://localhost:8000/api/v1/devices/{device_uuid}
```

### Check Update Status

```bash
# List all updates
curl -H "X-API-Key: $SERVER_API_KEY" http://localhost:8000/api/v1/updates/

# Check if device has pending updates
curl -H "X-API-Key: $SERVER_API_KEY" http://localhost:8000/api/v1/devices/{device_uuid}/updates/check
```

### Device Logs

On the Pi device:
```bash
# View live logs
journalctl -u voice-assistant.service -f

# View recent update activity
journalctl -u voice-assistant.service --since "1 hour ago" | grep -i update
```

### Server Logs

On the server:
```bash
# View live logs
journalctl -u voice-assistant-server.service -f

# View recent update activity
journalctl -u voice-assistant-server.service --since "1 hour ago" | grep -i update
```

## Update Process Details

### Device-Side Process

1. **Heartbeat Manager** sends ping every 5 minutes
2. **Update Manager** checks for pending updates
3. If update found, process based on type:
   - **Instant**: Apply immediately
   - **Urgent**: Wait for 1 hour inactivity
   - **Scheduled**: Wait until 2 AM
4. Download update package from server
5. Report status: downloading → installing
6. Extract package to temporary location
7. Stop voice assistant service
8. Copy new files to installation directory
9. Update VERSION file
10. Install system packages (if required)
11. Restart service
12. Report status: completed

### Server-Side Process

1. **create_update.sh** packages pi_client code
2. Upload package to Supabase Storage
3. Create record in `updates` table
4. Schedule update for target devices:
   - Query `devices` table
   - For instant updates: filter by `last_seen < 5 minutes`
   - Create records in `device_updates` table
5. Devices poll for updates via Supabase Realtime
6. Track update progress via status updates

## Database Schema

### devices Table

```sql
- id: UUID (primary key)
- device_uuid: TEXT (unique)
- device_name: TEXT
- registered_at: TIMESTAMPTZ
- last_seen: TIMESTAMPTZ  -- Updated every 5 minutes
- current_version: TEXT   -- Updated after successful update
- timezone: TEXT
- status: TEXT (online/offline/updating)
- metadata: JSONB
- created_at: TIMESTAMPTZ
- updated_at: TIMESTAMPTZ  -- Updated every 5 minutes
```

### updates Table

```sql
- id: UUID (primary key)
- version: TEXT (unique)
- created_at: TIMESTAMPTZ
- update_type: TEXT (scheduled/urgent/instant)
- description: TEXT
- package_url: TEXT
- requires_system_packages: BOOLEAN
- system_packages: JSONB
```

### device_updates Table

```sql
- id: UUID (primary key)
- device_id: UUID (foreign key → devices)
- update_id: UUID (foreign key → updates)
- status: TEXT (pending/downloading/installing/completed/failed)
- scheduled_for: TIMESTAMPTZ
- started_at: TIMESTAMPTZ
- completed_at: TIMESTAMPTZ
- error_message: TEXT
- created_at: TIMESTAMPTZ
- updated_at: TIMESTAMPTZ
```

## Troubleshooting

### Device Not Receiving Updates

1. Check if device is sending heartbeats:
   ```bash
   # On server, check last_seen timestamp
   curl -H "X-API-Key: $API_KEY" http://localhost:8000/api/v1/devices/{device_uuid}
   ```

2. Check device logs:
   ```bash
   # On Pi device
   journalctl -u voice-assistant.service -n 100 | grep -i heartbeat
   ```

3. Verify network connectivity from device to server

### Update Failed

1. Check device logs for error messages:
   ```bash
   journalctl -u voice-assistant.service -n 500 | grep -i error
   ```

2. Check device_updates status in database:
   ```sql
   SELECT * FROM device_updates 
   WHERE device_id = 'xxx' 
   ORDER BY created_at DESC 
   LIMIT 10;
   ```

3. Common issues:
   - Network interruption during download
   - Insufficient disk space
   - Missing system packages
   - Permission errors

### Instant Update Not Instant

1. Check device's `last_seen` timestamp:
   - Must be within last 5 minutes
   - Heartbeat may be delayed due to network issues

2. Verify update was created with "instant" type:
   ```bash
   curl -H "X-API-Key: $API_KEY" http://localhost:8000/api/v1/updates/ | grep instant
   ```

3. Check if device_update record was created:
   ```sql
   SELECT * FROM device_updates 
   WHERE update_id = 'xxx' AND status = 'pending';
   ```

## Best Practices

### When to Use Each Update Type

**Scheduled** ✅
- Adding new features
- Performance improvements
- Non-critical bug fixes
- UI/UX changes
- Documentation updates

**Instant** ⚠️
- API breaking changes that prevent current code from working
- Critical bug causing device malfunction
- Security vulnerability requiring immediate patch
- Database schema changes affecting current code

**Urgent** 🚨
- Security patches (non-breaking)
- Important bug fixes
- Stability improvements
- Issues affecting user experience

### Version Numbering Guidelines

- **Patch (Z)**: Bug fixes, typos, minor changes
  - `v1.2.3` → `v1.2.4`
  
- **Minor (Y)**: New features, backward compatible
  - `v1.2.4` → `v1.3.0`
  
- **Major (X)**: Breaking changes, major refactoring
  - `v1.3.0` → `v2.0.0`

### Testing Updates

1. **Development Testing**:
   - Test update locally on development Pi
   - Verify all functionality works post-update
   - Check logs for errors

2. **Staged Rollout**:
   - Use `target_devices` parameter to target specific devices
   - Test on 1-2 production devices first
   - Monitor for 24 hours before full rollout

3. **Rollback Plan**:
   - Keep previous version package available
   - Document rollback procedure
   - Have SSH access to devices for manual intervention

## Security Considerations

- All updates require valid API key
- Update packages stored in private Supabase Storage bucket
- Device authentication via unique device UUID
- TLS encryption for all network communication
- Update integrity verified via package checksums

## Future Enhancements

Potential improvements for the update system:

1. **Rollback Support**: Automatic rollback on update failure
2. **A/B Testing**: Deploy updates to subset of devices
3. **Staged Rollout**: Gradual rollout with canary deployments
4. **Update Approval**: Manual approval step before instant updates
5. **Bandwidth Throttling**: Limit update download speed
6. **Delta Updates**: Only send changed files, not full package
7. **Signature Verification**: Cryptographic signing of update packages

