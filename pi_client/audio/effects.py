#!/usr/bin/env python3
"""
Audio Effects for Pi Voice Assistant Client
Fade in/out and silence padding for smooth playback
"""

import wave
import numpy as np


def apply_fade_in_out(wav_file, fade_duration_ms=50):
    """
    Apply fade-in and fade-out effects to eliminate clicks
    
    Args:
        wav_file: Path to WAV file to process (modified in-place)
        fade_duration_ms: Duration of fade in milliseconds (default 50ms)
    """
    temp_file = None
    try:
        # Read the WAV file parameters first
        with wave.open(str(wav_file), 'rb') as wf:
            params = wf.getparams()
            channels = params.nchannels
            sampwidth = params.sampwidth
            framerate = params.framerate
            n_frames = params.nframes
        
        # Validate we have audio data
        if n_frames == 0:
            print(f"[WARNING] Audio file is empty, skipping fade")
            return
        
        # Determine dtype based on sample width
        if sampwidth == 1:
            dtype = np.uint8
            is_unsigned = True
        elif sampwidth == 2:
            dtype = np.int16
            is_unsigned = False
        elif sampwidth == 4:
            dtype = np.int32
            is_unsigned = False
        else:
            print(f"[WARNING] Unsupported sample width for fade: {sampwidth} bytes")
            return
        
        # Calculate fade length in frames
        fade_frames = int((fade_duration_ms / 1000.0) * framerate)
        fade_frames = min(fade_frames, n_frames // 4)
        
        if fade_frames < 10:
            print(f"[WARNING] Audio too short for fade effect ({n_frames} frames)")
            return
        
        fade_samples = fade_frames * channels
        
        print(f"[DEBUG] Applying {fade_duration_ms}ms fade ({fade_frames} frames, {fade_samples} samples)")
        
        # Create fade curves
        fade_in_curve = np.linspace(0, 1, fade_samples)
        fade_in_curve = 0.5 * (1 - np.cos(np.pi * fade_in_curve))
        
        fade_out_curve = np.linspace(1, 0, fade_samples)
        fade_out_curve = 0.5 * (1 - np.cos(np.pi * fade_out_curve))
        
        # Create temporary file
        temp_file = wav_file.parent / f"{wav_file.stem}_fade_temp.wav"
        
        # Process file
        with wave.open(str(wav_file), 'rb') as wf_in:
            with wave.open(str(temp_file), 'wb') as wf_out:
                wf_out.setnchannels(channels)
                wf_out.setsampwidth(sampwidth)
                wf_out.setframerate(framerate)
                
                # Process beginning
                beginning_data = wf_in.readframes(fade_frames)
                if len(beginning_data) == 0:
                    print(f"[WARNING] No beginning data to fade")
                    return
                    
                beginning_array = np.frombuffer(beginning_data, dtype=dtype).copy()
                
                # Ensure arrays match in size
                if len(beginning_array) != len(fade_in_curve):
                    print(f"[WARNING] Size mismatch: audio={len(beginning_array)}, fade={len(fade_in_curve)}")
                    # Truncate or pad fade curve to match
                    if len(beginning_array) < len(fade_in_curve):
                        fade_in_curve = fade_in_curve[:len(beginning_array)]
                    else:
                        beginning_array = beginning_array[:len(fade_in_curve)]
                
                if is_unsigned:
                    beginning_array = beginning_array.astype(np.int16) - 128
                
                beginning_array = (beginning_array * fade_in_curve).astype(beginning_array.dtype)
                
                if is_unsigned:
                    beginning_array = (beginning_array + 128).clip(0, 255).astype(np.uint8)
                
                wf_out.writeframes(beginning_array.tobytes())
                
                # Copy middle portion
                middle_frames = n_frames - (2 * fade_frames)
                if middle_frames > 0:
                    chunk_size = 4096
                    frames_written = 0
                    while frames_written < middle_frames:
                        frames_to_read = min(chunk_size, middle_frames - frames_written)
                        chunk = wf_in.readframes(frames_to_read)
                        if not chunk:
                            break
                        wf_out.writeframes(chunk)
                        frames_written += frames_to_read
                
                # Process ending
                ending_data = wf_in.readframes(fade_frames)
                if len(ending_data) == 0:
                    print(f"[WARNING] No ending data to fade")
                    return
                    
                ending_array = np.frombuffer(ending_data, dtype=dtype).copy()
                
                # Ensure arrays match in size
                if len(ending_array) != len(fade_out_curve):
                    print(f"[WARNING] Size mismatch: audio={len(ending_array)}, fade={len(fade_out_curve)}")
                    # Truncate or pad fade curve to match
                    if len(ending_array) < len(fade_out_curve):
                        fade_out_curve = fade_out_curve[:len(ending_array)]
                    else:
                        ending_array = ending_array[:len(fade_out_curve)]
                
                if is_unsigned:
                    ending_array = ending_array.astype(np.int16) - 128
                
                ending_array = (ending_array * fade_out_curve).astype(ending_array.dtype)
                
                if is_unsigned:
                    ending_array = (ending_array + 128).clip(0, 255).astype(np.uint8)
                
                wf_out.writeframes(ending_array.tobytes())
        
        # Replace original file
        temp_file.replace(wav_file)
        print(f"[AUDIO] Applied fade-in/fade-out effects")
        
    except Exception as e:
        print(f"[WARNING] Could not apply fade effects: {e}")
        if temp_file is not None and temp_file.exists():
            try:
                temp_file.unlink()
            except (OSError, PermissionError):
                # File cleanup failed - non-critical, continue
                pass


def add_silence_padding(wav_file, padding_ms=150):
    """
    Add silence padding to beginning and end of WAV file
    
    Args:
        wav_file: Path to WAV file to process (modified in-place)
        padding_ms: Duration of silence padding in milliseconds (default 150ms)
    """
    temp_file = None
    try:
        temp_file = wav_file.parent / f"{wav_file.stem}_temp.wav"
        
        with wave.open(str(wav_file), 'rb') as wf_in:
            params = wf_in.getparams()
            channels = params.nchannels
            sampwidth = params.sampwidth
            framerate = params.framerate
            
            # Determine dtype
            if sampwidth == 1:
                dtype = np.uint8
                default_value = 128
            elif sampwidth == 2:
                dtype = np.int16
                default_value = 0
            elif sampwidth == 4:
                dtype = np.int32
                default_value = 0
            else:
                print(f"[WARNING] Unsupported sample width: {sampwidth} bytes")
                return
            
            # Calculate padding length
            padding_frames = int((padding_ms / 1000.0) * framerate)
            silence_samples = padding_frames * channels
            silence = np.full(silence_samples, default_value, dtype=dtype)
            silence_bytes = silence.tobytes()
            
            # Write to temporary file with padding
            with wave.open(str(temp_file), 'wb') as wf_out:
                wf_out.setnchannels(channels)
                wf_out.setsampwidth(sampwidth)
                wf_out.setframerate(framerate)
                
                # Write leading silence
                wf_out.writeframes(silence_bytes)
                
                # Copy original audio
                chunk_size = 4096
                while True:
                    frames = wf_in.readframes(chunk_size)
                    if not frames:
                        break
                    wf_out.writeframes(frames)
                
                # Write trailing silence
                wf_out.writeframes(silence_bytes)
        
        # Replace original file
        temp_file.replace(wav_file)
        print(f"[AUDIO] Added {padding_ms}ms silence padding")
        
    except Exception as e:
        print(f"[WARNING] Could not add silence padding: {e}")
        if temp_file is not None and temp_file.exists():
            try:
                temp_file.unlink()
            except (OSError, PermissionError):
                # File cleanup failed - non-critical, continue
                pass

