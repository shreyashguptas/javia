# Python Version Compatibility Guide

## The Problem with Python 3.13

If you're running Raspberry Pi OS with Python 3.13 (latest versions), you may encounter issues installing PyAudio and other dependencies because:

1. **No pre-built wheels** - PyAudio doesn't have pre-compiled binaries for Python 3.13 yet
2. **Compilation requires memory** - Building from source needs more RAM than Pi Zero 2 W has
3. **Build dependencies** - Requires many additional packages and build tools

## ✅ Recommended Solution: Use System Packages

The best approach is to use the pre-built packages that come with Raspberry Pi OS:

### Step 1: Install System Packages

```bash
sudo apt update
sudo apt install -y \
    python3-pyaudio \
    python3-rpi.gpio \
    python3-requests \
    python3-numpy \
    python3-pip
```

These are pre-compiled for your exact Python version and architecture.

### Step 2: Create Virtual Environment with System Packages

```bash
# Use --system-site-packages to access system Python packages
python3 -m venv --system-site-packages ~/venvs/pi
source ~/venvs/pi/bin/activate
```

The `--system-site-packages` flag allows your virtual environment to use the system-installed packages while still maintaining isolation.

### Step 3: Install Remaining Packages

```bash
# Only install packages not available as system packages
pip install python-dotenv pathlib2
```

### Step 4: Verify Installation

```bash
python3 -c "import pyaudio; print('PyAudio:', pyaudio.__version__)"
python3 -c "import RPi.GPIO; print('RPi.GPIO: OK')"
python3 -c "import numpy; print('Numpy:', numpy.__version__)"
python3 -c "import requests; print('Requests:', requests.__version__)"
python3 -c "import dotenv; print('python-dotenv: OK')"
```

All should print without errors.

## 🔧 Alternative Solutions

### Option 1: Downgrade Python (Not Recommended)

You could try to install Python 3.11, but this is difficult on Pi Zero 2 W:

**Why not recommended:**
- Requires compiling Python from source (30+ minutes)
- Uses significant memory during compilation
- May conflict with system Python
- Complex to maintain

### Option 2: Use Docker (Not Practical for Pi Zero 2 W)

Docker could provide a consistent environment, but:
- Pi Zero 2 W has limited resources
- Docker adds overhead
- More complex setup
- Slower performance

### Option 3: Build with Swap (Last Resort)

If you absolutely must compile from source:

```bash
# Increase swap space temporarily
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile
# Change CONF_SWAPSIZE=100 to CONF_SWAPSIZE=1024
sudo dphys-swapfile setup
sudo dphys-swapfile swapon

# Install build dependencies
sudo apt install -y \
    python3-dev \
    portaudio19-dev \
    libatlas-base-dev \
    gfortran \
    libopenblas-dev

# Try to install (this will take 30-60 minutes)
pip install pyaudio numpy

# Reduce swap back after installation
sudo nano /etc/dphys-swapfile
# Change back to CONF_SWAPSIZE=100
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

**Warning:** This is slow, may fail, and wears out SD card faster.

## 📋 Package Availability

| Package | System Package | Pip Install | Notes |
|---------|---------------|-------------|-------|
| PyAudio | `python3-pyaudio` | ❌ Fails on 3.13 | Use system package |
| RPi.GPIO | `python3-rpi.gpio` | ⚠️ May work | System package safer |
| numpy | `python3-numpy` | ❌ Slow to compile | Use system package |
| requests | `python3-requests` | ✅ Works | Either method works |
| python-dotenv | N/A | ✅ Works | Only pip available |
| pathlib2 | N/A | ✅ Works | Only pip available |

## 🐛 Troubleshooting

### Error: "No module named 'pyaudio'"

**Problem:** PyAudio not installed or not accessible

**Solution:**
```bash
# Install system package
sudo apt install python3-pyaudio

# Recreate venv with system packages
rm -rf ~/venvs/pi
python3 -m venv --system-site-packages ~/venvs/pi
source ~/venvs/pi/bin/activate

# Test
python3 -c "import pyaudio; print('OK')"
```

### Error: "Failed building wheel for pyaudio"

**Problem:** Trying to compile PyAudio from source

**Solution:** Don't compile it! Use system package instead:
```bash
sudo apt install python3-pyaudio
```

### Error: "Killed" during pip install

**Problem:** Out of memory during compilation

**Solution:** Use system packages instead of compiling:
```bash
sudo apt install python3-numpy python3-pyaudio
```

### ImportError in Virtual Environment

**Problem:** Virtual environment can't see system packages

**Solution:** Recreate with `--system-site-packages`:
```bash
rm -rf ~/venvs/pi
python3 -m venv --system-site-packages ~/venvs/pi
```

## ✅ Verification Checklist

After installation, verify everything works:

```bash
# Activate environment
source ~/venvs/pi/bin/activate

# Test all imports
python3 << 'EOF'
import sys
print(f"Python version: {sys.version}")

import pyaudio
print(f"✓ PyAudio: {pyaudio.__version__}")

import RPi.GPIO as GPIO
print(f"✓ RPi.GPIO: OK")

import numpy as np
print(f"✓ NumPy: {np.__version__}")

import requests
print(f"✓ Requests: {requests.__version__}")

from dotenv import load_dotenv
print(f"✓ python-dotenv: OK")

print("\n✅ All dependencies installed successfully!")
EOF
```

## 📝 Summary

**Best Practice for Raspberry Pi Zero 2 W:**

1. ✅ Use system packages for PyAudio, RPi.GPIO, numpy, requests
2. ✅ Create venv with `--system-site-packages` flag
3. ✅ Only pip install python-dotenv and pathlib2
4. ❌ Don't try to compile PyAudio or numpy from source
5. ❌ Don't try to downgrade Python

This approach:
- **Fast**: No compilation needed
- **Reliable**: Pre-tested packages
- **Memory-efficient**: No build process
- **Maintainable**: Easy to update

## 🔗 Related Documentation

- [PyAudio Installation Issues](https://people.csail.mit.edu/hubert/pyaudio/)
- [Raspberry Pi Python Packages](https://www.raspberrypi.org/documentation/linux/software/python.md)
- [Virtual Environments](https://docs.python.org/3/library/venv.html)

---

**TL;DR:** Use `python3 -m venv --system-site-packages` and install system packages with `apt install python3-pyaudio python3-numpy` instead of trying to compile from source.
