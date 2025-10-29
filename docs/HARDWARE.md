# Hardware Setup Guide

## Components

### Required Hardware
- **Raspberry Pi 5** - High-performance quad-core ARM Cortex-A76 with 40-pin GPIO header
- **INMP441 MEMS Microphone** - I2S digital microphone (24-bit, up to 64kHz)
- **MAX98357A I2S Amplifier** - 3W Class D amplifier with built-in DAC
- **3W 4Ω Speaker** - Connected to MAX98357A output terminals
- **Push Button** - Momentary switch (normally open)
- **Breadboard and jumper wires** - For connections
- **5V 5A Power Supply** - USB-C power adapter (27W recommended for Pi 5)

## Wiring Diagram

**IMPORTANT GROUND NOTE**: 
- The Pi has multiple ground pins (6, 9, 14, 20, 25, 30, 34, 39)
- Connect **Pi Pin 6 (GND)** to your **breadboard negative rail** (ONE connection)
- Then connect ALL component grounds to the **breadboard negative rail**
- The breadboard distributes ground to all components

### INMP441 Microphone to Raspberry Pi
```
INMP441 Pin  →  Connection
─────────────────────────────────────────────────
VDD          →  3.3V (Pi Pin 1 via breadboard+)
GND          →  Ground (breadboard negative rail)
SCK          →  GPIO18/PCM_CLK (Pi Pin 12) [DIRECT]
WS           →  GPIO19/PCM_FS (Pi Pin 35) [DIRECT]
SD           →  GPIO20/PCM_DIN (Pi Pin 38) [DIRECT]
L/R          →  Ground (breadboard negative rail) [for left channel]
```

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

### Button to Raspberry Pi
```
Button Terminal  →  Connection
────────────────────────────────────────────────
Terminal 1       →  GPIO17 (Pi Pin 11) [DIRECT]
Terminal 2       →  Ground (breadboard negative rail)
```

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
Pin 15             ●○  Pin 16
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
- **Pin 12 (GPIO18/PCM_CLK)** → Microphone SCK & Amplifier BCLK [Shared]
- **Pin 35 (GPIO19/PCM_FS)** → Microphone WS & Amplifier LRC [Shared]

**I2S Data Lines** (direct wire connections):
- **Pin 38 (GPIO20/PCM_DIN)** → Microphone SD (data from mic to Pi)
- **Pin 40 (GPIO21/PCM_DOUT)** → Amplifier DIN (data from Pi to amp)

**Control Pins** (direct wire connections):
- **Pin 11 (GPIO17)** → Push button (other button terminal to ground)
- **Pin 13 (GPIO27)** → Amplifier SD/Shutdown pin (prevents audio clicks)

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

### 2. INMP441 Microphone
1. Insert INMP441 into breadboard
2. Connect **VDD** → breadboard **positive rail** (gets 3.3V)
3. Connect **GND** → breadboard **negative rail** (common ground)
4. Connect **L/R** → breadboard **negative rail** (configures left channel)
5. Connect **SCK** → Pi **Pin 12 (GPIO18)** [DIRECT wire to Pi]
6. Connect **WS** → Pi **Pin 35 (GPIO19)** [DIRECT wire to Pi]
7. Connect **SD** → Pi **Pin 38 (GPIO20)** [DIRECT wire to Pi]

**Wire types**: Steps 2-4 use breadboard, steps 5-7 are direct GPIO wires

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

### 5. Button
1. Connect one button terminal → Pi **Pin 11 (GPIO17)** [DIRECT wire to Pi]
2. Connect other button terminal → breadboard **negative rail** (common ground)
3. No pull-up resistor needed (software enables internal pull-up)

**Note**: Button ground goes to breadboard, NOT directly to Pi Pin 6

## Power Requirements

### Component Power Draw
- **Raspberry Pi 5**: ~4-8W typical, up to 12W peak (significantly higher than Pi Zero)
- **INMP441 Microphone**: ~4.6mW (1.4mA @ 3.3V)
- **MAX98357A Idle**: ~165mW (50mA @ 3.3V)
- **MAX98357A Active**: Up to 3W when playing audio
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

