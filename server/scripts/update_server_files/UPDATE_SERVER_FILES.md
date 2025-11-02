# Update Server Files

Quick reference guide for updating server code and scripts without full reconfiguration.

## Overview

The `update_server_files.sh` script provides a fast way to update server code on a deployed system without going through the full setup process. This is useful when you've made code changes or updated scripts and just need to deploy them.

## What It Does

1. ✅ Updates all server code from repository
2. ✅ Preserves your `.env` configuration
3. ✅ Preserves your Python virtual environment
4. ✅ Updates Python dependencies
5. ✅ Restarts the service
6. ✅ Verifies service health

## What It Doesn't Do

- ❌ Doesn't reconfigure environment variables
- ❌ Doesn't reinstall system packages
- ❌ Doesn't setup nginx or systemd (already configured)
- ❌ Doesn't setup Cloudflare tunnel

## When to Use

Use `update_server_files.sh` when:
- You've updated Python code (models, routers, services, etc.)
- You've modified scripts (create_update.sh, register_device.sh, etc.)
- You've changed API endpoints
- You need to deploy bug fixes or features

Use full `setup.sh` when:
- First time installation
- Need to change environment variables
- Need to install system packages
- Need to reconfigure nginx or systemd
- Major system changes required

## Prerequisites

- Server must already be set up (via `setup.sh`)
- You must have a cloned repository with your changes
- Must run as root or with sudo

## Usage

### Step 1: Update Your Code Locally

```bash
# On your development machine
cd /path/to/voice_assistant
# Make your changes...
git add .
git commit -m "Your changes"
git push origin main
```

### Step 2: Clone and Update on Server

```bash
# SSH to your server
ssh your-server

# Clone fresh copy to temp directory
cd /tmp
rm -rf javia  # Remove old temp clone if exists
git clone https://github.com/shreyashguptas/javia.git

# Run the update script
cd javia/server/scripts/update_server_files
sudo ./update_server_files.sh
```

That's it! Your server is now running with the updated code.

## What Files Get Updated

The script updates everything in `/opt/javia/` except:
- `.env` (preserved)
- `venv/` (preserved, dependencies updated)

This includes:
- `main.py`
- `config.py`
- All Python modules (models, routers, services, middleware, utils)
- All scripts (create_update, register_device, setup)
- Configuration files
- `requirements.txt`
- Documentation

## Verification

After running the script, it automatically:

1. **Checks service status**
   ```
   ✅ Service restarted successfully!
   ```

2. **Tests health endpoint**
   ```
   ✅ Health check passed: {"status":"healthy","version":"1.0.0"}
   ```

If either check fails, the script displays recent logs.

## Manual Verification (Optional)

```bash
# Check service status
systemctl status voice-assistant-server.service

# View live logs
journalctl -u voice-assistant-server.service -f

# Test health endpoint
curl http://localhost:8000/health
curl http://localhost:80/health  # Through nginx

# If you have cloudflare tunnel
curl https://yourdomain.com/health
```

## Common Scenarios

### Scenario 1: Updated a Script (e.g., create_update.sh)

```bash
# On server
cd /tmp
rm -rf javia
git clone https://github.com/shreyashguptas/javia.git
cd javia/server/scripts
sudo ./update_server_files.sh

# Now use the updated script
cd /opt/javia/scripts/create_update
./create_update.sh
```

### Scenario 2: Fixed a Bug in Service Code

```bash
# After pushing your fix to GitHub
cd /tmp
rm -rf javia
git clone https://github.com/shreyashguptas/javia.git
cd javia/server/scripts
sudo ./update_server_files.sh

# Verify fix
journalctl -u voice-assistant-server.service -f
```

### Scenario 3: Added New API Endpoint

```bash
# After committing new endpoint
cd /tmp
rm -rf javia
git clone https://github.com/shreyashguptas/javia.git
cd javia/server/scripts
sudo ./update_server_files.sh

# Test new endpoint
curl -H "X-API-Key: YOUR_KEY" http://localhost:8000/api/v1/your-new-endpoint
```

### Scenario 4: Updated Python Dependencies

```bash
# After updating requirements.txt
cd /tmp
rm -rf javia
git clone https://github.com/shreyashguptas/javia.git
cd javia/server/scripts
sudo ./update_server_files.sh
# Script automatically installs new dependencies
```

## Workflow Comparison

### Full Setup (Initial Install or Major Changes)

```bash
cd /tmp
git clone https://github.com/shreyashguptas/javia.git
cd javia/server/scripts/setup
sudo ./setup.sh
# Interactive prompts for configuration...
# Takes ~5-10 minutes
```

### Quick Update (Code Changes)

