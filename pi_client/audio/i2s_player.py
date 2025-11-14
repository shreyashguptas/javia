#!/usr/bin/env python3
"""
I2S Audio Player for Pi Voice Assistant Client
Plays audio through I2S amplifier with real-time volume control using pyalsaaudio
"""

import time
import wave
import shutil
import logging
from pathlib import Path
import config
from .base_player import AudioPlayer
from .effects import apply_fade_in_out, add_silence_padding
from utils.system_utils import apply_volume_to_audio
from .hardware_detect import get_alsa_device_name, get_pyalsaaudio_device_name

logger = logging.getLogger(__name__)


class I2SPlayer(AudioPlayer):
    """
    Audio player for I2S amplifier with Google Voice HAT.
    
    Features:
    - Real-time volume control (rotate encoder during playback)
    - Button interrupt support
    - Audio effects (fade in/out, silence padding)
    - pyalsaaudio streaming for smooth playback (no segfaults)
    """
    
    def __init__(self, gpio_manager):
        """
        Initialize I2S audio player.
        
        Args:
            gpio_manager: GPIOManager instance for amplifier and button control
        """
        self.gpio_manager = gpio_manager
        self._is_playing = False
    
    def play(self, audio_file_path: Path) -> bool:
        """
        Play audio through I2S amplifier with real-time volume control.
        
        Uses pyalsaaudio for streaming playback with real-time volume control.
        pyalsaaudio is a direct ALSA binding (PyAudio was removed to avoid segfaults).
        
        Args:
            audio_file_path: Path to WAV file to play
        
        Returns:
            bool: True if playback completed, False if interrupted
        """
        if not audio_file_path.exists():
            logger.error("Response file not found")
            return False
        
        # Use pyalsaaudio for reliable streaming playback with real-time volume control
        return self._play_with_pyalsaaudio(audio_file_path)
    
    def _play_with_pyalsaaudio(self, audio_file_path: Path) -> bool:
        """
        Play audio using pyalsaaudio with real-time volume control.
        
        This method uses pyalsaaudio (direct ALSA binding) for streaming playback.
        Volume is read per chunk, so rotating the encoder immediately affects
        the audio output. PyAudio was removed to avoid segfaults.
        
        Args:
            audio_file_path: Path to WAV file to play
        
        Returns:
            bool: True if playback completed, False if interrupted
        """
        import alsaaudio
        
        pcm = None
        temp_processed_file = None
        
        try:
            # Apply optional processing (fade/padding) to a temp file
            temp_processed_file = config.AUDIO_DIR / "temp_response_processed.wav"

            # Copy original to temp file
            shutil.copy(audio_file_path, temp_processed_file)

            # Apply fade and padding ONLY if configured
            if config.FADE_DURATION_MS > 0:
                if config.VERBOSE_OUTPUT:
                    logger.info(f"[PLAYBACK] Applying {config.FADE_DURATION_MS}ms fade effects...")
                apply_fade_in_out(temp_processed_file, fade_duration_ms=config.FADE_DURATION_MS)

            # Optional silence padding
            if getattr(config, 'SILENCE_PADDING_MS', 0) > 0:
                if config.VERBOSE_OUTPUT:
                    logger.info("[PLAYBACK] Adding silence padding...")
                add_silence_padding(temp_processed_file, padding_ms=config.SILENCE_PADDING_MS)
            
            # Read WAV file and validate parameters
            with wave.open(str(temp_processed_file), 'rb') as wf:
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                sample_rate = wf.getframerate()
                n_frames = wf.getnframes()
                
                # Validate audio parameters
                if channels <= 0 or channels > 2:
                    logger.error(f"Invalid channel count: {channels} (expected 1 or 2)")
                    return False
                
                if sample_rate <= 0:
                    logger.error(f"Invalid sample rate: {sample_rate}")
                    return False
                
                if n_frames == 0:
                    logger.error("Audio file is empty")
                    return False
                
                # Log audio parameters
                if config.VERBOSE_OUTPUT:
                    logger.info(f"[PLAYBACK] Audio parameters: {channels}ch, {sample_rate}Hz, {sample_width*8}bit")
                
                # Get ALSA device name for reference (used for logging/debugging)
                device_name = get_alsa_device_name()
                
                # Convert to pyalsaaudio-compatible format with retry logic
                # Try plughw first (with format conversion), then hw, then default
                primary_device = get_pyalsaaudio_device_name()  # Returns plughw:0,0 or None
                
                # Build device candidate list with fallbacks
                device_candidates = [primary_device]
                
                # For googlevoicehat, also try direct hw access as fallback
                if primary_device and primary_device.startswith("plughw:"):
                    device_candidates.append("hw:0,0")
                
                # Always try default as last resort
                if None not in device_candidates:
                    device_candidates.append(None)
                
                # Remove duplicates while preserving order
                seen = set()
                unique_candidates = []
                for d in device_candidates:
                    if d not in seen:
                        seen.add(d)
                        unique_candidates.append(d)
                device_candidates = unique_candidates
                
                pcm = None
                alsa_device_used = None
                
                # Try to open PCM device with retry logic
                for device_candidate in device_candidates:
                    try:
                        if config.VERBOSE_OUTPUT:
                            device_str = device_candidate if device_candidate else "default"
                            logger.info(f"[PLAYBACK] Attempting to open PCM device: {device_str}")
                        
                        # Open PCM device for playback
                        # pyalsaaudio.PCM requires mode (PCM_PLAYBACK or PCM_CAPTURE)
                        pcm = alsaaudio.PCM(alsaaudio.PCM_PLAYBACK, alsaaudio.PCM_NORMAL, device_candidate)
                        
                        # Set audio parameters
                        pcm.setchannels(channels)
                        pcm.setrate(sample_rate)
                        
                        # Set sample format based on sample width
                        if sample_width == 1:
                            pcm.setformat(alsaaudio.PCM_FORMAT_U8)
                        elif sample_width == 2:
                            pcm.setformat(alsaaudio.PCM_FORMAT_S16_LE)
                        elif sample_width == 3:
                            pcm.setformat(alsaaudio.PCM_FORMAT_S24_LE)
                        elif sample_width == 4:
                            pcm.setformat(alsaaudio.PCM_FORMAT_S32_LE)
                        else:
                            logger.error(f"Unsupported sample width: {sample_width} bytes")
                            if pcm:
                                pcm.close()
                                pcm = None
                            return False
                        
                        # Set period size (chunk size for streaming)
                        # setperiodsize() expects frames, not bytes
                        pcm.setperiodsize(config.CHUNK_SIZE)
                        
                        alsa_device_used = device_candidate if device_candidate else "default"
                        if config.VERBOSE_OUTPUT:
                            logger.info(f"[PLAYBACK] ✓ PCM device opened successfully: {alsa_device_used}")
                        break
                        
                    except alsaaudio.ALSAAudioError as e:
                        if config.VERBOSE_OUTPUT:
                            device_str = device_candidate if device_candidate else "default"
                            logger.warning(f"[PLAYBACK] Failed to open PCM device '{device_str}': {e}")
                        if pcm:
                            try:
                                pcm.close()
                            except:
                                pass
                            pcm = None
                        continue
                    except Exception as e:
                        if config.VERBOSE_OUTPUT:
                            device_str = device_candidate if device_candidate else "default"
                            logger.warning(f"[PLAYBACK] Unexpected error opening PCM device '{device_str}': {e}")
                        if pcm:
                            try:
                                pcm.close()
                            except:
                                pass
                            pcm = None
                        continue
                
                # Check if we successfully opened a device
                if pcm is None:
                    logger.error("[PLAYBACK] Failed to open PCM device with all candidate devices")
                    logger.error(f"[PLAYBACK] Original device name: {device_name}")
                    return False
                
                # Enable amplifier
                self.gpio_manager.enable_amplifier()
                time.sleep(0.200)  # Stabilization time
                
                # Play audio with real-time volume control
                current_vol = self.gpio_manager.get_current_volume()
                logger.info(f"[PLAYBACK] Playing (volume: {current_vol}%)... Rotate encoder to adjust, press button to stop")
                
                self._is_playing = True
                last_displayed_volume = current_vol
                interrupted = False
                
                while True:
                    # Read chunk from file
                    data = wf.readframes(config.CHUNK_SIZE)
                    
                    if not data:
                        break
                    
                    # Apply REAL-TIME volume scaling based on current_volume
                    # This happens EVERY chunk, so volume changes take effect immediately
                    current_vol = self.gpio_manager.get_current_volume()
                    
                    # Validate volume is in valid range
                    current_vol = max(0, min(100, current_vol))
                    
                    scaled_data = apply_volume_to_audio(data, current_vol, sample_width)
                    
                    # Write to ALSA PCM device with error handling
                    try:
                        pcm.write(scaled_data)
                    except alsaaudio.ALSAAudioError as e:
                        logger.error(f"[PLAYBACK] ALSA write error: {e}")
                        interrupted = True
                        break
                    except Exception as e:
                        logger.error(f"[PLAYBACK] Unexpected error during playback: {e}")
                        interrupted = True
                        break
                    
                    # Display volume changes in real-time
                    if current_vol != last_displayed_volume:
                        logger.info(f"[PLAYBACK] Volume adjusted: {last_displayed_volume}% → {current_vol}%")
                        last_displayed_volume = current_vol
                    
                    # Check for button interrupt
                    if self.gpio_manager.button.is_pressed:
                        logger.info("\n[INTERRUPT] *** BUTTON PRESSED! Stopping playback... ***")
                        interrupted = True
                        break
                    
                    # Check for programmatic stop() call
                    if not self._is_playing:
                        logger.info("\n[INTERRUPT] *** STOP() CALLED! Stopping playback... ***")
                        interrupted = True
                        break
            
            # Wait for audio to fully complete
            time.sleep(0.200)
            
            # Disable amplifier
            self.gpio_manager.disable_amplifier()
            
            # Clean up PCM device
            if pcm is not None:
                try:
                    pcm.close()
                except Exception as e:
                    if config.VERBOSE_OUTPUT:
                        logger.warning(f"[PLAYBACK] Error closing PCM device: {e}")
            
            # Clean up temp file
            if temp_processed_file and temp_processed_file.exists():
                try:
                    temp_processed_file.unlink()
                except OSError as e:
                    if config.VERBOSE_OUTPUT:
                        logger.warning(f"[PLAYBACK] Error cleaning up temp file: {e}")
            
            self._is_playing = False
            
            if interrupted:
                logger.info("[INTERRUPT] Playback cancelled!")
                while self.gpio_manager.button.is_pressed:
                    time.sleep(0.01)
                return False
            else:
                logger.info("[PLAYBACK] Complete!")
                return True
                
        except Exception as e:
            logger.error(f"Playback error: {e}")
            import traceback
            logger.debug(f"{traceback.format_exc()}")
            
            # Ensure amplifier is disabled
            try:
                self.gpio_manager.disable_amplifier()
            except Exception:
                pass
            
            # Clean up PCM device (ignore errors - cleanup is non-critical)
            if pcm is not None:
                try:
                    pcm.close()
                except (OSError, AttributeError, Exception):
                    # PCM cleanup failed - non-critical, continue
                    pass
            
            # Clean up temp file (ignore errors - cleanup is non-critical)
            if temp_processed_file and temp_processed_file.exists():
                try:
                    temp_processed_file.unlink()
                except OSError:
                    # File cleanup failed - non-critical, continue
                    pass
            
            self._is_playing = False
            return False
    
    def stop(self):
        """
        Stop current playback immediately.
        
        This method should be safe to call even if nothing is playing.
        Note: Current implementation relies on button interrupt for actual stopping.
        Setting _is_playing to False and disabling amplifier for programmatic stops.
        """
        if self._is_playing:
            logger.info("[PLAYER] Stopping playback...")
            self._is_playing = False
            try:
                self.gpio_manager.disable_amplifier()
            except Exception:
                pass