# Rotary Encoder Volume Control

This document describes the rotary encoder feature for volume control and push-to-talk functionality in the Voice Assistant.

## Overview

The Voice Assistant uses a **KY-040 Rotary Encoder** to provide intuitive physical volume control and push-to-talk functionality. This replaces the simple push button from the original design.

## Hardware

### Component: KY-040 Rotary Encoder

The KY-040 is an incremental rotary encoder module with the following features:

- **5 Pins**: CLK, DT, SW, +, GND
- **Operating Voltage**: 3.3V to 5V (we use 3.3V)
- **Pulses per Revolution**: 20 detents (clicks)
- **Quadrature Output**: CLK and DT signals 90° phase-shifted
- **Push Button**: Integrated momentary switch

### Pin Connections

| Rotary Encoder Pin | Raspberry Pi Connection | Physical Pin | Purpose |
|-------------------|------------------------|--------------|----------|
| CLK | GPIO22 | Pin 15 | Rotation detection (encoder A) |
| DT | GPIO23 | Pin 16 | Rotation direction (encoder B) |
| SW | GPIO17 | Pin 11 | Push button (push-to-talk) |
| + (VCC) | 3.3V | Pin 1 (via breadboard) | Power |
| GND (-) | Ground | Pin 6 (via breadboard) | Ground |

### Wiring Instructions

1. **Power Connection**:
   - Connect encoder **+** pin to breadboard **positive rail** (3.3V from Pi Pin 1)
   - Connect encoder **-** pin to breadboard **negative rail** (GND from Pi Pin 6)

2. **Signal Connections** (direct wires to Pi GPIO):
   - Connect **CLK** to Raspberry Pi **Pin 15** (GPIO22)
   - Connect **DT** to Raspberry Pi **Pin 16** (GPIO23)
   - Connect **SW** to Raspberry Pi **Pin 11** (GPIO17)

3. **No External Components Needed**:
   - Internal pull-up resistors are enabled in software
   - Some KY-040 modules have built-in pull-ups (not required)

## Functionality

### Push-to-Talk (SW Button)

**Press the rotary encoder button** to start/stop recording:

1. **First Press**: Start recording (plays ascending beep tone)
2. **Second Press**: Stop recording (plays descending beep tone)
3. During playback: Press button to interrupt and return to ready state

This maintains the exact same functionality as the original push button design.

### Volume Control (Rotation)

**Turn the rotary encoder knob** to adjust system volume:

- **Clockwise rotation**: Increase volume by 5% per step
- **Counter-clockwise rotation**: Decrease volume by 5% per step
- **Volume range**: 0% to 100% (automatically clamped)
- **Total steps**: 20 steps from 0% to 100% (matches encoder detents)

### Real-Time Feedback

Volume changes are displayed in the console:
```
[VOLUME] ↑ 70% → 75%
[VOLUME] ↑ 75% → 80%
[VOLUME] ↓ 80% → 75%
```

## Software Implementation

### Configuration (.env file)

The following environment variables control rotary encoder behavior:

```bash
# GPIO Pins
BUTTON_PIN=17          # Rotary encoder SW (push button) pin
ROTARY_CLK_PIN=22      # Rotary encoder CLK pin
ROTARY_DT_PIN=23       # Rotary encoder DT pin

# Volume Settings
VOLUME_STEP=5          # Volume change per encoder step (%)
INITIAL_VOLUME=70      # Initial volume on startup (%)
```

### Volume Step Options

- **VOLUME_STEP=5** (default): 20 steps from 0% to 100%
- **VOLUME_STEP=10**: 10 larger steps from 0% to 100%
- **VOLUME_STEP=1**: 100 fine-control steps from 0% to 100%

### How It Works

1. **Initialization**:
   - System sets initial volume to 70% (configurable)
   - Rotary encoder callback is attached to detect rotation

2. **Rotation Detection**:
   - gpiozero's `RotaryEncoder` class monitors CLK and DT pins
   - Quadrature signals determine direction (clockwise vs counter-clockwise)
   - Each detent "click" triggers the callback

3. **Volume Adjustment**:
   - Callback calculates new volume: `new_volume = current_volume + (steps × VOLUME_STEP)`
   - Volume is clamped to 0-100% range
   - ALSA mixer is updated via `amixer sset Master XX%`
   - Change is logged to console

4. **Button Press**:
   - SW pin uses same GPIO17 as original button design
   - Maintains backward compatibility with existing recording logic

## Technical Details

### gpiozero RotaryEncoder

The implementation uses Python's `gpiozero` library:

```python
from gpiozero import RotaryEncoder

# Create rotary encoder instance
rotary_encoder = RotaryEncoder(ROTARY_CLK_PIN, ROTARY_DT_PIN, max_steps=0)

# Attach rotation callback
def on_rotate():
    steps = rotary_encoder.steps
    volume_change = steps * VOLUME_STEP
    # ... update volume ...
    rotary_encoder.steps = 0  # Reset counter

rotary_encoder.when_rotated = on_rotate
```

### ALSA Volume Control

Volume is controlled using ALSA mixer commands:

```bash
# Set volume to 75%
amixer sset Master 75%

# Get current volume
amixer sget Master
```

The Python code parses `amixer` output to read current volume:
```python
def get_system_volume():
    result = subprocess.run(['amixer', 'sget', 'Master'], ...)
    # Parse output like "Front Left: Playback 100 [75%]"
    # Returns: 75
```

## Troubleshooting

### Rotary Encoder Not Responding

**Symptoms**: Rotation doesn't change volume, button doesn't trigger recording

**Check**:
1. Verify wiring:
   - CLK → GPIO22 (Pin 15)
   - DT → GPIO23 (Pin 16)
   - SW → GPIO17 (Pin 11)
   - + → 3.3V (via breadboard)
   - - → GND (via breadboard)

2. Test GPIO pins:
   ```bash
   # Check if pins are accessible
   gpio readall
   ```

3. Check system logs:
   ```bash
   # Monitor volume changes
   python3 client.py
   # Rotate encoder and watch for [VOLUME] messages
   ```

### Volume Control Not Working

**Symptoms**: Button works, but rotation doesn't change volume

**Check**:
1. Verify ALSA mixer is available:
   ```bash
   amixer sget Master
   ```
   Should show output like:
   ```
   Simple mixer control 'Master',0
     Capabilities: pvolume pvolume-joined pswitch pswitch-joined
     Playback channels: Mono
     Limits: Playback 0 - 65536
     Mono: Playback 45875 [70%] [on]
   ```

2. Manually test volume control:
   ```bash
   amixer sset Master 50%
   amixer sset Master 80%
   ```

3. Check CLK and DT connections:
   - Swap CLK and DT if rotation direction is inverted
   - Ensure wires are firmly connected

### Rotation Direction Inverted

**Symptoms**: Clockwise decreases volume, counter-clockwise increases

**Solution**: Swap the CLK and DT pin connections (either in hardware or .env):

```bash
# In .env file, swap these values:
ROTARY_CLK_PIN=23
ROTARY_DT_PIN=22
```

### Volume Changes Are Too Large/Small

**Solution**: Adjust `VOLUME_STEP` in .env file:

```bash
# For finer control:
VOLUME_STEP=1

# For coarser control:
VOLUME_STEP=10
```

### No Response When Turning Slowly

**Cause**: This is normal behavior for incremental encoders

**Details**:
- The encoder only detects complete steps (detents/clicks)
- Turning without reaching a detent won't trigger volume change
- This is by design for stable, discrete volume control

## Advantages Over Push Button

### Previous Design (Push Button Only)
- ✓ Simple push-to-talk
- ✗ No volume control
- ✗ Had to use software commands or external device for volume

### New Design (Rotary Encoder)
- ✓ Push-to-talk (same functionality)
- ✓ Physical volume control (intuitive knob)
- ✓ Real-time feedback
- ✓ No software/SSH needed for volume adjustment
- ✓ Tactile feedback from detents
- ✓ Instant volume changes during playback

## Safety Features

### Volume Clamping
Volume is automatically clamped to valid range:
- **Minimum**: 0% (muted)
- **Maximum**: 100% (full volume)
- Turning beyond limits has no effect (no overflow)

### Graceful Fallback
If ALSA mixer is unavailable:
- System logs warning message
- Tracks volume in software
- Button functionality continues to work
- Volume control silently fails (doesn't crash)

## Future Enhancements

Potential future improvements:

1. **Visual Feedback**:
   - LED ring showing volume level
   - OLED display showing current volume percentage

2. **Multi-Function Button**:
   - Long press: Different function
   - Double press: Mute toggle
   - Press during rotation: Fine adjustment mode

3. **Volume Profiles**:
   - Different volume presets for different times of day
   - Save/restore last used volume

4. **Acceleration**:
   - Faster rotation = larger volume steps
   - Slow rotation = fine control

## See Also

- [HARDWARE.md](HARDWARE.md) - Complete hardware setup guide
- [GETTING_STARTED.md](GETTING_STARTED.md) - Initial setup instructions
- [troubleshooting.md](troubleshooting.md) - General troubleshooting guide

