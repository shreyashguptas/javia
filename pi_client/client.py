#!/usr/bin/env python3
"""
Raspberry Pi Voice Assistant Client
Records audio, sends to server for processing, plays response
"""

import sys
import time
import subprocess
import logging

# Configure logging FIRST (before any other imports)
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',  # Clean format matching our existing output style
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

# Import configuration
import config

# Import utilities
from utils.system_utils import suppress_alsa_errors, optimize_system_performance

# Import hardware management
from hardware.gpio_manager import GPIOManager

# Import audio modules
from audio.beep_generator import BeepGenerator
from audio.recorder import record_audio
from audio.i2s_player import I2SPlayer

# Import network
from network.api_client import APIClient

# Import OTA Update system
from device_manager import DeviceManager
from activity_tracker import ActivityTracker
from update_manager import UpdateManager
from heartbeat_manager import HeartbeatManager

# Suppress ALSA warnings (must be done before any audio initialization)
suppress_alsa_errors()

# ==================== INITIALIZATION ====================

def setup():
    """Initialize the system with performance optimizations"""
    logger.info("\n" + "="*50)
    logger.info("Raspberry Pi Voice Assistant Client Starting...")
    logger.info("="*50 + "\n")
    
    # Optimize system performance first
    optimize_system_performance()

    # PERFORMANCE DIAGNOSTIC: Check WiFi power management status
    # WiFi power save mode can add 3000ms+ delays to network requests
    try:
        result = subprocess.run(['iwconfig'], capture_output=True, text=True, timeout=5)
        if 'Power Management:on' in result.stdout:
            logger.warning("\n" + "!"*50)
            logger.warning("⚠️  WARNING: WiFi power management is ENABLED")
            logger.warning("⚠️  This may cause 3000ms+ delays in network requests!")
            logger.warning("⚠️  ")
            logger.warning("⚠️  To disable temporarily:")
            logger.warning("⚠️    sudo iw dev wlan0 set power_save off")
            logger.warning("⚠️  ")
            logger.warning("⚠️  To make persistent, add to /etc/rc.local:")
            logger.warning("⚠️    iw dev wlan0 set power_save off")
            logger.warning("!"*50 + "\n")
        elif config.VERBOSE_OUTPUT and 'Power Management:off' in result.stdout:
            logger.info("[WIFI] ✓ WiFi power management is disabled (optimal)")
    except FileNotFoundError:
        # iwconfig not available (might be using Ethernet or newer tools)
        pass
    except Exception as e:
        if config.VERBOSE_OUTPUT:
            logger.debug(f"[WIFI] Could not check power management: {e}")

    # Initialize OTA update system
    logger.info("\n[INIT] Initializing OTA update system...")
    
    try:
        # Initialize device manager (no API key needed - device auth is via UUID)
        config.device_manager = DeviceManager(
            server_url=config.SERVER_URL,
            api_key=None,  # Not needed - device authentication uses device UUID
            timezone=config.DEVICE_TIMEZONE
        )
        if config.VERBOSE_OUTPUT:
            logger.info(f"[INIT] ✓ Device UUID: {config.device_manager.get_device_uuid()}")
            logger.info(f"[INIT] ✓ Current version: {config.device_manager.get_current_version()}")
        
        # Note: Device registration is now done manually on the server via register_device.sh
        # The device must be registered before it can make requests to the server
        
        # Initialize activity tracker
        config.activity_tracker = ActivityTracker()
        if config.VERBOSE_OUTPUT:
            logger.info("[INIT] ✓ Activity tracker initialized")

        # Initialize heartbeat manager (sends ping every 5 minutes)
        config.heartbeat_manager = HeartbeatManager(
            device_manager=config.device_manager,
            interval_seconds=300  # 5 minutes
        )
        config.heartbeat_manager.start()
        if config.VERBOSE_OUTPUT:
            logger.info("[INIT] ✓ Heartbeat manager started (5-minute interval)")

        # Initialize update manager
        config.update_manager = UpdateManager(
            server_url=config.SERVER_URL,
            api_key=None,  # Not needed - device authentication uses device UUID
            device_uuid=config.device_manager.get_device_uuid()
        )
        if config.VERBOSE_OUTPUT:
            logger.info("[INIT] ✓ Update manager initialized (OTA updates enabled)")
    except Exception as e:
        logger.warning(f"[INIT] ⚠️  OTA system initialization failed: {e}")
        logger.warning("[INIT] Continuing without OTA updates...")
    
    # Create audio directory
    config.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"[INIT] Audio directory: {config.AUDIO_DIR}")
    
    # Clean up old recordings (but keep beep files)
    try:
        if config.RECORDING_FILE.exists():
            config.RECORDING_FILE.unlink()
        if config.RESPONSE_FILE.exists():
            config.RESPONSE_FILE.unlink()
        logger.info(f"[INIT] Cleaned up old audio files")
    except Exception as e:
        logger.warning(f"[INIT] Could not clean old files: {e}")
    
    # Initialize hardware (GPIO, buttons, encoder, amplifier)
    logger.info("\n[INIT] Initializing hardware...")
    
    # Initialize beep generator first (needed by GPIO manager)
    logger.info("\n[INIT] Setting up audio feedback beeps...")
    beep_generator = BeepGenerator(gpio_manager=None)  # Will be set after GPIO init
    beep_generator.generate_beep_sounds()
    
    # Initialize GPIO manager with beep generator for immediate feedback
    gpio_manager = GPIOManager(activity_tracker=config.activity_tracker, beep_generator=beep_generator)
    
    # Update beep generator with gpio_manager reference
    beep_generator.gpio_manager = gpio_manager
    
    # Verify beep files exist
    if config.START_BEEP_FILE.exists() and config.STOP_BEEP_FILE.exists():
        logger.info(f"[INIT] ✓ Beep files ready:")
        logger.info(f"[INIT]   - Start: {config.START_BEEP_FILE}")
        logger.info(f"[INIT]   - Stop:  {config.STOP_BEEP_FILE}")
    else:
        logger.warning(f"[WARNING] Beep files missing! Audio feedback disabled.")
    
    # Initialize audio player
    audio_player = I2SPlayer(gpio_manager)
    
    # Initialize API client
    api_client = APIClient(config.device_manager)
    
    # Check server URL
    if config.SERVER_URL == "http://localhost:8000":
        logger.warning("\n[WARNING] Using default server URL (localhost:8000)")
        logger.warning("[WARNING] Please set SERVER_URL in .env for production use")
    
    logger.info(f"[INIT] Server URL: {config.SERVER_URL}")
    
    # Test audio devices (only if verbose)
    if config.VERBOSE_OUTPUT:
        logger.info("\n[INIT] Checking audio devices...")
        try:
            result = subprocess.run(['arecord', '-l'],
                                  capture_output=True, text=True, check=True)
            logger.info("[INIT] Recording devices found:")
            logger.info(result.stdout)
        except Exception as e:
            logger.warning(f"[WARNING] Could not list recording devices: {e}")

        try:
            result = subprocess.run(['aplay', '-l'],
                                  capture_output=True, text=True, check=True)
            logger.info("[INIT] Playback devices found:")
            logger.info(result.stdout)
        except Exception as e:
            logger.warning(f"[WARNING] Could not list playback devices: {e}")
    
    logger.info("\n[READY] System ready! Press button to start...\n")
    
    return gpio_manager, beep_generator, audio_player, api_client


