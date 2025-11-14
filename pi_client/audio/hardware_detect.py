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
    - googlevoicehat: Uses ALSA tools (arecord/aplay) and pyalsaaudio
    - other: Uses ALSA tools and pyalsaaudio
    
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
            logger.info("[HW DETECT] Using arecord for recording, pyalsaaudio for playback")
        else:
            _hardware_type_cache = "other"
            logger.info("[HW DETECT] ✓ Detected non-googlevoicehat audio hardware")
            logger.info("[HW DETECT] Using arecord for recording, pyalsaaudio for playback")
        
        return _hardware_type_cache
        
    except Exception as e:
        logger.warning(f"[HW DETECT] Could not detect audio hardware: {e}")
        # Default to "other" on detection failure
        _hardware_type_cache = "other"
        logger.info("[HW DETECT] Defaulting to 'other' hardware type")
        return _hardware_type_cache


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


def get_pyalsaaudio_device_name() -> Optional[str]:
    """
    Get the ALSA device name in pyalsaaudio-compatible format.
    
    pyalsaaudio accepts:
    - None for default device
    - "hw:X,Y" for card X, device Y
    - "plughw:X,Y" for card X, device Y with plug conversion
    
    Returns:
        str or None: Device name compatible with pyalsaaudio, or None for default
    """
    device_name = get_alsa_device_name()
    
    # Extract card and device numbers from device name
    # Format: "plughw:CARD=sndrpigooglevoi,DEV=0" or "hw:CARD=...,DEV=..."
    if device_name.startswith("plughw:CARD=") or device_name.startswith("hw:CARD="):
        # Extract device number
        if ",DEV=" in device_name:
            dev_part = device_name.split(",DEV=")[1]
            try:
                dev_num = int(dev_part)
                # For googlevoicehat, card is always 0 (from logs: card 0)
                # Try plughw first (with format conversion), then hw
                return f"plughw:0,{dev_num}"
            except ValueError:
                pass
    
    # For "default" or unrecognized formats, use None (ALSA default)
    if device_name == "default":
        return None
    
    # If we can't parse it, try None (default device)
    # This should work if ALSA default is correctly configured
    return None
