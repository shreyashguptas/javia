"""Heartbeat manager for sending periodic pings to server"""
import logging
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)


class HeartbeatManager:
    """Manages periodic heartbeat pings to server"""
    
    def __init__(self, device_manager, interval_seconds: int = 300):
        """
        Initialize heartbeat manager.
        
        Args:
            device_manager: DeviceManager instance
            interval_seconds: Interval between heartbeats in seconds (default: 300 = 5 minutes)
        """
        self.device_manager = device_manager
        self.interval_seconds = interval_seconds
        
        # Thread control
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        logger.info(f"Heartbeat manager initialized (interval: {interval_seconds}s)")
    
    def start(self):
        """Start the heartbeat thread"""
        if self._running:
            logger.warning("Heartbeat manager already running")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._thread.start()
        logger.info("Heartbeat manager started")
    
    def stop(self):
        """Stop the heartbeat thread"""
        if not self._running:
            return
        
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Heartbeat manager stopped")
    
    def _heartbeat_loop(self):
        """Background thread that sends heartbeats"""
        # Send initial heartbeat immediately
        self._send_heartbeat()
        
        while self._running:
            try:
                # Wait for next interval
                time.sleep(self.interval_seconds)
                
                if self._running:
                    self._send_heartbeat()
                    
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
                # Continue running even on error
                time.sleep(5)
    
    def _send_heartbeat(self):
        """Send a single heartbeat to the server"""
        try:
            success = self.device_manager.send_heartbeat(status="online")
            if success:
                logger.debug("Heartbeat sent successfully")
            else:
                logger.warning("Heartbeat failed (server may be unreachable)")
        except Exception as e:
            logger.error(f"Failed to send heartbeat: {e}")