### INMP441 Microphone
- **Type**: MEMS omnidirectional microphone
- **Interface**: I2S digital output
- **Resolution**: 24-bit
- **Sample Rate**: Up to 64kHz (we use 48kHz)
- **SNR**: 61dB
- **Sensitivity**: -26dBFS
- **Power**: 3.3V, 1.4mA

### MAX98357A Amplifier
- **Type**: Class D amplifier with integrated DAC
- **Output Power**: 3.2W into 4Ω @ 5V
- **THD+N**: 0.015% typical
- **Sample Rate**: 8kHz to 96kHz
- **Bit Depth**: 16-bit to 32-bit
- **Shutdown Pin**: Active high (HIGH = on, LOW = off)

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
- [ ] GPIO18/19 shared correctly between mic and amp
- [ ] GPIO20 connected to microphone SD pin
- [ ] GPIO21 connected to amplifier DIN pin
- [ ] GPIO27 connected to amplifier SD pin
- [ ] Speaker connected to amplifier output
- [ ] Button connected to GPIO17 and GND
- [ ] Power supply is 3A or higher

After power-on:
- [ ] Pi boots successfully
- [ ] No undervoltage warnings
- [ ] No smoke or overheating components
- [ ] Audio devices detected with `arecord -l` and `aplay -l`

## Troubleshooting Hardware

### Microphone Not Detected
**Check:**
1. 3.3V power at INMP441 VDD pin
2. All I2S signal connections (SCK, WS, SD)
3. L/R pin connected to GND
4. No loose breadboard connections

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

### Button Not Responding
**Check:**
1. Button connected to GPIO17 and GND
2. Button makes contact when pressed
3. No wiring to wrong GPIO pin

## Visual Wiring Summary

### Quick Reference - All Connections

```
RASPBERRY PI 5                 BREADBOARD                    COMPONENTS
═════════════                  ══════════                    ══════════

Pin 1 (3.3V) ────────────────► Positive Rail ──┬──────────► INMP441 VDD
                                                └──────────► MAX98357A VDD

Pin 6 (GND) ─────────────────► Negative Rail ──┬──────────► INMP441 GND
                                                ├──────────► INMP441 L/R
                                                ├──────────► MAX98357A GND
                                                └──────────► Button Terminal 2

Pin 11 (GPIO17) ──────────────────────────────────────────► Button Terminal 1

Pin 12 (GPIO18) ──┬────────────────────────────────────────► INMP441 SCK
                  └────────────────────────────────────────► MAX98357A BCLK

Pin 13 (GPIO27) ──────────────────────────────────────────► MAX98357A SD

Pin 35 (GPIO19) ──┬────────────────────────────────────────► INMP441 WS
                  └────────────────────────────────────────► MAX98357A LRC

Pin 38 (GPIO20) ──────────────────────────────────────────► INMP441 SD

Pin 40 (GPIO21) ──────────────────────────────────────────► MAX98357A DIN


MAX98357A OUT+ ───────────────────────────────────────────► Speaker Red
MAX98357A OUT- ───────────────────────────────────────────► Speaker Black
```

### Wire Count Summary
- **2 wires**: Pi → Breadboard (3.3V and GND)
- **5 wires**: Breadboard → Components (power and ground distribution)
- **8 wires**: Pi GPIO → Components (direct signal wires)
- **2 wires**: Amplifier → Speaker
- **Total: 17 wires**

### Ground Distribution Explained
```
Pi Pin 6 (GND)
      ↓
Breadboard Negative Rail (distributes to 4 connections)
      ├─→ INMP441 GND
      ├─→ INMP441 L/R
      ├─→ MAX98357A GND
      └─→ Button (one terminal)
```

**Key Point**: Only ONE wire goes from Pi to breadboard ground. The breadboard then distributes ground to all four components that need it.

## Next Steps

After hardware assembly:
1. Configure I2S audio: See `README.md` → Software Configuration
2. Test audio devices: See `docs/TROUBLESHOOTING.md` → Audio Testing
3. Install software: See `README.md` → Install Dependencies

