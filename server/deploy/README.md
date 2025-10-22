# Server Deployment Scripts

## Initial Deployment

Use `deploy.sh` for first-time installation:

```bash
# On your server (Debian VM)
cd /tmp
git clone https://github.com/shreyashguptas/javia.git
cd javia/server/deploy
sudo bash deploy.sh
```

This will:
- Install system dependencies
- Create service user
- Set up Python virtual environment
- Configure .env file (prompts for API keys)
- Install systemd service
- Configure nginx
- Install Cloudflare tunnel

## Updating the Server

After you've pushed code changes to GitHub, use `update.sh`:

```bash
# SSH to your server
ssh your-username@your-server-ip

# Run the update script
sudo bash /opt/javia/deploy/update.sh
```

**Or**, if you first need to get the update script itself (if it didn't exist before):

```bash
# Get the latest update script
cd /tmp
git clone https://github.com/shreyashguptas/javia.git javia_temp
sudo cp javia_temp/server/deploy/update.sh /opt/javia/deploy/
sudo chmod +x /opt/javia/deploy/update.sh
rm -rf javia_temp

# Now run it
sudo /opt/javia/deploy/update.sh
```

### What the Update Script Does

1. ✅ Backs up your `.env` file (preserves API keys)
2. ✅ Fetches latest code from GitHub
3. ✅ Stops the service
4. ✅ Updates all application files
5. ✅ Restores your `.env` file
6. ✅ Updates Python dependencies (if requirements.txt changed)
7. ✅ Restarts the service
8. ✅ Shows service status and recent logs

### Important Notes

- **Your `.env` file is preserved** - API keys and configuration won't be lost
- **Virtual environment is preserved** - Only dependencies are updated
- **Service is automatically restarted** - No manual intervention needed
- **Zero downtime** is not guaranteed - there will be a brief service interruption during update

## Troubleshooting

### View Logs
```bash
# Live logs
journalctl -u voice-assistant-server.service -f

# Last 50 lines
journalctl -u voice-assistant-server.service -n 50
```

### Check Service Status
```bash
systemctl status voice-assistant-server.service
```

### Restart Service Manually
```bash
sudo systemctl restart voice-assistant-server.service
```

### Check if Service is Running
```bash
curl http://localhost:8000/health
# Should return: {"status":"healthy","version":"1.0.0"}
```

### Roll Back to Previous Version

If the update breaks something:

```bash
# Stop the service
sudo systemctl stop voice-assistant-server.service

# Clone a specific previous commit
cd /tmp
git clone https://github.com/shreyashguptas/javia.git javia_rollback
cd javia_rollback
git checkout <PREVIOUS_COMMIT_HASH>

# Copy files
cd server
sudo rsync -av --exclude='venv' --exclude='.env' --exclude='__pycache__' ./ /opt/javia/

# Restart
sudo systemctl start voice-assistant-server.service
```

## Files

- `deploy.sh` - Initial deployment script
- `update.sh` - Update script for code changes
- `systemd/voice-assistant-server.service` - Systemd service file
- `nginx/voice-assistant.conf` - Nginx configuration (optional, deploy.sh creates inline)

