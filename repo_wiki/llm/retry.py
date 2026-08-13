"""Retry wrapper with exponential backoff for LLM providers."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

import repo_wiki.llm
from repo_wiki.llm.models import ErrorCode, LLMProvider, RetryableError

T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    base_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    exponential_base: float = 2.0
    jitter: bool = True


@dataclass
class RetryResult:
    """Result of a retry operation."""

    success: bool
    attempts: int
    final_error: Exception | None
    duration: float  # seconds


async def with_retry(
    operation: Callable[..., Any],
    *args: Any,
    retry_config: RetryConfig | None = None,
    provider: LLMProvider | None = None,
    **kwargs: Any,
) -> Any:
    """Execute an operation with retry logic.

    Args:
        operation: Async function to execute
        *args: Positional arguments for operation
        retry_config: Retry configuration (uses provider config if not provided)
        provider: Provider for extracting max_retries
        **kwargs: Keyword arguments for operation

    Returns:
        Result of operation

    Raises:
        RetryableError: If all retries exhausted
        The last exception if operation fails with non-retryable error
    """
    if retry_config is None:
        retry_config = RetryConfig()

    # Use provider max_retries if available
    if provider is not None and retry_config.max_retries == 3:
        retry_config.max_retries = provider._config.max_retries  # type: ignore

    last_error: Exception | None = None
    delay = retry_config.base_delay

    for attempt in range(retry_config.max_retries + 1):
        try:
            result = await operation(*args, **kwargs)
            return result
        except RetryableError as exc:
            last_error = exc
            if attempt < retry_config.max_retries:
                # Calculate delay with exponential backoff
                actual_delay = min(
                    delay * (retry_config.exponential_base**attempt), retry_config.max_delay
                )
                if retry_config.jitter:
                    actual_delay = actual_delay * (0.5 + random.random() * 0.5)

                await asyncio.sleep(actual_delay)
        except Exception:
            # Non-retryable error, propagate immediately
            raise

    # All retries exhausted
    if last_error is not None:
        raise last_error


def assistant_content_is_empty(content: str | None) -> bool:
    """Return True when assistant content is missing, empty, or whitespace-only."""
    return not str(content or "").strip()


async def chat_with_retry(
    provider: LLMProvider,
    request: repo_wiki.llm.ChatRequest,
    retry_config: RetryConfig | None = None,
) -> repo_wiki.llm.ChatResponse:
    """Send a chat request with retry logic.

    HTTP 200 responses with empty/whitespace assistant ``content`` are treated as
    ``RetryableError`` (MiniMax-M3 and similar reasoning models can spend the
    token budget on hidden reasoning and return a blank ``content`` field).

    Args:
        provider: LLM provider
        request: Chat request
        retry_config: Retry configuration

    Returns:
        Chat response

    Raises:
        RetryableError: If all retries exhausted
    """

    async def _chat_rejecting_empty_content(
        chat_request: repo_wiki.llm.ChatRequest,
    ) -> repo_wiki.llm.ChatResponse:
        response = await provider.chat(chat_request)
        if assistant_content_is_empty(response.content):
            raise RetryableError(
                message="Empty LLM assistant content",
                code=ErrorCode.EMPTY_CONTENT,
                details={"status": 200},
            )
        return response

    return await with_retry(
        _chat_rejecting_empty_content,
        request,
        retry_config=retry_config,
        provider=provider,
    )


def is_retryable_error(error: Exception) -> bool:
    """Check if an error is retryable.

    Args:
        error: Exception to check

    Returns:
        True if error is retryable
    """
    return isinstance(error, RetryableError)


def get_retry_info(error: RetryableError) -> dict[str, Any]:
    """Extract retry information from error.

    Args:
        error: RetryableError

    Returns:
        Dict with retry details (retry_after, status, etc.)
    """
    return {
        "code": error.code,
        "message": error.message,
        "details": error.details,
    }