# ==================== MAIN LOOP ====================

def main():
    """Main program loop"""
    try:
        # Setup all components
        gpio_manager, beep_generator, audio_player, api_client = setup()
        
        logger.info("\n[INFO] Voice assistant ready. Heartbeat sends ping every 5 minutes.")
        logger.info("[INFO] Updates: Applied immediately before processing each query\n")
        
        while True:
            # Wait for button press (plays start beep automatically)
            gpio_manager.wait_for_button_press()
            
            # Check for updates BEFORE processing query (mandatory)
            if hasattr(config, 'update_manager') and config.update_manager:
                try:
                    if config.update_manager.apply_update_if_available():
                        # Update is being applied, device will restart
                        logger.info("[UPDATE] Update detected! Installing now...")
                        logger.info("[UPDATE] Device will restart automatically...")
                        # This code won't be reached as device will restart
                        sys.exit(0)
                except Exception as e:
                    logger.warning(f"[UPDATE] Update check failed: {e}")
            
            logger.info("\n" + "="*50)
            logger.info("STARTING CONVERSATION")
            logger.info("="*50 + "\n")

            # OPTIMIZATION: Pre-warm context on server (saves 200-500ms from critical path)
            # Call /prepare endpoint to fetch and cache context while user is speaking
            try:
                session_id = api_client.prepare_context()
                if session_id:
                    config.save_session_id(session_id)
            except Exception as e:
                logger.warning(f"[PREPARE] Pre-warm failed: {e}, continuing anyway")

            # Step 1: Record (plays stop beep automatically)
            logger.info("[STEP 1/3] Recording audio...")
            if not record_audio(gpio_manager, beep_generator):
                logger.error("[ERROR] Recording failed. Restarting...")
                time.sleep(2)
                continue
            
            # Step 2: Send to server
            logger.info("\n[STEP 2/3] Processing on server...")
            if not api_client.send_audio_to_server():
                logger.error("[ERROR] Server processing failed. Restarting...")
                time.sleep(2)
                continue
            
            # Step 3: Play
            logger.info("\n[STEP 3/3] Playing response...")
            playback_completed = audio_player.play(config.RESPONSE_FILE)
            
            if playback_completed:
                logger.info("\n[COMPLETE] Conversation complete!")
                logger.info("="*50 + "\n")
                time.sleep(1)
            else:
                logger.info("\n[INTERRUPT] Waiting for next button press...")
                logger.info("="*50 + "\n")
                time.sleep(0.5)
            
    except KeyboardInterrupt:
        logger.info("\n\n[EXIT] Shutting down...")
    finally:
        # Stop heartbeat manager
        if hasattr(config, 'heartbeat_manager') and config.heartbeat_manager:
            config.heartbeat_manager.stop()
            logger.info("[EXIT] Heartbeat manager stopped")
        
        # Close GPIO devices
        gpio_manager.cleanup()


if __name__ == "__main__":
    main()
