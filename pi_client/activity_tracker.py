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
