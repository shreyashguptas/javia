# Register Device

This script registers a new Pi client device in the database, enabling it to authenticate and make requests to the server.

## Overview

The voice assistant uses UUID-based device authentication. Each Pi client has a unique UUID that must be explicitly registered on the server before the device can connect.

This provides:
- ✅ **Per-device control** - Explicitly authorize each device
- ✅ **No shared secrets** - Each device has unique identifier
- ✅ **Easy revocation** - Remove device from database to revoke access
- ✅ **Audit trail** - Track all device activity by UUID

## Why Interactive Mode?

**New in this version:** The script now features an interactive mode (similar to the Pi client setup) that makes registration easier:
- 📝 **Guided prompts** - Step-by-step input for all required fields
- 🌍 **Timezone picker** - Visual selection from 29+ common timezones
- ✅ **Confirmation** - Review your inputs before registering
- 🎯 **Error prevention** - Validates inputs as you type

**TL;DR:** Just run `./register_device.sh` without arguments for the easiest experience!

## Quick Start

```bash
# 1. Get the Device UUID from your Pi (shown during Pi setup)
# 2. SSH into your server
# 3. Navigate to the registration script
cd /opt/javia/scripts/register_device

# 4. Run the script (interactive mode)
./register_device.sh

# Follow the prompts to enter:
#   - Device UUID (from Pi)
#   - Device Name (e.g., "Kitchen Pi")
#   - Timezone (select from list)
```

That's it! Your device is now registered and can connect to the server.

## Prerequisites

- Server must be running with Supabase configured
- `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` must be set in your server `.env` file
- Device UUID from Pi client setup (shown during Pi client setup)

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

### Interactive Mode (Recommended)

Simply run the script without arguments for an interactive registration experience:

```bash
cd /opt/javia/scripts/register_device
./register_device.sh
```

The script will prompt you for:
1. **Device UUID** - The UUID from your Pi client
2. **Device Name** - A friendly name (e.g., "Kitchen Pi")
3. **Timezone** - Select from a list of common timezones

This is the easiest and recommended method as it guides you through the registration process step-by-step, similar to the Pi client setup experience.

### Command-Line Mode (Legacy)

You can also provide arguments directly:

```bash
cd /opt/javia/scripts/register_device
./register_device.sh <DEVICE_UUID> [device_name] [timezone]
```

#### Arguments

| Argument | Required | Description | Default |
|----------|----------|-------------|---------|
| `DEVICE_UUID` | Yes | UUID from Pi client (36 characters) | - |
| `device_name` | No | Friendly name for the device | "New Device" |
| `timezone` | No | Device timezone (e.g., `America/Los_Angeles`) | "UTC" |

## Examples

### Interactive Registration (Recommended)

```bash
./register_device.sh
```

Example session:

```
===========================================
Device Registration
===========================================

===================================
Interactive Device Registration
===================================

Enter the Device UUID from your Pi client:
(This is displayed when you run the Pi client setup)

Device UUID: 018c8f5e-8c3a-7890-a1b2-3c4d5e6f7890

Enter a friendly name for this device:
(Examples: "Kitchen Pi", "Living Room Assistant", "Bedroom Device")

Device Name (default: New Device): Kitchen Pi

Select the device timezone:

Available Timezones:
   1. America/New_York
   2. America/Chicago
   3. America/Denver
   4. America/Phoenix
 → 5. America/Los_Angeles
   ...
   29. UTC

Enter number (1-29), or press Enter for UTC: 5

===================================
Registration Summary
===================================

Device UUID:  018c8f5e-8c3a-7890-a1b2-3c4d5e6f7890
Device Name:  Kitchen Pi
Timezone:     America/Los_Angeles

Proceed with registration? (Y/n): Y
```

### Command-Line Registration

Basic registration with defaults:
```bash
./register_device.sh 018c8f5e-8c3a-7890-a1b2-3c4d5e6f7890
```

