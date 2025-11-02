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
- `SERVER_API_KEY` must be set in server `.env` file (either `/opt/javia/.env` or `server/.env`)
- You must be in the project repository directory

## Usage

### Interactive Mode (Recommended)

Simply run the script without arguments for an interactive guided experience:

```bash
cd /path/to/voice_assistant/server/scripts/create_update
./create_update.sh
```

The interactive mode will guide you through:

**Step 1: Version Number**
- Input format: `vX.Y.Z` (e.g., `v1.2.3`)
- Semantic versioning guidelines provided
- Shows current version if available

**Step 2: Update Description**
- Clear, descriptive text about what's included
- Examples provided for guidance

**Step 3: Update Type**
- **Option 1: Scheduled Update** (default)
  - Devices update at 2 AM local time
  - Best for feature updates and improvements
- **Option 2: Urgent Update**
  - Devices update after 1 hour of inactivity
  - Best for critical security patches and urgent fixes

**Step 4: System Packages** (optional)
- Comma-separated list of apt packages
- Common package suggestions provided
- Can be skipped if no system packages needed

**Step 5: Confirmation**
- Review all details before creating the update
- Cancel or proceed

### Command-Line Mode (Legacy)

You can also provide all arguments directly:

```bash
./create_update.sh <version> <description> [update_type] [system_packages]
```

#### Arguments

| Argument | Required | Description | Default |
|----------|----------|-------------|---------|
| `version` | Yes | Version string (e.g., `v1.2.3`) | - |
| `description` | Yes | Human-readable update description | - |
| `update_type` | No | Update distribution type: `scheduled` or `urgent` | `scheduled` |
| `system_packages` | No | Comma-separated list of apt packages to install | - |

## Update Types

### Scheduled Updates (Default)
- **Installation Time**: 2 AM local time (device timezone)
- **Check Frequency**: Daily
- **Use Case**: Feature updates, improvements, non-critical bug fixes
- **Impact**: Non-disruptive to normal usage
- **Best For**: 
  - New features and enhancements
  - Performance improvements
  - Minor bug fixes
  - Documentation updates

### Urgent Updates
- **Installation Time**: After 1 hour of inactivity
- **Check Frequency**: Every 5 minutes
- **Use Case**: Critical security patches, urgent bug fixes
- **Impact**: Prioritizes update installation
- **Best For**:
  - Security vulnerabilities
  - Critical system bugs
  - Data corruption fixes
  - Service disruptions

## Examples

### Interactive Mode (Recommended)

```bash
cd /opt/javia/scripts/create_update
./create_update.sh
```

Follow the prompts to enter:
- Version (e.g., `v1.2.3`)
- Description (e.g., `"Bug fixes and performance improvements"`)
- Update type (choose 1 for scheduled, 2 for urgent)
- System packages (optional, e.g., `libopus0,python3-pyaudio`)

### Basic Update (Scheduled) - Command Line

```bash
./create_update.sh v1.2.3 "Bug fixes and performance improvements"
```

This creates a scheduled update that devices will install at 2 AM local time.

### Urgent Security Patch - Command Line

```bash
./create_update.sh v1.2.4 "Critical security fix" urgent
```

This creates an urgent update that devices will install after 1 hour of inactivity.

### Update with System Packages - Command Line

```bash
./create_update.sh v1.3.0 "Audio improvements with new codec" scheduled "libopus0,libopus-dev"
```

This installs additional system packages before applying the update.

### Complex Update - Command Line

```bash
./create_update.sh v2.0.0 "Major update with new features and dependencies" urgent "python3-numpy,python3-scipy,libatlas-base-dev"
```

## What Gets Packaged

The script packages the following from the `pi_client` directory:
- All Python files (`*.py`)
- `requirements.txt` (Python dependencies)
- `env.example` (environment configuration template)
- `VERSION` file (automatically set to specified version)
- `update_metadata.json` (update information)

## Update Distribution Flow

