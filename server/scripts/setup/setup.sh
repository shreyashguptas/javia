#!/bin/bash
set -e

# Voice Assistant Server Setup Script
# This script handles fresh installs, updates, and fixes
# Run from the cloned Git repository directory

echo "==========================================="
echo "Voice Assistant Server Setup"
echo "==========================================="
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root or with sudo" 
   exit 1
fi

# Configuration
INSTALL_DIR="/opt/javia"
VENV_DIR="$INSTALL_DIR/venv"
SERVICE_USER="voiceassistant"
SERVICE_GROUP="voiceassistant"

# Determine source directory (must be run from git repo)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Validate we're in the right place
if [ ! -f "$SERVER_DIR/main.py" ]; then
    echo "❌ ERROR: Cannot find main.py!"
    echo "Expected to find main.py at: $SERVER_DIR/main.py"
    echo ""
    echo "Please ensure you:"
    echo "  1. Cloned the repository: git clone https://github.com/shreyashguptas/javia.git"
    echo "  2. Are running this script from: /tmp/javia/server/scripts/setup/setup.sh"
    echo ""
    exit 1
fi

echo "✓ Found server files at: $SERVER_DIR"
echo ""

# Detect if this is a fresh install or an update
IS_FRESH_INSTALL=false
if [ ! -f "$INSTALL_DIR/.env" ]; then
    IS_FRESH_INSTALL=true
    echo "📦 Detected: FRESH INSTALLATION"
else
    echo "🔄 Detected: UPDATE/RECONFIGURATION"
fi
echo ""

# ==================== STEP 1: SYSTEM DEPENDENCIES ====================
echo "[1/10] Checking system dependencies..."

# Check if packages are already installed to avoid unnecessary updates
PACKAGES_TO_INSTALL=""
for pkg in python3 python3-pip python3-venv nginx git wget rsync libopus0 libopus-dev ffmpeg; do
    if ! dpkg -l | grep -q "^ii  $pkg "; then
        PACKAGES_TO_INSTALL="$PACKAGES_TO_INSTALL $pkg"
    fi
done

if [ -n "$PACKAGES_TO_INSTALL" ]; then
    echo "Installing missing packages:$PACKAGES_TO_INSTALL"
    apt update
    apt install -y $PACKAGES_TO_INSTALL
    echo "✓ System dependencies installed"
else
    echo "✓ All system dependencies already installed"
fi

echo ""

# ==================== STEP 2: CREATE SERVICE USER ====================
echo "[2/10] Setting up service user..."

if ! id -u $SERVICE_USER > /dev/null 2>&1; then
    useradd -r -s /bin/false -d $INSTALL_DIR $SERVICE_USER
    echo "✓ Created user: $SERVICE_USER"
else
    echo "✓ User $SERVICE_USER already exists"
fi

echo ""

# ==================== STEP 3: STOP SERVICE ====================
echo "[3/10] Stopping service (if running)..."
systemctl stop voice-assistant-server.service 2>/dev/null || true
echo "✓ Service stopped"
echo ""

# ==================== STEP 4: CREATE DIRECTORIES ====================
echo "[4/10] Setting up directories..."
mkdir -p "$INSTALL_DIR"
echo "✓ Directories ready"
echo ""

# ==================== STEP 5: COPY/UPDATE FILES ====================
echo "[5/10] Copying latest server files..."

# Backup .env if it exists (with automatic cleanup of old backups)
ENV_BACKUP=""
BACKUP_DIR="$INSTALL_DIR/.env.backups"
if [ -f "$INSTALL_DIR/.env" ]; then
    # Create backup directory if it doesn't exist
    mkdir -p "$BACKUP_DIR"
    chmod 700 "$BACKUP_DIR"
    
    # Generate timestamped backup filename
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    ENV_BACKUP="$BACKUP_DIR/.env.backup.$TIMESTAMP"
    
    # Keep only the 2 most recent backups - delete older ones
    if [ -d "$BACKUP_DIR" ]; then
        # Count existing backups
        BACKUP_COUNT=$(find "$BACKUP_DIR" -name ".env.backup.*" -type f 2>/dev/null | wc -l)
        
        if [ "$BACKUP_COUNT" -ge 2 ]; then
            # Delete oldest backups, keeping only the most recent 1 (we'll add the new one to make 2 total)
            # Sort by modification time (newest first) and keep only the first one
            find "$BACKUP_DIR" -name ".env.backup.*" -type f -print0 2>/dev/null | \
                xargs -0 ls -t 2>/dev/null | tail -n +2 | xargs rm -f 2>/dev/null || true
            echo "✓ Cleaned up old backups (keeping 2 most recent)"
        fi
    fi
    
    # Create the new backup
    cp "$INSTALL_DIR/.env" "$ENV_BACKUP"
    chmod 600 "$ENV_BACKUP"
    echo "✓ Backed up existing .env file to: $(basename "$ENV_BACKUP")"
fi

