"""Cache service for API-Sports MCP Server."""

import asyncio
import hashlib
import json
import time
from collections import OrderedDict
from typing import Any

from ..config import get_settings
from ..logger import get_logger

logger = get_logger(__name__)


class CacheEntry:
    """Cache entry with TTL support."""

    def __init__(self, value: Any, ttl: int):
        self.value = value
        self.expires_at = time.time() + ttl if ttl > 0 else float('inf')

    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return time.time() > self.expires_at


class CacheService:
    """In-memory cache service with TTL and LRU eviction."""

    def __init__(self):
        self.settings = get_settings()
        self.enabled = self.settings.cache_enabled
        self.max_size = self.settings.cache_max_size

        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.lock = asyncio.Lock()

        # Statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def _generate_key(self, prefix: str, params: dict[str, Any]) -> str:
        """Generate cache key from prefix and parameters."""
        # Sort params for consistent key generation
        sorted_params = json.dumps(params, sort_keys=True)
        hash_digest = hashlib.md5(sorted_params.encode()).hexdigest()
        return f"{prefix}:{hash_digest}"

    def _get_ttl(self, cache_type: str) -> int:
        """Get TTL for specific cache type."""
        ttl_map = {
            "teams": self.settings.cache_ttl_teams,
            "fixtures_completed": self.settings.cache_ttl_fixtures_completed,
            "fixtures_upcoming": self.settings.cache_ttl_fixtures_upcoming,
            "statistics": self.settings.cache_ttl_statistics,
            "standings": self.settings.cache_ttl_standings,
            "predictions": self.settings.cache_ttl_predictions,
        }
        return ttl_map.get(cache_type, 3600)  # Default 1 hour

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        if not self.enabled:
            return None

        async with self.lock:
            if key in self.cache:
                entry = self.cache[key]

                if entry.is_expired():
                    # Remove expired entry
                    del self.cache[key]
                    self.misses += 1
                    logger.debug(f"Cache miss (expired): {key}")
                    return None

                # Move to end (LRU)
                self.cache.move_to_end(key)
                self.hits += 1

                logger.debug(
                    f"Cache hit: {key}",
                    extra={"hit_rate": self.get_hit_rate()}
                )
                return entry.value

            self.misses += 1
            logger.debug(f"Cache miss: {key}")
            return None

    async def set(self, key: str, value: Any, cache_type: str) -> None:
        """Set value in cache with TTL based on type."""
        if not self.enabled:
            return

        ttl = self._get_ttl(cache_type)

        async with self.lock:
            # Remove if exists to update position
            if key in self.cache:
                del self.cache[key]

            # Check size limit
            while len(self.cache) >= self.max_size:
                # Evict least recently used
                evicted_key = next(iter(self.cache))
                del self.cache[evicted_key]
                self.evictions += 1
                logger.debug(f"Cache eviction: {evicted_key}")

            # Add new entry
            self.cache[key] = CacheEntry(value, ttl)
            logger.debug(
                f"Cache set: {key}",
                extra={
                    "ttl": ttl,
                    "cache_size": len(self.cache),
                    "cache_type": cache_type,
                }
            )

    async def invalidate(self, pattern: str | None = None) -> int:
        """Invalidate cache entries matching pattern or all if pattern is None."""
        if not self.enabled:
            return 0

        async with self.lock:
            if pattern is None:
                # Clear all
                count = len(self.cache)
                self.cache.clear()
                logger.info(f"Cache cleared: {count} entries")
                return count

            # Remove entries matching pattern
            keys_to_remove = [
                key for key in self.cache.keys()
                if pattern in key
            ]

            for key in keys_to_remove:
                del self.cache[key]

            logger.info(f"Cache invalidated: {len(keys_to_remove)} entries matching '{pattern}'")
            return len(keys_to_remove)

    async def cleanup_expired(self) -> int:
        """Remove expired entries from cache."""
        if not self.enabled:
            return 0

        async with self.lock:
            current_time = time.time()
            keys_to_remove = [
                key for key, entry in self.cache.items()
                if entry.is_expired()
            ]

            for key in keys_to_remove:
                del self.cache[key]

            if keys_to_remove:
                logger.debug(f"Cleaned up {len(keys_to_remove)} expired cache entries")

            return len(keys_to_remove)

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "enabled": self.enabled,
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "hit_rate": f"{hit_rate:.2f}%",
            "total_requests": total_requests,
        }

    def get_hit_rate(self) -> float:
        """Get cache hit rate as percentage."""
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0

    # Convenience methods for specific cache types

    async def get_teams(self, params: dict[str, Any]) -> Any | None:
        """Get teams from cache."""
        key = self._generate_key("teams", params)
        return await self.get(key)

    async def set_teams(self, params: dict[str, Any], value: Any) -> None:
        """Set teams in cache."""
        key = self._generate_key("teams", params)
        await self.set(key, value, "teams")

    async def get_fixtures(self, params: dict[str, Any], is_completed: bool = False) -> Any | None:
        """Get fixtures from cache."""
        key = self._generate_key("fixtures", params)
        return await self.get(key)

    async def set_fixtures(self, params: dict[str, Any], value: Any, is_completed: bool = False) -> None:
        """Set fixtures in cache."""
        key = self._generate_key("fixtures", params)
        cache_type = "fixtures_completed" if is_completed else "fixtures_upcoming"
        await self.set(key, value, cache_type)

    async def get_statistics(self, params: dict[str, Any]) -> Any | None:
        """Get statistics from cache."""
        key = self._generate_key("statistics", params)
        return await self.get(key)

    async def set_statistics(self, params: dict[str, Any], value: Any) -> None:
        """Set statistics in cache."""
        key = self._generate_key("statistics", params)
        await self.set(key, value, "statistics")

    async def get_standings(self, params: dict[str, Any]) -> Any | None:
        """Get standings from cache."""
        key = self._generate_key("standings", params)
        return await self.get(key)

    async def set_standings(self, params: dict[str, Any], value: Any) -> None:
        """Set standings in cache."""
        key = self._generate_key("standings", params)
        await self.set(key, value, "standings")

    async def get_predictions(self, params: dict[str, Any]) -> Any | None:
        """Get predictions from cache."""
        key = self._generate_key("predictions", params)
        return await self.get(key)

    async def set_predictions(self, params: dict[str, Any], value: Any) -> None:
        """Set predictions in cache."""
        key = self._generate_key("predictions", params)
        await self.set(key, value, "predictions")
