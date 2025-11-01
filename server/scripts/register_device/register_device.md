# Register Device

This script registers a new Pi client device in the database, enabling it to authenticate and make requests to the server.

## Overview

The voice assistant uses UUID-based device authentication. Each Pi client has a unique UUID that must be explicitly registered on the server before the device can connect.

This provides:
- ✅ **Per-device control** - Explicitly authorize each device
- ✅ **No shared secrets** - Each device has unique identifier
- ✅ **Easy revocation** - Remove device from database to revoke access
- ✅ **Audit trail** - Track all device activity by UUID

## Prerequisites

- Server must be running with Supabase configured
- `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` must be set in `/opt/javia/.env`
- Device UUID from Pi client setup

## Getting the Device UUID

The device UUID is displayed when you run the Pi client setup script:

```bash
# On Raspberry Pi
cd /tmp/javia/pi_client/deploy
bash setup.sh
```

At the end of setup, you'll see:

```
=========================================== 
⚠️  IMPORTANT: Device Registration Required
===========================================

Your Device UUID:

  ┌────────────────────────────────────────────┐
  │  018c8f5e-8c3a-7890-a1b2-3c4d5e6f7890      │
  └────────────────────────────────────────────┘
```

Copy this UUID to register the device on the server.

## Usage

```bash
cd /opt/javia/scripts/register_device
./register_device.sh <DEVICE_UUID> [device_name] [timezone]
```

### Arguments

| Argument | Required | Description | Default |
|----------|----------|-------------|---------|
| `DEVICE_UUID` | Yes | UUID from Pi client (36 characters) | - |
| `device_name` | No | Friendly name for the device | "New Device" |
| `timezone` | No | Device timezone (e.g., `America/Los_Angeles`) | "UTC" |

## Examples

### Basic Registration

```bash
./register_device.sh 018c8f5e-8c3a-7890-a1b2-3c4d5e6f7890
```

Registers device with default name "New Device" and UTC timezone.

### With Device Name

```bash
./register_device.sh 018c8f5e-8c3a-7890-a1b2-3c4d5e6f7890 "Kitchen Pi"
```

Registers device with friendly name "Kitchen Pi".

### Full Registration

```bash
./register_device.sh 018c8f5e-8c3a-7890-a1b2-3c4d5e6f7890 "Living Room Assistant" "America/New_York"
```

Registers device with name and timezone.

## What Happens

When you register a device:

1. **UUID validated** - Checks format (must be valid UUID)
2. **Database checked** - Ensures UUID isn't already registered
3. **Device created** - Adds device to `devices` table in Supabase
4. **Status set** - Device status set to "online"
5. **Version initialized** - Current version set to "v0.0.0"

## Success Output

```
===========================================
Device Registration
===========================================

Device UUID:  018c8f5e-8c3a-7890-a1b2-3c4d5e6f7890
Device Name:  Kitchen Pi
Timezone:     America/Los_Angeles

✓ UUID format validated
✓ Connected to Supabase
✓ Device UUID is unique

✅ Device registered successfully!

Device Details:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  UUID:         018c8f5e-8c3a-7890-a1b2-3c4d5e6f7890
  Name:         Kitchen Pi
  Timezone:     America/Los_Angeles
  Status:       online
  Registered:   2024-01-15 10:30:00
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The Pi client can now connect and make requests to the server.

===========================================
Registration Complete!
===========================================
```

## Device Already Registered

If the device UUID is already registered, you'll see:

```
⚠️  Device already registered!
   UUID: 018c8f5e-8c3a-7890-a1b2-3c4d5e6f7890
   Name: Kitchen Pi
   Status: online
   Registered: 2024-01-15 10:30:00
   Last Seen: 2024-01-15 14:25:00

To update this device, use the device management endpoints or modify the database directly.
```

The script will exit successfully without making changes.

## Testing the Device

After registration, test that the device can connect:

```bash
# On Raspberry Pi
sudo journalctl -u voice-assistant-client.service -f
```

Press the button and speak. You should see successful requests in the logs.

## Managing Devices

### View All Devices

```bash
curl -H "X-API-Key: YOUR_API_KEY" https://yourdomain.com/api/v1/devices/
```

### View Specific Device

```bash
curl -H "X-API-Key: YOUR_API_KEY" https://yourdomain.com/api/v1/devices/018c8f5e-8c3a-7890-a1b2-3c4d5e6f7890
```

### Check Device in Database

Using Supabase dashboard:
1. Go to Table Editor
2. Select `devices` table
3. Find device by UUID

## Revoking Device Access

To revoke a device's access, update its status in the database:

```sql
UPDATE devices 
SET status = 'disabled' 
WHERE device_uuid = '018c8f5e-8c3a-7890-a1b2-3c4d5e6f7890';
```

Or delete the device entirely:

```sql
DELETE FROM devices 
WHERE device_uuid = '018c8f5e-8c3a-7890-a1b2-3c4d5e6f7890';
```

The device will receive a 403 Forbidden error on its next request.

## Troubleshooting

### "ERROR: .env file not found"

Make sure you're running from the correct directory:

```bash
cd /opt/javia/scripts/register_device
./register_device.sh <UUID>
```

### "ERROR: Supabase not configured"

Check that Supabase credentials are set in `/opt/javia/.env`:

```bash
sudo nano /opt/javia/.env
```

Verify these variables are set:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`

### "ERROR: Invalid UUID format"

Ensure you copied the complete UUID (36 characters with hyphens):

```
✓ Correct: 018c8f5e-8c3a-7890-a1b2-3c4d5e6f7890
✗ Wrong:   018c8f5e8c3a7890a1b23c4d5e6f7890
✗ Wrong:   018c8f5e-8c3a-7890
```

### "ERROR: Failed to connect to Supabase"

1. Verify Supabase URL is correct
2. Check that service role key has proper permissions
3. Ensure server has internet connectivity
4. Check Supabase dashboard for service status

## Common Timezones

- **US Eastern**: `America/New_York`
- **US Central**: `America/Chicago`
- **US Mountain**: `America/Denver`
- **US Pacific**: `America/Los_Angeles`
- **UTC**: `UTC`
- **UK**: `Europe/London`
- **EU Central**: `Europe/Paris`
- **Australia Sydney**: `Australia/Sydney`

See [full timezone list](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) for more options.

## Security Notes

- Device UUIDs are not secrets - they're identifiers
- Access control is enforced by database registration check
- Use `SUPABASE_SERVICE_KEY` (not anon key) for admin operations
- Regularly audit registered devices in database
- Remove unused devices to maintain security

## See Also

- [Getting Started Guide](../../docs/GETTING_STARTED.md)
- [API Documentation](../../docs/API.md)
- [OTA Updates](../create_update/create_update.md)
- [Server Setup](../setup/setup.md)

