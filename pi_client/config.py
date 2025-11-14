#!/usr/bin/env python3
"""
Configuration Module for Pi Voice Assistant Client
Centralizes all configuration constants and environment variables
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ==================== SERVER CONFIGURATION ====================

# Server Configuration
SERVER_URL = os.getenv('SERVER_URL', 'http://localhost:8000')
# Device authentication uses unique UUID (X-Device-UUID header), not API keys

# ==================== OTA UPDATE CONFIGURATION ====================

# OTA Update Configuration
DEVICE_TIMEZONE = os.getenv('DEVICE_TIMEZONE', 'UTC')
SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')

# ==================== GPIO CONFIGURATION ====================

# GPIO Pin Assignments
BUTTON_PIN = int(os.getenv('BUTTON_PIN', '17'))  # Rotary encoder SW pin
ROTARY_CLK_PIN = int(os.getenv('ROTARY_CLK_PIN', '22'))  # Rotary encoder CLK pin
ROTARY_DT_PIN = int(os.getenv('ROTARY_DT_PIN', '23'))  # Rotary encoder DT pin
AMPLIFIER_SD_PIN = int(os.getenv('AMPLIFIER_SD_PIN', '27'))

# ==================== AUDIO CONFIGURATION ====================

# Audio Format Settings
SAMPLE_RATE = int(os.getenv('SAMPLE_RATE', '48000'))
CHANNELS = 2  # Stereo: 2x INMP441 microphones (L/R channels)
CHUNK_SIZE = 512  # Reduced from 1024 for lower latency (5.3ms vs 10.6ms per chunk)
MICROPHONE_GAIN = float(os.getenv('MICROPHONE_GAIN', '1.0'))  # No gain needed - INMP441 outputs 70-80% signal naturally
FADE_DURATION_MS = int(os.getenv('FADE_DURATION_MS', '0'))  # Disabled by default for performance
SILENCE_PADDING_MS = int(os.getenv('SILENCE_PADDING_MS', '0'))  # 0ms default

# Opus upload settings
OPUS_TARGET_SAMPLE_RATE = int(os.getenv('OPUS_TARGET_SAMPLE_RATE', '24000'))  # 24kHz optimized for speech
OPUS_TARGET_CHANNELS = 1  # mono
OPUS_BITRATE = int(os.getenv('OPUS_BITRATE', '64000'))  # 64kbps

# ==================== VOLUME CONFIGURATION ====================

# Volume Control Settings
VOLUME_STEP = int(os.getenv('VOLUME_STEP', '5'))  # Volume change per rotary encoder step (%)
INITIAL_VOLUME = int(os.getenv('INITIAL_VOLUME', '50'))  # Default volume on first boot (50%)
VERBOSE_OUTPUT = os.getenv('VERBOSE_OUTPUT', 'false').lower() == 'true'  # Control verbose logging

# Volume persistence file
VOLUME_FILE = Path(os.path.expanduser("~/.javia/volume"))

# ==================== FILE PATHS ====================

# Audio Directory and File Paths
# Prefer RAM-backed storage for low-latency temp files
_RAM_DIR = Path("/dev/shm/javia")
_HOME_DIR = Path(os.path.expanduser("~/javia/audio"))
if _RAM_DIR.parent.exists():
    try:
        _RAM_DIR.mkdir(parents=True, exist_ok=True)
        AUDIO_DIR = _RAM_DIR
    except Exception:
        AUDIO_DIR = _HOME_DIR
        AUDIO_DIR.mkdir(parents=True, exist_ok=True)
else:
    AUDIO_DIR = _HOME_DIR
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
RECORDING_FILE = AUDIO_DIR / "recording.wav"
RECORDING_OPUS_FILE = AUDIO_DIR / "recording.opus"
RESPONSE_FILE = AUDIO_DIR / "response.wav"
START_BEEP_FILE = AUDIO_DIR / "start_beep.wav"
STOP_BEEP_FILE = AUDIO_DIR / "stop_beep.wav"

# Session management
SESSION_FILE = Path(os.path.expanduser("~/.javia/session_id"))

# ==================== GLOBAL STATE ====================
# Note: These are initialized by the main client and hardware modules

# Telemetry: timestamps for latency spans (set by recorder/api client)
LAST_RECORD_END_TS = None  # time.time() when recording fully stops and file saved

# GPIO objects (initialized in hardware.gpio_manager)
button = None
rotary_encoder = None
amplifier_sd = None

# Volume state (managed by hardware.gpio_manager)
current_volume = INITIAL_VOLUME

# OTA Update managers (initialized in client setup)
device_manager = None
activity_tracker = None
update_manager = None


# ==================== SESSION MANAGEMENT HELPERS ====================

def get_session_id() -> Optional[str]:
    """
    Read session ID from persistent storage.
    
    Returns:
        Session ID string if found, None otherwise
    """
    try:
        if SESSION_FILE.exists():
            session_id = SESSION_FILE.read_text().strip()
            if session_id:
                return session_id
    except (OSError, IOError) as e:
        # Fail silently - session management is non-critical
        if VERBOSE_OUTPUT:
            print(f"[DEBUG] Failed to read session ID: {e}")
    return None


def save_session_id(session_id: str) -> bool:
    """
    Save session ID to persistent storage.
    
    Args:
        session_id: Session ID string to save
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure directory exists
        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        SESSION_FILE.write_text(session_id.strip())
        return True
    except (OSError, IOError) as e:
        # Fail silently - session management is non-critical
        if VERBOSE_OUTPUT:
            print(f"[DEBUG] Failed to save session ID: {e}")
        return False


# ==================== VOLUME PERSISTENCE HELPERS ====================

def load_volume() -> int:
    """
    Load volume from persistent storage.
    
    Returns:
        Volume level (0-100). Returns 50% if file doesn't exist (first boot).
    """
    try:
        if VOLUME_FILE.exists():
            volume_str = VOLUME_FILE.read_text().strip()
            volume = int(volume_str)
            # Clamp to valid range
            volume = max(0, min(100, volume))
            if VERBOSE_OUTPUT:
                print(f"[VOLUME] Loaded persisted volume: {volume}%")
            return volume
    except (OSError, IOError, ValueError) as e:
        # Fail silently - use default volume
        if VERBOSE_OUTPUT:
            print(f"[DEBUG] Failed to load volume: {e}")
    
    # First boot - return 50% as default (regardless of INITIAL_VOLUME env var)
    return 50


def save_volume(volume: int) -> bool:
    """
    Save volume to persistent storage.
    
    Args:
        volume: Volume level (0-100) to save
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure directory exists
        VOLUME_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Clamp to valid range
        volume = max(0, min(100, volume))
        
        # Save volume
        VOLUME_FILE.write_text(str(volume))
        
        # Secure the file (read/write by owner only)
        os.chmod(VOLUME_FILE, 0o600)
        
        return True
    except (OSError, IOError) as e:
        # Fail silently - volume persistence is non-critical
        if VERBOSE_OUTPUT:
            print(f"[DEBUG] Failed to save volume: {e}")
        return False

