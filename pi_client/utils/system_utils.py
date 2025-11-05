#!/usr/bin/env python3
"""
System Utilities for Pi Voice Assistant Client
ALSA error suppression, CPU optimization, and audio processing utilities
"""

import subprocess
import numpy as np
from ctypes import *

# ==================== ALSA ERROR SUPPRESSION ====================

def suppress_alsa_errors():
    """
    Suppress ALSA error messages that clutter the console.
    Must be called before any ALSA operations.
    """
    ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)
    
    def py_error_handler(filename, line, function, err, fmt):
        """Suppress ALSA error messages"""
        pass
    
    c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)
    
    try:
        asound = cdll.LoadLibrary('libasound.so.2')
        asound.snd_lib_error_set_handler(c_error_handler)
    except (OSError, AttributeError):
        # ALSA library not available - non-critical, continue without error suppression
        pass


# ==================== SYSTEM PERFORMANCE ====================

def optimize_system_performance():
    """
    Optimize Raspberry Pi system performance for real-time audio.
    
    PERFORMANCE OPTIMIZATIONS:
    - Sets CPU governor to 'performance' mode (max frequency)
    - Reduces system latency for audio processing
    - Based on Linux audio wiki recommendations
    """
    try:
        # Try to set CPU governor to performance mode
        result = subprocess.run(
            ['sudo', 'sh', '-c', 
             'echo performance > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'],
            capture_output=True,
            timeout=2
        )
        if result.returncode == 0:
            print("[PERF] ✓ CPU governor set to 'performance' mode")
        else:
            print("[PERF] ℹ Could not set CPU governor (may already be optimized)")
    except Exception:
        print("[PERF] ℹ Running with default CPU settings")


# ==================== AUDIO UTILITIES ====================

def apply_volume_to_audio(audio_data: bytes, volume_percent: int, sample_width: int = 2) -> bytes:
    """
    Apply software volume scaling to audio data.
    
    This is required because the googlevoicehat driver doesn't support hardware volume control.
    Software scaling ensures all audio (beeps and AI speech) respects the volume setting.
    
    Args:
        audio_data: Raw PCM audio data (bytes)
        volume_percent: Volume level 0-100 (%)
        sample_width: Sample width in bytes (default 2 for 16-bit)
    
    Returns:
        Volume-scaled audio data (bytes)
    """
    if volume_percent == 100:
        # No scaling needed
        return audio_data
    
    # Convert volume percentage to linear scale (0.0 - 1.0)
    volume_scale = volume_percent / 100.0
    
    # Convert bytes to numpy array based on sample width
    if sample_width == 2:
        # 16-bit signed integer
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        # Apply volume scaling and clip to prevent distortion
        scaled_array = (audio_array.astype(np.float32) * volume_scale).clip(-32768, 32767).astype(np.int16)
        return scaled_array.tobytes()
    else:
        # Unsupported sample width, return original
        return audio_data

