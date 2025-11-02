"""
Audio Package for Pi Voice Assistant Client
Audio recording, playback, effects, and compression
"""

from .base_player import AudioPlayer
from .codec import compress_to_opus, decompress_from_opus
from .effects import apply_fade_in_out, add_silence_padding

__all__ = [
    'AudioPlayer',
    'compress_to_opus',
    'decompress_from_opus',
    'apply_fade_in_out',
    'add_silence_padding'
]

