# Hardware Setup Guide

## Components Overview

### Raspberry Pi Zero 2 W
- **Mainboard**: Raspberry Pi Zero 2 W
- **Power**: 5V via micro USB or GPIO pins
- **GPIO**: 40-pin header with I2S support
- **OS**: Raspberry Pi OS (Bookworm or later recommended)

### Google Voice HAT
- **Type**: AIY Voice HAT v1.0 / Google Voice HAT Sound Card
- **Interface**: I2S digital audio (microphone + speaker)
- **Microphone**: Built-in dual MEMS microphones
- **Speaker Driver**: Built-in 3W Class D amplifier
- **Power**: 3.3V from Raspberry Pi
- **Features**: 
  - Integrated microphone array with voice processing
  - High-quality speaker amplifier
  - Low-noise audio capture
  - Optimized for voice applications
- **Sound Card**: `snd_rpi_googlevoicehat_soundcar` (card 0)

### Speaker (Connected to Voice HAT)
- **Type**: 3W 4Ω Mini Speaker
- **Interface**: Screw terminals or JST connector on Voice HAT
- **Power**: 3W maximum
- **Recommended**: 4Ω impedance for optimal performance

### Button
- **Type**: Momentary push button (normally open)
- **Connection**: GPIO17 with internal pull-up resistor
- **Purpose**: Start/stop recording

## Detailed Wiring Instructions

### Step 1: Attach Google Voice HAT to Raspberry Pi
1. **Power off** your Raspberry Pi Zero 2 W completely
2. **Align the Voice HAT** with the 40-pin GPIO header on the Pi
3. **Press down firmly** to connect all 40 pins - ensure it's seated properly
4. **Verify connection** - The HAT should sit flush against the Pi

**IMPORTANT**: The Voice HAT connects to ALL 40 GPIO pins. This includes:
- I2S audio pins (GPIO18, GPIO19, GPIO20, GPIO21)
- Power pins (3.3V and 5V)
- Ground pins
- Additional GPIO pins (which you can still use)

### Step 2: Connect Speaker to Voice HAT
```
Speaker → Voice HAT Speaker Terminal
Red wire    → Speaker + (or R+ terminal)
Black wire  → Speaker - (or R- terminal)
```

**Notes**:
- Use a 3W 4Ω speaker for best results
- Speaker terminals are usually screw terminals or JST connector
- Ensure polarity is correct (red to +, black to -)

### Step 3: Connect Button
```
Button → Raspberry Pi GPIO
Terminal 1 → GPIO17 (Physical Pin 11) - accessible through Voice HAT
Terminal 2 → GND (Physical Pin 6) - accessible through Voice HAT
```

**Notes**:
- The Voice HAT passes through GPIO pins, so you can still connect to GPIO17
- Use a normally-open momentary push button
- The software uses internal pull-up resistor, so no external resistor needed

### Step 4: Amplifier Shutdown Control (Optional but Recommended)
```
Voice HAT SD Pin → GPIO27 (Physical Pin 13)
```

**Notes**:
- The Voice HAT may have an SD (shutdown) pin exposed
- Connecting this to GPIO27 allows software control of amplifier muting
- This significantly reduces audio clicks/pops
- If not available, the software will still work without it

## Pin Reference

### Raspberry Pi Zero 2 W GPIO Pins (with Voice HAT)
```
Pin 1  - 3.3V Power (used by Voice HAT)
Pin 2  - 5V Power (used by Voice HAT)
Pin 6  - Ground (available for button)
Pin 9  - Ground (used by Voice HAT)
Pin 11 - GPIO17 (Button) - AVAILABLE through Voice HAT
Pin 12 - GPIO18/PCM_CLK (I2S Clock) - USED by Voice HAT
Pin 13 - GPIO27 (Amplifier SD) - MAY be available
Pin 35 - GPIO19/PCM_FS (I2S Frame Sync) - USED by Voice HAT
Pin 38 - GPIO20/PCM_DIN (I2S Data In) - USED by Voice HAT
Pin 40 - GPIO21/PCM_DOUT (I2S Data Out) - USED by Voice HAT
```