```
1. Create Update (this script)
   │
   ├─> Package pi_client code
   ├─> Create metadata
   ├─> Upload to server
   └─> Register in database
   
2. Server Stores Update
   │
   ├─> Supabase storage
   └─> Database entry
   
3. Devices Check for Updates
   │
   ├─> Scheduled: Daily check
   └─> Urgent: Check every 5 minutes
   
4. Device Downloads Update
   │
   ├─> Verify version
   ├─> Download package
   └─> Verify integrity
   
5. Device Installs Update
   │
   ├─> Scheduled: At 2 AM local time
   ├─> Urgent: After 1 hour inactivity
   ├─> Install system packages (if needed)
   ├─> Update Python code
   └─> Restart service
```

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

### Monitor Device Logs

SSH into a device and monitor the update process:

```bash
ssh pi@device-ip
journalctl -u voice-assistant.service -f
```

## Troubleshooting

### "Server .env file not found"

The script searches for the `.env` file in multiple locations. Make sure one exists:

```bash
# Check if .env exists
ls -l /opt/javia/.env
# or
ls -l /path/to/server/.env

# If missing, run server setup
cd /opt/javia/scripts/setup
sudo ./setup.sh
```

### "Invalid version format"

Version must follow semantic versioning: `vX.Y.Z`

✅ Valid: `v1.2.3`, `v2.0.0`, `v0.1.5`
❌ Invalid: `1.2.3`, `v1.2`, `version-1.2.3`

### "Failed to create update (HTTP 401)"

Authentication failed. Check your `SERVER_API_KEY`:

```bash
sudo nano /opt/javia/.env
# Verify SERVER_API_KEY is set and correct
```

### "Failed to create update (HTTP 500)"

Server error. Check server logs:

```bash
sudo journalctl -u voice-assistant-server.service -n 50
```

Common causes:
- Supabase not configured correctly
- Storage bucket doesn't exist
- Database connection issues

### "Pi client directory not found"

The script expects this directory structure:
```
voice_assistant/
├── pi_client/          # Must exist
│   ├── client.py
│   ├── requirements.txt
│   └── VERSION
└── server/
    └── scripts/
        └── create_update/
            └── create_update.sh  # Run from here
```

Ensure you're running from the correct location:

```bash
cd /path/to/voice_assistant/server/scripts/create_update
./create_update.sh
```

### Package Upload Fails

Check Supabase configuration:

```bash
# Verify Supabase credentials in .env
grep SUPABASE /opt/javia/.env

# Test server connection
curl http://localhost:8000/health

# Check server logs
sudo journalctl -u voice-assistant-server.service -n 100
```

### Devices Not Receiving Update

1. **Verify devices are registered:**
   ```bash
   curl -H "X-API-Key: YOUR_API_KEY" https://yourdomain.com/api/v1/devices/
   ```

2. **Check device status:**
   - Device must be online
   - Device must have network connectivity
   - Device must have correct server URL configured

3. **Check device logs:**
   ```bash
   ssh pi@device-ip
   journalctl -u voice-assistant.service -n 100
   ```

4. **Verify update was created:**
   ```bash
   curl -H "X-API-Key: YOUR_API_KEY" https://yourdomain.com/api/v1/updates/
   ```

## Update Rollback

If an update causes issues, you can create a rollback update by deploying a previous version:

```bash
# Interactive mode
./create_update.sh
# Enter previous stable version (e.g., v1.2.2)
# Set as urgent update for faster rollback

# Or command-line mode
./create_update.sh v1.2.2 "Rollback to stable version" urgent
```

Devices will install the "older" version, effectively rolling back the changes.

## Version Management Best Practices

### Semantic Versioning

