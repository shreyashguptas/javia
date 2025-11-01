#!/bin/bash
set -e

# Device Registration Script
# Registers a new Pi client device in the database for authentication
#
# Usage:
#   Interactive mode (recommended):
#     ./register_device.sh
#
#   Or with arguments (legacy):
#     ./register_device.sh <DEVICE_UUID> [device_name] [timezone]

echo "==========================================="
echo "Device Registration"
echo "==========================================="
echo ""

# Check if running in the correct directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Check if .env file exists
if [ ! -f "$INSTALL_DIR/.env" ]; then
    echo "❌ ERROR: .env file not found at $INSTALL_DIR/.env"
    echo ""
    echo "Please ensure:"
    echo "  1. You have set up the server (run server setup script first)"
    echo "  2. The .env file exists in the server directory"
    echo ""
    echo "If you haven't set up the server yet, run:"
    echo "  cd $INSTALL_DIR/scripts/setup"
    echo "  sudo ./setup.sh"
    echo ""
    exit 1
fi

cd "$INSTALL_DIR"

# Interactive mode if no arguments provided
if [ -z "$1" ]; then
    echo "==================================="
    echo "Interactive Device Registration"
    echo "==================================="
    echo ""
    
    # Prompt for Device UUID
    echo "Enter the Device UUID from your Pi client:"
    echo "(This is displayed when you run the Pi client setup)"
    echo ""
    read -p "Device UUID: " DEVICE_UUID
    
    # Validate UUID is not empty
    if [ -z "$DEVICE_UUID" ]; then
        echo ""
        echo "❌ ERROR: Device UUID cannot be empty!"
        exit 1
    fi
    
    echo ""
    
    # Prompt for Device Name
    echo "Enter a friendly name for this device:"
    echo "(Examples: \"Kitchen Pi\", \"Living Room Assistant\", \"Bedroom Device\")"
    echo ""
    read -p "Device Name (default: New Device): " DEVICE_NAME
    if [ -z "$DEVICE_NAME" ]; then
        DEVICE_NAME="New Device"
    fi
    
    echo ""
    
    # Prompt for Timezone
    echo "Select the device timezone:"
    echo ""
    
    # Show timezone selector
    TIMEZONE=$(python3 << 'TZEOF'
import sys

timezones = [
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Phoenix",
    "America/Los_Angeles",
    "America/Anchorage",
    "America/Honolulu",
    "America/Toronto",
    "America/Vancouver",
    "America/Edmonton",
    "America/Winnipeg",
    "America/Halifax",
    "America/Mexico_City",
    "America/Monterrey",
    "America/Tijuana",
    "Europe/London",
    "Europe/Paris",
    "Europe/Berlin",
    "Europe/Amsterdam",
    "Europe/Madrid",
    "Asia/Tokyo",
    "Asia/Shanghai",
    "Asia/Singapore",
    "Asia/Dubai",
    "Asia/Kolkata",
    "Australia/Sydney",
    "Australia/Melbourne",
    "Pacific/Auckland",
    "UTC"
]

# Default to UTC
default_index = timezones.index('UTC')

# Write prompts to stderr so they appear, but result goes to stdout
print("Available Timezones:", file=sys.stderr)
for i, tz in enumerate(timezones):
    marker = " → " if i == default_index else "   "
    print(f"{marker}{i+1}. {tz}", file=sys.stderr)

print(f"\nDefault: UTC", file=sys.stderr)

# Read from /dev/tty directly for user input
try:
    with open('/dev/tty', 'r') as tty:
        sys.stderr.write(f"\nEnter number (1-{len(timezones)}), or press Enter for UTC: ")
        sys.stderr.flush()
        choice = tty.readline().strip()
except:
    # Fallback if /dev/tty is not available
    choice = input(f"\nEnter number (1-{len(timezones)}), or press Enter for UTC: ")

if choice.strip():
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(timezones):
            print(timezones[idx])
        else:
            print("UTC")
    except ValueError:
        print("UTC")
else:
    print("UTC")
TZEOF
)
    
    echo ""
    echo "==================================="
    echo "Registration Summary"
    echo "==================================="
    echo ""
    echo "Device UUID:  $DEVICE_UUID"
    echo "Device Name:  $DEVICE_NAME"
    echo "Timezone:     $TIMEZONE"
    echo ""
    read -p "Proceed with registration? (Y/n): " CONFIRM
    
    if [ "$CONFIRM" = "n" ] || [ "$CONFIRM" = "N" ]; then
        echo "Registration cancelled."
        exit 0
    fi
    echo ""
