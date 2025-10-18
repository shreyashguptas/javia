# Hardware Setup Guide

## Components

### Required Hardware
- **Raspberry Pi Zero 2 W** - Mainboard with 40-pin GPIO header
- **INMP441 MEMS Microphone** - I2S digital microphone (24-bit, up to 64kHz)
- **MAX98357A I2S Amplifier** - 3W Class D amplifier with built-in DAC
- **3W 4Ω Speaker** - Connected to MAX98357A output terminals
- **Push Button** - Momentary switch (normally open)
- **Breadboard and jumper wires** - For connections
- **5V 3A Power Supply** - USB power adapter with quality cable

## Wiring Diagram

### INMP441 Microphone to Raspberry Pi
```
INMP441 Pin  →  Raspberry Pi Pin
─────────────────────────────────
VDD          →  3.3V (Pin 1)
GND          →  GND (Pin 6)
SCK          →  GPIO18/PCM_CLK (Pin 12)
WS           →  GPIO19/PCM_FS (Pin 35)
SD           →  GPIO20/PCM_DIN (Pin 38)
L/R          →  GND (Pin 6) [for left channel]
```

### MAX98357A Amplifier to Raspberry Pi
```
MAX98357A Pin  →  Raspberry Pi Pin
───────────────────────────────────
VDD            →  3.3V (Pin 1)
GND            →  GND (Pin 6)
BCLK           →  GPIO18/PCM_CLK (Pin 12)
LRC            →  GPIO19/PCM_FS (Pin 35)
DIN            →  GPIO21/PCM_DOUT (Pin 40)
SD (Shutdown)  →  GPIO27 (Pin 13) [prevents audio clicks]
```

### Speaker to MAX98357A
```
Speaker Wire  →  MAX98357A Terminal
─────────────────────────────────
Red           →  OUT+
Black         →  OUT-
```

### Button to Raspberry Pi
```
Button Terminal  →  Raspberry Pi Pin
────────────────────────────────────
Terminal 1       →  GPIO17 (Pin 11)
Terminal 2       →  GND (Pin 6)
```

## Pin Reference

### Raspberry Pi Zero 2 W GPIO Header
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

### I2S Signal Sharing
Both microphone and amplifier share the same clock signals:
- **GPIO18 (PCM_CLK)** - I2S bit clock (shared by both)
- **GPIO19 (PCM_FS)** - I2S frame sync/word select (shared by both)
- **GPIO20 (PCM_DIN)** - Data from microphone to Pi
- **GPIO21 (PCM_DOUT)** - Data from Pi to amplifier

## Assembly Steps

### 1. Power Rails
1. Connect Pi **Pin 1 (3.3V)** to breadboard **positive rail**
2. Connect Pi **Pin 6 (GND)** to breadboard **negative rail**
3. Verify voltage with multimeter: should read ~3.3V

### 2. INMP441 Microphone
1. Insert INMP441 into breadboard
2. Connect **VDD** to positive rail (3.3V)
3. Connect **GND** to negative rail
4. Connect **SCK** to Pi GPIO18 (Pin 12)
5. Connect **WS** to Pi GPIO19 (Pin 35)
6. Connect **SD** to Pi GPIO20 (Pin 38)
7. Connect **L/R** to negative rail (configures left channel)

### 3. MAX98357A Amplifier
1. Insert MAX98357A into breadboard
2. Connect **VDD** to positive rail (3.3V)
3. Connect **GND** to negative rail
4. Connect **BCLK** to Pi GPIO18 (Pin 12) - shares with microphone
5. Connect **LRC** to Pi GPIO19 (Pin 35) - shares with microphone
6. Connect **DIN** to Pi GPIO21 (Pin 40)
7. Connect **SD** to Pi GPIO27 (Pin 13) - enables click suppression

### 4. Speaker
1. Connect speaker **red wire** to MAX98357A **OUT+** terminal
2. Connect speaker **black wire** to MAX98357A **OUT-** terminal
3. Verify polarity is correct

### 5. Button
1. Connect one button terminal to Pi GPIO17 (Pin 11)
2. Connect other button terminal to Pi GND (Pin 6)
3. No pull-up resistor needed (software enables internal pull-up)

## Power Requirements

### Component Power Draw
- **Raspberry Pi Zero 2 W**: ~1.5W typical, 2W peak
- **INMP441 Microphone**: ~4.6mW (1.4mA @ 3.3V)
- **MAX98357A Idle**: ~165mW (50mA @ 3.3V)
- **MAX98357A Active**: Up to 3W when playing audio
- **Total System**: 2-6W depending on audio playback

### Recommended Power Supply
- **Minimum**: 5V 2.5A (12.5W)
- **Recommended**: 5V 3A (15W) ← Best for most cases
- **High Volume**: 5V 4A (20W) if using maximum speaker volume

### Power Supply Quality
- Use a **high-quality USB power adapter** (not phone charger)
- Use a **short, thick USB cable** (longer cables = more voltage drop)
- Verify no undervoltage warnings: `vcgencmd get_throttled`
- Expected result: `0x0` (no throttling)

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
- ❌ Confusing GPIO numbers with physical pin numbers
- ❌ Connecting speaker reversed polarity (won't damage, but may sound worse)
- ❌ Forgetting to connect L/R pin on INMP441 (mic won't work)
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

## Next Steps

After hardware assembly:
1. Configure I2S audio: See `README.md` → Software Configuration
2. Test audio devices: See `docs/TROUBLESHOOTING.md` → Audio Testing
3. Install software: See `README.md` → Install Dependencies

