#!/usr/bin/env python3
"""
I2S Audio Player for Pi Voice Assistant Client
Plays audio through I2S amplifier with real-time volume control
"""

import time
import wave
import shutil
import subprocess
import logging
from pathlib import Path
import config
from .base_player import AudioPlayer
from .effects import apply_fade_in_out, add_silence_padding
from utils.system_utils import apply_volume_to_audio
from .hardware_detect import is_googlevoicehat, get_alsa_device_name

logger = logging.getLogger(__name__)


class I2SPlayer(AudioPlayer):
    """
    Audio player for I2S amplifier with Google Voice HAT.
    
    Features:
    - Real-time volume control (rotate encoder during playback)
    - Button interrupt support
    - Audio effects (fade in/out, silence padding)
    - PyAudio streaming for smooth playback
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
        Play audio through I2S amplifier with volume control.
        
        STRATEGY:
        - For googlevoicehat: Use aplay (no PyAudio = no segfaults)
        - For other hardware: Use PyAudio (real-time volume control)
        - Button interrupt: Terminate aplay process or stop PyAudio stream
        
        VOLUME CONTROL:
        - googlevoicehat: Pre-scale audio file to target volume
        - PyAudio: Real-time volume scaling per chunk
        
        Args:
            audio_file_path: Path to WAV file to play
        
        Returns:
            bool: True if playback completed, False if interrupted
        """
        if not audio_file_path.exists():
            logger.error("Response file not found")
            return False
        
        # Route to appropriate playback method
        if is_googlevoicehat():
            return self._play_with_aplay(audio_file_path)
        else:
            return self._play_with_pyaudio(audio_file_path)
    
    def _play_with_aplay(self, audio_file_path: Path) -> bool:
        """
        Play audio using aplay (for googlevoicehat).
        
        Args:
            audio_file_path: Path to WAV file to play
        
        Returns:
            bool: True if playback completed, False if interrupted
        """
        temp_processed_file = None
        process = None
        
        try:
            # Apply optional processing (fade/padding) and volume scaling
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
            
            # Apply volume scaling
            current_vol = self.gpio_manager.get_current_volume()
            volume_scaled_file = config.AUDIO_DIR / "temp_response_volume.wav"
            self._scale_wav_file(temp_processed_file, volume_scaled_file, current_vol)
            
            # Enable amplifier
            self.gpio_manager.enable_amplifier()
            time.sleep(0.200)  # Stabilization time
            
            # Start aplay in background
            device_name = get_alsa_device_name()
            process = subprocess.Popen(
                ['aplay', '-D', device_name, str(volume_scaled_file)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            logger.info(f"[PLAYBACK] Playing (volume: {current_vol}%)... Press button to stop")
            self._is_playing = True
            
            # Monitor for button press or process completion
            interrupted = False
            while process.poll() is None:
                if self.gpio_manager.button.is_pressed:
                    logger.info("\n[INTERRUPT] *** BUTTON PRESSED! Stopping playback... ***")
                    process.terminate()
                    try:
                        process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    interrupted = True
                    break
                time.sleep(0.05)
            
            # Wait for audio to complete
            time.sleep(0.200)
            
            # Disable amplifier
            self.gpio_manager.disable_amplifier()
            
            # Clean up temp files
            if temp_processed_file and temp_processed_file.exists():
                temp_processed_file.unlink()
            if volume_scaled_file.exists():
                volume_scaled_file.unlink()
            
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
            self.gpio_manager.disable_amplifier()
            
            # Clean up process
            if process and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=1)
                except (subprocess.TimeoutExpired, ProcessLookupError):
                    # Process didn't terminate, try force kill
                    try:
                        process.kill()
                    except ProcessLookupError:
                        # Process already gone, ignore
                        pass
            
            # Clean up temp files (ignore errors - cleanup is non-critical)
            try:
                if temp_processed_file and temp_processed_file.exists():
                    temp_processed_file.unlink()
                if 'volume_scaled_file' in locals() and volume_scaled_file.exists():
                    volume_scaled_file.unlink()
            except (OSError, PermissionError):
                # File cleanup failed - non-critical, continue
                pass
            
            self._is_playing = False
            return False
    
    def _play_with_pyaudio(self, audio_file_path: Path) -> bool:
        """
        Play audio using PyAudio (for non-googlevoicehat hardware).
        
        Real-time volume control during playback.
        
        Args:
            audio_file_path: Path to WAV file to play
        
        Returns:
            bool: True if playback completed, False if interrupted
        """
        import pyaudio
        
        audio = None
        stream = None
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
            
            # Read WAV file
            with wave.open(str(temp_processed_file), 'rb') as wf:
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                sample_rate = wf.getframerate()
                n_frames = wf.getnframes()
                
                # Initialize PyAudio
                audio = pyaudio.PyAudio()
                
                # Open output stream (use default device)
                stream = audio.open(
                    format=audio.get_format_from_width(sample_width),
                    channels=channels,
                    rate=sample_rate,
                    output=True,
                    frames_per_buffer=config.CHUNK_SIZE
                )
                
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
                    scaled_data = apply_volume_to_audio(data, current_vol, sample_width)
                    
                    # Write to output stream
                    stream.write(scaled_data)
                    
                    # Display volume changes in real-time
                    if current_vol != last_displayed_volume:
                        logger.info(f"[PLAYBACK] Volume adjusted: {last_displayed_volume}% → {current_vol}%")
                        last_displayed_volume = current_vol
                    
                    # Check for button interrupt
                    if self.gpio_manager.button.is_pressed:
                        logger.info("\n[INTERRUPT] *** BUTTON PRESSED! Stopping playback... ***")
                        interrupted = True
                        break
            
            # Wait for audio to fully complete
            time.sleep(0.200)
            
            # Disable amplifier
            self.gpio_manager.disable_amplifier()
            
            # Clean up
            if stream is not None:
                stream.stop_stream()
                stream.close()
            if audio is not None:
                audio.terminate()
            
            # Clean up temp file
            if temp_processed_file and temp_processed_file.exists():
                temp_processed_file.unlink()
            
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
            self.gpio_manager.disable_amplifier()
            
            # Clean up (ignore errors - cleanup is non-critical)
            try:
                if stream is not None:
                    stream.stop_stream()
                    stream.close()
            except (OSError, AttributeError):
                # Stream cleanup failed - non-critical, continue
                pass
            
            try:
                if audio is not None:
                    audio.terminate()
            except (OSError, AttributeError):
                # Audio cleanup failed - non-critical, continue
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
    
    def stop(self):
        """
        Stop current playback.
        
        Note: Current implementation relies on button interrupt.
        Could be extended to support programmatic stopping.
        """
        if self._is_playing:
            logger.info("[PLAYER] Stopping playback...")
            self._is_playing = False
            self.gpio_manager.disable_amplifier()