else
    # Legacy command-line arguments mode
    DEVICE_UUID="$1"
    DEVICE_NAME="${2:-New Device}"
    TIMEZONE="${3:-UTC}"
    
    echo "Device UUID:  $DEVICE_UUID"
    echo "Device Name:  $DEVICE_NAME"
    echo "Timezone:     $TIMEZONE"
    echo ""
fi

# Load environment variables from .env file
set -a
source "$INSTALL_DIR/.env"
set +a

# Check if Supabase is configured
if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_SERVICE_KEY" ]; then
    echo "❌ ERROR: Supabase not configured!"
    echo "Please ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set in .env file."
    echo "Location: $INSTALL_DIR/.env"
    exit 1
fi

# Export the device registration variables for Python
export DEVICE_UUID
export DEVICE_NAME
export TIMEZONE

# Use Python to register the device
python3 << 'PYTHON_EOF'
import os
import sys
import re
from datetime import datetime, timezone as tz
from supabase import create_client

# Get environment variables
device_uuid = os.environ.get('DEVICE_UUID', '')
device_name = os.environ.get('DEVICE_NAME', 'New Device')
device_timezone = os.environ.get('TIMEZONE', 'UTC')
supabase_url = os.environ.get('SUPABASE_URL', '')
supabase_key = os.environ.get('SUPABASE_SERVICE_KEY', '')

# Validate UUID format (UUID7 or UUID4 format)
uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
if not re.match(uuid_pattern, device_uuid.lower()):
    print("❌ ERROR: Invalid UUID format!")
    print(f"Received: {device_uuid}")
    print("Expected format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
    sys.exit(1)

print("✓ UUID format validated")

# Initialize Supabase client with service role key (admin access)
try:
    supabase = create_client(supabase_url, supabase_key)
    print("✓ Connected to Supabase")
except Exception as e:
    print(f"❌ ERROR: Failed to connect to Supabase: {e}")
    sys.exit(1)

# Check if device already exists
try:
    result = supabase.table("devices").select("*").eq("device_uuid", device_uuid).execute()
    
    if result.data:
        device = result.data[0]
        print(f"\n⚠️  Device already registered!")
        print(f"   UUID: {device['device_uuid']}")
        print(f"   Name: {device.get('device_name', 'N/A')}")
        print(f"   Status: {device.get('status', 'N/A')}")
        print(f"   Registered: {device.get('registered_at', 'N/A')}")
        print(f"   Last Seen: {device.get('last_seen', 'N/A')}")
        print("")
        print("To update this device, use the device management endpoints or modify the database directly.")
        sys.exit(0)
    
    print("✓ Device UUID is unique")
except Exception as e:
    print(f"❌ ERROR: Failed to check for existing device: {e}")
    sys.exit(1)

# Register the device
try:
    insert_data = {
        "device_uuid": device_uuid,
        "device_name": device_name,
        "timezone": device_timezone,
        "status": "online",
        "current_version": "v0.0.0",
        "metadata": {}
    }
    
    result = supabase.table("devices").insert(insert_data).execute()
    
    if result.data:
        device = result.data[0]
        print("\n✅ Device registered successfully!")
        print("")
        print("Device Details:")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"  UUID:         {device['device_uuid']}")
        print(f"  Name:         {device.get('device_name', 'N/A')}")
        print(f"  Timezone:     {device.get('timezone', 'UTC')}")
        print(f"  Status:       {device.get('status', 'online')}")
        print(f"  Registered:   {device.get('registered_at', 'just now')}")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("")
        print("The Pi client can now connect and make requests to the server.")
        print("")
    else:
        print("❌ ERROR: Failed to register device (no data returned)")
        sys.exit(1)
        
except Exception as e:
    print(f"❌ ERROR: Failed to register device: {e}")
    import traceback
    print(traceback.format_exc())
    sys.exit(1)

PYTHON_EOF

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo "==========================================="
    echo "Registration Complete!"
    echo "==========================================="
    echo ""
else
    echo ""
    echo "==========================================="
    echo "Registration Failed"
    echo "==========================================="
    echo ""
    exit $exit_code
fi

