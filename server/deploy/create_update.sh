#!/bin/bash
set -e

# Script to package Pi client code and create OTA update
# Usage: ./create_update.sh <version> <description> [update_type] [system_packages]
# Example: ./create_update.sh v1.2.3 "Bug fixes and improvements" scheduled
# Example: ./create_update.sh v1.2.4 "Security patch" urgent "libopus0,python3-pyaudio"

echo "==========================================="
echo "Voice Assistant - Create OTA Update"
echo "==========================================="
echo ""

# Check arguments
if [ $# -lt 2 ]; then
    echo "Usage: $0 <version> <description> [update_type] [system_packages]"
    echo ""
    echo "Arguments:"
    echo "  version          - Version string (e.g., v1.2.3)"
    echo "  description      - Update description"
    echo "  update_type      - Update type: 'scheduled' or 'urgent' (default: scheduled)"
    echo "  system_packages  - Comma-separated list of apt packages (optional)"
    echo ""
    echo "Examples:"
    echo "  $0 v1.2.3 \"Bug fixes and improvements\" scheduled"
    echo "  $0 v1.2.4 \"Security patch\" urgent \"libopus0,python3-pyaudio\""
    exit 1
fi

VERSION="$1"
DESCRIPTION="$2"
UPDATE_TYPE="${3:-scheduled}"
SYSTEM_PACKAGES="${4:-}"

# Validate update type
if [ "$UPDATE_TYPE" != "scheduled" ] && [ "$UPDATE_TYPE" != "urgent" ]; then
    echo "❌ Error: update_type must be 'scheduled' or 'urgent'"
    exit 1
fi

# Determine project root (2 levels up from this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PI_CLIENT_DIR="$PROJECT_ROOT/pi_client"

echo "[INFO] Project root: $PROJECT_ROOT"
echo "[INFO] Pi client directory: $PI_CLIENT_DIR"
echo ""

# Validate Pi client directory exists
if [ ! -d "$PI_CLIENT_DIR" ]; then
    echo "❌ Error: Pi client directory not found at $PI_CLIENT_DIR"
    exit 1
fi

# Create temporary working directory
TEMP_DIR=$(mktemp -d)
echo "[1/6] Created temporary directory: $TEMP_DIR"

# Create package structure
PACKAGE_DIR="$TEMP_DIR/pi_client"
mkdir -p "$PACKAGE_DIR"

# Copy Pi client files
echo "[2/6] Copying Pi client files..."
cp "$PI_CLIENT_DIR"/*.py "$PACKAGE_DIR/" 2>/dev/null || true
cp "$PI_CLIENT_DIR/requirements.txt" "$PACKAGE_DIR/" 2>/dev/null || true
cp "$PI_CLIENT_DIR/env.example" "$PACKAGE_DIR/" 2>/dev/null || true

# Update VERSION file
echo "$VERSION" > "$PACKAGE_DIR/VERSION"
echo "    ✓ Set version to: $VERSION"

# Create update metadata
echo "[3/6] Creating update metadata..."
METADATA_FILE="$TEMP_DIR/update_metadata.json"

# Build system packages JSON array
if [ -n "$SYSTEM_PACKAGES" ]; then
    # Convert comma-separated string to JSON array
    SYSTEM_PACKAGES_JSON=$(echo "$SYSTEM_PACKAGES" | python3 -c "import sys, json; print(json.dumps(sys.stdin.read().strip().split(',')))")
    REQUIRES_SYSTEM_PACKAGES="true"
else
    SYSTEM_PACKAGES_JSON="[]"
    REQUIRES_SYSTEM_PACKAGES="false"
fi

cat > "$METADATA_FILE" <<EOF
{
  "version": "$VERSION",
  "description": "$DESCRIPTION",
  "update_type": "$UPDATE_TYPE",
  "requires_system_packages": $REQUIRES_SYSTEM_PACKAGES,
  "system_packages": $SYSTEM_PACKAGES_JSON,
  "created_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF

echo "    ✓ Metadata file created"

# Copy metadata to package
cp "$METADATA_FILE" "$TEMP_DIR/update_metadata.json"

# Create ZIP package
echo "[4/6] Creating ZIP package..."
PACKAGE_FILE="$TEMP_DIR/update_${VERSION}.zip"

cd "$TEMP_DIR"
zip -r "$PACKAGE_FILE" pi_client/ update_metadata.json > /dev/null
cd - > /dev/null

PACKAGE_SIZE=$(ls -lh "$PACKAGE_FILE" | awk '{print $5}')
echo "    ✓ Package created: $PACKAGE_FILE ($PACKAGE_SIZE)"

# Load server configuration
echo "[5/6] Loading server configuration..."
SERVER_ENV_FILE="$PROJECT_ROOT/server/.env"

if [ ! -f "$SERVER_ENV_FILE" ]; then
    echo "❌ Error: Server .env file not found at $SERVER_ENV_FILE"
    echo "Please ensure the server is configured."
    exit 1
fi

# Source environment variables (safely)
set -a
source "$SERVER_ENV_FILE"
set +a

# Determine server URL
if [ -z "$SERVER_URL" ]; then
    # Try to construct from host and port
    HOST="${HOST:-0.0.0.0}"
    PORT="${PORT:-8000}"
    
    if [ "$HOST" = "0.0.0.0" ] || [ "$HOST" = "localhost" ]; then
        SERVER_URL="http://localhost:$PORT"
    else
        SERVER_URL="http://$HOST:$PORT"
    fi
fi

echo "    ✓ Server URL: $SERVER_URL"

# Check for API key
if [ -z "$SERVER_API_KEY" ]; then
    echo "❌ Error: SERVER_API_KEY not found in .env file"
    exit 1
fi

# Upload to server and create update
echo "[6/6] Uploading to server and creating update..."
echo ""

# Call server API
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$SERVER_URL/api/v1/updates/create" \
    -H "X-API-Key: $SERVER_API_KEY" \
    -F "version=$VERSION" \
    -F "description=$DESCRIPTION" \
    -F "update_type=$UPDATE_TYPE" \
    -F "requires_system_packages=$REQUIRES_SYSTEM_PACKAGES" \
    -F "system_packages=$SYSTEM_PACKAGES_JSON" \
    -F "package=@$PACKAGE_FILE")

# Extract HTTP status code
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
RESPONSE_BODY=$(echo "$RESPONSE" | sed '$d')

# Check response
if [ "$HTTP_CODE" = "201" ] || [ "$HTTP_CODE" = "200" ]; then
    echo "✅ Update created successfully!"
    echo ""
    echo "Update Details:"
    echo "  Version:        $VERSION"
    echo "  Description:    $DESCRIPTION"
    echo "  Type:           $UPDATE_TYPE"
    echo "  System Packages: $SYSTEM_PACKAGES_JSON"
    echo ""
    echo "Server Response:"
    echo "$RESPONSE_BODY" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE_BODY"
    echo ""
    echo "==========================================="
    echo "Update Distribution Summary"
    echo "==========================================="
    if [ "$UPDATE_TYPE" = "urgent" ]; then
        echo "Update type: URGENT"
        echo "Devices will update after 1 hour of inactivity"
    else
        echo "Update type: SCHEDULED"
        echo "Devices will update at 2 AM local time"
    fi
    echo ""
    echo "All registered devices will receive this update."
    echo "Check device status: $SERVER_URL/api/v1/devices/"
    echo ""
else
    echo "❌ Failed to create update (HTTP $HTTP_CODE)"
    echo ""
    echo "Error Response:"
    echo "$RESPONSE_BODY"
    echo ""
    exit 1
fi

# Clean up
rm -rf "$TEMP_DIR"
echo "✓ Cleaned up temporary files"
echo ""
echo "==========================================="
echo "Update creation complete!"
echo "==========================================="

