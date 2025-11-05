#!/usr/bin/env python3
"""
Beep Generator for Pi Voice Assistant Client
Generates and plays beep sounds for audio feedback
"""

import time
import wave
import subprocess
import logging
import numpy as np
import config
from utils.system_utils import apply_volume_to_audio
from audio.hardware_detect import get_alsa_device_name

logger = logging.getLogger(__name__)


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
        Play a short beep sound with volume control.
        
        Uses aplay for reliable playback (no segfaults, no library conflicts).
        Volume scaling is applied by pre-scaling the WAV file before playback.
        
        Args:
            beep_file: Path to beep WAV file
            description: Description for logging (e.g., "start", "stop")
        """
        if not beep_file.exists():
            logger.warning(f"Beep file not found: {beep_file}")
            return
        
        try:
            current_vol = self.gpio_manager.get_current_volume()
            
            # Create volume-scaled temporary file
            temp_beep = config.AUDIO_DIR / f"temp_{description}_beep.wav"
            self._scale_wav_file(beep_file, temp_beep, current_vol)
            
            # Enable amplifier
            self.gpio_manager.enable_amplifier()
            time.sleep(0.02)  # Stabilization time
            
            # Play beep using aplay (reliable ALSA tool)
            self._play_with_aplay(temp_beep)
            
            # Wait for beep to complete
            time.sleep(0.05)
            
            # Disable amplifier
            self.gpio_manager.disable_amplifier()
            
            # Clean up temp file
            if temp_beep.exists():
                temp_beep.unlink()
            
            if config.VERBOSE_OUTPUT:
                logger.info(f"[BEEP] ▶ {description} beep (volume: {current_vol}%)")
                
        except Exception as e:
            logger.error(f"Failed to play beep: {e}")
            self.gpio_manager.disable_amplifier()
            # Clean up temp file on error (ignore errors - cleanup is non-critical)
            try:
                if temp_beep.exists():
                    temp_beep.unlink()
            except (OSError, PermissionError):
                # File cleanup failed - non-critical, continue
                pass
    
    def _scale_wav_file(self, input_file, output_file, volume_percent):
        """
        Pre-scale WAV file to target volume.
        
        Args:
            input_file: Input WAV file path
            output_file: Output WAV file path
            volume_percent: Volume level 0-100
        """
        with wave.open(str(input_file), 'rb') as wf:
            params = wf.getparams()
            audio_data = wf.readframes(wf.getnframes())
            
            # Scale audio data
            scaled_data = apply_volume_to_audio(audio_data, volume_percent, params.sampwidth)
            
            # Write scaled file
            with wave.open(str(output_file), 'wb') as out_wf:
                out_wf.setparams(params)
                out_wf.writeframes(scaled_data)
    
    def _play_with_aplay(self, wav_file):
        """
        Play WAV file using aplay (reliable ALSA tool).
        
        Args:
            wav_file: Path to WAV file
        """
        try:
            device_name = get_alsa_device_name()
            subprocess.run(
                ['aplay', '-D', device_name, str(wav_file)],
                capture_output=True,
                check=True,
                timeout=2
            )
        except subprocess.TimeoutExpired:
            logger.warning("Beep playback timeout")
        except subprocess.CalledProcessError as e:
            logger.error(f"aplay failed: {e}")
        except Exception as e:
            logger.error(f"Beep playback error: {e}")
    
    def play_beep(self, beep_file, description=""):
        """Play beep synchronously (wrapper for compatibility)"""
        self.play_beep_async(beep_file, description)

