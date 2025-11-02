"""
Utils Package for Pi Voice Assistant Client
System utilities and helper functions
"""

from .system_utils import (
    suppress_alsa_errors,
    optimize_system_performance,
    apply_volume_to_audio
)

__all__ = [
    'suppress_alsa_errors',
    'optimize_system_performance',
    'apply_volume_to_audio'
]

