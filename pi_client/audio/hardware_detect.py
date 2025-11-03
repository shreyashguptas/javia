#!/usr/bin/env python3
"""
Hardware Detection Module for Pi Voice Assistant Client
Centralized hardware detection to determine audio device capabilities
"""

import subprocess
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Cache detection result to avoid repeated subprocess calls
_hardware_type_cache: Optional[str] = None


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
        return _hardware_type_cache
    
    try:
        # Run arecord -l to list capture devices
        result = subprocess.run(
            ['arecord', '-l'], 
            capture_output=True, 
            text=True,
            timeout=2
        )
        
        output = result.stdout.lower()
        
        # Check for googlevoicehat driver indicators
        is_voicehat = (
            'googlevoicehat' in output or 
            'sndrpigooglevoi' in output or
            'google voicehat' in output
        )
        
        if is_voicehat:
            _hardware_type_cache = "googlevoicehat"
            logger.info("Detected googlevoicehat audio hardware")
        else:
            _hardware_type_cache = "other"
            logger.info("Detected non-googlevoicehat audio hardware")
        
        return _hardware_type_cache
        
    except Exception as e:
        logger.warning(f"Could not detect audio hardware: {e}")
        # Default to "other" on detection failure
        _hardware_type_cache = "other"
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
    hardware_type = detect_audio_hardware()
    
    if hardware_type == "googlevoicehat":
        return "plughw:CARD=sndrpigooglevoi,DEV=0"
    else:
        # Default ALSA device
        return "default"


def reset_cache():
    """Reset the hardware detection cache (for testing)"""
    global _hardware_type_cache
    _hardware_type_cache = None

