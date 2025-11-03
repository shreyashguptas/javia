# Hardware Setup Guide

## Components

### Required Hardware
- **Raspberry Pi 5** - High-performance quad-core ARM Cortex-A76 with 40-pin GPIO header
- **2x INMP441 MEMS Microphones** - I2S digital microphones (24-bit, up to 64kHz) for stereo recording
- **MAX98357A I2S Amplifier** - 3W Class D amplifier with built-in DAC
- **3W 4Ω Speaker** - Connected to MAX98357A output terminals
- **KY-040 Rotary Encoder** - Rotary encoder with push button (for volume control and push-to-talk)
- **Breadboard and jumper wires** - For connections
- **5V 5A Power Supply** - USB-C power adapter (27W recommended for Pi 5)

## Wiring Diagram

**IMPORTANT GROUND NOTE**: 
- The Pi has multiple ground pins (6, 9, 14, 20, 25, 30, 34, 39)
- Connect **Pi Pin 6 (GND)** to your **breadboard negative rail** (ONE connection)
- Then connect ALL component grounds to the **breadboard negative rail**
- The breadboard distributes ground to all components

### Dual INMP441 Microphones to Raspberry Pi (Stereo Setup)

**CRITICAL**: Both microphones share the same I2S clock and data pins. The L/R pin determines which channel (left/right) each microphone uses.

#### INMP441 Microphone #1 (Left Channel)
```
INMP441 #1 Pin  →  Connection
─────────────────────────────────────────────────
VDD             →  3.3V (Pi Pin 1 via breadboard+)
GND             →  Ground (breadboard negative rail)
SCK             →  GPIO18/PCM_CLK (Pi Pin 12) [DIRECT - shared with Mic #2]
WS              →  GPIO19/PCM_FS (Pi Pin 35) [DIRECT - shared with Mic #2]
SD              →  GPIO20/PCM_DIN (Pi Pin 38) [DIRECT - shared with Mic #2]
L/R             →  Ground (breadboard negative rail) [LEFT channel select]
```

#### INMP441 Microphone #2 (Right Channel)
```
INMP441 #2 Pin  →  Connection
─────────────────────────────────────────────────
VDD             →  3.3V (Pi Pin 1 via breadboard+)
GND             →  Ground (breadboard negative rail)
SCK             →  GPIO18/PCM_CLK (Pi Pin 12) [DIRECT - shared with Mic #1]
WS              →  GPIO19/PCM_FS (Pi Pin 35) [DIRECT - shared with Mic #1]
SD              →  GPIO20/PCM_DIN (Pi Pin 38) [DIRECT - shared with Mic #1]
L/R             →  3.3V (Pi Pin 1 via breadboard+) [RIGHT channel select]
```

**Key Points:**
- Both microphones share SCK, WS, and SD pins (I2S bus)
- L/R pin determines which channel: GND = Left, 3.3V = Right
- I2S protocol multiplexes both microphones on the same data line
- Spacing between mics: 3-6cm recommended for optimal stereo separation

### MAX98357A Amplifier to Raspberry Pi
```
MAX98357A Pin  →  Connection
─────────────────────────────────────────────────
VDD            →  3.3V (Pi Pin 1 via breadboard+)
GND            →  Ground (breadboard negative rail)
BCLK           →  GPIO18/PCM_CLK (Pi Pin 12) [DIRECT]
LRC            →  GPIO19/PCM_FS (Pi Pin 35) [DIRECT]
DIN            →  GPIO21/PCM_DOUT (Pi Pin 40) [DIRECT]
SD (Shutdown)  →  GPIO27 (Pi Pin 13) [DIRECT - prevents audio clicks]
```

### Speaker to MAX98357A
```
Speaker Wire  →  MAX98357A Terminal
─────────────────────────────────
Red           →  OUT+ (screw terminal)
Black         →  OUT- (screw terminal)
```

### KY-040 Rotary Encoder to Raspberry Pi
```
Rotary Encoder Pin  →  Connection
──────────────────────────────────────────────────────────
CLK                 →  GPIO22 (Pi Pin 15) [DIRECT]
DT                  →  GPIO23 (Pi Pin 16) [DIRECT]
SW (Button)         →  GPIO17 (Pi Pin 11) [DIRECT]
+ (VCC)             →  3.3V (Pi Pin 1 via breadboard+)
GND (-)             →  Ground (breadboard negative rail)
```