# Clean up old backups in /tmp/ from previous script versions (optional cleanup)
if [ -d "/tmp" ]; then
    OLD_BACKUP_COUNT=$(find /tmp -maxdepth 1 -name "javia_server_env_backup_*" -type f 2>/dev/null | wc -l)
    if [ "$OLD_BACKUP_COUNT" -gt 0 ]; then
        find /tmp -maxdepth 1 -name "javia_server_env_backup_*" -type f -delete 2>/dev/null || true
        echo "✓ Cleaned up $OLD_BACKUP_COUNT old backup(s) from /tmp/"
    fi
fi

# Remove old files but preserve venv, .env, and .env.backups
if [ -d "$INSTALL_DIR" ]; then
    find "$INSTALL_DIR" -mindepth 1 -maxdepth 1 ! -name 'venv' ! -name '.env' ! -name '.env.backups' -exec rm -rf {} + 2>/dev/null || true
fi

# Copy all files from server directory
echo "Copying files from: $SERVER_DIR"
rsync -av --exclude='__pycache__' --exclude='*.pyc' "$SERVER_DIR/" "$INSTALL_DIR/"
echo "✓ Files copied successfully"
echo ""

# ==================== STEP 6: VIRTUAL ENVIRONMENT ====================
echo "[6/10] Setting up Python virtual environment..."

if [ -d "$VENV_DIR" ]; then
    echo "✓ Virtual environment already exists, updating..."
else
    echo "Creating new virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
pip install --upgrade pip > /dev/null 2>&1
pip install -r "$INSTALL_DIR/requirements.txt"
echo "✓ Virtual environment ready"
echo ""

# ==================== STEP 7: CONFIGURE .ENV ====================
echo "[7/10] Configuring environment..."

# Create .env from template if it doesn't exist
if [ ! -f "$INSTALL_DIR/.env" ]; then
    if [ -f "$INSTALL_DIR/env.example" ]; then
        cp "$INSTALL_DIR/env.example" "$INSTALL_DIR/.env"
        echo "✓ Created .env from template"
    else
        echo "❌ ERROR: env.example not found!"
        exit 1
    fi
else
    # .env file exists - ask if user wants to reset it
    echo ""
    echo "==================================="
    echo "Existing .env File Detected"
    echo "==================================="
    echo ""
    echo "An existing .env file was found at: $INSTALL_DIR/.env"
    echo ""
    echo "Options:"
    echo "  1) Keep existing .env and update only the values you change (default)"
    echo "  2) Reset .env file - Delete current .env and create fresh from env.example"
    echo ""
    echo "⚠️  WARNING: Option 2 will DELETE your current .env file!"
    echo "            You will need to re-enter ALL configuration values."
    echo ""
    read -p "Do you want to RESET your .env file? (y/N): " RESET_ENV_CHOICE

    if [ "$RESET_ENV_CHOICE" = "y" ] || [ "$RESET_ENV_CHOICE" = "Y" ]; then
        echo ""
        echo "Resetting .env file..."

        # Backup current .env before deleting
        TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        BACKUP_FILE="/tmp/.env.backup.$TIMESTAMP"
        cp "$INSTALL_DIR/.env" "$BACKUP_FILE"
        echo "✓ Backed up current .env to: $BACKUP_FILE"

        # Delete current .env
        rm -f "$INSTALL_DIR/.env"

        # Create fresh .env from env.example
        if [ -f "$INSTALL_DIR/env.example" ]; then
            cp "$INSTALL_DIR/env.example" "$INSTALL_DIR/.env"
            echo "✓ Created fresh .env from env.example"
            echo ""
            echo "You will now be prompted to configure all values."

            # Treat this as a fresh install for configuration purposes
            IS_FRESH_INSTALL=true
        else
            echo "❌ ERROR: env.example not found!"
            echo "Restoring backup..."
            cp "$BACKUP_FILE" "$INSTALL_DIR/.env"
            exit 1
        fi
    else
        echo "✓ Keeping existing .env file"
    fi
fi

cd "$INSTALL_DIR"

