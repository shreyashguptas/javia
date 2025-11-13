"""
Device Authentication Cache Module

Provides TTL-based caching for device authentication results to reduce database
query overhead. Each device lookup is cached for a configurable period (default 10 minutes).

Performance Impact:
- Reduces database queries by ~1 per request
- Expected latency reduction: 50-200ms per request
- Memory usage: ~1KB per cached device (negligible for typical device counts)

Usage:
    from utils.device_cache import device_cache

    # Check cache first
    device = device_cache.get(device_uuid)
    if device is None:
        # Cache miss - query database
        device = query_database(device_uuid)
        device_cache.set(device_uuid, device)

    # Manual invalidation when device is updated
    device_cache.invalidate(device_uuid)
"""

from datetime import datetime, timedelta
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class DeviceCache:
    """
    TTL-based cache for device authentication results.

    Thread-safe for FastAPI async operations (GIL provides safety for dict operations).

    Attributes:
        _cache: Dict mapping device_uuid to (device_data, timestamp) tuples
        _ttl: Time-to-live duration for cached entries
    """

    def __init__(self, ttl_minutes: int = 10):
        """
        Initialize device cache.

        Args:
            ttl_minutes: Time-to-live for cached entries in minutes (default: 10)
        """
        self._cache: Dict[str, tuple[dict, datetime]] = {}
        self._ttl = timedelta(minutes=ttl_minutes)
        logger.info(f"[CACHE] Device authentication cache initialized (TTL: {ttl_minutes}min)")

    def get(self, device_uuid: str) -> Optional[dict]:
        """
        Retrieve device from cache if not expired.

        Args:
            device_uuid: Device UUID to look up

        Returns:
            Device data dict if cached and not expired, None otherwise
        """
        if device_uuid in self._cache:
            device_data, timestamp = self._cache[device_uuid]
            age = datetime.now() - timestamp

            if age < self._ttl:
                logger.debug(f"[CACHE] Device auth cache HIT: {device_uuid} (age: {int(age.total_seconds())}s)")
                return device_data
            else:
                # Expired - remove from cache
                del self._cache[device_uuid]
                logger.debug(f"[CACHE] Device auth cache EXPIRED: {device_uuid} (age: {int(age.total_seconds())}s)")

        logger.debug(f"[CACHE] Device auth cache MISS: {device_uuid}")
        return None

    def set(self, device_uuid: str, device_data: dict):
        """
        Store device in cache with current timestamp.

        Args:
            device_uuid: Device UUID key
            device_data: Device data to cache (full device record)
        """
        self._cache[device_uuid] = (device_data, datetime.now())
        logger.debug(f"[CACHE] Device auth cached: {device_uuid} (TTL: {self._ttl.total_seconds()}s)")

    def invalidate(self, device_uuid: str):
        """
        Manually remove device from cache (e.g., after device update/deletion).

        Args:
            device_uuid: Device UUID to invalidate
        """
        if self._cache.pop(device_uuid, None) is not None:
            logger.info(f"[CACHE] Device auth cache invalidated: {device_uuid}")
        else:
            logger.debug(f"[CACHE] Device auth cache invalidation (not cached): {device_uuid}")

    def clear(self):
        """Clear all cached entries (useful for testing or emergency)."""
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"[CACHE] Device auth cache cleared ({count} entries removed)")

    def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dict with cache size and oldest entry age
        """
        if not self._cache:
            return {"size": 0, "oldest_age_seconds": 0}

        oldest_timestamp = min(timestamp for _, timestamp in self._cache.values())
        oldest_age = (datetime.now() - oldest_timestamp).total_seconds()

        return {
            "size": len(self._cache),
            "oldest_age_seconds": int(oldest_age),
            "ttl_seconds": int(self._ttl.total_seconds())
        }


# Global cache instance (singleton pattern)
# Initialized once when module is imported
device_cache = DeviceCache(ttl_minutes=10)
