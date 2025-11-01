#!/bin/bash
set -e

# Device Registration Script
# Registers a new Pi client device in the database for authentication
#
# Usage:
#   ./register_device.sh <DEVICE_UUID> [device_name] [timezone]
#
# Example:
#   ./register_device.sh 018c8f5e-8c3a-7890-a1b2-3c4d5e6f7890 "Kitchen Pi" "America/Los_Angeles"

echo "==========================================="
echo "Device Registration"
echo "==========================================="
echo ""

# Check if running in the correct directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Check if .env file exists
if [ ! -f "$INSTALL_DIR/.env" ]; then
    echo "❌ ERROR: .env file not found!"
    echo "Please ensure you're running this script from the server installation directory."
    echo "Expected .env location: $INSTALL_DIR/.env"
    exit 1
fi

cd "$INSTALL_DIR"

# Validate arguments
if [ -z "$1" ]; then
    echo "❌ ERROR: Device UUID is required!"
    echo ""
    echo "Usage:"
    echo "  ./register_device.sh <DEVICE_UUID> [device_name] [timezone]"
    echo ""
    echo "Example:"
    echo "  ./register_device.sh 018c8f5e-8c3a-7890-a1b2-3c4d5e6f7890 \"Kitchen Pi\" \"America/Los_Angeles\""
    echo ""
    exit 1
fi

DEVICE_UUID="$1"
DEVICE_NAME="${2:-New Device}"
TIMEZONE="${3:-UTC}"

echo "Device UUID:  $DEVICE_UUID"
echo "Device Name:  $DEVICE_NAME"
echo "Timezone:     $TIMEZONE"
echo ""

# Source environment variables
source .env

# Check if Supabase is configured
if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_SERVICE_KEY" ]; then
    echo "❌ ERROR: Supabase not configured!"
    echo "Please ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set in .env file."
    exit 1
fi

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

