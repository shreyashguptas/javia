#!/usr/bin/env python3
"""
Hardware Detection Module for Pi Voice Assistant Client
Centralized hardware detection to determine audio device capabilities
"""

import subprocess
import logging
from typing import Optional
import config

logger = logging.getLogger(__name__)

# Cache detection result to avoid repeated subprocess calls
_hardware_type_cache: Optional[str] = None
_device_name_cache: Optional[str] = None


def detect_audio_hardware() -> str:
    """
    Detect the audio hardware type.
    
    This function determines which audio driver is in use so we can
    route to the appropriate audio methods:
    - googlevoicehat: Use aplay/arecord (PyAudio is incompatible)
    - other: Use PyAudio or fallback to aplay/arecord
    
    Returns:
        str: Hardware type - "googlevoicehat" or "other"
    """
    global _hardware_type_cache
    
    # Return cached result if available
    if _hardware_type_cache is not None:
        if config.VERBOSE_OUTPUT:
            logger.info(f"[HW DETECT] Using cached hardware type: {_hardware_type_cache}")
        return _hardware_type_cache
    
    try:
        # Run arecord -l to list capture devices
        logger.info("[HW DETECT] Running 'arecord -l' to detect audio hardware...")
        result = subprocess.run(
            ['arecord', '-l'], 
            capture_output=True, 
            text=True,
            timeout=2
        )
        
        output = result.stdout.lower()
        logger.info(f"[HW DETECT] arecord output:\n{result.stdout}")
        
        # Check for googlevoicehat driver indicators
        is_voicehat = (
            'googlevoicehat' in output or 
            'sndrpigooglevoi' in output or
            'google voicehat' in output
        )
        
        if is_voicehat:
            _hardware_type_cache = "googlevoicehat"
            logger.info("[HW DETECT] ✓ Detected googlevoicehat audio hardware")
            logger.info("[HW DETECT] Will use arecord for recording (PyAudio incompatible)")
        else:
            _hardware_type_cache = "other"
            logger.info("[HW DETECT] ✓ Detected non-googlevoicehat audio hardware")
            logger.info("[HW DETECT] Will use PyAudio with arecord fallback")
        
        return _hardware_type_cache
        
    except Exception as e:
        logger.warning(f"[HW DETECT] Could not detect audio hardware: {e}")
        # Default to "other" on detection failure
        _hardware_type_cache = "other"
        logger.info("[HW DETECT] Defaulting to 'other' hardware type")
        return _hardware_type_cache


def is_googlevoicehat() -> bool:
    """
    Check if the system is using googlevoicehat driver.
    
    The googlevoicehat-soundcard driver has known compatibility issues with PyAudio,
    causing segmentation faults. This function allows code to detect the driver
    and use more reliable ALSA tools (aplay/arecord) instead.
    
    Returns:
        bool: True if googlevoicehat is detected, False otherwise
    """
    return detect_audio_hardware() == "googlevoicehat"


def get_alsa_device_name() -> str:
    """
    Get the ALSA device name for audio operations.

    Returns:
        str: ALSA device name (e.g., 'plughw:CARD=sndrpigooglevoi,DEV=0')
    """
    global _device_name_cache

    # Return cached result if available
    if _device_name_cache is not None:
        if config.VERBOSE_OUTPUT:
            logger.info(f"[HW DETECT] Using ALSA device: {_device_name_cache}")
        return _device_name_cache

    hardware_type = detect_audio_hardware()

    if hardware_type == "googlevoicehat":
        _device_name_cache = "plughw:CARD=sndrpigooglevoi,DEV=0"
    else:
        # Default ALSA device
        _device_name_cache = "default"

    if config.VERBOSE_OUTPUT:
        logger.info(f"[HW DETECT] Using ALSA device: {_device_name_cache}")
    return _device_name_cache


def reset_cache():
    """Reset the hardware detection cache (for testing)"""
    global _hardware_type_cache, _device_name_cache
    _hardware_type_cache = None
    _device_name_cache = None

