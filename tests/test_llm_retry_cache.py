"""Tests for retry and cache policies."""

from __future__ import annotations

import pytest

from repo_wiki.llm import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    RetryConfig,
    create_mock_provider,
    get_retry_info,
    is_retryable_error,
)
from repo_wiki.llm.cache import (
    CacheConfig,
    LLMCache,
    create_cache,
)
from repo_wiki.llm.models import ErrorCode, NonRetryableError, RetryableError
from repo_wiki.llm.retry import chat_with_retry


class TestRetryConfig:
    """Tests for RetryConfig."""

    def test_default_config(self) -> None:
        """Test default retry config."""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True

    def test_custom_config(self) -> None:
        """Test custom retry config."""
        config = RetryConfig(
            max_retries=5,
            base_delay=2.0,
            max_delay=120.0,
        )
        assert config.max_retries == 5
        assert config.base_delay == 2.0
        assert config.max_delay == 120.0


class TestIsRetryableError:
    """Tests for is_retryable_error."""

    def test_retryable_error(self) -> None:
        """Test RetryableError is detected."""
        error = RetryableError(message="Timeout", code=ErrorCode.TIMEOUT)
        assert is_retryable_error(error) is True

    def test_non_retryable_error(self) -> None:
        """Test NonRetryableError is detected."""
        error = NonRetryableError(message="Auth failed", code=ErrorCode.AUTH_FAILURE)
        assert is_retryable_error(error) is False

    def test_regular_exception(self) -> None:
        """Test regular exception is not retryable."""
        error = ValueError("Bad value")
        assert is_retryable_error(error) is False


class TestGetRetryInfo:
    """Tests for get_retry_info."""

    def test_extract_retry_info(self) -> None:
        """Test extracting retry info from error."""
        error = RetryableError(
            message="Rate limited",
            code=ErrorCode.RATE_LIMIT,
            details={"retry_after": "60"},
        )
        info = get_retry_info(error)
        assert info["code"] == ErrorCode.RATE_LIMIT
        assert info["message"] == "Rate limited"
        assert info["details"]["retry_after"] == "60"


class TestChatWithRetry:
    """Tests for chat_with_retry."""

    @pytest.mark.asyncio
    async def test_successful_chat(self) -> None:
        """Test successful chat without retry."""
        provider = create_mock_provider(response_content="Success")
        request = ChatRequest(
            messages=[ChatMessage(role="user", content="Test")],
            model="mock",
        )
        response = await chat_with_retry(provider, request)
        assert response.content == "Success"
        assert provider.call_count == 1


class TestCacheConfig:
    """Tests for CacheConfig."""

    def test_default_config(self) -> None:
        """Test default cache config."""
        config = CacheConfig()
        assert config.enabled is True
        assert config.max_entries == 1000
        assert config.ttl_seconds == 3600

    def test_disabled_cache(self) -> None:
        """Test disabled cache config."""
        config = CacheConfig(enabled=False)
        assert config.enabled is False


class TestLLMCache:
    """Tests for LLMCache."""

    @pytest.fixture
    def cache(self) -> LLMCache:
        """Create a test cache."""
        return create_cache(enabled=True, max_entries=100, ttl_seconds=60)

    def test_cache_miss(self, cache: LLMCache) -> None:
        """Test cache miss returns None."""
        request = ChatRequest(
            messages=[ChatMessage(role="user", content="Hello")],
            model="test",
        )
        result = cache.get(request)
        assert result is None

    def test_cache_put_and_get(self, cache: LLMCache) -> None:
        """Test putting and getting from cache."""
        request = ChatRequest(
            messages=[ChatMessage(role="user", content="Hello")],
            model="test",
        )
        response = ChatResponse(
            content="Cached response",
            model="test",
        )

        cached = cache.put(request, response)
        assert cached is True

        result = cache.get(request)
        assert result is not None
        assert result.content == "Cached response"

    def test_cache_does_not_cache_errors(self, cache: LLMCache) -> None:
        """Test that errors are not cached."""
        request = ChatRequest(
            messages=[ChatMessage(role="user", content="Hello")],
            model="test",
        )
        response = ChatResponse(
            content="",
            model="test",
            error=NonRetryableError(message="Error", code=ErrorCode.AUTH_FAILURE),
        )

        cached = cache.put(request, response)
        assert cached is False

    def test_cache_skips_secret_content(self, cache: LLMCache) -> None:
        """Test that content with secrets is not cached."""
        request = ChatRequest(
            messages=[ChatMessage(role="user", content="My API key is sk-12345")],
            model="test",
        )
        response = ChatResponse(content="Response", model="test")

        cached = cache.put(request, response)
        assert cached is False

    def test_cache_ttl_expiry(self, cache: LLMCache) -> None:
        """Test cache respects TTL."""
        cache._config.ttl_seconds = -1  # Already expired

        request = ChatRequest(
            messages=[ChatMessage(role="user", content="Hello")],
            model="test",
        )
        response = ChatResponse(content="Cached", model="test")

        cache.put(request, response)
        result = cache.get(request)
        assert result is None

    def test_cache_max_entries(self, cache: LLMCache) -> None:
        """Test cache respects max entries."""
        cache._config.max_entries = 2

        for i in range(5):
            request = ChatRequest(
                messages=[ChatMessage(role="user", content=f"Message {i}")],
                model="test",
            )
            response = ChatResponse(content=f"Response {i}", model="test")
            cache.put(request, response)

        # Should have at most max_entries
        assert len(cache._entries) <= 2

    def test_cache_clear(self, cache: LLMCache) -> None:
        """Test clearing cache."""
        request = ChatRequest(
            messages=[ChatMessage(role="user", content="Hello")],
            model="test",
        )
        response = ChatResponse(content="Cached", model="test")

        cache.put(request, response)
        assert len(cache._entries) > 0

        cache.clear()
        assert len(cache._entries) == 0

    def test_cache_stats(self, cache: LLMCache) -> None:
        """Test cache statistics."""
        stats = cache.stats()
        assert "entries" in stats
        assert "max_entries" in stats
        assert "enabled" in stats
        assert "total_hits" in stats
        assert stats["enabled"] is True

    def test_cache_disabled(self) -> None:
        """Test disabled cache returns None on get."""
        cache = create_cache(enabled=False)
        request = ChatRequest(
            messages=[ChatMessage(role="user", content="Hello")],
            model="test",
        )
        response = ChatResponse(content="Cached", model="test")

        cache.put(request, response)
        result = cache.get(request)
        assert result is None


class TestCreateCache:
    """Tests for create_cache factory."""

    def test_create_with_defaults(self) -> None:
        """Test create_cache with defaults."""
        cache = create_cache()
        assert cache._config.enabled is True
        assert cache._config.max_entries == 1000

    def test_create_disabled(self) -> None:
        """Test create_cache disabled."""
        cache = create_cache(enabled=False)
        assert cache._config.enabled is False

    def test_create_with_custom_values(self) -> None:
        """Test create_cache with custom values."""
        cache = create_cache(max_entries=500, ttl_seconds=7200)
        assert cache._config.max_entries == 500
        assert cache._config.ttl_seconds == 7200
