# Voice Assistant Project

A complete voice assistant implementation for Raspberry Pi Zero 2 W using INMP441 microphone, MAX98357A amplifier, and Groq API.

## Quick Start

1. **Hardware Setup**: Connect INMP441 microphone and MAX98357A amplifier according to wiring diagram
2. **Software Setup**: Run the automated setup script
3. **Configuration**: Add your Groq API key to `voice_assistant.py`
4. **Test**: Run the test scripts to verify everything works
5. **Run**: Start the voice assistant

## Hardware Requirements

- Raspberry Pi Zero 2 W
- INMP441 MEMS Microphone (I2S)
- MAX98357A I2S Amplifier
- 3W 4Ω Speaker
- Push Button
- Breadboard and jumper wires

## Software Requirements

- Raspberry Pi OS (latest)
- Python 3.7+
- Groq API key

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd voice_assistant

# Run automated setup
chmod +x scripts/setup.sh
./scripts/setup.sh

# Reboot the system
sudo reboot
```

## Configuration

1. **I2S Audio**: Add configuration to `/boot/firmware/config.txt`
2. **API Key**: Set your Groq API key in `voice_assistant.py`
3. **GPIO**: Configure button pin if needed

## Testing

```bash
# Test basic functionality
python3 examples/simple_test.py

# Test microphone specifically
python3 examples/mic_test.py

# Test audio system
python3 scripts/test_audio.py
```

## Usage

```bash
# Start voice assistant
python3 voice_assistant.py

# Or use the startup script
./start.sh
```

## Troubleshooting

See `docs/troubleshooting.md` for common issues and solutions.

## Documentation

- `docs/hardware_setup.md` - Detailed hardware setup guide
- `docs/troubleshooting.md` - Common issues and solutions
- `docs/api_setup.md` - Groq API configuration guide

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

MIT License - see LICENSE file for details
