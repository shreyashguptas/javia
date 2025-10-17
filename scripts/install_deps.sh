#!/bin/bash

# Dependency Installation Script for Voice Assistant
# This script installs all required dependencies

set -e  # Exit on any error

echo "=========================================="
echo "Voice Assistant Dependency Installer"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    print_error "Please do not run this script as root"
    exit 1
fi

# Update package list
print_status "Updating package list..."
sudo apt update

# Install system dependencies
print_status "Installing system dependencies..."
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    portaudio19-dev \
    alsa-utils \
    alsa-tools \
    git \
    curl \
    wget \
    build-essential \
    libasound2-dev \
    libportaudio2 \
    libportaudiocpp0 \
    portaudio19-dev

# Create virtual environment if it doesn't exist
VENV_PATH="$HOME/venvs/pi"
if [ ! -d "$VENV_PATH" ]; then
    print_status "Creating virtual environment at $VENV_PATH..."
    python3 -m venv "$VENV_PATH"
else
    print_warning "Virtual environment already exists at $VENV_PATH"
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source "$VENV_PATH/bin/activate"

# Upgrade pip
print_status "Upgrading pip..."
pip install --upgrade pip

# Install Python packages
print_status "Installing Python packages..."
pip install \
    pyaudio \
    RPi.GPIO \
    requests \
    pathlib2 \
    python-dotenv \
    numpy \
    scipy

# Verify installations
print_status "Verifying installations..."

# Test PyAudio
if python3 -c "import pyaudio; print('PyAudio version:', pyaudio.__version__)" 2>/dev/null; then
    print_status "PyAudio installed successfully"
else
    print_error "PyAudio installation failed"
    exit 1
fi

# Test RPi.GPIO
if python3 -c "import RPi.GPIO; print('RPi.GPIO imported successfully')" 2>/dev/null; then
    print_status "RPi.GPIO installed successfully"
else
    print_error "RPi.GPIO installation failed"
    exit 1
fi

# Test requests
if python3 -c "import requests; print('Requests version:', requests.__version__)" 2>/dev/null; then
    print_status "Requests installed successfully"
else
    print_error "Requests installation failed"
    exit 1
fi

# Test audio system
print_status "Testing audio system..."
if arecord -l >/dev/null 2>&1; then
    print_status "Audio recording system working"
else
    print_warning "Audio recording system may have issues"
fi

if aplay -l >/dev/null 2>&1; then
    print_status "Audio playback system working"
else
    print_warning "Audio playback system may have issues"
fi

# Create activation script
print_status "Creating activation script..."
tee "$HOME/activate_voice_assistant.sh" > /dev/null << EOF
#!/bin/bash
# Voice Assistant Environment Activation Script

echo "Activating Voice Assistant environment..."

# Activate virtual environment
source "$VENV_PATH/bin/activate"

# Set environment variables
export PYTHONPATH="$HOME/voice_assistant:\$PYTHONPATH"

echo "Environment activated!"
echo "Virtual environment: $VENV_PATH"
echo "Python path: \$PYTHONPATH"
echo ""
echo "To run the voice assistant:"
echo "  cd ~/voice_assistant"
echo "  python3 voice_assistant.py"
EOF

chmod +x "$HOME/activate_voice_assistant.sh"

# Create deactivation script
print_status "Creating deactivation script..."
tee "$HOME/deactivate_voice_assistant.sh" > /dev/null << EOF
#!/bin/bash
# Voice Assistant Environment Deactivation Script

echo "Deactivating Voice Assistant environment..."

# Deactivate virtual environment
deactivate

# Unset environment variables
unset PYTHONPATH

echo "Environment deactivated!"
EOF

chmod +x "$HOME/deactivate_voice_assistant.sh"

# Final instructions
print_status "Dependency installation complete!"
echo ""
echo "=========================================="
echo "Installation Summary:"
echo "=========================================="
echo "✓ System packages installed"
echo "✓ Python virtual environment created"
echo "✓ Python packages installed"
echo "✓ Audio system tested"
echo "✓ Activation scripts created"
echo ""
echo "=========================================="
echo "Next Steps:"
echo "=========================================="
echo "1. Activate the environment:"
echo "   source ~/activate_voice_assistant.sh"
echo ""
echo "2. Or manually activate:"
echo "   source ~/venvs/pi/bin/activate"
echo ""
echo "3. Test the installation:"
echo "   python3 -c \"import pyaudio, RPi.GPIO, requests; print('All packages working!')\""
echo ""
echo "4. Run the voice assistant:"
echo "   cd ~/voice_assistant"
echo "   python3 voice_assistant.py"
echo ""
echo "=========================================="
echo "Useful Commands:"
echo "=========================================="
echo "Activate env:     source ~/activate_voice_assistant.sh"
echo "Deactivate env:   source ~/deactivate_voice_assistant.sh"
echo "Test audio:       python3 ~/voice_assistant/scripts/test_audio.py"
echo "Check packages:   pip list"
echo "Update packages:  pip install --upgrade package_name"
echo ""
echo "=========================================="
echo "Troubleshooting:"
echo "=========================================="
echo "If PyAudio fails to install:"
echo "  sudo apt install portaudio19-dev python3-dev"
echo "  pip install pyaudio"
echo ""
echo "If RPi.GPIO fails to install:"
echo "  sudo apt install python3-rpi.gpio"
echo "  pip install RPi.GPIO"
echo ""
echo "If audio doesn't work:"
echo "  sudo usermod -a -G audio \$USER"
echo "  sudo usermod -a -G gpio \$USER"
echo "  (then logout and login again)"
echo ""
echo "For more help, see docs/troubleshooting.md"
echo "=========================================="