# Handle configuration based on fresh install vs update
if [ "$IS_FRESH_INSTALL" = true ]; then
    # FRESH INSTALL - Require all values
    echo ""
    echo "==================================="
    echo "Server Configuration (REQUIRED)"
    echo "==================================="
    echo ""
    
    # Require GROQ_API_KEY
    while true; do
        echo "Enter your GROQ_API_KEY:"
        read -p "GROQ_API_KEY: " GROQ_KEY_INPUT
        if [ -n "$GROQ_KEY_INPUT" ]; then
            break
        else
            echo "❌ GROQ_API_KEY cannot be empty. Please enter a valid API key."
            echo ""
        fi
    done
    
    echo ""
    # Require OPENAI_API_KEY
    while true; do
        echo "Enter your OPENAI_API_KEY (required for embeddings and summarization):"
        read -p "OPENAI_API_KEY: " OPENAI_KEY_INPUT
        if [ -n "$OPENAI_KEY_INPUT" ]; then
            break
        else
            echo "❌ OPENAI_API_KEY cannot be empty. Please enter a valid API key."
            echo ""
        fi
    done
    
    echo ""
    echo "Generating SERVER_API_KEY using UUID7..."
    # Install uuid6 package (provides uuid7 support) if needed
    pip install -q uuid6 > /dev/null 2>&1 || true
    SERVER_KEY_INPUT=$(python3 -c "from uuid6 import uuid7; print(str(uuid7()))")
    
    echo ""
    echo "==================================="
    echo "GENERATED SERVER_API_KEY (ADMIN ONLY):"
    echo "$SERVER_KEY_INPUT"
    echo "==================================="
    echo ""
    echo "NOTE: This key is for server admin/management endpoints ONLY."
    echo "Pi clients authenticate using device UUIDs (not this key)."
    echo ""
    echo "Save this key for:"
    echo "  - Admin API access"
    echo "  - Device management tools"
    echo "  - Future web dashboard"
    echo ""
    read -p "Press Enter after you've saved the SERVER_API_KEY..."
    
    echo ""
    echo "==================================="
    echo "OTA Update Configuration (Optional)"
    echo "==================================="
    echo ""
    echo "For over-the-air updates, you need Supabase credentials."
    echo "If you don't have these yet, you can skip and add them later."
    echo ""
    
    echo "Enter your SUPABASE_URL (or press Enter to skip):"
    read -p "SUPABASE_URL: " SUPABASE_URL_INPUT
    
    if [ -n "$SUPABASE_URL_INPUT" ]; then
        echo ""
        echo "Enter your SUPABASE_KEY (anon key):"
        read -p "SUPABASE_KEY: " SUPABASE_KEY_INPUT
        
        echo ""
        echo "Enter your SUPABASE_SERVICE_KEY (service role key):"
        read -p "SUPABASE_SERVICE_KEY: " SUPABASE_SERVICE_KEY_INPUT
    else
        SUPABASE_KEY_INPUT=""
        SUPABASE_SERVICE_KEY_INPUT=""
        echo "⊘ Skipped OTA update configuration (can be added later)"
    fi
    
    echo ""
    echo "==================================="
    echo "CORS Configuration (ALLOWED_ORIGINS)"
    echo "==================================="
    echo ""
    echo "This controls which origins can make CORS requests to your API."
    echo "Use '*' to allow all origins (less secure, not recommended for production)."
    echo "For production, specify your actual domains (comma-separated, no spaces)."
    echo ""
    echo "Examples:"
    echo "  - Single origin: https://myapp.com"
    echo "  - Multiple origins: https://myapp.com,https://www.myapp.com,https://admin.myapp.com"
    echo "  - Allow all: *"
    echo ""
    echo "Enter your ALLOWED_ORIGINS (press Enter to use default '*'):"
    read -p "ALLOWED_ORIGINS: " ALLOWED_ORIGINS_INPUT
    
    if [ -z "$ALLOWED_ORIGINS_INPUT" ]; then
        ALLOWED_ORIGINS_INPUT="*"
        echo "✓ Using default value: *"
    else
        echo "✓ Will set ALLOWED_ORIGINS to: $ALLOWED_ORIGINS_INPUT"
    fi
    
