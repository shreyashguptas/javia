#!/usr/bin/env python3
"""
I2S Audio Player for Pi Voice Assistant Client
Plays audio through I2S amplifier with real-time volume control
"""

import time
import wave
import shutil
import pyaudio
from pathlib import Path
import config
from .base_player import AudioPlayer
from .effects import apply_fade_in_out, add_silence_padding
from utils.system_utils import apply_volume_to_audio


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
        Play audio through I2S amplifier with REAL-TIME volume control.
        
        REAL-TIME FEATURES:
        - Volume changes take effect immediately during playback
        - Rotate encoder while speaking to adjust volume
        - Smooth volume transitions with no clicks
        
        AUDIO QUALITY:
        - Minimal processing to preserve quality
        - Optional fade/padding (only if configured)
        - PyAudio streaming for real-time control
        
        VOLUME CONTROL:
        - Monitors current_volume every chunk (10ms)
        - Applies volume scaling in real-time
        - Changes are immediate and smooth
        
        Args:
            audio_file_path: Path to WAV file to play
        
        Returns:
            bool: True if playback completed, False if interrupted
        """
        if not audio_file_path.exists():
            print("[ERROR] Response file not found")
            return False
        
        audio = None
        stream = None
        temp_processed_file = None
        
        try:
            if config.VERBOSE_OUTPUT:
                print("[PLAYBACK] Preparing audio...")
            
            # Apply optional processing (fade/padding) to a temp file
            # Volume scaling happens in real-time during playback
            temp_processed_file = config.AUDIO_DIR / "temp_response_processed.wav"
            
            # Copy original to temp file
            shutil.copy(audio_file_path, temp_processed_file)
            
            # Apply fade and padding ONLY if configured (optional for quality)
            if config.FADE_DURATION_MS > 0:
                if config.VERBOSE_OUTPUT:
                    print(f"[PLAYBACK] Applying {config.FADE_DURATION_MS}ms fade effects...")
                apply_fade_in_out(temp_processed_file, fade_duration_ms=config.FADE_DURATION_MS)
            
            # Add minimal silence padding (reduced from 150ms to 50ms for performance)
            if config.VERBOSE_OUTPUT:
                print("[PLAYBACK] Adding silence padding...")
            add_silence_padding(temp_processed_file, padding_ms=50)
            
            # Read WAV file
            with wave.open(str(temp_processed_file), 'rb') as wf:
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                sample_rate = wf.getframerate()
                n_frames = wf.getnframes()
                
                # Initialize PyAudio
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
                    output_device_index=device_index,
                    frames_per_buffer=config.CHUNK_SIZE
                )
                
                # Enable amplifier
                self.gpio_manager.enable_amplifier()
                time.sleep(0.200)  # Stabilization time
                
                # Play audio with real-time volume control
                current_vol = self.gpio_manager.get_current_volume()
                print(f"[PLAYBACK] Playing (volume: {current_vol}%)... Rotate encoder to adjust, press button to stop")
                
                self._is_playing = True
                chunk_size = config.CHUNK_SIZE * channels * sample_width
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
                        print(f"[PLAYBACK] Volume adjusted: {last_displayed_volume}% → {current_vol}%")
                        last_displayed_volume = current_vol
                    
                    # Check for button interrupt
                    if self.gpio_manager.button.is_pressed:
                        print("\n[INTERRUPT] *** BUTTON PRESSED! Stopping playback... ***")
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
                print("[INTERRUPT] Playback cancelled!")
                while self.gpio_manager.button.is_pressed:
                    time.sleep(0.01)
                return False
            else:
                print("[PLAYBACK] Complete!")
                return True
                
        except Exception as e:
            print(f"[ERROR] Playback error: {e}")
            import traceback
            print(f"[DEBUG] {traceback.format_exc()}")
            self.gpio_manager.disable_amplifier()
            
            # Clean up
            try:
                if stream is not None:
                    stream.stop_stream()
                    stream.close()
            except:
                pass
            
            try:
                if audio is not None:
                    audio.terminate()
            except:
                pass
            
            # Clean up temp file
            if temp_processed_file and temp_processed_file.exists():
                try:
                    temp_processed_file.unlink()
                except:
                    pass
            
            self._is_playing = False
            return False
    
    def stop(self):
        """
        Stop current playback.
        
        Note: Current implementation relies on button interrupt.
        Could be extended to support programmatic stopping.
        """
        if self._is_playing:
            print("[PLAYER] Stopping playback...")
            self._is_playing = False
            self.gpio_manager.disable_amplifier()

