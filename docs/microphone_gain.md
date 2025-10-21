# Microphone Gain Configuration

## Overview

The INMP441 microphone may record audio that's too quiet for reliable transcription. This guide explains software amplification to boost microphone volume.

## The Problem

At normal speaking distance (6-12 inches), recordings may be too quiet, causing:
- Poor transcription accuracy
- Missed words or phrases
- Low confidence scores from Whisper API
- Need to speak very loudly

## Solution: Software Gain

The voice assistant includes built-in amplification that processes audio after recording.

### Configure Gain

Edit your `.env` file:
```bash
nano .env
```

Add or modify:
```env
GROQ_API_KEY=your_api_key_here
MICROPHONE_GAIN=2.0
```

### Gain Values

| Value | Effect | Use Case |
|-------|--------|----------|
| 1.0 | No amplification | Mic already loud enough |
| 2.0 | Double volume | **Recommended starting point** |
| 2.5 | 2.5x volume | Quiet microphone |
| 3.0 | Triple volume | Very quiet microphone |
| 4.0 | Quadruple volume | Extremely quiet (may distort) |
| 5.0+ | Not recommended | Will likely distort |

### Testing Gain Values

1. **Start with 2.0** (default):
   ```env
   MICROPHONE_GAIN=2.0
   ```

2. **Test recording**:
   ```bash
   python3 javia.py
   # Press button and speak at normal volume
   ```

3. **If still too quiet**, increase to 3.0:
   ```env
   MICROPHONE_GAIN=3.0
   ```

4. **If too loud or distorted**, decrease to 1.5:
   ```env
   MICROPHONE_GAIN=1.5
   ```

## ALSA Volume Control

Also increase hardware capture volume:

```bash
# Check current volume
amixer -c 0 get Capture

# Set to 100%
amixer -c 0 set Capture 100%
```

Make permanent by adding to `~/.bashrc`:
```bash
echo "amixer -c 0 set Capture 100%" >> ~/.bashrc
```

## Hardware Adjustments

Physical improvements:
1. **Move microphone closer** - 6-12 inches optimal
2. **Reduce background noise** - Quieter environment
3. **Speak clearly** - Enunciate at normal volume
4. **Check wiring** - Ensure secure connections
5. **Verify power** - 3.3V should be stable

## How Software Gain Works

The amplification process:
1. **Recording** - Captures audio at normal levels
2. **Conversion** - Bytes → numpy array
3. **Amplification** - Each sample multiplied by gain
4. **Clipping** - Values clipped to prevent overflow (-32768 to 32767)
5. **Conversion** - Array → audio bytes
6. **Saving** - Amplified audio saved to WAV

### Code Reference
```python
# javia.py lines 152-186
def amplify_audio(audio_data, gain=2.0):
    audio_array = np.frombuffer(audio_data, dtype=np.int16)
    amplified = audio_array * gain
    amplified = np.clip(amplified, -32768, 32767)
    return amplified.astype(np.int16).tobytes()
```

## Troubleshooting

### Audio Still Too Quiet

1. **Increase gain**:
   ```env
   MICROPHONE_GAIN=3.5
   ```

2. **Check ALSA volume**:
   ```bash
   amixer -c 0 set Capture 100%
   ```

3. **Test directly**:
   ```bash
   arecord -D plughw:0,0 -c1 -r 48000 -f S16_LE -d 5 test.wav
   aplay test.wav
   ```

4. **Verify wiring** - Use multimeter

### Audio Distorted

1. **Reduce gain**:
   ```env
   MICROPHONE_GAIN=1.5
   ```

2. **Move microphone farther** - If too close

3. **Reduce ALSA volume**:
   ```bash
   amixer -c 0 set Capture 75%
   ```

4. **Speak at normal volume** - Don't shout

### Transcription Still Poor

1. **Check internet** - Slow connection causes timeouts
2. **Verify API key** - Ensure valid Groq API key
3. **Test recording**:
   ```bash
   arecord -D plughw:0,0 -c1 -r 48000 -f S16_LE -d 5 test.wav
   aplay test.wav
   ```
4. **Reduce background noise**
5. **Check microphone distance** - 6-12 inches optimal

## Recommended Settings

For most setups:
```env
GROQ_API_KEY=your_api_key_here
MICROPHONE_GAIN=2.0
SAMPLE_RATE=48000
```

### Optimal Speaking Technique
- **Distance**: 6-12 inches from mic
- **Volume**: Normal conversational voice
- **Pace**: Moderate speed, clear enunciation
- **Environment**: Quiet room, minimal echo
- **Position**: Speak directly toward microphone

## Advanced Configuration

### Different Environments

**Quiet Room:**
```env
MICROPHONE_GAIN=2.0
```

**Noisy Environment:**
```env
MICROPHONE_GAIN=3.0
```

**Close Microphone:**
```env
MICROPHONE_GAIN=1.5
```

### Monitoring Levels

Check RMS (Root Mean Square) levels:
```bash
arecord -D plughw:0,0 -c1 -r 48000 -f S16_LE -V mono -d 5 test.wav
```

Watch the VU meter during recording to see input levels.

## Technical Details

### Audio Format
- **Sample Rate**: 48000 Hz (required by googlevoicehat-soundcard)
- **Bit Depth**: 16-bit (int16)
- **Channels**: Mono (1 channel)
- **Format**: PCM WAV

### Gain Calculation
```
amplified_sample = original_sample × gain
```

Examples with gain = 2.0:
- Original: 1000 → Amplified: 2000
- Original: -500 → Amplified: -1000
- Original: 20000 → Amplified: 32767 (clipped)

### Performance Impact
- **Processing time**: <50ms for 5-second recording
- **CPU usage**: Negligible on Pi Zero 2 W
- **Memory**: <1MB additional

## Summary

- **Default gain**: 2.0 (doubles volume)
- **Recommended range**: 1.5-3.0
- **Configuration**: Set `MICROPHONE_GAIN` in `.env`
- **Adjustment**: Increase if quiet, decrease if distorted

Setting `MICROPHONE_GAIN=2.0` provides clear, reliable recordings for accurate transcription in most cases.

## Related Documentation

- Hardware Setup: `HARDWARE.md`
- Troubleshooting: `TROUBLESHOOTING.md`
- Audio Quality: `AUDIO_CLICKS.md`