else
    # UPDATE - Show current values and allow keeping or changing
    echo ""
    echo "Found existing configuration!"
    echo ""
    
    # Load current values using Python (safer than sourcing)
    CURRENT_VALUES=$(python3 << 'EOF'
import os
import re

env_file = '.env'
groq_key = 'NOT_SET'
openai_key = 'NOT_SET'
server_key = 'NOT_SET'
supabase_url = 'NOT_SET'
supabase_key = 'NOT_SET'
supabase_service_key = 'NOT_SET'
allowed_origins = 'NOT_SET'

try:
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                if line.startswith('GROQ_API_KEY='):
                    groq_key = line.split('=', 1)[1].strip()
                elif line.startswith('OPENAI_API_KEY='):
                    openai_key = line.split('=', 1)[1].strip()
                elif line.startswith('SERVER_API_KEY='):
                    server_key = line.split('=', 1)[1].strip()
                elif line.startswith('SUPABASE_URL='):
                    supabase_url = line.split('=', 1)[1].strip()
                elif line.startswith('SUPABASE_KEY='):
                    supabase_key = line.split('=', 1)[1].strip()
                elif line.startswith('SUPABASE_SERVICE_KEY='):
                    supabase_service_key = line.split('=', 1)[1].strip()
                elif line.startswith('ALLOWED_ORIGINS='):
                    allowed_origins = line.split('=', 1)[1].strip()
    print(f"GROQ_KEY={groq_key}")
    print(f"OPENAI_KEY={openai_key}")
    print(f"SERVER_KEY={server_key}")
    print(f"SUPABASE_URL={supabase_url}")
    print(f"SUPABASE_KEY={supabase_key}")
    print(f"SUPABASE_SERVICE_KEY={supabase_service_key}")
    print(f"ALLOWED_ORIGINS={allowed_origins}")
except Exception as e:
    print(f"GROQ_KEY=NOT_SET")
    print(f"OPENAI_KEY=NOT_SET")
    print(f"SERVER_KEY=NOT_SET")
    print(f"SUPABASE_URL=NOT_SET")
    print(f"SUPABASE_KEY=NOT_SET")
    print(f"SUPABASE_SERVICE_KEY=NOT_SET")
    print(f"ALLOWED_ORIGINS=NOT_SET")
EOF
)
    
    # Parse the output
    CURRENT_GROQ_KEY=$(echo "$CURRENT_VALUES" | grep "^GROQ_KEY=" | cut -d'=' -f2)
    CURRENT_OPENAI_KEY=$(echo "$CURRENT_VALUES" | grep "^OPENAI_KEY=" | cut -d'=' -f2)
    CURRENT_SERVER_KEY=$(echo "$CURRENT_VALUES" | grep "^SERVER_KEY=" | cut -d'=' -f2)
    CURRENT_SUPABASE_URL=$(echo "$CURRENT_VALUES" | grep "^SUPABASE_URL=" | cut -d'=' -f2)
    CURRENT_SUPABASE_KEY=$(echo "$CURRENT_VALUES" | grep "^SUPABASE_KEY=" | cut -d'=' -f2)
    CURRENT_SUPABASE_SERVICE_KEY=$(echo "$CURRENT_VALUES" | grep "^SUPABASE_SERVICE_KEY=" | cut -d'=' -f2)
    CURRENT_ALLOWED_ORIGINS=$(echo "$CURRENT_VALUES" | grep "^ALLOWED_ORIGINS=" | cut -d'=' -f2)
    
    echo "==================================="
    echo "Current Configuration"
    echo "==================================="
    echo ""
    echo "GROQ_API_KEY"
    echo "------------"
    echo "Current value: ${CURRENT_GROQ_KEY:0:20}... (hidden)"
    echo ""
    echo "Enter new GROQ_API_KEY (or press Enter to keep current):"
    read -p "GROQ_API_KEY: " GROQ_KEY_INPUT
    
    if [ -z "$GROQ_KEY_INPUT" ]; then
        GROQ_KEY_INPUT="$CURRENT_GROQ_KEY"
        echo "✓ Keeping existing GROQ_API_KEY"
    else
        echo "✓ Will update GROQ_API_KEY"
    fi
    
    echo ""
    echo "OPENAI_API_KEY"
    echo "------------"
    echo "Current value: ${CURRENT_OPENAI_KEY:0:20}... (hidden)"
    echo ""
    echo "Enter new OPENAI_API_KEY (or press Enter to keep current):"
    read -p "OPENAI_API_KEY: " OPENAI_KEY_INPUT
    
    if [ -z "$OPENAI_KEY_INPUT" ]; then
        OPENAI_KEY_INPUT="$CURRENT_OPENAI_KEY"
        echo "✓ Keeping existing OPENAI_API_KEY"
    else
        echo "✓ Will update OPENAI_API_KEY"
    fi
    
    echo ""
    echo "==================================="
    echo "SERVER_API_KEY (Admin Only)"
    echo "------------"
    echo "Current value: $CURRENT_SERVER_KEY"
    echo ""
    echo "NOTE: This key is for admin/management endpoints only."
    echo "Pi clients authenticate using device UUIDs (not this key)."
    echo "Changing this key only affects admin tools and scripts."
    echo ""
    echo "Options:"
    echo "  1) Keep current SERVER_API_KEY (press Enter)"
    echo "  2) Generate new SERVER_API_KEY (type 'new')"
    echo ""
    read -p "Choice (Enter or 'new'): " SERVER_KEY_CHOICE
    
    if [ "$SERVER_KEY_CHOICE" = "new" ]; then
        echo ""
        echo "Generating new SERVER_API_KEY using UUID7..."
        pip install -q uuid6 > /dev/null 2>&1 || true
        SERVER_KEY_INPUT=$(python3 -c "from uuid6 import uuid7; print(str(uuid7()))")
        echo ""
        echo "==================================="
        echo "NEW SERVER_API_KEY (SAVE THIS!):"
        echo "$SERVER_KEY_INPUT"
        echo "==================================="
        echo ""
        echo "IMPORTANT: Save this key for admin operations."
        echo "Used for: Device management API, OTA update creation, admin tools"
        echo ""
        read -p "Press Enter after you've saved the SERVER_API_KEY..."
    else
        SERVER_KEY_INPUT="$CURRENT_SERVER_KEY"
        echo "✓ Keeping existing SERVER_API_KEY"
    fi
    
    echo ""
    echo "==================================="
    echo "OTA Update Configuration (Supabase)"
    echo "==================================="
    echo ""
    echo "SUPABASE_URL"
    echo "------------"
    if [ "$CURRENT_SUPABASE_URL" != "NOT_SET" ] && [ "$CURRENT_SUPABASE_URL" != "https://your-project.supabase.co" ]; then
        echo "Current value: $CURRENT_SUPABASE_URL"
    else
        echo "Current value: Not configured"
    fi
    echo ""
    read -p "SUPABASE_URL (press Enter to keep current): " SUPABASE_URL_INPUT
    
    if [ -z "$SUPABASE_URL_INPUT" ]; then
        SUPABASE_URL_INPUT="$CURRENT_SUPABASE_URL"
        echo "✓ Keeping existing SUPABASE_URL"
    else
        echo "✓ Will update SUPABASE_URL"
    fi
    
    echo ""
    echo "SUPABASE_KEY (anon key)"
    echo "------------"
    if [ "$CURRENT_SUPABASE_KEY" != "NOT_SET" ] && [ "$CURRENT_SUPABASE_KEY" != "your-anon-key" ]; then
        echo "Current value: ${CURRENT_SUPABASE_KEY:0:20}... (hidden)"
    else
        echo "Current value: Not configured"
    fi
    echo ""
    read -p "SUPABASE_KEY (press Enter to keep current): " SUPABASE_KEY_INPUT
    
    if [ -z "$SUPABASE_KEY_INPUT" ]; then
        SUPABASE_KEY_INPUT="$CURRENT_SUPABASE_KEY"
        echo "✓ Keeping existing SUPABASE_KEY"
    else
        echo "✓ Will update SUPABASE_KEY"
    fi
    
    echo ""
    echo "SUPABASE_SERVICE_KEY (service role key)"
    echo "------------"
    if [ "$CURRENT_SUPABASE_SERVICE_KEY" != "NOT_SET" ] && [ "$CURRENT_SUPABASE_SERVICE_KEY" != "your-service-role-key" ]; then
        echo "Current value: ${CURRENT_SUPABASE_SERVICE_KEY:0:20}... (hidden)"
    else
        echo "Current value: Not configured"
    fi
    echo ""
    read -p "SUPABASE_SERVICE_KEY (press Enter to keep current): " SUPABASE_SERVICE_KEY_INPUT
    
    if [ -z "$SUPABASE_SERVICE_KEY_INPUT" ]; then
        SUPABASE_SERVICE_KEY_INPUT="$CURRENT_SUPABASE_SERVICE_KEY"
        echo "✓ Keeping existing SUPABASE_SERVICE_KEY"
    else
        echo "✓ Will update SUPABASE_SERVICE_KEY"
    fi
    
    echo ""
    echo "==================================="
    echo "CORS Configuration (ALLOWED_ORIGINS)"
    echo "==================================="
    echo ""
    echo "This controls which origins can make CORS requests to your API."
    echo "Use '*' to allow all origins (less secure, not recommended for production)."
    echo "For production, specify your actual domains (comma-separated, no spaces)."
    echo ""
    echo "Examples:"
    echo "  - Single origin: https://myapp.com"
    echo "  - Multiple origins: https://myapp.com,https://www.myapp.com,https://admin.myapp.com"
    echo "  - Allow all: *"
    echo ""
    if [ "$CURRENT_ALLOWED_ORIGINS" != "NOT_SET" ] && [ "$CURRENT_ALLOWED_ORIGINS" != "*" ]; then
        echo "Current value: $CURRENT_ALLOWED_ORIGINS"
    elif [ "$CURRENT_ALLOWED_ORIGINS" = "*" ]; then
        echo "Current value: * (all origins allowed)"
    else
        echo "Current value: Not set (will default to *)"
    fi
    echo ""
    read -p "ALLOWED_ORIGINS (press Enter to keep current): " ALLOWED_ORIGINS_INPUT
    
    if [ -z "$ALLOWED_ORIGINS_INPUT" ]; then
        if [ "$CURRENT_ALLOWED_ORIGINS" != "NOT_SET" ]; then
            ALLOWED_ORIGINS_INPUT="$CURRENT_ALLOWED_ORIGINS"
            echo "✓ Keeping existing ALLOWED_ORIGINS"
        else
            ALLOWED_ORIGINS_INPUT="*"
            echo "✓ Using default value: *"
        fi
    else
        echo "✓ Will update ALLOWED_ORIGINS"
    fi
