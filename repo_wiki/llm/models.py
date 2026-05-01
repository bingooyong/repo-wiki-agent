"""LLM provider request/response models and error types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class LLMError(Exception):
    """Base exception for LLM-related errors."""

    def __init__(self, message: str, code: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class RetryableError(LLMError):
    """Error that can be retried (e.g., rate limit, timeout)."""

    pass


class NonRetryableError(LLMError):
    """Error that should not be retried (e.g., auth failure, invalid request)."""

    pass


class ErrorCode(str, Enum):
    """Standardized error codes for LLM providers."""

    # Success
    SUCCESS = "SUCCESS"

    # Retryable errors
    TIMEOUT = "TIMEOUT"
    RATE_LIMIT = "RATE_LIMIT"
    SERVER_ERROR = "SERVER_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"

    # Non-retryable errors
    AUTH_FAILURE = "AUTH_FAILURE"
    INVALID_API_KEY = "INVALID_API_KEY"
    MISSING_API_KEY = "MISSING_API_KEY"
    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_MODEL = "INVALID_MODEL"
    CONTEXT_LENGTH = "CONTEXT_LENGTH"
    UNKNOWN = "UNKNOWN"


@dataclass
class ChatMessage:
    """A single chat message."""

    role: str  # "system", "user", "assistant"
    content: str
    name: str | None = None  # Optional for function/ tool roles


@dataclass
class ChatRequest:
    """A chat completion request."""

    messages: list[ChatMessage]
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: float = 60.0
    stream: bool = False
    # Provider-specific fields
    extra_headers: dict[str, str] = field(default_factory=dict)
    extra_body: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatResponse:
    """A chat completion response."""

    content: str
    model: str
    usage: dict[str, int] | None = None  # {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}
    finish_reason: str | None = None  # "stop", "length", "content_filter"
    raw_response: dict[str, Any] | None = None  # Provider-specific raw response
    error: LLMError | None = None  # Set if this is an error response


@dataclass
class ProviderCapabilities:
    """Capabilities of an LLM provider."""

    supports_streaming: bool = False
    supports_functions: bool = False
    supports_vision: bool = False
    supports_json_mode: bool = False
    supports_reasoning: bool = False
    max_context_tokens: int = 128000


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'openai', 'minimax')."""

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """Provider capabilities."""

    @abstractmethod
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Send a chat request to the provider.

        Args:
            request: Chat request

        Returns:
            Chat response

        Raises:
            RetryableError: For retryable failures (timeout, rate limit)
            NonRetryableError: For non-retryable failures (auth, invalid request)
        """

    @abstractmethod
    def validate_config(self) -> list[tuple[str, str | None, str]]:
        """Validate provider configuration.

        Returns:
            List of (key, value_or_none, validation_reason) tuples
        """