**Note**: The Voice HAT uses the following GPIO pins for I2S audio:
- GPIO18 (PCM_CLK) - I2S bit clock
- GPIO19 (PCM_FS) - I2S frame sync / word select
- GPIO20 (PCM_DIN) - I2S data in (microphone)
- GPIO21 (PCM_DOUT) - I2S data out (speaker)

Other GPIO pins remain available for your use (like GPIO17 for the button).

## Physical Setup

### Assembly Steps
1. **Power off** the Raspberry Pi
2. **Mount Voice HAT** on GPIO header
3. **Connect speaker** to Voice HAT terminals
4. **Connect button** to GPIO17 and GND (can use breadboard or direct wire)
5. **Power on** and configure software

### Connection Tips
- Ensure Voice HAT is firmly seated on all 40 pins
- Speaker polarity matters - red to +, black to -
- Button connection is simple - no pull-up resistor needed (software enables internal pull-up)
- Keep speaker wires away from Pi's antenna area for best WiFi performance

## Power Requirements

### Total Power Consumption
- **Raspberry Pi Zero 2 W**: ~1.5W (typical), up to 2W (peak)
- **Google Voice HAT**: ~0.5W (idle), up to 4W (active with speaker)
- **Speaker**: Up to 3W (when playing audio at high volume)
- **Total System**: ~2-6W depending on audio playback

### Recommended Power Supply
- **Minimum**: 5V 2.5A USB power adapter (12.5W)
- **Recommended**: 5V 3A USB power adapter (15W) - **BEST for most use cases**
- **High-quality cable**: Use a good quality micro USB cable (short cable = less voltage drop)

**IMPORTANT**: 
- Insufficient power causes audio glitches, system instability, and throttling
- Check for undervoltage with: `vcgencmd get_throttled`
- If throttled, upgrade to a better power supply

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

### Voice HAT Not Detected
**Symptoms**: No sound card appears with `arecord -l` or `aplay -l`

**Solutions**:
- Power off and reseat the Voice HAT firmly
- Check `/boot/firmware/config.txt` for I2S configuration
- Verify with: `dtoverlay=googlevoicehat-soundcard`
- Reboot after configuration changes
- Check for physical damage to GPIO pins

### No Audio Input
**Symptoms**: Recording produces silent or very quiet files

**Solutions**:
- Verify Voice HAT is properly seated
- Check software gain settings (`MICROPHONE_GAIN=2.0` in `.env`)
- Test with: `arecord -D plughw:0,0 -c1 -r 16000 -f S16_LE -d 5 test.wav`
- Listen to test file: `aplay test.wav`
- Ensure microphone is not blocked or damaged

### No Audio Output  
**Symptoms**: Speaker makes no sound during playback

**Solutions**:
- Verify speaker connections (red to +, black to -)
- Check speaker impedance (should be 4Ω)
- Test speaker with another device
- Verify amplifier SD pin is enabled (GPIO27 HIGH during playback)
- Check power supply (needs at least 2.5A)

### Audio Clicks/Pops
**Symptoms**: Clicking sounds at start/end of audio playback

**Solutions**:
- Ensure GPIO27 is configured for amplifier shutdown control
- Increase silence padding in code (`padding_ms=200`)
- Verify power supply is adequate (3A recommended)
- Add delay before/after playback (already implemented)

### Button Not Working
**Symptoms**: Pressing button doesn't start/stop recording

**Solutions**:
- Check button connection to GPIO17 and GND
- Test button with multimeter for continuity
- Verify button is normally-open (not normally-closed)
- Check software configuration (`BUTTON_PIN=17`)

### Power Issues / System Instability
**Symptoms**: Random crashes, reboots, or throttling warnings

**Solutions**:
- Check for undervoltage: `vcgencmd get_throttled`
- If throttled (result ≠ 0x0), upgrade power supply
- Use 5V 3A power adapter minimum
- Use short, high-quality micro USB cable
- Avoid USB hubs or splitters
