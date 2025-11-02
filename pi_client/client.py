#!/usr/bin/env python3
"""
Raspberry Pi Voice Assistant Client
Records audio, sends to server for processing, plays response
"""

import os

# Suppress JACK server startup attempts (must be set before importing pyaudio)
os.environ['JACK_NO_START_SERVER'] = '1'
os.environ['JACK_NO_AUDIO_RESERVATION'] = '1'

import sys
import time
import subprocess
import pyaudio

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
    print("\n" + "="*50)
    print("Raspberry Pi Voice Assistant Client Starting...")
    print("="*50 + "\n")
    
    # Optimize system performance first
    optimize_system_performance()
    
    # Initialize OTA update system
    print("\n[INIT] Initializing OTA update system...")
    
    try:
        # Initialize device manager (no API key needed - device auth is via UUID)
        config.device_manager = DeviceManager(
            server_url=config.SERVER_URL,
            api_key=None,  # Not needed - device authentication uses device UUID
            timezone=config.DEVICE_TIMEZONE
        )
        print(f"[INIT] ✓ Device UUID: {config.device_manager.get_device_uuid()}")
        print(f"[INIT] ✓ Current version: {config.device_manager.get_current_version()}")
        
        # Note: Device registration is now done manually on the server via register_device.sh
        # The device must be registered before it can make requests to the server
        
        # Initialize activity tracker
        config.activity_tracker = ActivityTracker()
        print("[INIT] ✓ Activity tracker initialized")
        
        # Initialize heartbeat manager (sends ping every 5 minutes)
        config.heartbeat_manager = HeartbeatManager(
            device_manager=config.device_manager,
            interval_seconds=300  # 5 minutes
        )
        config.heartbeat_manager.start()
        print("[INIT] ✓ Heartbeat manager started (5-minute interval)")
        
        # Initialize update manager if Supabase is configured
        if config.SUPABASE_URL and config.SUPABASE_KEY:
            config.update_manager = UpdateManager(
                server_url=config.SERVER_URL,
                api_key=None,  # Not needed - device authentication uses device UUID
                device_uuid=config.device_manager.get_device_uuid(),
                timezone_str=config.DEVICE_TIMEZONE,
                activity_tracker=config.activity_tracker,
                supabase_url=config.SUPABASE_URL,
                supabase_key=config.SUPABASE_KEY
            )
            config.update_manager.start()
            print("[INIT] ✓ Update manager started (OTA updates enabled)")
        else:
            print("[INIT] ℹ Supabase not configured - OTA updates disabled")
    except Exception as e:
        print(f"[INIT] ⚠️  OTA system initialization failed: {e}")
        print("[INIT] Continuing without OTA updates...")
    
    # Create audio directory
    config.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[INIT] Audio directory: {config.AUDIO_DIR}")
    
    # Clean up old recordings (but keep beep files)
    try:
        if config.RECORDING_FILE.exists():
            config.RECORDING_FILE.unlink()
        if config.RESPONSE_FILE.exists():
            config.RESPONSE_FILE.unlink()
        print(f"[INIT] Cleaned up old audio files")
    except Exception as e:
        print(f"[INIT] Could not clean old files: {e}")
    
    # Initialize hardware (GPIO, buttons, encoder, amplifier)
    print("\n[INIT] Initializing hardware...")
    gpio_manager = GPIOManager(activity_tracker=config.activity_tracker)
    
    # Initialize beep generator
    print("\n[INIT] Setting up audio feedback beeps...")
    beep_generator = BeepGenerator(gpio_manager)
    beep_generator.generate_beep_sounds()
    
    # Verify beep files exist
    if config.START_BEEP_FILE.exists() and config.STOP_BEEP_FILE.exists():
        print(f"[INIT] ✓ Beep files ready:")
        print(f"[INIT]   - Start: {config.START_BEEP_FILE}")
        print(f"[INIT]   - Stop:  {config.STOP_BEEP_FILE}")
    else:
        print(f"[WARNING] Beep files missing! Audio feedback disabled.")
    
    # Initialize audio player
    audio_player = I2SPlayer(gpio_manager)
    
    # Initialize API client
    api_client = APIClient(config.device_manager)
    
    # Check server URL
    if config.SERVER_URL == "http://localhost:8000":
        print("\n[WARNING] Using default server URL (localhost:8000)")
        print("[WARNING] Please set SERVER_URL in .env for production use")
    
    print(f"[INIT] Server URL: {config.SERVER_URL}")
    
    # Test audio devices
    print("\n[INIT] Checking audio devices...")
    try:
        result = subprocess.run(['arecord', '-l'], 
                              capture_output=True, text=True, check=True)
        print("[INIT] Recording devices found:")
        print(result.stdout)
    except Exception as e:
        print(f"[WARNING] Could not list recording devices: {e}")
    
    try:
        result = subprocess.run(['aplay', '-l'], 
                              capture_output=True, text=True, check=True)
        print("[INIT] Playback devices found:")
        print(result.stdout)
    except Exception as e:
        print(f"[WARNING] Could not list playback devices: {e}")
    
    print("\n[READY] System ready! Press button to start...\n")
    
    return gpio_manager, beep_generator, audio_player, api_client


# ==================== MAIN LOOP ====================

def main():
    """Main program loop"""
    try:
        # Setup all components
        gpio_manager, beep_generator, audio_player, api_client = setup()
        
        print("\n[INFO] Voice assistant ready. OTA updates running in background.")
        print("[INFO] Heartbeat: Sending status ping every 5 minutes")
        print("[INFO] Updates: Instant (if online), Nightly at 2 AM, or Urgent after 1 hour inactivity\n")
        
        while True:
            # Wait for button press
            gpio_manager.wait_for_button_press()
            
            # Play start beep
            beep_generator.play_beep_async(config.START_BEEP_FILE, "start")
            
            print("\n" + "="*50)
            print("STARTING CONVERSATION")
            print("="*50 + "\n")
            
            # Step 1: Record
            print("[STEP 1/3] Recording audio...")
            if not record_audio(gpio_manager):
                print("[ERROR] Recording failed. Restarting...")
                time.sleep(2)
                continue
            
            # Play stop beep after recording
            beep_generator.play_beep_async(config.STOP_BEEP_FILE, "stop")
            
            # Step 2: Send to server
            print("\n[STEP 2/3] Processing on server...")
            if not api_client.send_audio_to_server():
                print("[ERROR] Server processing failed. Restarting...")
                time.sleep(2)
                continue
            
            # Step 3: Play
            print("\n[STEP 3/3] Playing response...")
            playback_completed = audio_player.play(config.RESPONSE_FILE)
            
            if playback_completed:
                print("\n[COMPLETE] Conversation complete!")
                print("="*50 + "\n")
                time.sleep(1)
            else:
                print("\n[INTERRUPT] Waiting for next button press...")
                print("="*50 + "\n")
                time.sleep(0.5)
            
    except KeyboardInterrupt:
        print("\n\n[EXIT] Shutting down...")
    finally:
        # Stop heartbeat manager
        if hasattr(config, 'heartbeat_manager') and config.heartbeat_manager:
            config.heartbeat_manager.stop()
            print("[EXIT] Heartbeat manager stopped")
        
        # Stop update manager
        if hasattr(config, 'update_manager') and config.update_manager:
            config.update_manager.stop()
            print("[EXIT] Update manager stopped")
        
        # Close GPIO devices
        gpio_manager.cleanup()


if __name__ == "__main__":
    main()
