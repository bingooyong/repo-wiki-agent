"""Cache policy for LLM responses."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from repo_wiki.llm.models import ChatRequest, ChatResponse


@dataclass
class CacheConfig:
    """Configuration for cache behavior."""

    enabled: bool = True
    max_entries: int = 1000
    ttl_seconds: int = 3600  # 1 hour default


@dataclass
class CacheEntry:
    """A cached LLM response."""

    key: str
    response: ChatResponse
    created_at: float  # timestamp
    hits: int = 0


class LLMCache:
    """Cache for LLM responses.

    Cache key is based on request content (not secrets).
    Never caches failures or secret-bearing payloads.
    """

    def __init__(self, config: CacheConfig | None = None) -> None:
        """Initialize cache.

        Args:
            config: Cache configuration
        """
        self._config = config or CacheConfig()
        self._entries: dict[str, CacheEntry] = {}
        self._access_order: list[str] = []

    def _generate_key(self, request: ChatRequest) -> str | None:
        """Generate cache key from request.

        Returns None if request contains secrets or should not be cached.

        Args:
            request: Chat request

        Returns:
            Cache key or None
        """
        try:
            # Build deterministic representation
            messages_data = []
            for msg in request.messages:
                # Skip messages with potential secrets
                content_lower = msg.content.lower()
                secret_indicators = [
                    "api_key",
                    "api key",
                    "token",
                    "secret",
                    "password",
                    "credential",
                    "sk-",
                ]
                if any(indicator in content_lower for indicator in secret_indicators):
                    return None

                messages_data.append(
                    {
                        "role": msg.role,
                        "content": msg.content,
                    }
                )

            key_data = {
                "model": request.model,
                "messages": messages_data,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
            }

            key_str = json.dumps(key_data, sort_keys=True)
            return hashlib.sha256(key_str.encode()).hexdigest()

        except (TypeError, ValueError):
            return None

    def get(self, request: ChatRequest) -> ChatResponse | None:
        """Get cached response for request.

        Args:
            request: Chat request

        Returns:
            Cached response or None
        """
        if not self._config.enabled:
            return None

        key = self._generate_key(request)
        if key is None:
            return None

        entry = self._entries.get(key)
        if entry is None:
            return None

        # Check TTL
        import time

        if time.time() - entry.created_at > self._config.ttl_seconds:
            self._remove_entry(key)
            return None

        # Update access tracking
        entry.hits += 1
        self._move_to_end(key)

        return entry.response

    def put(self, request: ChatRequest, response: ChatResponse) -> bool:
        """Cache a response.

        Never caches error responses or secret-bearing requests.

        Args:
            request: Chat request
            response: Chat response

        Returns:
            True if cached, False if skipped
        """
        if not self._config.enabled:
            return False

        # Don't cache error responses
        if response.error is not None:
            return False

        key = self._generate_key(request)
        if key is None:
            return False

        # Check size limit
        if len(self._entries) >= self._config.max_entries:
            self._evict_oldest()

        import time

        entry = CacheEntry(
            key=key,
            response=response,
            created_at=time.time(),
        )
        self._entries[key] = entry
        self._access_order.append(key)
        return True

    def _remove_entry(self, key: str) -> None:
        """Remove entry from cache."""
        if key in self._entries:
            del self._entries[key]
        if key in self._access_order:
            self._access_order.remove(key)

    def _move_to_end(self, key: str) -> None:
        """Move key to end of access order (most recently used)."""
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)

    def _evict_oldest(self) -> None:
        """Evict least recently used entry."""
        if self._access_order:
            oldest = self._access_order[0]
            self._remove_entry(oldest)

    def clear(self) -> None:
        """Clear all cache entries."""
        self._entries.clear()
        self._access_order.clear()

    def stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with cache stats
        """
        total_hits = sum(e.hits for e in self._entries.values())
        return {
            "entries": len(self._entries),
            "max_entries": self._config.max_entries,
            "enabled": self._config.enabled,
            "total_hits": total_hits,
        }


def create_cache(enabled: bool = True, **kwargs: Any) -> LLMCache:
    """Create an LLM cache with configuration.

    Args:
        enabled: Whether cache is enabled
        **kwargs: Additional CacheConfig options

    Returns:
        Configured LLMCache
    """
    config = CacheConfig(enabled=enabled, **kwargs)
    return LLMCache(config)
