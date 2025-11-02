#!/usr/bin/env python3
"""
Beep Generator for Pi Voice Assistant Client
Generates and plays beep sounds for audio feedback
"""

import time
import wave
import threading
import numpy as np
import pyaudio
import config
from utils.system_utils import apply_volume_to_audio


class BeepGenerator:
    """
    Generates pleasant beep sounds for start/stop feedback.
    
    Beeps are generated at full volume and scaled during playback
    based on current volume setting.
    """
    
    def __init__(self, gpio_manager):
        """
        Initialize beep generator.
        
        Args:
            gpio_manager: GPIOManager instance for amplifier control
        """
        self.gpio_manager = gpio_manager
        self.start_beep_file = config.START_BEEP_FILE
        self.stop_beep_file = config.STOP_BEEP_FILE
    
    def generate_beep_sounds(self):
        """
        Generate pleasant beep sounds at FULL VOLUME (100%).
        Volume scaling is applied in real-time during playback via current_volume.
        """
        try:
            sample_rate = config.SAMPLE_RATE  # Match I2S device sample rate (48000 Hz)
            
            # Generate at FULL volume - scaling happens during playback
            beep_volume = 1.0  # ALWAYS 100% - volume control happens at playback time
            
            # Start beep: Short rising tone (600Hz -> 900Hz)
            print("[INIT] Generating start beep sound...")
            duration = 0.1  # 100ms - short and snappy
            num_samples = int(sample_rate * duration)
            t = np.linspace(0, duration, num_samples)
            
            # Frequency sweep from 600Hz to 900Hz
            start_freq = 600
            end_freq = 900
            frequency = np.linspace(start_freq, end_freq, num_samples)
            phase = 2 * np.pi * np.cumsum(frequency) / sample_rate
            
            # Generate tone
            tone = np.sin(phase)
            
            # Generate envelope with exact length matching - quick attack/release
            attack_len = num_samples // 5
            sustain_len = num_samples // 2
            release_len = num_samples - attack_len - sustain_len  # Ensure exact match
            
            envelope = np.concatenate([
                np.linspace(0, 1, attack_len),   # Quick attack
                np.ones(sustain_len),            # Brief sustain
                np.linspace(1, 0, release_len)   # Quick release
            ])
            
            # Apply envelope at FULL volume (100%)
            start_beep = (tone * envelope * beep_volume * 32767).astype(np.int16)
            
            # Save start beep
            with wave.open(str(self.start_beep_file), 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(start_beep.tobytes())
            
            print(f"[INIT] ✓ Start beep saved: {self.start_beep_file} ({len(start_beep) * 2} bytes)")
            
            # Stop beep: Reverse of start (falling tone 900Hz -> 600Hz)
            print("[INIT] Generating stop beep sound...")
            # Use same duration for consistency
            duration = 0.1  # 100ms
            num_samples = int(sample_rate * duration)
            t = np.linspace(0, duration, num_samples)
            
            # Frequency sweep from 900Hz to 600Hz (reverse of start)
            start_freq = 900
            end_freq = 600
            frequency = np.linspace(start_freq, end_freq, num_samples)
            phase = 2 * np.pi * np.cumsum(frequency) / sample_rate
            
            # Generate tone
            tone = np.sin(phase)
            
            # Generate envelope with exact length matching - same as start beep
            attack_len = num_samples // 5
            sustain_len = num_samples // 2
            release_len = num_samples - attack_len - sustain_len  # Ensure exact match
            
            envelope = np.concatenate([
                np.linspace(0, 1, attack_len),   # Quick attack
                np.ones(sustain_len),            # Brief sustain
                np.linspace(1, 0, release_len)   # Quick release
            ])
            
            # Apply envelope and volume
            stop_beep = (tone * envelope * beep_volume * 32767).astype(np.int16)
            
            # Save stop beep
            with wave.open(str(self.stop_beep_file), 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(stop_beep.tobytes())
            
            print(f"[INIT] ✓ Stop beep saved: {self.stop_beep_file} ({len(stop_beep) * 2} bytes)")
            print(f"[INIT] ✓ Beep sounds generated at full volume (volume control during playback)")
            
        except Exception as e:
            print(f"[WARNING] Could not generate beep sounds: {e}")
            import traceback
            print(f"[WARNING] Traceback: {traceback.format_exc()}")
    
    def play_beep_async(self, beep_file, description=""):
        """
        Play a short beep sound with REAL-TIME volume control.
        
        REAL-TIME VOLUME:
        - Beep respects current_volume setting
        - Uses PyAudio streaming for real-time volume scaling
        - No pre-processing - volume applied during playback
        
        Args:
            beep_file: Path to beep WAV file
            description: Description for logging (e.g., "start", "stop")
        """
        def _play_beep_thread():
            if not beep_file.exists():
                return
            
            audio = None
            stream = None
            
            try:
                # Read beep WAV file
                with wave.open(str(beep_file), 'rb') as wf:
                    channels = wf.getnchannels()
                    sample_width = wf.getsampwidth()
                    sample_rate = wf.getframerate()
                    beep_data = wf.readframes(wf.getnframes())
                
                # Apply REAL-TIME volume scaling
                current_vol = self.gpio_manager.get_current_volume()
                scaled_beep = apply_volume_to_audio(beep_data, current_vol, sample_width)
                
                # Initialize PyAudio for playback
                audio = pyaudio.PyAudio()
                
                # Find output device
                device_index = None
                for i in range(audio.get_device_count()):
                    info = audio.get_device_info_by_index(i)
                    device_name = info.get('name', '').lower()
                    max_output = info.get('maxOutputChannels', 0)
                    
                    if max_output > 0 and ('googlevoicehat' in device_name or 
                                          'voicehat' in device_name or
                                          'sndrpigooglevoi' in device_name):
                        device_index = i
                        break
                
                # Open output stream
                stream = audio.open(
                    format=audio.get_format_from_width(sample_width),
                    channels=channels,
                    rate=sample_rate,
                    output=True,
                    output_device_index=device_index
                )
                
                # Enable amplifier
                self.gpio_manager.enable_amplifier()
                time.sleep(0.02)
                
                # Play scaled beep
                stream.write(scaled_beep)
                
                # Wait for playback to complete
                time.sleep(0.02)
                
                # Disable amplifier
                self.gpio_manager.disable_amplifier()
                
                # Clean up
                if stream:
                    stream.stop_stream()
                    stream.close()
                if audio:
                    audio.terminate()
                
            except Exception:
                self.gpio_manager.disable_amplifier()
                try:
                    if stream:
                        stream.stop_stream()
                        stream.close()
                except:
                    pass
                try:
                    if audio:
                        audio.terminate()
                except:
                    pass
        
        # Start beep in background thread - returns immediately
        thread = threading.Thread(target=_play_beep_thread, daemon=True)
        thread.start()
        if config.VERBOSE_OUTPUT:
            current_vol = self.gpio_manager.get_current_volume()
            print(f"[BEEP] ▶ {description} beep (volume: {current_vol}%)")
    
    def play_beep(self, beep_file, description=""):
        """Legacy synchronous beep - kept for compatibility"""
        self.play_beep_async(beep_file, description)

