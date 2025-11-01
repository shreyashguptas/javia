# Server Scripts

This directory contains all administrative scripts for managing the voice assistant server and devices.

## Directory Structure

```
scripts/
├── README.md (this file)
├── setup/
│   ├── setup.sh           - Server installation and configuration
│   └── setup.md           - Setup documentation
├── register_device/
│   ├── register_device.sh - Register Pi client devices
│   └── register_device.md - Device registration documentation
└── create_update/
    ├── create_update.sh   - Package and distribute OTA updates
    └── create_update.md   - Update creation documentation
```

## Quick Links

### Server Setup
```bash
cd /opt/javia/scripts/setup
sudo ./setup.sh
```
- Fresh server installation
- Updates to existing installation
- Configuration management

[Read the setup documentation →](./setup/setup.md)

### Device Registration
```bash
cd /opt/javia/scripts/register_device
./register_device.sh <DEVICE_UUID> [device_name] [timezone]
```
- Register new Pi clients
- Enable device authentication
- Grant server access

[Read the device registration documentation →](./register_device/register_device.md)

### Create OTA Updates
```bash
cd /opt/javia/scripts/create_update
./create_update.sh <version> <description> [update_type] [system_packages]
```
- Package Pi client updates
- Distribute to all devices
- Schedule or urgent delivery

[Read the update creation documentation →](./create_update/create_update.md)

## Usage Notes

### Running from Installation Directory

All scripts are designed to be run from within the `/opt/javia/scripts/` directory structure:

```bash
# Correct
cd /opt/javia/scripts/register_device
./register_device.sh 018c...

# Also works with absolute paths
/opt/javia/scripts/register_device/register_device.sh 018c...
```

### Running from Repository (Development)

When developing or testing, run from the repository:

```bash
# Setup script (must be run as root)
cd /tmp/javia/server/scripts/setup
sudo ./setup.sh

# Other scripts work from repository too
cd /tmp/javia/server/scripts/register_device
./register_device.sh 018c...
```

## Prerequisites

All scripts require:
- Server is installed at `/opt/javia/`
- `.env` file is configured at `/opt/javia/.env`
- Supabase is configured (for device/update operations)

## Common Tasks

### Initial Server Setup
```bash
cd /tmp
git clone https://github.com/shreyashguptas/javia.git
cd javia/server/scripts/setup
sudo ./setup.sh
```

### Register a New Pi Client
1. Run Pi client setup to get UUID
2. Register on server:
   ```bash
   cd /opt/javia/scripts/register_device
   ./register_device.sh <UUID> "Device Name" "Timezone"
   ```

### Deploy an Update to All Devices
```bash
cd /opt/javia/scripts/create_update
./create_update.sh v1.2.3 "Bug fixes" scheduled
```

## Troubleshooting

### Script Not Found

Make sure you're in the correct directory:
```bash
pwd
# Should show: /opt/javia/scripts/<script_name>/
```

### Permission Denied

Some scripts require sudo:
```bash
# Setup requires root
sudo ./setup.sh

# Most other scripts don't
./register_device.sh <UUID>
```

### .env Not Found

Scripts expect `.env` at `/opt/javia/.env`:
```bash
ls -la /opt/javia/.env
# If missing, run setup.sh first
```

## Documentation

Each script has detailed documentation in its directory:
- [setup.md](./setup/setup.md) - Complete server setup guide
- [register_device.md](./register_device/register_device.md) - Device registration guide
- [create_update.md](./create_update/create_update.md) - OTA update creation guide

## See Also

- [Getting Started Guide](../../docs/GETTING_STARTED.md)
- [Deployment Guide](../../docs/DEPLOYMENT.md)
- [OTA Updates Documentation](../../docs/OTA_UPDATES.md)
- [API Documentation](../../docs/API.md)

