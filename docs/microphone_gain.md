# Microphone Gain Configuration

## Overview

The INMP441 microphone sometimes records audio that's too quiet for reliable transcription. This guide explains how to increase microphone volume using software amplification.

## The Problem

When recording audio at a normal speaking distance (6-12 inches), the INMP441 microphone may produce recordings that are too quiet, resulting in:
- Poor transcription accuracy
- Missed words or phrases  
- Low confidence scores from Whisper API
- Need to speak very loudly or very close to the microphone

## Solutions

### Solution 1: Software Gain (Recommended)

The voice assistant includes built-in software amplification that processes the audio after recording but before sending to the Groq API.

#### How to Configure

Edit your `.env` file:

```bash
nano .env
```

Add or modify the `MICROPHONE_GAIN` setting:

```env
GROQ_API_KEY=your_api_key_here
MICROPHONE_GAIN=2.0
```

#### Gain Values

| Value | Effect | Use Case |
|-------|--------|----------|
| 1.0 | No amplification | Microphone already loud enough |
| 2.0 | Double volume | **Recommended starting point** |
| 2.5 | 2.5x volume | Quiet microphone |
| 3.0 | Triple volume | Very quiet microphone |
| 4.0 | Quadruple volume | Extremely quiet (may distort) |
| 5.0+ | Not recommended | Will likely cause distortion |

#### Testing Different Gain Values

1. Start with **2.0** (default):
   ```env
   MICROPHONE_GAIN=2.0
   ```

2. Test the recording:
   ```bash
   python3 voice_assistant.py
   # Press button and speak at normal volume
   ```

3. If still too quiet, increase to **3.0**:
   ```env
   MICROPHONE_GAIN=3.0
   ```

4. If too loud or distorted, decrease to **1.5**:
   ```env
   MICROPHONE_GAIN=1.5
   ```

### Solution 2: ALSA Volume Control

You can also increase the hardware capture volume using ALSA:

```bash
# Check current capture volume
amixer -c 0 get Capture

# Set capture volume to 100%
amixer -c 0 set Capture 100%

# If Capture doesn't exist, try:
amixer -c 0 set Mic 100%
```

To make this permanent, add to your startup script:

```bash
# Edit ~/.bashrc or create a startup script
echo "amixer -c 0 set Capture 100%" >> ~/.bashrc
```

### Solution 3: Hardware Adjustments

Physical adjustments can also help:

1. **Move microphone closer** - Optimal distance is 6-12 inches
2. **Reduce background noise** - Quieter environment = better signal
3. **Speak clearly** - Enunciate and speak at normal volume
4. **Check wiring** - Ensure secure connections
5. **Power supply** - Verify stable 3.3V to microphone

## How Software Gain Works

The software amplification works by:

1. **Recording** - Audio is captured from the microphone at normal levels
2. **Conversion** - Audio bytes are converted to numpy array
3. **Amplification** - Each sample is multiplied by the gain factor
4. **Clipping** - Values are clipped to prevent overflow (-32768 to 32767)
5. **Conversion** - Array is converted back to audio bytes
6. **Saving** - Amplified audio is saved to WAV file

### Code Example

```python
def amplify_audio(audio_data, gain=2.0):
    # Convert bytes to numpy array
    audio_array = np.frombuffer(audio_data, dtype=np.int16)
    
    # Apply gain
    amplified = audio_array * gain
    
    # Clip to prevent overflow
    amplified = np.clip(amplified, -32768, 32767)
    
    # Convert back to int16
    return amplified.astype(np.int16).tobytes()
```

## Troubleshooting

### Audio is Still Too Quiet

1. **Increase gain further**:
   ```env
   MICROPHONE_GAIN=3.5
   ```

2. **Check ALSA volume**:
   ```bash
   amixer -c 0 set Capture 100%
   ```

3. **Test microphone directly**:
   ```bash
   arecord -D plughw:0,0 -c1 -r 16000 -f S16_LE -t wav test.wav
   aplay test.wav
   ```

4. **Verify wiring** - Use multimeter to check connections

### Audio is Distorted

1. **Reduce gain**:
   ```env
   MICROPHONE_GAIN=1.5
   ```

2. **Move microphone farther away** - If too close, it may clip

3. **Reduce ALSA volume**:
   ```bash
   amixer -c 0 set Capture 75%
   ```

4. **Speak at normal volume** - Don't shout into the microphone

### Transcription Still Poor

1. **Check internet connection** - Slow connection = timeout
2. **Verify API key** - Ensure Groq API key is valid
3. **Test recording quality**:
   ```bash
   # Record test file with voice assistant
   python3 examples/mic_test.py
   
   # Or test directly with arecord (5 seconds)
   arecord -D plughw:0,0 -c1 -r 16000 -f S16_LE -t wav -d 5 test.wav
   
   # Listen to the recording
   aplay test.wav
   ```

4. **Check background noise** - Reduce ambient noise
5. **Increase recording duration**:
   ```env
   RECORD_SECONDS=7
   ```

## Best Practices

### Recommended Settings

For most setups, these settings work well:

```env
GROQ_API_KEY=your_api_key_here
MICROPHONE_GAIN=2.0
RECORD_SECONDS=5
SAMPLE_RATE=16000
```

### Optimal Speaking Technique

- **Distance**: 6-12 inches from microphone
- **Volume**: Normal conversational voice
- **Pace**: Moderate speed, clear enunciation
- **Environment**: Quiet room with minimal echo
- **Position**: Speak directly toward microphone

### Testing Procedure

1. Set gain to 2.0
2. Record a test phrase
3. Listen to the recording
4. Check transcription accuracy
5. Adjust gain if needed
6. Repeat until optimal

## Advanced Configuration

### Dynamic Gain Adjustment

You can create different profiles for different environments:

**Quiet Room:**
```env
MICROPHONE_GAIN=2.0
```

**Noisy Environment:**
```env
MICROPHONE_GAIN=3.0
RECORD_SECONDS=7
```

**Close Microphone:**
```env
MICROPHONE_GAIN=1.5
```

### Monitoring Audio Levels

Use the audio testing script to monitor levels:

```bash
python3 scripts/test_audio.py levels
```

This will show you the RMS (Root Mean Square) level of your recordings, helping you determine the optimal gain.

## Technical Details

### Audio Format

- **Sample Rate**: 16000 Hz (16 kHz)
- **Bit Depth**: 16-bit (int16)
- **Channels**: Mono (1 channel)
- **Format**: PCM WAV

### Gain Calculation

The amplification is applied as:

```
amplified_sample = original_sample × gain
```

For example, with gain = 2.0:
- Original: 1000 → Amplified: 2000
- Original: -500 → Amplified: -1000
- Original: 20000 → Amplified: 32767 (clipped)

### Performance Impact

Software amplification has minimal performance impact:
- **Processing time**: < 50ms for 5-second recording
- **CPU usage**: Negligible on Pi Zero 2 W
- **Memory**: < 1MB additional

## Summary

- **Default gain**: 2.0 (doubles volume)
- **Recommended range**: 1.5 - 3.0
- **Configuration**: Set `MICROPHONE_GAIN` in `.env` file
- **Testing**: Use `examples/mic_test.py` to test
- **Adjustment**: Increase if too quiet, decrease if distorted

For most users, setting `MICROPHONE_GAIN=2.0` will provide clear, reliable recordings for accurate transcription.