fi

# Update .env file with the values
GROQ_KEY_INPUT="$GROQ_KEY_INPUT" OPENAI_KEY_INPUT="$OPENAI_KEY_INPUT" SERVER_KEY_INPUT="$SERVER_KEY_INPUT" SUPABASE_URL_INPUT="$SUPABASE_URL_INPUT" SUPABASE_KEY_INPUT="$SUPABASE_KEY_INPUT" SUPABASE_SERVICE_KEY_INPUT="$SUPABASE_SERVICE_KEY_INPUT" ALLOWED_ORIGINS_INPUT="$ALLOWED_ORIGINS_INPUT" python3 << 'EOF'
import os
import re

groq_key = os.environ.get('GROQ_KEY_INPUT', '').strip()
openai_key = os.environ.get('OPENAI_KEY_INPUT', '').strip()
server_key = os.environ.get('SERVER_KEY_INPUT', '').strip()
supabase_url = os.environ.get('SUPABASE_URL_INPUT', '').strip()
supabase_key = os.environ.get('SUPABASE_KEY_INPUT', '').strip()
supabase_service_key = os.environ.get('SUPABASE_SERVICE_KEY_INPUT', '').strip()
allowed_origins = os.environ.get('ALLOWED_ORIGINS_INPUT', '').strip()

