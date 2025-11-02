#!/bin/bash
set -e

# Script to package Pi client code and create OTA update
# Usage: ./create_update.sh [version] [description] [system_packages]
# Or run without arguments for interactive mode

echo "==========================================="
echo "Voice Assistant - Create OTA Update"
echo "==========================================="
echo ""

# Determine project root and locate pi_client
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if we're in development structure (has 'server' directory)
if [ -d "$SCRIPT_DIR/../../server" ]; then
    # Development structure: create_update -> scripts -> server -> project_root
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
    SERVER_DIR="$PROJECT_ROOT/server"
else
    # Production structure: create_update -> scripts -> javia
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
    SERVER_DIR="$PROJECT_ROOT"
fi

PI_CLIENT_DIR="$PROJECT_ROOT/pi_client"
USE_TEMP_CLONE=false

echo "[INFO] Project root: $PROJECT_ROOT"

# Check if pi_client exists locally
if [ -d "$PI_CLIENT_DIR" ]; then
    echo "[INFO] Using local pi_client directory: $PI_CLIENT_DIR"
else
    echo "[INFO] Pi client not found locally, will fetch from git repository"
    USE_TEMP_CLONE=true
fi
echo ""

# Check if virtual environment exists
VENV_PYTHON="$SERVER_DIR/venv/bin/python3"
if [ ! -f "$VENV_PYTHON" ]; then
    # Try installed location
    VENV_PYTHON="/opt/javia/venv/bin/python3"
    if [ ! -f "$VENV_PYTHON" ]; then
        echo "⚠️  Warning: Python virtual environment not found!"
        echo "Using system Python instead (may not have required packages)"
        VENV_PYTHON="python3"
    fi
fi

