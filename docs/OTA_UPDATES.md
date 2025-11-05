# OTA (Over-The-Air) Update System

This document describes the simplified OTA update system for managing voice assistant Pi clients remotely.

## Table of Contents

- [Overview](#overview)
- [How It Works](#how-it-works)
- [Setup](#setup)
- [Creating Updates](#creating-updates)
- [Monitoring Updates](#monitoring-updates)
- [Troubleshooting](#troubleshooting)

## Overview

The OTA update system allows you to remotely update all your Raspberry Pi voice assistant devices from a central server. When you push an update, ALL registered devices receive it immediately.

### Key Features

- **Automatic Device Registration**: Pi clients auto-register with UUID7 identifiers on first boot
- **Device Heartbeat**: Pi clients ping server every 5 minutes to report online status
- **Immediate Updates**: All devices get updates immediately when available
- **Mandatory Update Checks**: Devices check for updates before processing each query
- **Real-time Tracking**: Monitor update status for all devices via Supabase
- **System Package Updates**: Can install/update apt packages if needed

## How It Works

### Simple Update Flow

```
1. Admin creates update → Server packages code → Uploads to Supabase Storage
2. Server creates update record → Schedules for ALL registered devices
3. Pi client presses button → Checks for updates BEFORE recording
4. If update available → Downloads, installs, restarts immediately
5. If no update → Proceeds with normal query processing
```

### Device Heartbeat

- Every 5 minutes, Pi clients send heartbeat to server
- Updates `last_seen` timestamp and `current_version` in database
- Server updates device status based on heartbeat activity

### Update Detection

- **Before each query**: Device checks for pending updates
- **If update found**: Immediately downloads, installs, and restarts
- **If no update**: Proceeds with normal voice processing

This ensures devices are always up-to-date before processing queries, preventing issues from outdated code.

## Setup

### Prerequisites

1. **Supabase Project**:
   - Create a project at [supabase.com](https://supabase.com)
   - Database migrations are applied automatically
   - Create storage bucket: "update-packages" (private)

2. **Server Configuration** (`server/.env`):
   ```bash
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_KEY=your-anon-key
   SUPABASE_SERVICE_KEY=your-service-role-key
   SERVER_API_KEY=your-secret-api-key
   ```

3. **Pi Client Configuration** (`pi_client/.env`):
   ```bash
   SERVER_URL=https://your-server.com
   DEVICE_TIMEZONE=America/Los_Angeles  # Your local timezone
   ```

### Database Schema

**devices table**:
- `id` (uuid) - Primary key
- `device_uuid` (text) - UUID7 identifier
- `device_name` (text) - Optional friendly name
- `registered_at` (timestamp) - Registration time
- `last_seen` (timestamp) - Last heartbeat (updated every 5 min)
- `current_version` (text) - Current software version
- `timezone` (text) - Device timezone
- `status` (text) - online | offline | updating
- `metadata` (jsonb) - Hardware info, OS version, etc.

**updates table**:
- `id` (uuid) - Primary key
- `version` (text) - Version string (e.g., "v1.2.3")
- `created_at` (timestamp) - Creation time
- `description` (text) - What's in this update
- `package_url` (text) - Download URL for ZIP file
- `requires_system_packages` (bool) - Whether apt packages needed
- `system_packages` (jsonb) - Array of apt package names

**device_updates table**:
- `id` (uuid) - Primary key
- `device_id` (uuid) - Foreign key to devices
- `update_id` (uuid) - Foreign key to updates
- `status` (text) - pending | downloading | installing | completed | failed
- `started_at` (timestamp) - When update started
- `completed_at` (timestamp) - When update finished
- `error_message` (text) - Error details if failed

## Creating Updates

### Interactive Mode (Recommended)

Run the script without arguments for a guided experience:

```bash
cd /opt/javia/scripts/create_update
./create_update.sh
```

The interactive mode prompts for:
1. **Version Number** - Format: vX.Y.Z (e.g., v1.2.3)
2. **Update Description** - What's included in this update
3. **System Packages** - Optional apt packages to install
4. **Confirmation** - Review and confirm before creating

### Command-Line Mode

Provide all parameters directly:

```bash
cd /opt/javia/scripts/create_update
./create_update.sh v1.2.3 "Bug fixes and improvements" ""
```

Arguments:
1. Version (e.g., "v1.2.3")
2. Description
3. System packages (comma-separated or empty string)

### What Gets Packaged

The script automatically packages:
- All Python files from `pi_client/`
- `requirements.txt`
- Subdirectories: `audio/`, `hardware/`, `network/`, `utils/`
- `VERSION` file (updated with new version)
- `update_metadata.json` (metadata for installer)

### Update Package Structure

```
update_v1.2.3.zip
├── pi_client/
│   ├── client.py
│   ├── device_manager.py
│   ├── update_manager.py
│   ├── heartbeat_manager.py
│   ├── requirements.txt
│   ├── VERSION
│   ├── audio/
│   ├── hardware/
│   ├── network/
│   └── utils/
└── update_metadata.json
```

## Monitoring Updates

### View All Devices

```bash
curl -H "X-API-Key: YOUR_KEY" http://your-server:8000/api/v1/devices/
```

### View All Updates

```bash
curl -H "X-API-Key: YOUR_KEY" http://your-server:8000/api/v1/updates/
```

### Check Device's Pending Updates

```bash
curl -H "X-API-Key: YOUR_KEY" \
  http://your-server:8000/api/v1/devices/DEVICE_UUID/updates/check
```

### Device Logs (on Pi)

```bash
# View live logs
sudo journalctl -u voice-assistant-client -f

# View update-related logs
sudo journalctl -u voice-assistant-client | grep -i update
```

### Server Logs

```bash
# View live logs
sudo journalctl -u voice-assistant-server -f

# View update-related logs
sudo journalctl -u voice-assistant-server | grep -i update
```

## Troubleshooting

### Device Not Registering

**Symptoms**: Device not appearing in device list

**Solutions**:
1. Check server URL in `.env`:
   ```bash
   cat ~/javia_client/.env | grep SERVER_URL
   ```
2. Verify device is sending heartbeats:
   ```bash
   sudo journalctl -u voice-assistant-client | grep -i heartbeat
   ```
3. Check server logs for registration errors:
   ```bash
   sudo journalctl -u voice-assistant-server | grep -i register
   ```

### Updates Not Detected

**Symptoms**: Update created but device doesn't see it

**Solutions**:
1. Verify update was created in database:
   ```sql
   SELECT * FROM updates ORDER BY created_at DESC LIMIT 1;
   ```
2. Check device_updates records:
   ```sql
   SELECT * FROM device_updates WHERE status = 'pending';
   ```
3. Check device logs for update check:
   ```bash
   sudo journalctl -u voice-assistant-client | grep "UPDATE CHECK"
   ```
4. Force button press to trigger update check

### Update Failed

**Symptoms**: Device shows "failed" status in database

**Solutions**:
1. Check device logs:
   ```bash
   sudo journalctl -u voice-assistant-client -n 100 | grep -i error
   ```
2. Look for error messages in database:
   ```sql
   SELECT error_message FROM device_updates 
   WHERE device_id = 'DEVICE_ID' AND status = 'failed'
   ORDER BY created_at DESC LIMIT 1;
   ```
3. Common issues:
   - **Network timeout**: Check internet connectivity
   - **Insufficient disk space**: Run `df -h` on Pi
   - **Permission errors**: Check systemd service permissions
   - **Package conflicts**: Review system_packages requirements

### Device Shows as Offline

**Symptoms**: Device status is "offline" in database but device is running

**Solutions**:
1. Check if heartbeat is working:
   ```bash
   sudo journalctl -u voice-assistant-client | grep -i heartbeat | tail -20
   ```
2. Verify server is reachable from device:
   ```bash
   curl -I http://your-server:8000/health
   ```
3. Check network connectivity:
   ```bash
   ping -c 3 google.com
   ```
4. Restart service to re-establish heartbeat:
   ```bash
   sudo systemctl restart voice-assistant-client
   ```

### Update Stuck in "downloading"

**Symptoms**: Status shows "downloading" for extended period

**Solutions**:
1. Check network connectivity:
   ```bash
   ping -c 3 google.com
   ```
2. Verify Supabase Storage accessibility:
   ```bash
   curl -I https://your-project.supabase.co/storage/v1/object/public/update-packages/
   ```
3. Restart service to retry:
   ```bash
   sudo systemctl restart voice-assistant-client
   ```

## Best Practices

### Version Numbering

Follow semantic versioning (vX.Y.Z):

- **Patch (Z)**: Bug fixes, typos, minor changes
  - Example: `v1.2.3` → `v1.2.4`
  
- **Minor (Y)**: New features, backward compatible
  - Example: `v1.2.4` → `v1.3.0`
  
- **Major (X)**: Breaking changes, major refactoring
  - Example: `v1.3.0` → `v2.0.0`

### Testing Strategy

1. **Development Testing**:
   - Test update locally on development Pi
   - Verify all functionality works post-update
   - Check logs for errors

2. **Staged Rollout** (optional):
   - Use `target_devices` parameter to target specific devices
   - Test on 1-2 production devices first
   - Monitor for issues before full rollout

3. **Monitoring**:
   - Watch device status after pushing update
   - Check for failed updates in database
   - Review device logs for any issues

### Update Best Practices

1. **Test First**: Always test updates on dev device before production
2. **Clear Descriptions**: Write detailed update descriptions
3. **Version Incrementing**: Follow semantic versioning
4. **Monitor Rollout**: Check device statuses after creating update
5. **Keep Backups**: Keep previous versions available for rollback
6. **Document Changes**: Note what changed in each version

## API Reference

### Device Endpoints

- `POST /api/v1/devices/register` - Register new device
- `POST /api/v1/devices/{uuid}/heartbeat` - Update heartbeat
- `GET /api/v1/devices/{uuid}` - Get device info
- `GET /api/v1/devices/` - List all devices
- `GET /api/v1/devices/{uuid}/updates/check` - Check for pending updates

### Update Endpoints

- `POST /api/v1/updates/create` - Create new update (push to all devices)
- `GET /api/v1/updates/{id}/download` - Download update package
- `POST /api/v1/updates/{id}/status` - Report update status
- `GET /api/v1/updates/` - List all updates

All endpoints require `X-API-Key` header for authentication.

## Security Considerations

1. **API Authentication**: All endpoints require valid API key
2. **Supabase RLS**: Row-level security policies prevent unauthorized access
3. **Private Storage**: Update packages stored in private Supabase bucket
4. **Service Role Key**: Keep `SUPABASE_SERVICE_KEY` secure (server-side only)
5. **Network Security**: Use HTTPS for production deployments
6. **Device Authentication**: Devices authenticate via unique UUID7

## System Architecture

```
┌─────────────────┐
│  Admin Creates  │
│     Update      │
└────────┬────────┘
         │
         v
┌─────────────────┐
│  Server Uploads │
│  to Supabase    │
└────────┬────────┘
         │
         v
┌─────────────────────────────┐
│  Creates device_updates     │
│  for ALL registered devices │
└────────┬────────────────────┘
         │
         v
┌─────────────────────────────┐
│  Pi Client: Button Press    │
└────────┬────────────────────┘
         │
         v
┌─────────────────────────────┐
│  Check for updates (API)    │
└────────┬────────────────────┘
         │
    ┌────┴────┐
    │         │
    v         v
 Update    No Update
 Found     Found
    │         │
    v         │
 Download     │
 Install      │
 Restart      │
    │         │
    └────┬────┘
         v
   Process Query
```

## Future Enhancements

- [ ] Real-time dashboard for monitoring devices
- [ ] Update rollback capability
- [ ] Staged rollouts (percentage-based)
- [ ] Update scheduling UI
- [ ] Notification system for failed updates
- [ ] Delta updates (only changed files)
- [ ] Checksum verification for packages

