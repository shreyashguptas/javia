"""Activity tracker for monitoring user interactions"""
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class ActivityTracker:
    """Tracks user activity to determine when device is idle for updates"""
    
    def __init__(self):
        """Initialize activity tracker"""
        self._last_activity_time: Optional[datetime] = None
        self._lock = threading.Lock()
        logger.info("Activity tracker initialized")
    
    def record_activity(self, activity_type: str = "button_press"):
        """
        Record user activity.
        
        Args:
            activity_type: Type of activity (e.g., 'button_press', 'recording', 'playback')
        """
        with self._lock:
            self._last_activity_time = datetime.now(timezone.utc)
            logger.debug(f"Activity recorded: {activity_type} at {self._last_activity_time}")
    
    def get_last_activity_time(self) -> Optional[datetime]:
        """
        Get timestamp of last activity.
        
        Returns:
            Last activity timestamp or None if no activity recorded
        """
        with self._lock:
            return self._last_activity_time
    
    def get_inactivity_duration_seconds(self) -> float:
        """
        Get duration of inactivity in seconds.
        
        Returns:
            Seconds since last activity, or infinity if no activity recorded
        """
        with self._lock:
            if self._last_activity_time is None:
                return float('inf')
            
            now = datetime.now(timezone.utc)
            duration = (now - self._last_activity_time).total_seconds()
            return duration
    
    def is_inactive_for(self, duration_seconds: float) -> bool:
        """
        Check if device has been inactive for at least the specified duration.
        
        Args:
            duration_seconds: Minimum inactivity duration in seconds
            
        Returns:
            True if inactive for at least duration_seconds, False otherwise
        """
        inactivity = self.get_inactivity_duration_seconds()
        return inactivity >= duration_seconds
    
    def reset(self):
        """Reset activity tracking"""
        with self._lock:
            self._last_activity_time = None
            logger.info("Activity tracker reset")