**Note on Rotary Encoder:**
- **CLK & DT pins**: Used for detecting rotation direction (clockwise/counter-clockwise)
- **SW pin**: Push button function - press to start/stop recording (same as old button)
- **Rotation**: Turn clockwise to increase volume, counter-clockwise to decrease
- **Volume step**: 5% per click (configurable in .env)
- **No external pull-up resistors needed**: Internal pull-ups enabled in software

## Pin Reference

### Raspberry Pi 5 GPIO Header
```
Pin  1  (3.3V)     ●○  Pin  2  (5V)
Pin  3             ●○  Pin  4  (5V)
Pin  5             ●○  Pin  6  (GND)
Pin  7             ●○  Pin  8
Pin  9  (GND)      ●○  Pin 10
Pin 11 (GPIO17)    ●○  Pin 12 (GPIO18/PCM_CLK)
Pin 13 (GPIO27)    ●○  Pin 14 (GND)
Pin 15 (GPIO22)    ●○  Pin 16 (GPIO23)
...
Pin 35 (GPIO19/PCM_FS)  ●○  Pin 36
Pin 37             ●○  Pin 38 (GPIO20/PCM_DIN)
Pin 39 (GND)       ●○  Pin 40 (GPIO21/PCM_DOUT)
```

### Connection Summary by Pi Pin

**Power Connections** (via breadboard rails):
- **Pin 1 (3.3V)** → Breadboard positive rail → Powers INMP441 VDD & MAX98357A VDD
- **Pin 6 (GND)** → Breadboard negative rail → Common ground for all components

**I2S Shared Signals** (direct wire connections):
- **Pin 12 (GPIO18/PCM_CLK)** → Both Microphones SCK & Amplifier BCLK [Shared]
- **Pin 35 (GPIO19/PCM_FS)** → Both Microphones WS & Amplifier LRC [Shared]

**I2S Data Lines** (direct wire connections):
- **Pin 38 (GPIO20/PCM_DIN)** → Both Microphones SD (stereo data from mics to Pi)
- **Pin 40 (GPIO21/PCM_DOUT)** → Amplifier DIN (data from Pi to amp)

**Control Pins** (direct wire connections):
- **Pin 11 (GPIO17)** → Rotary encoder SW/button pin (push-to-talk)
- **Pin 13 (GPIO27)** → Amplifier SD/Shutdown pin (prevents audio clicks)
- **Pin 15 (GPIO22)** → Rotary encoder CLK pin (rotation detection)
- **Pin 16 (GPIO23)** → Rotary encoder DT pin (rotation direction)

## Assembly Steps

### 1. Power Rails Setup
**Critical First Step:**
1. Connect Pi **Pin 1 (3.3V)** to breadboard **positive rail** (red line)
2. Connect Pi **Pin 6 (GND)** to breadboard **negative rail** (blue line)
3. Verify voltage with multimeter: should read ~3.3V between rails
4. **Note**: These are the ONLY two wires connecting Pi power to breadboard

**Why Pin 6 for ground?**
- Pi 5 has 8 ground pins (6, 9, 14, 20, 25, 30, 34, 39) - any works
- Pin 6 is chosen because it's adjacent to Pin 1 (3.3V), making breadboard wiring neat
- You only need ONE ground connection - the breadboard distributes it

### 2. Dual INMP441 Microphones (Stereo Setup)

#### Microphone #1 (Left Channel)
1. Insert INMP441 #1 into breadboard
2. Connect **VDD** → breadboard **positive rail** (gets 3.3V)
3. Connect **GND** → breadboard **negative rail** (common ground)
4. Connect **L/R** → breadboard **negative rail** (LEFT channel: GND)
5. Connect **SCK** → Pi **Pin 12 (GPIO18)** [DIRECT wire to Pi]
6. Connect **WS** → Pi **Pin 35 (GPIO19)** [DIRECT wire to Pi]
7. Connect **SD** → Pi **Pin 38 (GPIO20)** [DIRECT wire to Pi]

