# Hardware Setup Guide

## Components Overview

### Raspberry Pi Zero 2 W
- **Mainboard**: Raspberry Pi Zero 2 W
- **Power**: 5V via micro USB or GPIO pins
- **GPIO**: 40-pin header with I2S support

### INMP441 MEMS Microphone
- **Type**: Omnidirectional MEMS microphone
- **Interface**: I2S digital
- **Resolution**: 24-bit
- **Sample Rate**: Up to 64 kHz
- **Power**: 3.3V

### MAX98357A I2S Amplifier
- **Type**: 3W Class D amplifier
- **Interface**: I2S digital
- **Output**: 3W into 4Ω
- **Power**: 3.3V
- **Features**: Built-in DAC, no external components needed

### Speaker
- **Type**: 3W 4Ω Mini Speaker
- **Interface**: JST-PH2.0 connector
- **Power**: 3W maximum

## Detailed Wiring Instructions

### Step 1: Power Connections
1. Connect **Pi 3.3V (Pin 1)** to breadboard positive rail
2. Connect **Pi GND (Pin 6)** to breadboard negative rail
3. Connect **Pi GND (Pin 9)** to breadboard negative rail (additional ground)

### Step 2: INMP441 Microphone
```
INMP441 Pin → Raspberry Pi Pin
VDD         → 3.3V (Pin 1)
GND         → GND (Pin 6)
SCK         → GPIO18/PCM_CLK (Pin 12)
WS          → GPIO19/PCM_FS (Pin 35)
SD          → GPIO20/PCM_DIN (Pin 38)
L/R         → GND (Pin 6) [Left channel]
```

### Step 3: MAX98357A Amplifier
```
MAX98357A Pin → Raspberry Pi Pin
VDD           → 3.3V (Pin 1)
GND           → GND (Pin 6)
BCLK          → GPIO18/PCM_CLK (Pin 12)
LRC           → GPIO19/PCM_FS (Pin 35)
DIN           → GPIO20/PCM_DOUT (Pin 40)
SD (Shutdown) → GPIO27 (Pin 13) ← IMPORTANT: Prevents clicks/pops
```

### Step 4: Speaker Connection
```
Speaker → MAX98357A
Red     → OUT+ terminal
Black   → OUT- terminal
```

### Step 5: Button Connection
```
Button → Raspberry Pi
Terminal 1 → GPIO17 (Pin 11)
Terminal 2 → GND (Pin 6)
```

## Pin Reference

### Raspberry Pi Zero 2 W GPIO Pins
```
Pin 1  - 3.3V Power
Pin 6  - Ground
Pin 9  - Ground
Pin 11 - GPIO17 (Button)
Pin 12 - GPIO18/PCM_CLK (I2S Clock)
Pin 35 - GPIO19/PCM_FS (I2S Frame Sync)
Pin 38 - GPIO20/PCM_DIN (I2S Data In)
Pin 40 - GPIO20/PCM_DOUT (I2S Data Out)
```

## Breadboard Layout

### Recommended Layout
1. **Top Rail**: 3.3V power distribution
2. **Bottom Rail**: Ground distribution
3. **Left Side**: INMP441 microphone
4. **Right Side**: MAX98357A amplifier
5. **Center**: Button and jumper wires

### Connection Tips
- Use short jumper wires to minimize noise
- Ensure all connections are secure
- Double-check power polarity
- Keep I2S signal wires away from power lines

## Power Requirements

### Total Power Consumption
- **Raspberry Pi Zero 2 W**: ~1.5W
- **INMP441 Microphone**: ~1.4mA @ 3.3V
- **MAX98357A Amplifier**: ~50mA @ 3.3V (idle)
- **Speaker**: Up to 3W (when playing audio)

### Recommended Power Supply
- **Minimum**: 5V 2A USB power adapter
- **Recommended**: 5V 3A USB power adapter
- **For high volume**: 5V 4A USB power adapter

## Testing Connections

### Before Power On
1. Verify all connections with multimeter
2. Check for short circuits
3. Ensure proper polarity
4. Confirm breadboard integrity

### After Power On
1. Check 3.3V rail voltage
2. Verify ground continuity
3. Test GPIO pin states
4. Monitor power consumption

## Troubleshooting Hardware

### No Audio Input
- Check microphone power (3.3V)
- Verify I2S signal connections
- Test with multimeter
- Check for loose connections

### No Audio Output
- Verify amplifier power
- Check speaker connections
- Test amplifier with multimeter
- Confirm I2S signal routing

### Button Not Working
- Check GPIO17 connection
- Verify pull-up resistor
- Test button continuity
- Check GPIO configuration

### Power Issues
- Measure 3.3V rail voltage
- Check power supply capacity
- Monitor current draw
- Verify ground connections
