#!/usr/bin/env python3
"""
GPIO Manager for Pi Voice Assistant Client
Manages button, rotary encoder, and amplifier hardware
"""

import time
import threading
from gpiozero import Button, OutputDevice, RotaryEncoder
import config


class GPIOManager:
    """
    Manages all GPIO hardware for the voice assistant.
    
    Handles:
    - Rotary encoder button (for recording start/stop)
    - Rotary encoder (for volume control)
    - Amplifier shutdown pin
    - Volume state management
    """
    
    def __init__(self, activity_tracker=None, beep_generator=None):
        """
        Initialize GPIO hardware.
        
        Args:
            activity_tracker: Optional ActivityTracker instance for recording button presses
            beep_generator: Optional BeepGenerator instance for audio feedback
        """
        self.activity_tracker = activity_tracker
        self.beep_generator = beep_generator
        self.current_volume = config.INITIAL_VOLUME
        
        # Initialize GPIO objects
        self.button = None
        self.rotary_encoder = None
        self.amplifier_sd = None
        
        self._setup_gpio()
    
    def _setup_gpio(self):
        """Setup GPIO pins and callbacks"""
        # Setup rotary encoder button (SW pin)
        self.button = Button(config.BUTTON_PIN, pull_up=True, bounce_time=0.05)
        print(f"[INIT] Rotary encoder button (SW) configured on GPIO{config.BUTTON_PIN}")
        
        # Setup rotary encoder for volume control
        self.rotary_encoder = RotaryEncoder(
            config.ROTARY_CLK_PIN, 
            config.ROTARY_DT_PIN, 
            max_steps=0
        )
        print(f"[INIT] Rotary encoder configured: CLK=GPIO{config.ROTARY_CLK_PIN}, DT=GPIO{config.ROTARY_DT_PIN}")
        
        # Setup amplifier shutdown pin (active high means on)
        self.amplifier_sd = OutputDevice(
            config.AMPLIFIER_SD_PIN, 
            active_high=True, 
            initial_value=False
        )
        print(f"[INIT] Amplifier SD pin configured on GPIO{config.AMPLIFIER_SD_PIN}")
        
        # Setup volume control
        print(f"\n[INIT] Setting up software volume control...")
        print(f"[INIT] ✓ Volume control ready: {self.current_volume}% (100% = full volume)")
        print(f"[INIT] ℹ Rotate encoder anytime to adjust volume (even during playback!)")
        
        # Setup rotary encoder callback for volume control
        self.rotary_encoder.when_rotated = self._on_rotate
        print(f"[INIT] ✓ Rotary encoder active: ±{config.VOLUME_STEP}% per step (button + rotation)")
        
        # Update global config reference
        config.button = self.button
        config.rotary_encoder = self.rotary_encoder
        config.amplifier_sd = self.amplifier_sd
        config.current_volume = self.current_volume
    
    def _on_rotate(self):
        """Handle rotary encoder rotation for volume control"""
        steps = self.rotary_encoder.steps
        if steps != 0:
            # Calculate new volume
            volume_change = steps * config.VOLUME_STEP
            new_volume = self.current_volume + volume_change
            
            # Clamp to valid range
            new_volume = max(0, min(100, new_volume))
            
            # Only update if changed
            if new_volume != self.current_volume:
                old_volume = self.current_volume
                self.current_volume = new_volume
                
                # Update global config
                config.current_volume = self.current_volume
                
                # Show volume change
                print(f"[VOLUME] {'↑' if volume_change > 0 else '↓'} {old_volume}% → {self.current_volume}%")
            
            # Reset steps counter
            self.rotary_encoder.steps = 0
    
    def wait_for_button_press(self):
        """
        Wait for button press with instant response.
        
        PERFORMANCE OPTIMIZATION:
        - Beep plays asynchronously (non-blocking)
        - Recording setup happens in parallel with beep
        - Minimal debounce delay
        """
        print("[BUTTON] Waiting for button press to start recording...")
        
        while not self.button.is_pressed:
            time.sleep(0.005)  # Reduced from 0.01 for faster detection
        
        print("[BUTTON] *** BUTTON PRESSED! Starting recording... ***")
        
        # Record activity for update manager
        if self.activity_tracker:
            self.activity_tracker.record_activity("button_press")
        
        # Play start beep asynchronously - doesn't block recording startup
        if self.beep_generator:
            self.beep_generator.play_beep_async(config.START_BEEP_FILE, "start")
        
        time.sleep(0.02)  # Minimal debounce (reduced from 0.05)
    
    def wait_for_button_release(self):
        """Wait for button press again to stop recording"""
        print("[BUTTON] Press button again to stop recording...")
        
        # Wait for button to be released first
        while self.button.is_pressed:
            time.sleep(0.01)
        
        # Now wait for button press again
        while not self.button.is_pressed:
            time.sleep(0.01)
        
        print("[BUTTON] *** BUTTON PRESSED! Stopping recording... ***")
        
        time.sleep(0.05)  # Debounce
        
        # Wait for release
        while self.button.is_pressed:
            time.sleep(0.01)
        
        print("[BUTTON] Released. Processing audio...\n")
    
    def get_current_volume(self):
        """Get current volume level (0-100)"""
        return self.current_volume
    
    def enable_amplifier(self):
        """Enable the audio amplifier"""
        self.amplifier_sd.on()
    
    def disable_amplifier(self):
        """Disable the audio amplifier"""
        self.amplifier_sd.off()
    
    def cleanup(self):
        """Clean up GPIO resources"""
        if self.button:
            self.button.close()
        if self.rotary_encoder:
            self.rotary_encoder.close()
        if self.amplifier_sd:
            self.amplifier_sd.close()
        print("[EXIT] GPIO cleanup complete")

