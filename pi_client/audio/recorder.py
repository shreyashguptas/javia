#!/usr/bin/env python3
"""
Audio Recorder for Pi Voice Assistant Client
Records audio from I2S microphone using arecord (reliable ALSA tool)
"""

import os
import time
import wave
import subprocess
import logging
import config
from audio.hardware_detect import get_alsa_device_name

logger = logging.getLogger(__name__)


# ==================== AUDIO RECORDING ====================

# Note: ALSA mixer controls are NOT used for I2S microphones (INMP441)
# I2S devices have fixed hardware gain, no software mixer control needed
# Any ALSA mixer manipulation can actually REDUCE recording quality


def record_audio(gpio_manager, beep_generator):
    """
    Record RAW audio from I2S microphone using arecord (reliable ALSA tool).
    
    This method uses arecord directly, which is the most reliable approach
    for I2S hardware with googlevoicehat driver. No Python audio libraries
    are used, eliminating segfault risks and library conflicts.
    
    CRITICAL PERFORMANCE OPTIMIZATION:
    - Zero audio processing on Pi (just raw capture)
    - Amplification handled by server (has powerful CPU)
    - Fastest possible recording - minimal CPU usage
    - Instant availability after recording stops
    
    Args:
        gpio_manager: GPIOManager instance for button control
        beep_generator: BeepGenerator instance for audio feedback
    
    Returns:
        bool: True if successful, False otherwise
    """
    logger.info("[AUDIO] Recording with arecord... SPEAK NOW!")
    logger.info("[AUDIO] " + "="*40)
    
    process = None
    
    try:
        # Get ALSA device name from hardware detection
        device_name_original = get_alsa_device_name()
        device_name = device_name_original
        
        logger.info(f"[AUDIO] Default device: {device_name}")
        
        # Start arecord in background
        # Note: We capture stderr to see ALSA error messages
        logger.info(f"[AUDIO] Starting arecord on device: {device_name}")
        logger.info(f"[AUDIO] Output file: {config.RECORDING_FILE}")
        
        process = subprocess.Popen(
            [
                'arecord',
                '-D', device_name,              # ALSA device (hw: for I2S is more reliable)
                '-f', 'S16_LE',                 # 16-bit signed little-endian
                '-r', str(config.SAMPLE_RATE),  # 48000 Hz
                '-c', str(config.CHANNELS),     # 2 channels (stereo - dual INMP441 mics)
                str(config.RECORDING_FILE)      # Output file
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        logger.info(f"[AUDIO] arecord started (PID: {process.pid})")
        
        # Give arecord a moment to initialize and detect any immediate errors
        time.sleep(0.2)
        
        # Check if process is still running (didn't crash immediately)
        if process.poll() is not None:
            # Process already terminated - there was an error
            stdout, stderr = process.communicate()
            error_msg = stderr.decode('utf-8', errors='ignore') if stderr else "Unknown error"
            logger.error(f"[ERROR] arecord failed to start with device {device_name}")
            logger.error(f"[ERROR] Error: {error_msg}")
            
            # If we used plughw and it failed, don't retry
            # If we used hw and it failed, try plughw as fallback
            if device_name != device_name_original:
                logger.info(f"[AUDIO] Retrying with original device: {device_name_original}")
                device_name = device_name_original
                
                # Retry with original device
                process = subprocess.Popen(
                    [
                        'arecord',
                        '-D', device_name,
                        '-f', 'S16_LE',
                        '-r', str(config.SAMPLE_RATE),
                        '-c', str(config.CHANNELS),
                        str(config.RECORDING_FILE)
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                logger.info(f"[AUDIO] Retry: arecord started (PID: {process.pid})")
                time.sleep(0.2)
                
                if process.poll() is not None:
                    stdout, stderr = process.communicate()
                    error_msg = stderr.decode('utf-8', errors='ignore') if stderr else "Unknown error"
                    logger.error(f"[ERROR] arecord also failed with {device_name}: {error_msg}")
                    return False
            else:
                return False
        
        # Wait for button to be released first
        while gpio_manager.button.is_pressed:
            time.sleep(0.005)
        
        # Record until button is pressed again
        start_time = time.time()
        while not gpio_manager.button.is_pressed:
            # Progress indicator every 5 seconds (reduced verbosity)
            elapsed = time.time() - start_time
            if int(elapsed) > 0 and int(elapsed) % 5 == 0:
                if int(elapsed * 10) % 50 == 0:  # Only print once per 5 seconds
                    logger.info(f"[AUDIO] {int(elapsed)}s recorded...")
            time.sleep(0.1)
        
        logger.info("[AUDIO] " + "="*40)
        logger.info("[BUTTON] *** BUTTON PRESSED! Stopping recording... ***")
        
        # Play stop beep to indicate mic stopped listening
        if beep_generator:
            beep_generator.play_beep_async(config.STOP_BEEP_FILE, "stop")
        
        # Stop arecord gracefully and give it time to flush the file
        logger.info("[AUDIO] Stopping arecord and flushing to disk...")
        process.terminate()
        
        try:
            # Wait for process to terminate and capture output
            stdout, stderr = process.communicate(timeout=3)
            
            # Decode stderr to check for errors
            stderr_text = stderr.decode('utf-8', errors='ignore') if stderr else ""
            
            # Log any errors or warnings from arecord
            if stderr_text:
                logger.info("[AUDIO] arecord output:")
                for line in stderr_text.split('\n'):
                    if line.strip():
                        # Log all output to help diagnose
                        if 'error' in line.lower() or 'failed' in line.lower():
                            logger.error(f"  {line.strip()}")
                        elif 'warning' in line.lower():
                            logger.warning(f"  {line.strip()}")
                        else:
                            logger.info(f"  {line.strip()}")
        except subprocess.TimeoutExpired:
            logger.warning("[AUDIO] arecord didn't terminate gracefully, forcing kill...")
            process.kill()
            stdout, stderr = process.communicate()
            stderr_text = stderr.decode('utf-8', errors='ignore') if stderr else ""
            if stderr_text:
                logger.error(f"[AUDIO] arecord errors: {stderr_text}")
        
        # Give the filesystem a moment to sync
        time.sleep(0.1)
        
        # Wait for button release
        while gpio_manager.button.is_pressed:
            time.sleep(0.005)
        
        # Check if file was created
        if not config.RECORDING_FILE.exists():
            logger.error("[ERROR] Recording file was not created!")
            logger.error(f"[ERROR] Expected file at: {config.RECORDING_FILE}")
            logger.error("[ERROR] Possible causes:")
            logger.error("[ERROR]   1. arecord couldn't access the audio device")
            logger.error("[ERROR]   2. Filesystem permissions issue")
            logger.error("[ERROR]   3. Audio device is busy or locked")
            logger.error("[ERROR]   4. Hardware not properly initialized")
            
            # Try to check directory permissions
            audio_dir = config.RECORDING_FILE.parent
            if audio_dir.exists():
                logger.info(f"[DEBUG] Audio directory exists: {audio_dir}")
                logger.info(f"[DEBUG] Directory is writable: {os.access(audio_dir, os.W_OK)}")
            else:
                logger.error(f"[ERROR] Audio directory does not exist: {audio_dir}")
            
            return False
        
        file_size = config.RECORDING_FILE.stat().st_size
        duration = time.time() - start_time
        
        # Calculate expected minimum file size (at least 0.5 seconds of audio)
        # 48000 Hz * 2 bytes/sample * 2 channels * 0.5 seconds = 96000 bytes minimum
        expected_min_size = config.SAMPLE_RATE * 2 * config.CHANNELS * 0.5
        
        if file_size < expected_min_size:
            logger.error(f"[ERROR] Recording file is too small ({file_size} bytes, expected >{expected_min_size:.0f})")
            logger.error("[ERROR] Microphone may not be working - check hardware connections")
            logger.error("[ERROR] Verify INMP441 is connected to GPIO20 (PCM_DIN)")
        elif file_size < 1000:
            logger.warning(f"[WARNING] Recording file is very small ({file_size} bytes)")
        else:
            logger.info(f"[AUDIO] ✓ Recording looks good ({duration:.1f}s, {file_size:,} bytes)")
        
        logger.info(f"[AUDIO] Saved: {config.RECORDING_FILE}")
        # Mark recording end timestamp for telemetry
        try:
            config.LAST_RECORD_END_TS = time.time()
        except Exception:
            pass
        
        # Additional diagnostic: Check if file contains mostly silence
        try:
            import wave
            import numpy as np
            with wave.open(str(config.RECORDING_FILE), 'rb') as wf:
                audio_data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
                max_amplitude = np.abs(audio_data).max()
                avg_amplitude = np.abs(audio_data).mean()

                if config.VERBOSE_OUTPUT:
                    logger.info(f"[AUDIO] Signal levels - Max: {max_amplitude}/32768, Avg: {avg_amplitude:.1f}/32768")

                    # Calculate expected amplitude after server-side amplification
                    amplified_max = max_amplitude * config.MICROPHONE_GAIN
                    amplified_percent = (amplified_max / 32768) * 100

                    logger.info(f"[AUDIO] After {config.MICROPHONE_GAIN}x gain on server: ~{amplified_percent:.0f}% of max")

                if max_amplitude < 100:
                    logger.error("[ERROR] Audio signal is critically weak - microphone might not be working!")
                    logger.error("[ERROR] Check hardware connections:")
                    logger.error("[ERROR]   1. INMP441 L/R pin → Ground (for left channel)")
                    logger.error("[ERROR]   2. INMP441 VDD → 3.3V")
                    logger.error("[ERROR]   3. INMP441 SD → GPIO20 (PCM_DIN)")
                    logger.error("[ERROR]   4. INMP441 WS → GPIO19 (PCM_FS)")
                    logger.error("[ERROR]   5. INMP441 SCK → GPIO18 (PCM_CLK)")
                elif max_amplitude < 1000:
                    logger.warning("[WARNING] Audio signal is very quiet - microphone might not be working properly")
                    logger.warning("[WARNING] Check INMP441 connections and verify it's not damaged")
                elif amplified_max < 10000:
                    logger.warning(f"[WARNING] Audio will be quiet even with {config.MICROPHONE_GAIN}x gain")
                    logger.warning(f"[WARNING] Consider speaking louder or positioning mic closer")
                elif amplified_max > 32768:
                    logger.warning(f"[WARNING] Audio may clip with {config.MICROPHONE_GAIN}x gain!")
                    logger.warning(f"[WARNING] Reduce MICROPHONE_GAIN in config.py or .env file")
        except Exception as diag_error:
            if config.VERBOSE_OUTPUT:
                logger.debug(f"[DEBUG] Could not analyze audio levels: {diag_error}")
        
        return True
        
    except Exception as e:
        logger.error(f"[ERROR] Recording failed: {e}")
        import traceback
        logger.debug(f"{traceback.format_exc()}")
        return False
        
    finally:
        # Clean up process
        if process and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=1)
            except:
                try:
                    process.kill()
                except:
                    pass