With device name:
```bash
./register_device.sh 018c8f5e-8c3a-7890-a1b2-3c4d5e6f7890 "Kitchen Pi"
```

Full registration with all parameters:
```bash
./register_device.sh 018c8f5e-8c3a-7890-a1b2-3c4d5e6f7890 "Living Room Assistant" "America/New_York"
```

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

This means the server hasn't been set up yet or the `.env` file is missing.

**Solution:**
1. Ensure you've run the server setup first:
   ```bash
   cd /opt/javia/scripts/setup
   sudo ./setup.sh
   ```
2. Verify the `.env` file exists:
   ```bash
   ls -la /opt/javia/.env
   ```
3. If running from a different location, the script will automatically detect the correct path (it looks for the `.env` file two directories up from the script location)

### "ERROR: Supabase not configured"

The Supabase credentials are missing or incomplete in your `.env` file.

**Solution:**
1. Open your server `.env` file:
   ```bash
   sudo nano /opt/javia/.env
   ```
2. Verify these variables are set:
   - `SUPABASE_URL` - Your Supabase project URL
   - `SUPABASE_SERVICE_KEY` - Your Supabase service role key (not anon key!)
3. Get these from your Supabase dashboard:
   - Go to Project Settings > API
   - Copy the URL
   - Copy the `service_role` key (under "Project API keys")

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

### ".env: line X: are: command not found" or similar bash errors

This error occurs when the `.env` file has formatting issues that bash tries to interpret as commands.

**What happened:** The script now uses Python to safely parse the `.env` file, avoiding this issue entirely.

**If you still see this error:**
1. Make sure you're running the latest version of the script
2. Check your `.env` file for unusual formatting:
   ```bash
   nano /opt/javia/.env
   ```
3. Look for lines with:
   - Unquoted spaces in values
   - Inline comments without proper formatting
   - Missing `=` signs
   - Special characters that bash might interpret

**Example of problematic `.env` formatting:**
```bash
# BAD - spaces without quotes
SOME_KEY=this value has spaces

# GOOD - quoted or no spaces
SOME_KEY="this value has spaces"
SOME_KEY=this_value_has_underscores
```

**Quick fix:** The updated script automatically handles these issues by parsing the file with Python instead of sourcing it with bash.

## Available Timezones

The interactive mode includes a comprehensive list of timezones to choose from:

### North America
- **US Eastern**: `America/New_York`
- **US Central**: `America/Chicago`
- **US Mountain**: `America/Denver`
- **US Mountain (no DST)**: `America/Phoenix`
- **US Pacific**: `America/Los_Angeles`
- **US Alaska**: `America/Anchorage`
- **US Hawaii**: `America/Honolulu`
- **Canada Toronto**: `America/Toronto`
- **Canada Vancouver**: `America/Vancouver`
- **Canada Edmonton**: `America/Edmonton`
- **Canada Winnipeg**: `America/Winnipeg`
- **Canada Halifax**: `America/Halifax`
- **Mexico City**: `America/Mexico_City`
- **Mexico Monterrey**: `America/Monterrey`
- **Mexico Tijuana**: `America/Tijuana`

### Europe
- **UK**: `Europe/London`
- **France/Central Europe**: `Europe/Paris`
- **Germany**: `Europe/Berlin`
- **Netherlands**: `Europe/Amsterdam`
- **Spain**: `Europe/Madrid`

### Asia
- **Japan**: `Asia/Tokyo`
- **China**: `Asia/Shanghai`
- **Singapore**: `Asia/Singapore`
- **UAE**: `Asia/Dubai`
- **India**: `Asia/Kolkata`

### Pacific
- **Australia Sydney**: `Australia/Sydney`
- **Australia Melbourne**: `Australia/Melbourne`
- **New Zealand**: `Pacific/Auckland`

### Other
- **UTC**: `UTC` (Coordinated Universal Time)

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

