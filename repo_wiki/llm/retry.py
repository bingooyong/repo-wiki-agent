"""Retry wrapper with exponential backoff for LLM providers."""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from repo_wiki.llm.models import LLMProvider, RetryableError

import repo_wiki.llm


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
                actual_delay = min(delay * (retry_config.exponential_base ** attempt), retry_config.max_delay)
                if retry_config.jitter:
                    actual_delay = actual_delay * (0.5 + random.random() * 0.5)

                await asyncio.sleep(actual_delay)
        except Exception as exc:
            # Non-retryable error, propagate immediately
            raise

    # All retries exhausted
    if last_error is not None:
        raise last_error


async def chat_with_retry(
    provider: LLMProvider,
    request: repo_wiki.llm.ChatRequest,
    retry_config: RetryConfig | None = None,
) -> repo_wiki.llm.ChatResponse:
    """Send a chat request with retry logic.

    Args:
        provider: LLM provider
        request: Chat request
        retry_config: Retry configuration

    Returns:
        Chat response

    Raises:
        RetryableError: If all retries exhausted
    """
    return await with_retry(
        provider.chat,
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
