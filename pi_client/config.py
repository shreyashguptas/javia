#!/usr/bin/env python3
"""
Configuration Module for Pi Voice Assistant Client
Centralizes all configuration constants and environment variables
"""

import os
from pathlib import Path
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
CHANNELS = 1
CHUNK_SIZE = 512  # Reduced from 1024 for lower latency (5.3ms vs 10.6ms per chunk)
MICROPHONE_GAIN = float(os.getenv('MICROPHONE_GAIN', '2.0'))  # 2.0x gain reaches ~100% of max (perfect for Whisper)
FADE_DURATION_MS = int(os.getenv('FADE_DURATION_MS', '50'))

# ==================== VOLUME CONFIGURATION ====================

# Volume Control Settings
VOLUME_STEP = int(os.getenv('VOLUME_STEP', '5'))  # Volume change per rotary encoder step (%)
INITIAL_VOLUME = int(os.getenv('INITIAL_VOLUME', '100'))  # Initial volume on startup (%)
VERBOSE_OUTPUT = os.getenv('VERBOSE_OUTPUT', 'true').lower() == 'true'  # Control verbose logging

# ==================== FILE PATHS ====================

# Audio Directory and File Paths
AUDIO_DIR = Path(os.path.expanduser("~/javia/audio"))
RECORDING_FILE = AUDIO_DIR / "recording.wav"
RECORDING_OPUS_FILE = AUDIO_DIR / "recording.opus"
RESPONSE_OPUS_FILE = AUDIO_DIR / "response.opus"
RESPONSE_FILE = AUDIO_DIR / "response.wav"
START_BEEP_FILE = AUDIO_DIR / "start_beep.wav"
STOP_BEEP_FILE = AUDIO_DIR / "stop_beep.wav"

# ==================== GLOBAL STATE ====================
# Note: These are initialized by the main client and hardware modules

# Performance optimizations: Caching
_CACHED_AUDIO_DEVICE_INDEX = None

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