```bash
cd /tmp
rm -rf javia
git clone https://github.com/shreyashguptas/javia.git
cd javia/server/scripts
sudo ./update_server_files.sh
# No prompts, takes ~30 seconds
```

## Troubleshooting

### "Production installation not found"

You haven't run the full setup yet. Run this first:

```bash
cd /tmp/javia/server/scripts/setup
sudo ./setup.sh
```

### "Cannot find main.py"

You're not running from the correct directory. The script must be run from a cloned repository:

```bash
cd /tmp
git clone https://github.com/shreyashguptas/javia.git
cd javia/server/scripts
sudo ./update_server_files.sh
```

### "Service failed to start"

The script will show recent logs. Common issues:

1. **Syntax error in code**
   ```bash
   # Check for Python syntax errors
   cd /opt/javia
   source venv/bin/activate
   python3 -m py_compile main.py
   ```

2. **Missing dependency**
   ```bash
   # Reinstall dependencies
   cd /opt/javia
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configuration issue**
   ```bash
   # Check .env file
   sudo nano /opt/javia/.env
   # Verify all required variables are set
   ```

4. **View detailed logs**
   ```bash
   journalctl -u voice-assistant-server.service -n 100 --no-pager
   ```

### Service Starts But Health Check Fails

Wait a few seconds and try again:

```bash
sleep 5
curl http://localhost:8000/health
```

If still failing, check logs:

```bash
journalctl -u voice-assistant-server.service -f
```

## Best Practices

1. **Always test locally first**
   - Test changes on your development machine
   - Run linters and tests before committing

2. **Use version control**
   - Commit changes before deploying
   - Use meaningful commit messages
   - Tag releases for important updates

3. **Deploy during low traffic**
   - Service restarts briefly during update
   - Plan updates during off-peak hours if possible

4. **Monitor after deployment**
   ```bash
   journalctl -u voice-assistant-server.service -f
   ```
   - Watch for errors or warnings
   - Test critical endpoints
   - Verify device connections

5. **Keep a rollback plan**
   - Know the last working commit
   - Can quickly deploy previous version if needed:
     ```bash
     cd /tmp/javia
     git checkout <previous-commit>
     cd server/scripts
     sudo ./update_server_files.sh
     ```

## Integration with Workflow

### Development Cycle

```
1. Local Development
   ├─ Make changes
   ├─ Test locally
   └─ Commit & push

2. Deploy to Server
   ├─ SSH to server
   ├─ Clone latest
   └─ Run update_server_files.sh

3. Verify Deployment
   ├─ Check service status
   ├─ Test endpoints
   └─ Monitor logs

4. Update Pi Clients (if needed)
   └─ Run create_update.sh
```

### File Location Reference

```
Repository (GitHub):
  └─ voice_assistant/
     └─ server/
        └─ scripts/
           ├─ update_server_files.sh  ← Run this

Temp Clone (Server):
  └─ /tmp/javia/
     └─ server/
        └─ scripts/
           └─ update_server_files.sh  ← From here

Production (Server):
  └─ /opt/javia/  ← Updates here
     ├─ .env (preserved)
     ├─ venv/ (preserved)
     └─ All other files (updated)
```

## Script Output Example

```
===========================================
Voice Assistant - Update Server Files
===========================================

✓ Found server files at: /tmp/javia/server

📦 Updating files from repository to production...

[1/4] Stopping service...
✓ Service stopped

[2/4] Backing up configuration...
✓ Backed up .env file

[3/4] Updating files...
Copying from: /tmp/javia/server
Copying to:   /opt/javia

sending incremental file list
main.py
routers/devices.py
services/groq_service.py
scripts/create_update/create_update.sh

✓ Restored .env file
✓ Files updated

[4/4] Updating Python dependencies...
✓ Dependencies updated

Restarting service...
✅ Service restarted successfully!

✅ Health check passed: {"status":"healthy","version":"1.0.0"}

===========================================
Update Complete!
===========================================

Updated files in: /opt/javia

View logs:
  journalctl -u voice-assistant-server.service -f
```

## See Also

- [Server Setup](../server/scripts/setup/setup.md) - Full setup guide
- [Create OTA Update](../server/scripts/create_update/create_update.md) - Deploy to Pi clients
- [Deployment Guide](DEPLOYMENT.md) - Complete deployment process
- [Architecture](ARCHITECTURE.md) - System architecture overview

## Quick Reference

```bash
# Clone and update in one go
cd /tmp && rm -rf javia && \
git clone https://github.com/shreyashguptas/javia.git && \
cd javia/server/scripts && \
sudo ./update_server_files.sh

# Then use updated scripts
cd /opt/javia/scripts/create_update
./create_update.sh
```

Remember: This script only updates code. For environment changes, run the full `setup.sh`.

