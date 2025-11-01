# Create OTA Update

This script packages the Pi client code and creates an over-the-air (OTA) update that will be automatically distributed to all registered devices.

## Overview

The `create_update.sh` script automates the process of:
1. Packaging Pi client code into a distributable format
2. Creating update metadata
3. Uploading the package to the server
4. Registering the update in the database

All registered devices will automatically check for and install the update according to the update type (scheduled or urgent).

## Prerequisites

- Server must be running with Supabase configured
- `SERVER_API_KEY` must be set in `/opt/javia/.env`
- You must be in the project repository directory

## Usage

```bash
cd /opt/javia/scripts/create_update
./create_update.sh <version> <description> [update_type] [system_packages]
```

### Arguments

| Argument | Required | Description | Default |
|----------|----------|-------------|---------|
| `version` | Yes | Version string (e.g., `v1.2.3`) | - |
| `description` | Yes | Human-readable update description | - |
| `update_type` | No | Update distribution type: `scheduled` or `urgent` | `scheduled` |
| `system_packages` | No | Comma-separated list of apt packages to install | - |

### Update Types

**Scheduled Updates** (default)
- Devices update at 2 AM local time
- Non-disruptive to normal usage
- Best for feature updates and improvements

**Urgent Updates**
- Devices update after 1 hour of inactivity
- For critical security patches and bug fixes
- Prioritizes update installation

## Examples

### Basic Update (Scheduled)

```bash
./create_update.sh v1.2.3 "Bug fixes and performance improvements"
```

This creates a scheduled update that devices will install at 2 AM local time.

### Urgent Security Patch

```bash
./create_update.sh v1.2.4 "Critical security fix" urgent
```

This creates an urgent update that devices will install after 1 hour of inactivity.

### Update with System Packages

```bash
./create_update.sh v1.3.0 "Audio improvements with new codec" scheduled "libopus0,libopus-dev"
```

This installs additional system packages before applying the update.

### Complex Update

```bash
./create_update.sh v2.0.0 "Major update with new features and dependencies" urgent "python3-numpy,python3-scipy,libatlas-base-dev"
```

## What Gets Packaged

The script packages the following from the `pi_client` directory:
- All Python files (`*.py`)
- `requirements.txt`
- `env.example`
- `VERSION` file (automatically set to specified version)
- Update metadata (JSON)

## Update Distribution

Once created, the update is automatically distributed to all registered devices:

1. **Server stores the update** in Supabase storage
2. **Devices check for updates** periodically
3. **Update is downloaded** when available
4. **Installation happens** according to update type:
   - **Scheduled**: At 2 AM local time
   - **Urgent**: After 1 hour of inactivity

## Monitoring Updates

### Check Update Status

```bash
# View all updates
curl -H "X-API-Key: YOUR_API_KEY" https://yourdomain.com/api/v1/updates/

# View specific update
curl -H "X-API-Key: YOUR_API_KEY" https://yourdomain.com/api/v1/updates/v1.2.3
```

### Check Device Update Status

```bash
# View all devices and their versions
curl -H "X-API-Key: YOUR_API_KEY" https://yourdomain.com/api/v1/devices/

# View specific device
curl -H "X-API-Key: YOUR_API_KEY" https://yourdomain.com/api/v1/devices/DEVICE_UUID
```

## Troubleshooting

### "Server .env file not found"

Make sure you're running the script from the correct location and that the server is set up:

```bash
cd /opt/javia/scripts/create_update
./create_update.sh v1.2.3 "Update description"
```

### "Failed to create update (HTTP 401)"

Check that your `SERVER_API_KEY` is correctly set in `/opt/javia/.env`:

```bash
sudo nano /opt/javia/.env
# Verify SERVER_API_KEY is set
```

### "Pi client directory not found"

The script expects to find the pi_client code at `../../pi_client/`. Ensure you're running from the correct directory structure.

### Package Upload Fails

Check server logs for details:

```bash
sudo journalctl -u voice-assistant-server.service -n 50
```

Ensure Supabase storage is configured correctly in the server's `.env` file.

## Update Rollback

If an update causes issues, you can create a rollback update:

```bash
# Create update with previous version
./create_update.sh v1.2.2 "Rollback to stable version" urgent
```

Devices will install the "older" version, effectively rolling back.

## Best Practices

1. **Test updates locally first** on a test Pi device
2. **Use semantic versioning** (v1.2.3)
3. **Write descriptive update notes** for tracking
4. **Use scheduled updates** for non-critical changes
5. **Reserve urgent updates** for security fixes
6. **Monitor device status** after deploying updates
7. **Keep system packages minimal** to reduce installation time

## See Also

- [OTA Updates Documentation](../../docs/OTA_UPDATES.md)
- [Device Management](../register_device/register_device.md)
- [Server Setup](../setup/setup.md)

