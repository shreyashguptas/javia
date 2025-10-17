#!/bin/bash

# Raspberry Pi Voice Assistant Setup Script
# This script automates the setup process for the voice assistant

set -e  # Exit on any error

echo "=========================================="
echo "Raspberry Pi Voice Assistant Setup"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo; then
    print_warning "This script is designed for Raspberry Pi. Continue anyway? (y/N)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Update system packages
print_status "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install required system packages
print_status "Installing system dependencies..."
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-pyaudio \
    python3-rpi.gpio \
    python3-requests \
    python3-numpy \
    alsa-utils \
    alsa-tools \
    git \
    curl \
    wget

# Create virtual environment with system site packages
print_status "Creating Python virtual environment..."
if [ ! -d "$HOME/venvs/pi" ]; then
    python3 -m venv --system-site-packages "$HOME/venvs/pi"
    print_status "Virtual environment created at $HOME/venvs/pi (with system packages)"
else
    print_warning "Virtual environment already exists at $HOME/venvs/pi"
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source "$HOME/venvs/pi/bin/activate"

# Install Python packages (only the ones not available as system packages)
print_status "Installing Python packages..."
pip install --upgrade pip
pip install python-dotenv pathlib2

# Configure I2S audio
print_status "Configuring I2S audio..."

# Backup original config
if [ ! -f "/boot/firmware/config.txt.backup" ]; then
    sudo cp /boot/firmware/config.txt /boot/firmware/config.txt.backup
    print_status "Backed up original config.txt"
fi

# Add I2S configuration
if ! grep -q "dtparam=i2s=on" /boot/firmware/config.txt; then
    print_status "Adding I2S configuration to config.txt..."
    
    # Add I2S configuration at the end of file
    sudo tee -a /boot/firmware/config.txt > /dev/null << EOF

# I2S Configuration for INMP441 + MAX98357A
dtparam=i2s=on
dtoverlay=googlevoicehat-soundcard

# GPIO settings for button
gpio=17=ip,pu
EOF
    
    print_status "I2S configuration added to config.txt"
else
    print_warning "I2S configuration already exists in config.txt"
fi

# Create project directory
PROJECT_DIR="$HOME/voice_assistant"
print_status "Creating project directory at $PROJECT_DIR..."
mkdir -p "$PROJECT_DIR"

# Copy project files
print_status "Copying project files..."
if [ -f "voice_assistant.py" ]; then
    cp voice_assistant.py "$PROJECT_DIR/"
    print_status "Copied voice_assistant.py"
else
    print_warning "voice_assistant.py not found in current directory"
fi

# Create .env file from example
print_status "Creating .env file..."
if [ -f "env.example" ]; then
    cp env.example "$PROJECT_DIR/.env"
    print_status "Created .env file from template"
    print_warning "Please edit $PROJECT_DIR/.env and add your Groq API key"
else
    print_warning "env.example not found, creating basic .env file"
    tee "$PROJECT_DIR/.env" > /dev/null << EOF
# Groq API Configuration
GROQ_API_KEY=YOUR_GROQ_API_KEY_HERE
EOF
fi

# Set up audio permissions
print_status "Setting up audio permissions..."
sudo usermod -a -G audio "$USER"
sudo usermod -a -G gpio "$USER"