#### Microphone #2 (Right Channel)
1. Insert INMP441 #2 into breadboard (space 3-6cm from Mic #1)
2. Connect **VDD** → breadboard **positive rail** (gets 3.3V)
3. Connect **GND** → breadboard **negative rail** (common ground)
4. Connect **L/R** → breadboard **positive rail** (RIGHT channel: 3.3V)
5. Connect **SCK** → Pi **Pin 12 (GPIO18)** [DIRECT wire to Pi - shared with Mic #1]
6. Connect **WS** → Pi **Pin 35 (GPIO19)** [DIRECT wire to Pi - shared with Mic #1]
7. Connect **SD** → Pi **Pin 38 (GPIO20)** [DIRECT wire to Pi - shared with Mic #1]

**Critical Notes:**
- **L/R Pin Determines Channel**: Mic #1 L/R→GND (left), Mic #2 L/R→3.3V (right)
- **Shared I2S Bus**: Both mics connect to the same SCK, WS, and SD pins
- **Wire Types**: Steps 2-4 use breadboard rails, steps 5-7 are direct GPIO wires
- **Microphone Spacing**: Position 3-6cm apart for optimal stereo separation
- **Orientation**: Point both microphones in the same direction (sound ports aligned)

### 3. MAX98357A Amplifier
1. Insert MAX98357A into breadboard
2. Connect **VDD** → breadboard **positive rail** (gets 3.3V)
3. Connect **GND** → breadboard **negative rail** (common ground)
4. Connect **BCLK** → Pi **Pin 12 (GPIO18)** [DIRECT - shared with mic SCK]
5. Connect **LRC** → Pi **Pin 35 (GPIO19)** [DIRECT - shared with mic WS]
6. Connect **DIN** → Pi **Pin 40 (GPIO21)** [DIRECT wire to Pi]
7. Connect **SD** → Pi **Pin 13 (GPIO27)** [DIRECT - prevents audio clicks]

**Note**: Pins 12 and 35 each have TWO wires (one from mic, one from amp)

### 4. Speaker
1. Connect speaker **red wire** to MAX98357A **OUT+** terminal
2. Connect speaker **black wire** to MAX98357A **OUT-** terminal
3. Verify polarity is correct

### 5. Rotary Encoder
1. Connect **CLK** → Pi **Pin 15 (GPIO22)** [DIRECT wire to Pi]
2. Connect **DT** → Pi **Pin 16 (GPIO23)** [DIRECT wire to Pi]
3. Connect **SW** → Pi **Pin 11 (GPIO17)** [DIRECT wire to Pi]
4. Connect **+** (VCC) → breadboard **positive rail** (gets 3.3V)
5. Connect **-** (GND) → breadboard **negative rail** (common ground)
6. No pull-up resistors needed (software enables internal pull-ups)

**Functionality**:
- **Press SW button**: Start/stop recording (push-to-talk)
- **Turn clockwise**: Increase volume by 5% per step
- **Turn counter-clockwise**: Decrease volume by 5% per step
- **Volume range**: 0% to 100% (automatically clamped)

**Note**: Rotary encoder ground goes to breadboard, NOT directly to Pi Pin 6

## Power Requirements

### Component Power Draw
- **Raspberry Pi 5**: ~4-8W typical, up to 12W peak (significantly higher than Pi Zero)
- **2x INMP441 Microphones**: ~9.2mW total (2.8mA @ 3.3V for both)
- **MAX98357A Idle**: ~165mW (50mA @ 3.3V)
- **MAX98357A Active**: Up to 3W when playing audio
- **KY-040 Rotary Encoder**: ~1.65mW (0.5mA @ 3.3V)
- **Total System**: 8-18W depending on CPU load and audio playback

### Recommended Power Supply
- **Official Pi 5 Power Supply**: 5V 5A (27W) USB-C ← **Strongly recommended**
- **Minimum**: 5V 3A (15W) USB-C with good quality cable
- **Do NOT use**: Old micro-USB chargers or low-quality USB-C adapters

### Power Supply Quality
- Use the **official Raspberry Pi 5 27W USB-C Power Supply** for best results
- Pi 5 requires USB-C Power Delivery (PD) or high-quality USB-C adapter
- Verify no undervoltage warnings: `vcgencmd get_throttled`
- Expected result: `0x0` (no throttling)
- **Note**: Pi 5 has higher power requirements than previous models

## Hardware Notes

### INMP441 Microphone (Dual Setup)
- **Type**: MEMS omnidirectional microphone
- **Interface**: I2S digital output
- **Resolution**: 24-bit
- **Sample Rate**: Up to 64kHz (we use 48kHz stereo)
- **SNR**: 61dB
- **Sensitivity**: -26dBFS
- **Power**: 3.3V, 1.4mA per microphone (2.8mA total for both)
- **Configuration**: Stereo pair (L/R channel select via L/R pin)
- **Channel Select**: L/R pin LOW = Left channel, L/R pin HIGH = Right channel
- **Benefits**: Stereo recording, spatial audio, better noise rejection, beamforming capability

### MAX98357A Amplifier
- **Type**: Class D amplifier with integrated DAC
- **Output Power**: 3.2W into 4Ω @ 5V
- **THD+N**: 0.015% typical
- **Sample Rate**: 8kHz to 96kHz
- **Bit Depth**: 16-bit to 32-bit
- **Shutdown Pin**: Active high (HIGH = on, LOW = off)

### KY-040 Rotary Encoder
- **Type**: Incremental rotary encoder with push button
- **Operating Voltage**: 3.3V to 5V (3.3V compatible)
- **Pulses per Revolution**: 20 (with detents)
- **Output Type**: Quadrature (CLK and DT signals 90° out of phase)
- **Push Button**: Momentary switch (normally open)
- **Rotation Detection**: Clockwise and counter-clockwise
- **Power**: ~0.5mA @ 3.3V (negligible)
- **Features**: Built-in pull-up resistors (optional - we enable internal pull-ups in software)

### googlevoicehat-soundcard Driver
The software driver `googlevoicehat-soundcard` is used because:
- It properly configures I2S for simultaneous recording and playback
- Supports 48000 Hz sample rate required by our hardware
- Compatible with INMP441 + MAX98357A setup
- Widely tested and stable

**Note**: This is a software driver, not physical Google Voice HAT hardware.

## Connection Tips

### Best Practices
1. **Keep wires short** - Minimizes noise and signal degradation
2. **Separate power and signal** - Don't run them parallel on breadboard
3. **Secure connections** - Push wires firmly into breadboard
4. **Test continuity** - Use multimeter to verify connections
5. **Check polarity** - Verify power connections before powering on

### Common Mistakes to Avoid
- ❌ Confusing GPIO numbers with physical pin numbers (use physical pin numbers!)
- ❌ Connecting multiple wires directly to Pi Pin 6 (use breadboard ground rail instead)
- ❌ Forgetting breadboard power rails (Pi Pin 1 and 6 must connect to breadboard first)
- ❌ Connecting speaker reversed polarity (won't damage, but may sound worse)
- ❌ Forgetting to connect L/R pin on INMP441 to ground (mic won't work)
- ❌ Using insufficient power supply (causes audio glitches)
- ❌ Loose breadboard connections (intermittent failures)

## Verification Checklist

Before first power-on:
- [ ] All power connections verified (3.3V and GND)
- [ ] No short circuits between power rails
- [ ] GPIO18/19 shared correctly between both mics and amp
- [ ] GPIO20 connected to both microphone SD pins
- [ ] **CRITICAL**: Mic #1 L/R → GND, Mic #2 L/R → 3.3V
- [ ] Both microphones spaced 3-6cm apart
- [ ] GPIO21 connected to amplifier DIN pin
- [ ] GPIO27 connected to amplifier SD pin
- [ ] Speaker connected to amplifier output
- [ ] Rotary encoder CLK connected to GPIO22
- [ ] Rotary encoder DT connected to GPIO23
- [ ] Rotary encoder SW connected to GPIO17
- [ ] Rotary encoder + connected to 3.3V (via breadboard)
- [ ] Rotary encoder - connected to GND (via breadboard)
- [ ] Power supply is 5A (27W recommended for Pi 5)

After power-on:
- [ ] Pi boots successfully
- [ ] No undervoltage warnings
- [ ] No smoke or overheating components
- [ ] Audio devices detected with `arecord -l` and `aplay -l`

## Troubleshooting Hardware

### Microphones Not Detected or Only One Channel Working
**Check:**
1. 3.3V power at both INMP441 VDD pins
2. All I2S signal connections (SCK, WS, SD) to both microphones
3. **CRITICAL**: Mic #1 L/R pin → GND (left channel), Mic #2 L/R pin → 3.3V (right channel)
4. Both microphones SD pins connected to Pi Pin 38 (GPIO20)
5. No loose breadboard connections
6. Test with: `arecord -D plughw:CARD=sndrpigooglevoi,DEV=0 -f S16_LE -r 48000 -c 2 test.wav`
7. Check stereo recording: `aplay test.wav` and verify both channels have audio

### Speaker Not Working
**Check:**
1. 3.3V power at MAX98357A VDD pin
2. All I2S signal connections (BCLK, LRC, DIN)
3. Speaker connected to OUT+ and OUT-
4. GPIO27 (SD pin) is HIGH during playback

### Audio Clicks/Pops
**Solution:**
- Ensure GPIO27 is connected to MAX98357A SD pin
- Software controls this pin to prevent clicks
- See `docs/TROUBLESHOOTING.md` for more details

### Rotary Encoder Not Responding
**Check:**
1. SW pin connected to GPIO17 and GND
2. CLK pin connected to GPIO22
3. DT pin connected to GPIO23
4. + pin connected to 3.3V (via breadboard)
5. - pin connected to GND (via breadboard)
6. No wiring to wrong GPIO pins
7. Encoder makes contact when pressed/rotated

### Volume Control Not Working
**Check:**
1. Run `amixer sget Master` to verify ALSA mixer is available
2. Check that CLK and DT pins are properly connected
3. Try rotating the encoder in both directions
4. Check system logs for volume change messages
5. Verify VOLUME_STEP is set in .env file (default: 5)

## Visual Wiring Summary

### Quick Reference - All Connections

```
RASPBERRY PI 5                 BREADBOARD                    COMPONENTS
═════════════                  ══════════                    ══════════

Pin 1 (3.3V) ────────────────► Positive Rail ──┬──────────► INMP441 #1 VDD
                                                ├──────────► INMP441 #2 VDD
                                                ├──────────► INMP441 #2 L/R (Right channel)
                                                ├──────────► MAX98357A VDD
                                                └──────────► Rotary Encoder +

Pin 6 (GND) ─────────────────► Negative Rail ──┬──────────► INMP441 #1 GND
                                                ├──────────► INMP441 #1 L/R (Left channel)
                                                ├──────────► INMP441 #2 GND
                                                ├──────────► MAX98357A GND
                                                └──────────► Rotary Encoder -

Pin 11 (GPIO17) ──────────────────────────────────────────► Rotary Encoder SW

Pin 12 (GPIO18) ──┬────────────────────────────────────────► INMP441 #1 SCK
                  ├────────────────────────────────────────► INMP441 #2 SCK
                  └────────────────────────────────────────► MAX98357A BCLK

Pin 13 (GPIO27) ──────────────────────────────────────────► MAX98357A SD

Pin 15 (GPIO22) ──────────────────────────────────────────► Rotary Encoder CLK

Pin 16 (GPIO23) ──────────────────────────────────────────► Rotary Encoder DT

Pin 35 (GPIO19) ──┬────────────────────────────────────────► INMP441 #1 WS
                  ├────────────────────────────────────────► INMP441 #2 WS
                  └────────────────────────────────────────► MAX98357A LRC

Pin 38 (GPIO20) ──┬────────────────────────────────────────► INMP441 #1 SD
                  └────────────────────────────────────────► INMP441 #2 SD

Pin 40 (GPIO21) ──────────────────────────────────────────► MAX98357A DIN


MAX98357A OUT+ ───────────────────────────────────────────► Speaker Red
MAX98357A OUT- ───────────────────────────────────────────► Speaker Black
```

### Wire Count Summary
- **2 wires**: Pi → Breadboard (3.3V and GND)
- **10 wires**: Breadboard → Components (power and ground distribution)
- **13 wires**: Pi GPIO → Components (direct signal wires - 3 shared I2S pins each have 3 connections)
- **2 wires**: Amplifier → Speaker
- **Total: 27 wires**

### Ground Distribution Explained
```
Pi Pin 6 (GND)
      ↓
Breadboard Negative Rail (distributes to 6 connections)
      ├─→ INMP441 #1 GND
      ├─→ INMP441 #1 L/R (Left channel select)
      ├─→ INMP441 #2 GND
      ├─→ MAX98357A GND
      └─→ Rotary Encoder GND (-)
```

**Key Point**: Only ONE wire goes from Pi to breadboard ground. The breadboard then distributes ground to all components that need it.

### Power (3.3V) Distribution Explained
```
Pi Pin 1 (3.3V)
      ↓
Breadboard Positive Rail (distributes to 5 connections)
      ├─→ INMP441 #1 VDD
      ├─→ INMP441 #2 VDD
      ├─→ INMP441 #2 L/R (Right channel select)
      ├─→ MAX98357A VDD
      └─→ Rotary Encoder VCC (+)
```

## Next Steps

After hardware assembly:
1. Configure I2S audio: See `README.md` → Software Configuration
2. Test audio devices: See `docs/TROUBLESHOOTING.md` → Audio Testing
3. Install software: See `README.md` → Install Dependencies

