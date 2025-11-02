#!/usr/bin/env python3
"""
Abstract Audio Player Interface for Pi Voice Assistant Client
Defines the interface that all audio player implementations must follow
"""

from abc import ABC, abstractmethod
from pathlib import Path


class AudioPlayer(ABC):
    """
    Abstract base class for audio players.
    
    This interface allows different speaker implementations to be swapped
    without changing the rest of the codebase. For example, you could
    implement players for different hardware, audio libraries, or protocols.
    """
    
    @abstractmethod
    def play(self, audio_file_path: Path) -> bool:
        """
        Play audio file with real-time volume control and interrupt support.
        
        Args:
            audio_file_path: Path to audio file to play
        
        Returns:
            bool: True if playback completed normally, False if interrupted
        """
        pass
    
    @abstractmethod
    def stop(self):
        """
        Stop current playback immediately.
        
        This method should be safe to call even if nothing is playing.
        """
        pass