# Create systemd service (optional)
print_status "Creating systemd service..."
sudo tee /etc/systemd/system/voice-assistant.service > /dev/null << EOF
[Unit]
Description=Raspberry Pi Voice Assistant
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$HOME/venvs/pi/bin
ExecStart=$HOME/venvs/pi/bin/python $PROJECT_DIR/voice_assistant.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable service (but don't start yet)
sudo systemctl daemon-reload
sudo systemctl enable voice-assistant.service

print_status "Systemd service created and enabled"

# Test audio setup
print_status "Testing audio setup..."

# Check if audio devices are detected
if arecord -l | grep -q "voice-assistant"; then
    print_status "I2S microphone detected"
else
    print_warning "I2S microphone not detected. You may need to reboot."
fi

if aplay -l | grep -q "voice-assistant"; then
    print_status "I2S amplifier detected"
else
    print_warning "I2S amplifier not detected. You may need to reboot."
fi

# Create test script
print_status "Creating test script..."
tee "$PROJECT_DIR/test_setup.py" > /dev/null << 'EOF'
#!/usr/bin/env python3
"""
Test script for voice assistant setup
"""

import sys
import subprocess
import pyaudio
import RPi.GPIO as GPIO

def test_audio_devices():
    """Test audio device detection"""
    print("Testing audio devices...")
    
    try:
        # Test arecord
        result = subprocess.run(['arecord', '-l'], 
                              capture_output=True, text=True, check=True)
        print("Recording devices:")
        print(result.stdout)
        
        # Test aplay
        result = subprocess.run(['aplay', '-l'], 
                              capture_output=True, text=True, check=True)
        print("Playback devices:")
        print(result.stdout)
        
        return True
    except Exception as e:
        print(f"Error testing audio devices: {e}")
        return False

def test_pyaudio():
    """Test PyAudio functionality"""
    print("Testing PyAudio...")
    
    try:
        p = pyaudio.PyAudio()
        print(f"PyAudio version: {pyaudio.__version__}")
        print(f"Device count: {p.get_device_count()}")
        
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                print(f"Input device {i}: {info['name']}")
            if info['maxOutputChannels'] > 0:
                print(f"Output device {i}: {info['name']}")
        
        p.terminate()
        return True
    except Exception as e:
        print(f"Error testing PyAudio: {e}")
        return False

def test_gpio():
    """Test GPIO functionality"""
    print("Testing GPIO...")
    
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        state = GPIO.input(17)
        print(f"GPIO17 (button) state: {state}")
        GPIO.cleanup()
        return True
    except Exception as e:
        print(f"Error testing GPIO: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 50)
    print("Voice Assistant Setup Test")
    print("=" * 50)
    
    tests = [
        ("Audio Devices", test_audio_devices),
        ("PyAudio", test_pyaudio),
        ("GPIO", test_gpio)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        print("-" * 20)
        try:
            result = test_func()
            results.append((test_name, result))
            print(f"{test_name}: {'PASS' if result else 'FAIL'}")
        except Exception as e:
            print(f"{test_name}: FAIL - {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("Test Results:")
    print("=" * 50)
    
    all_passed = True
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{test_name}: {status}")
        if not result:
            all_passed = False
    
    if all_passed:
        print("\nAll tests passed! Setup is complete.")
    else:
        print("\nSome tests failed. Check the output above for details.")
        print("You may need to:")
        print("1. Reboot the system")
        print("2. Check hardware connections")
        print("3. Verify configuration files")

if __name__ == "__main__":
    main()
EOF

chmod +x "$PROJECT_DIR/test_setup.py"

# Create startup script
print_status "Creating startup script..."
tee "$PROJECT_DIR/start.sh" > /dev/null << EOF
#!/bin/bash
# Voice Assistant Startup Script

echo "Starting Voice Assistant..."

# Activate virtual environment
source "$HOME/venvs/pi/bin/activate"

# Change to project directory
cd "$PROJECT_DIR"

# Run the voice assistant
python3 voice_assistant.py
EOF

chmod +x "$PROJECT_DIR/start.sh"

# Create stop script
print_status "Creating stop script..."
tee "$PROJECT_DIR/stop.sh" > /dev/null << EOF
#!/bin/bash
# Voice Assistant Stop Script

echo "Stopping Voice Assistant..."

# Stop systemd service
sudo systemctl stop voice-assistant.service

# Kill any running Python processes
pkill -f voice_assistant.py

echo "Voice Assistant stopped."
EOF

chmod +x "$PROJECT_DIR/stop.sh"

# Final instructions
print_status "Setup complete!"
echo ""
echo "=========================================="
echo "Next Steps:"
echo "=========================================="
echo "1. Reboot your Raspberry Pi:"
echo "   sudo reboot"
echo ""
echo "2. After reboot, test the setup:"
echo "   cd $PROJECT_DIR"
echo "   source $HOME/venvs/pi/bin/activate"
echo "   python3 test_setup.py"
echo ""
echo "3. Configure your Groq API key in .env file:"
echo "   nano $PROJECT_DIR/.env"
echo ""
echo "4. Start the voice assistant:"
echo "   ./start.sh"
echo ""
echo "5. Or start as a service:"
echo "   sudo systemctl start voice-assistant.service"
echo ""
echo "=========================================="
echo "Useful Commands:"
echo "=========================================="
echo "Test audio:     arecord -D plughw:0,0 -c1 -r 16000 -f S16_LE test.wav"
echo "Play audio:      aplay -D plughw:0,0 test.wav"
echo "Check service:   sudo systemctl status voice-assistant.service"
echo "View logs:       sudo journalctl -u voice-assistant.service -f"
echo "Stop service:    sudo systemctl stop voice-assistant.service"
echo "Start service:   sudo systemctl start voice-assistant.service"
echo ""
echo "=========================================="
echo "Troubleshooting:"
echo "=========================================="
echo "If audio doesn't work:"
echo "1. Check hardware connections"
echo "2. Verify config.txt settings"
echo "3. Run test_setup.py"
echo "4. Check system logs"
echo ""
echo "For more help, see docs/troubleshooting.md"
echo "=========================================="