Follow [Semantic Versioning 2.0.0](https://semver.org/):

**MAJOR version** (`vX.0.0`)
- Breaking changes
- API changes that break compatibility
- Major architecture changes

**MINOR version** (`v1.X.0`)
- New features
- Backward-compatible changes
- New voice commands or capabilities

**PATCH version** (`v1.2.X`)
- Bug fixes
- Performance improvements
- Security patches

### Update Type Guidelines

| Change Type | Severity | Update Type | Example |
|-------------|----------|-------------|---------|
| Security fix | Critical | Urgent | `v1.2.4 "Critical security patch" urgent` |
| Major bug | High | Urgent | `v1.2.5 "Fix audio crash" urgent` |
| Data corruption | Critical | Urgent | `v1.2.6 "Fix data loss bug" urgent` |
| New feature | Medium | Scheduled | `v1.3.0 "Add weather support" scheduled` |
| Bug fix | Low | Scheduled | `v1.2.7 "Fix typo in logs" scheduled` |
| Performance | Medium | Scheduled | `v1.2.8 "Optimize memory usage" scheduled` |

## Testing Updates

### Test Before Deployment

Always test updates on a test device before deploying to all devices:

1. **Set up test device:**
   ```bash
   # Register device with test name
   ./register_device.sh TEST_UUID "Test Device" "UTC"
   ```

2. **Deploy to test device first:**
   - Create update as usual
   - Monitor test device logs
   - Verify functionality

3. **Deploy to production:**
   - If test succeeds, update will roll out to all devices
   - If test fails, create rollback update

### Local Testing

Test the package creation without uploading:

```bash
# Modify script to stop before upload
# Check the generated package manually
```

## Best Practices

1. **Always use interactive mode** for better guidance and fewer errors
2. **Test updates locally first** on a test Pi device before production deployment
3. **Use semantic versioning** (vX.Y.Z) consistently
4. **Write descriptive update notes** for tracking and debugging
5. **Use scheduled updates** for non-critical changes to avoid disruption
6. **Reserve urgent updates** for security fixes and critical bugs only
7. **Keep system packages minimal** to reduce installation time and potential conflicts
8. **Monitor device status** after deploying updates
9. **Document breaking changes** in update descriptions
10. **Maintain a changelog** separate from update descriptions for detailed history

## System Package Management

### Common Packages

```bash
# Audio processing
libopus0,libopus-dev

# Audio I/O
python3-pyaudio,portaudio19-dev

# Numerical processing
python3-numpy,python3-scipy

# Linear algebra (required for some ML libraries)
libatlas-base-dev,liblapack-dev

# Media codecs
libavcodec-dev,libavformat-dev

# System tools
htop,iotop,net-tools
```

### Package Installation Notes

- System packages are installed via `apt-get` on the Pi
- Installation happens before Python code update
- Failed package installation will abort the update
- Keep package list minimal to reduce update time
- Test package installation on a test device first

## Integration with CI/CD

You can integrate this script into your CI/CD pipeline:

```bash
# GitHub Actions example
- name: Create OTA Update
  run: |
    cd server/scripts/create_update
    ./create_update.sh "${{ github.ref_name }}" "Release ${{ github.ref_name }}" scheduled
```

## See Also

- [OTA Updates Documentation](../../docs/OTA_UPDATES.md) - Detailed update system architecture
- [Device Management](../register_device/register_device.md) - How to register and manage devices
- [Server Setup](../setup/setup.md) - Initial server configuration
- [Deployment Guide](../../docs/DEPLOYMENT.md) - Full deployment process
- [Architecture](../../docs/ARCHITECTURE.md) - System architecture overview

## Quick Reference

```bash
# Interactive mode (recommended)
./create_update.sh

# Command-line mode
./create_update.sh <version> <description> [update_type] [system_packages]

# Examples
./create_update.sh v1.2.3 "Bug fixes"
./create_update.sh v1.2.4 "Security patch" urgent
./create_update.sh v1.3.0 "New features" scheduled "libopus0"

# Check update status
curl -H "X-API-Key: KEY" https://domain.com/api/v1/updates/

# Check device status
curl -H "X-API-Key: KEY" https://domain.com/api/v1/devices/

# Monitor device logs
ssh pi@device-ip
journalctl -u voice-assistant.service -f
```