# Interactive mode if no arguments provided
if [ -z "$1" ]; then
    echo "==================================="
    echo "Interactive Update Creation"
    echo "==================================="
    echo ""
    
    # =================================
    # 0. GIT REPOSITORY (if needed)
    # =================================
    if [ "$USE_TEMP_CLONE" = true ]; then
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "Step 1: Git Repository Configuration"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        echo "Pi client code not found locally. Will fetch from Git repository."
        echo ""
        
        # Git repository URL
        echo "Enter the Git repository URL:"
        echo "Examples:"
        echo "  • https://github.com/username/voice_assistant.git"
        echo "  • git@github.com:username/voice_assistant.git"
        echo ""
        read -p "Repository URL: " GIT_REPO_URL
        
        if [ -z "$GIT_REPO_URL" ]; then
            echo "❌ Error: Repository URL is required"
            exit 1
        fi
        
        echo ""
        
        # Git branch/tag
        echo "Enter the branch, tag, or commit to package:"
        echo "Examples:"
        echo "  • main (default branch)"
        echo "  • v1.2.3 (specific tag)"
        echo "  • develop (development branch)"
        echo ""
        read -p "Branch/Tag/Commit (default: main): " GIT_REF
        
        if [ -z "$GIT_REF" ]; then
            GIT_REF="main"
        fi
        
        echo ""
        echo "✓ Will clone: $GIT_REPO_URL"
        echo "✓ Will use ref: $GIT_REF"
        echo ""
    fi
    
    # =================================
    # 1. VERSION INPUT
    # =================================
    STEP_NUM=2
    if [ "$USE_TEMP_CLONE" = true ]; then
        STEP_NUM=2
    else
        STEP_NUM=1
    fi
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Step $STEP_NUM: Version Number"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Enter the version number for this update."
    echo "Format: vX.Y.Z (e.g., v1.2.3)"
    echo ""
    echo "Version Guidelines:"
    echo "  • Major (X): Breaking changes or major features"
    echo "  • Minor (Y): New features, backward compatible"
    echo "  • Patch (Z): Bug fixes and small improvements"
    echo ""
    
    # Get current version from Pi client if available
    if [ -f "$PI_CLIENT_DIR/VERSION" ]; then
        CURRENT_VERSION=$(cat "$PI_CLIENT_DIR/VERSION")
        echo "Current version: $CURRENT_VERSION"
        echo ""
    fi
    
    while true; do
        read -p "Version (e.g., v1.2.3): " VERSION
        
        # Validate version format
        if [[ "$VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
            break
        else
            echo "❌ Invalid format. Please use vX.Y.Z format (e.g., v1.2.3)"
            echo ""
        fi
    done
    
    echo ""
    
    # =================================
    # 2. DESCRIPTION INPUT
    # =================================
    ((STEP_NUM++))
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Step $STEP_NUM: Update Description"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Enter a clear description of what this update includes."
    echo ""
    echo "Examples:"
    echo "  • \"Bug fixes and performance improvements\""
    echo "  • \"Critical security patch for audio processing\""
    echo "  • \"Added support for new voice commands\""
    echo "  • \"Fixed memory leak in audio buffer\""
    echo ""
    
    while true; do
        read -p "Description: " DESCRIPTION
        
        if [ -n "$DESCRIPTION" ]; then
            break
        else
            echo "❌ Description cannot be empty. Please provide a description."
            echo ""
        fi
    done
    
    echo ""
    
    # Update type is no longer needed - all updates are immediate
    UPDATE_TYPE=""
    
    # =================================
    # 3. SYSTEM PACKAGES
    # =================================
    ((STEP_NUM++))
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Step $STEP_NUM: System Packages (Optional)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Does this update require any system packages (apt packages)?"
    echo ""
    echo "Common packages:"
    echo "  • libopus0, libopus-dev - Audio codec support"
    echo "  • python3-pyaudio - Audio I/O"
    echo "  • python3-numpy - Numerical processing"
    echo "  • libatlas-base-dev - Linear algebra"
    echo ""
    echo "Enter comma-separated package names, or press Enter to skip."
    echo "Example: libopus0,python3-pyaudio"
    echo ""
    read -p "System packages (optional): " SYSTEM_PACKAGES
    
    echo ""
    
    # =================================
    # 5. CONFIRMATION SUMMARY
    # =================================
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Update Summary"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Version:           $VERSION"
    echo "Description:       $DESCRIPTION"
    if [ -n "$SYSTEM_PACKAGES" ]; then
        echo "System Packages:   $SYSTEM_PACKAGES"
    else
        echo "System Packages:   None"
    fi
    echo ""
    
    echo "⚡ IMMEDIATE UPDATE"
    echo "All registered devices will receive this update immediately."
    echo "Devices will check for updates before processing each query."
    echo ""
    
    read -p "Proceed with creating this update? (Y/n): " CONFIRM
    
    if [ "$CONFIRM" = "n" ] || [ "$CONFIRM" = "N" ]; then
        echo ""
        echo "Update creation cancelled."
        exit 0
    fi
    echo ""
    
else
    # Command-line arguments mode (legacy)
    VERSION="$1"
    DESCRIPTION="$2"
    SYSTEM_PACKAGES="${3:-}"
    UPDATE_TYPE=""  # No longer used
    
    # Validate version format
    if [[ ! "$VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo "❌ Error: Invalid version format. Use vX.Y.Z (e.g., v1.2.3)"
        exit 1
    fi
    
    echo "Creating update with provided arguments..."
    echo "  Version: $VERSION"
    echo "  Description: $DESCRIPTION"
    if [ -n "$SYSTEM_PACKAGES" ]; then
        echo "  System Packages: $SYSTEM_PACKAGES"
    fi
    echo ""
fi

# =================================
# PACKAGE CREATION
# =================================
echo "==========================================="
echo "Creating Update Package"
echo "==========================================="
echo ""

# Create temporary working directory
TEMP_DIR=$(mktemp -d)
echo "[1/7] Created temporary directory: $TEMP_DIR"

# =================================
# FETCH PI CLIENT CODE (if needed)
# =================================
if [ "$USE_TEMP_CLONE" = true ]; then
    echo "[2/7] Fetching pi_client code from git..."
    
    # Clone the repository
    GIT_CLONE_DIR="$TEMP_DIR/repo_clone"
    echo "    • Cloning repository: $GIT_REPO_URL"
    echo "    • Branch/Tag/Commit: $GIT_REF"
    
    if git clone --depth 1 --branch "$GIT_REF" "$GIT_REPO_URL" "$GIT_CLONE_DIR" > /dev/null 2>&1; then
        echo "    ✓ Repository cloned successfully"
        PI_CLIENT_DIR="$GIT_CLONE_DIR/pi_client"
        
        # Verify pi_client directory exists in cloned repo
        if [ ! -d "$PI_CLIENT_DIR" ]; then
            echo "    ❌ Error: pi_client directory not found in repository"
            echo "    Expected: $PI_CLIENT_DIR"
            rm -rf "$TEMP_DIR"
            exit 1
        fi
    else
        echo "    ❌ Error: Failed to clone repository"
        echo ""
        echo "Possible causes:"
        echo "  • Invalid repository URL"
        echo "  • Branch/tag '$GIT_REF' doesn't exist"
        echo "  • Network connection issues"
        echo "  • Git authentication required (use SSH key or token)"
        echo ""
        rm -rf "$TEMP_DIR"
        exit 1
    fi
    echo ""
fi

# Create package structure
PACKAGE_DIR="$TEMP_DIR/pi_client"
mkdir -p "$PACKAGE_DIR"

# Copy Pi client files
if [ "$USE_TEMP_CLONE" = true ]; then
    echo "[3/7] Packaging pi_client files..."
else
    echo "[2/7] Packaging pi_client files..."
fi

# Copy all Python files
cp "$PI_CLIENT_DIR"/*.py "$PACKAGE_DIR/" 2>/dev/null || true

# Copy configuration files
cp "$PI_CLIENT_DIR/requirements.txt" "$PACKAGE_DIR/" 2>/dev/null || true
cp "$PI_CLIENT_DIR/env.example" "$PACKAGE_DIR/" 2>/dev/null || true

# Copy subdirectories (audio, hardware, network, utils, etc.)
for subdir in audio hardware network utils; do
    if [ -d "$PI_CLIENT_DIR/$subdir" ]; then
        cp -r "$PI_CLIENT_DIR/$subdir" "$PACKAGE_DIR/"
    fi
done

echo "    ✓ Copied pi_client files"

# Update VERSION file
echo "$VERSION" > "$PACKAGE_DIR/VERSION"
echo "    ✓ Set version to: $VERSION"

# Create update metadata
if [ "$USE_TEMP_CLONE" = true ]; then
    echo "[4/7] Creating update metadata..."
else
    echo "[3/7] Creating update metadata..."
fi
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
  "requires_system_packages": $REQUIRES_SYSTEM_PACKAGES,
  "system_packages": $SYSTEM_PACKAGES_JSON,
  "created_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF

echo "    ✓ Metadata file created"

# Create ZIP package
if [ "$USE_TEMP_CLONE" = true ]; then
    echo "[5/7] Creating ZIP package..."
else
    echo "[4/7] Creating ZIP package..."
fi
PACKAGE_FILE="$TEMP_DIR/update_${VERSION}.zip"

cd "$TEMP_DIR"
zip -r "$PACKAGE_FILE" pi_client/ update_metadata.json > /dev/null
cd - > /dev/null

PACKAGE_SIZE=$(ls -lh "$PACKAGE_FILE" | awk '{print $5}')
echo "    ✓ Package created: $PACKAGE_FILE ($PACKAGE_SIZE)"

# =================================
# SERVER CONFIGURATION
# =================================
if [ "$USE_TEMP_CLONE" = true ]; then
    echo "[6/7] Loading server configuration..."
else
    echo "[5/7] Loading server configuration..."
fi

# Try multiple locations for .env file
SERVER_ENV_FILE=""
if [ -f "$SERVER_DIR/.env" ]; then
    SERVER_ENV_FILE="$SERVER_DIR/.env"
elif [ -f "/opt/javia/.env" ]; then
    SERVER_ENV_FILE="/opt/javia/.env"
else
    echo "❌ Error: Server .env file not found"
    echo "Searched locations:"
    echo "  - $SERVER_DIR/.env"
    echo "  - /opt/javia/.env"
    echo ""
    echo "Please ensure the server is configured."
    exit 1
fi

echo "    ✓ Found .env at: $SERVER_ENV_FILE"

# Load environment variables using Python (safer than sourcing)
LOADED_VARS=$(python3 << EOF
import os
import sys

env_file = '$SERVER_ENV_FILE'
server_url = None
server_api_key = None
host = 'localhost'
port = '8000'

try:
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()
            # Remove inline comments
            if '#' in value and not (value.startswith('"') or value.startswith("'")):
                value = value.split('#')[0].strip()
            # Remove quotes
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            
            if key == 'SERVER_URL':
                server_url = value
            elif key == 'SERVER_API_KEY':
                server_api_key = value
            elif key == 'HOST':
                host = value
            elif key == 'PORT':
                port = value
    
    # Construct server URL if not explicitly set
    if not server_url or server_url == 'http://localhost:8000':
        if host == '0.0.0.0' or host == 'localhost':
            server_url = f'http://localhost:{port}'
        else:
            server_url = f'http://{host}:{port}'
    
    if not server_api_key:
        print("ERROR:SERVER_API_KEY not found", file=sys.stderr)
        sys.exit(1)
    
    print(f"SERVER_URL={server_url}")
    print(f"SERVER_API_KEY={server_api_key}")
    
except Exception as e:
    print(f"ERROR:Failed to load .env: {e}", file=sys.stderr)
    sys.exit(1)
EOF
)

if [ $? -ne 0 ]; then
    echo "❌ Error: Failed to load server configuration"
    exit 1
fi

# Parse the output
export SERVER_URL=$(echo "$LOADED_VARS" | grep "^SERVER_URL=" | cut -d'=' -f2-)
export SERVER_API_KEY=$(echo "$LOADED_VARS" | grep "^SERVER_API_KEY=" | cut -d'=' -f2-)

echo "    ✓ Server URL: $SERVER_URL"
echo ""

# =================================
# UPLOAD TO SERVER
# =================================
if [ "$USE_TEMP_CLONE" = true ]; then
    echo "[7/7] Uploading to server and creating update..."
else
    echo "[6/7] Uploading to server and creating update..."
fi
echo ""

# Call server API
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$SERVER_URL/api/v1/updates/create" \
    -H "X-API-Key: $SERVER_API_KEY" \
    -F "version=$VERSION" \
    -F "description=$DESCRIPTION" \
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
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Update Details"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "  Version:         $VERSION"
    echo "  Description:     $DESCRIPTION"
    if [ -n "$SYSTEM_PACKAGES" ]; then
        echo "  System Packages: $SYSTEM_PACKAGES"
    fi
    echo "  Package Size:    $PACKAGE_SIZE"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Distribution"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "  ⚡ IMMEDIATE UPDATE"
    echo "  ├─ All registered devices will receive this update"
    echo "  ├─ Devices check for updates before processing each query"
    echo "  ├─ Update installs immediately when detected"
    echo "  └─ Device restarts automatically after successful update"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Pretty print server response if possible
    echo "Server Response:"
    echo "$RESPONSE_BODY" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE_BODY"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Next Steps"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "✓ All registered devices will receive this update"
    echo ""
    echo "Monitor update progress:"
    echo "  • Check device status: $SERVER_URL/api/v1/devices/"
    echo "  • View update details: $SERVER_URL/api/v1/updates/$VERSION"
    echo ""
    echo "Check device logs after update:"
    echo "  ssh pi@device-ip"
    echo "  journalctl -u voice-assistant.service -f"
    echo ""
else
    echo "❌ Failed to create update (HTTP $HTTP_CODE)"
    echo ""
    echo "Error Response:"
    echo "$RESPONSE_BODY"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Verify SERVER_API_KEY is correct in $SERVER_ENV_FILE"
    echo "  2. Check server is running: curl $SERVER_URL/health"
    echo "  3. View server logs: journalctl -u voice-assistant-server.service -n 50"
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
echo ""