with open('.env', 'r') as f:
    content = f.read()

# Replace GROQ_API_KEY
if groq_key and groq_key != 'NOT_SET':
    content = re.sub(r'GROQ_API_KEY=.*', f'GROQ_API_KEY={groq_key}', content)
    print("✓ Updated GROQ_API_KEY")

# Replace OPENAI_API_KEY
if openai_key and openai_key != 'NOT_SET':
    if 'OPENAI_API_KEY=' in content:
        content = re.sub(r'OPENAI_API_KEY=.*', f'OPENAI_API_KEY={openai_key}', content)
    else:
        # Add after GROQ_API_KEY line
        content = re.sub(r'(GROQ_API_KEY=.*\n)', f'\\1OPENAI_API_KEY={openai_key}\n', content)
    print("✓ Updated OPENAI_API_KEY")

# Replace SERVER_API_KEY
if server_key and server_key != 'NOT_SET':
    content = re.sub(r'SERVER_API_KEY=.*', f'SERVER_API_KEY={server_key}', content)
    print("✓ Updated SERVER_API_KEY")

# Replace SUPABASE_URL if provided
if supabase_url and supabase_url != 'NOT_SET':
    if 'SUPABASE_URL=' in content:
        content = re.sub(r'SUPABASE_URL=.*', f'SUPABASE_URL={supabase_url}', content)
    else:
        # Add after SERVER_API_KEY line
        content = re.sub(r'(SERVER_API_KEY=.*\n)', f'\\1SUPABASE_URL={supabase_url}\n', content)
    print("✓ Updated SUPABASE_URL")

# Replace SUPABASE_KEY if provided
if supabase_key and supabase_key != 'NOT_SET':
    if 'SUPABASE_KEY=' in content:
        content = re.sub(r'SUPABASE_KEY=.*', f'SUPABASE_KEY={supabase_key}', content)
    else:
        # Add after SUPABASE_URL line
        content = re.sub(r'(SUPABASE_URL=.*\n)', f'\\1SUPABASE_KEY={supabase_key}\n', content)
    print("✓ Updated SUPABASE_KEY")

# Replace SUPABASE_SERVICE_KEY if provided
if supabase_service_key and supabase_service_key != 'NOT_SET':
    if 'SUPABASE_SERVICE_KEY=' in content:
        content = re.sub(r'SUPABASE_SERVICE_KEY=.*', f'SUPABASE_SERVICE_KEY={supabase_service_key}', content)
    else:
        # Add after SUPABASE_KEY line
        content = re.sub(r'(SUPABASE_KEY=.*\n)', f'\\1SUPABASE_SERVICE_KEY={supabase_service_key}\n', content)
    print("✓ Updated SUPABASE_SERVICE_KEY")

# Replace ALLOWED_ORIGINS if provided
if allowed_origins and allowed_origins != 'NOT_SET':
    if 'ALLOWED_ORIGINS=' in content:
        content = re.sub(r'ALLOWED_ORIGINS=.*', f'ALLOWED_ORIGINS={allowed_origins}', content)
    else:
        # Add after LOG_LEVEL line (before Audio Configuration section)
        if 'LOG_LEVEL=' in content:
            content = re.sub(r'(LOG_LEVEL=.*\n)', f'\\1# CORS Configuration: Comma-separated list of allowed origins\n# Use "*" to allow all origins (not recommended for production)\nALLOWED_ORIGINS={allowed_origins}\n', content)
        else:
            # Fallback: add after SUPABASE_SERVICE_KEY line
            content = re.sub(r'(SUPABASE_SERVICE_KEY=.*\n)', f'\\1# CORS Configuration: Comma-separated list of allowed origins\n# Use "*" to allow all origins (not recommended for production)\nALLOWED_ORIGINS={allowed_origins}\n', content)
    print("✓ Updated ALLOWED_ORIGINS")

with open('.env', 'w') as f:
    f.write(content)
EOF

# Secure the .env file
chmod 600 "$INSTALL_DIR/.env"

echo ""
echo "✓ Environment configured"
echo ""

# ==================== STEP 8: SET PERMISSIONS & REGISTRATION SCRIPT ====================
echo "[8/10] Setting permissions and registration script..."
chown -R $SERVICE_USER:$SERVICE_GROUP "$INSTALL_DIR"
chmod 600 "$INSTALL_DIR/.env"

# Make registration script accessible and executable
if [ -f "$INSTALL_DIR/scripts/register_device/register_device.sh" ]; then
    chmod 755 "$INSTALL_DIR/scripts/register_device/register_device.sh"
    echo "✓ Device registration script ready: $INSTALL_DIR/scripts/register_device/register_device.sh"
else
    echo "⚠️  Device registration script not found (will need to copy manually)"
fi

echo "✓ Permissions set"
echo ""

# ==================== STEP 9: SYSTEMD SERVICE ====================
echo "[9/10] Setting up systemd service..."

# Create systemd service file
cat > /tmp/voice-assistant-server.service <<EOF
[Unit]
Description=Voice Assistant Server
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_GROUP
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$VENV_DIR/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="PYTHONUNBUFFERED=1"
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$VENV_DIR/bin/python3 $INSTALL_DIR/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

mv /tmp/voice-assistant-server.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable voice-assistant-server.service
echo "✓ Systemd service configured"
echo ""

# ==================== STEP 10: NGINX CONFIGURATION ====================
echo "[10/10] Configuring Nginx..."

# Create nginx configuration
cat > /etc/nginx/sites-available/voice-assistant << 'NGINX_EOF'
server {
    listen 80;
    server_name _;
    
    # Health check endpoint
    location /health {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Main API endpoints
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Increase timeout for long-running requests
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
    
    # Increase max upload size for audio files
    client_max_body_size 26M;
}
NGINX_EOF

# Enable the site
ln -sf /etc/nginx/sites-available/voice-assistant /etc/nginx/sites-enabled/voice-assistant
rm -f /etc/nginx/sites-enabled/default

# Test and reload nginx
nginx -t && systemctl restart nginx

echo "✓ Nginx configured and running on port 80"
echo ""

# ==================== START SERVICE ====================
echo "Starting service..."
systemctl start voice-assistant-server.service

# Wait for service to initialize
sleep 2

# Check if service is actually running
echo ""
echo "Checking service status..."
if systemctl is-active --quiet voice-assistant-server.service; then
    echo "✅ Service is RUNNING successfully!"
    echo ""
    echo "==========================================="
    echo "Setup Complete!"
    echo "==========================================="
    echo ""
    
    # Test local connectivity
    echo "Testing local connectivity..."
    HEALTH_CHECK=$(curl -s http://localhost:8000/health || echo "FAILED")
    if [[ "$HEALTH_CHECK" == *"healthy"* ]]; then
        echo "✅ Local health check passed: $HEALTH_CHECK"
    else
        echo "⚠️  Local health check failed (service may still be starting)"
    fi
    echo ""
    
else
    echo "❌ Service FAILED to start!"
    echo ""
    echo "==========================================="
    echo "Setup Failed - Service Not Running"
    echo "==========================================="
    echo ""
    echo "Error logs (last 20 lines):"
    echo "-------------------------------------"
    journalctl -u voice-assistant-server.service -n 20 --no-pager
    echo "-------------------------------------"
    echo ""
    echo "To fix:"
    echo "  1. Check the error logs above"
    echo "  2. Edit .env if needed: nano $INSTALL_DIR/.env"
    echo "  3. Run this script again: bash $SCRIPT_DIR/setup.sh"
    echo ""
    exit 1
fi

# ==================== CLOUDFLARE TUNNEL SETUP ====================
# Check if cloudflared is already configured
CLOUDFLARED_CONFIGURED=false
if systemctl is-active --quiet cloudflared 2>/dev/null; then
    CLOUDFLARED_CONFIGURED=true
fi

if [ "$IS_FRESH_INSTALL" = true ] || [ "$CLOUDFLARED_CONFIGURED" = false ]; then
    # Fresh install or cloudflared not configured - offer setup
    echo ""
    echo "==================================="
    echo "Cloudflare Tunnel Setup"
    echo "==================================="
    echo ""
    
    if [ "$CLOUDFLARED_CONFIGURED" = false ]; then
        echo "Cloudflare Tunnel is NOT configured."
    fi
    
    echo "Do you want to set up Cloudflare Tunnel now?"
    echo "  1) Yes - Install and configure Cloudflare Tunnel"
    echo "  2) No - Skip (you can run this script again later)"
    echo ""
    read -p "Choose option [1-2]: " CLOUDFLARE_CHOICE
    
    if [ "$CLOUDFLARE_CHOICE" = "1" ]; then
        # Install cloudflared if not present
        if ! command -v cloudflared &> /dev/null; then
            echo ""
            echo "Installing cloudflared..."
            wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
            dpkg -i cloudflared-linux-amd64.deb
            rm cloudflared-linux-amd64.deb
            echo "✓ cloudflared installed"
        else
            echo "✓ cloudflared already installed"
        fi
        
        echo ""
        echo "==================================="
        echo "Cloudflare Tunnel Configuration Steps"
        echo "==================================="
        echo ""
        echo "Prerequisites:"
        echo "  ✓ You must have already added your domain to Cloudflare"
        echo "  ✓ Your domain's nameservers must be pointed to Cloudflare"
        echo ""
        echo "Step 1: Authenticate with Cloudflare"
        echo "  Run: cloudflared tunnel login"
        echo "  This will open a browser - login and authorize the tunnel"
        echo ""
        echo "Step 2: Create a tunnel"
        echo "  Run: cloudflared tunnel create javia-voice-assistant"
        echo "  Save the Tunnel ID that is displayed"
        echo ""
        echo "Step 3: Configure the tunnel"
        echo "  Run the following command (replace YOUR_DOMAIN with your actual domain):"
        echo "  cat > /etc/cloudflared/config.yml << 'TUNNEL_EOF'"
        echo "  tunnel: <TUNNEL_ID_FROM_STEP_2>"
        echo "  credentials-file: /root/.cloudflared/<TUNNEL_ID>.json"
        echo "  ingress:"
        echo "    - hostname: YOUR_DOMAIN.com"
        echo "      service: http://localhost:80"
        echo "      originRequest:"
        echo "        noTLSVerify: false"
        echo "        connectTimeout: 2m"
        echo "        tcpKeepAlive: 30s"
        echo "        keepAliveTimeout: 5m"
        echo "        keepAliveConnections: 10"
        echo "    - service: http_status:404"
        echo "  TUNNEL_EOF"
        echo "  "
        echo "  NOTE: The originRequest settings above are critical for long-running requests:"
        echo "    - connectTimeout: 2m       (allows up to 2 minutes to establish connection)"
        echo "    - keepAliveTimeout: 5m     (keeps connection alive for up to 5 minutes)"
        echo "    - tcpKeepAlive: 30s        (sends keepalive packets every 30 seconds)"
        echo "  These prevent timeouts during long TTS generation or slow network conditions."
        echo ""
        echo "Step 4: Route your domain to the tunnel"
        echo "  Run: cloudflared tunnel route dns javia-voice-assistant YOUR_DOMAIN.com"
        echo "  This automatically creates a CNAME record in Cloudflare DNS"
        echo ""
        echo "Step 5: Start the tunnel as a service"
        echo "  Run: cloudflared service install"
        echo "  Run: systemctl start cloudflared"
        echo "  Run: systemctl enable cloudflared"
        echo ""
        echo "Step 6: Test your setup"
        echo "  Local test: curl http://localhost:80/health"
        echo "  Public test: curl https://YOUR_DOMAIN.com/health"
        echo "  You should see: {\"status\":\"healthy\",\"version\":\"1.0.0\"}"
        echo ""
        echo "Step 7: Configure Raspberry Pi clients"
        echo "  1. Run Pi client setup to get device UUID"
        echo "  2. Register device UUID on server (see Device Registration section below)"
        echo "  3. Pi clients will authenticate using their unique UUID"
        echo ""
    else
        echo "✓ Skipped Cloudflare Tunnel setup"
    fi
else
    # Update scenario and cloudflared is already configured
    echo ""
    echo "==================================="
    echo "Cloudflare Tunnel Status"
    echo "==================================="
    echo ""
    echo "✅ Cloudflare Tunnel is already configured and running"
    echo ""
    echo "Do you want to reconfigure Cloudflare Tunnel?"
    echo "  1) No - Keep current configuration (recommended)"
    echo "  2) Yes - Show reconfiguration instructions"
    echo ""
    read -p "Choose option [1-2]: " CLOUDFLARE_RECONFIG_CHOICE
    
    if [ "$CLOUDFLARE_RECONFIG_CHOICE" = "2" ]; then
        echo ""
        echo "==================================="
        echo "Cloudflare Tunnel Reconfiguration"
        echo "==================================="
        echo ""
        echo "To reconfigure your tunnel:"
        echo ""
        echo "View current config: cat /etc/cloudflared/config.yml"
        echo "Edit config: nano /etc/cloudflared/config.yml"
        echo "Restart tunnel: systemctl restart cloudflared"
        echo "View tunnel status: systemctl status cloudflared"
        echo "View tunnel logs: journalctl -u cloudflared -f"
        echo ""
    else
        echo "✓ Keeping current Cloudflare Tunnel configuration"
    fi
fi

echo ""
echo "==========================================="
echo "Device Registration"
echo "==========================================="
echo ""
echo "To register a new Pi client device:"
echo ""
echo "  cd $INSTALL_DIR/scripts/register_device"
echo "  ./register_device.sh <DEVICE_UUID> [device_name] [timezone]"
echo ""
echo "Example:"
echo "  cd $INSTALL_DIR/scripts/register_device"
echo "  ./register_device.sh 018c8f5e-8c3a-7890-a1b2-3c4d5e6f7890 \"Kitchen Pi\" \"America/Los_Angeles\""
echo ""
echo "The device UUID will be displayed when you run setup on the Pi client."
echo ""
echo "==========================================="
echo "Useful Commands"
echo "==========================================="
echo ""
echo "Service Status:"
echo "  systemctl status voice-assistant-server.service"
echo ""
echo "View live logs:"
echo "  journalctl -u voice-assistant-server.service -f"
echo ""
echo "Check recent logs:"
echo "  journalctl -u voice-assistant-server.service -n 50"
echo ""
echo "Restart service:"
echo "  systemctl restart voice-assistant-server.service"
echo ""
echo "Stop service:"
echo "  systemctl stop voice-assistant-server.service"
echo ""
echo "Test endpoints:"
echo "  curl http://localhost:8000/health"
echo "  curl http://localhost:80/health"
echo ""
echo "Edit configuration:"
echo "  nano $INSTALL_DIR/.env"
echo "  # Then restart: systemctl restart voice-assistant-server.service"
echo ""
echo "==========================================="
echo "You can run this script again anytime to update!"
echo "==========================================="
echo ""

