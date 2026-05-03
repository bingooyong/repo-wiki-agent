"""Mock LLM provider for CI and testing."""

from __future__ import annotations

import time
from dataclasses import dataclass

from repo_wiki.llm.config import LLMProviderConfig, ValidationReason
from repo_wiki.llm.models import (
    ChatRequest,
    ChatResponse,
    LLMProvider,
    ProviderCapabilities,
)


@dataclass
class MockResponse:
    """Configurable mock response for testing."""

    content: str = "This is a mock response."
    usage: dict[str, int] | None = None
    finish_reason: str = "stop"
    delay: float = 0.0  # Simulated delay in seconds


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for CI and downstream composer tests.

    Supports configurable responses, error simulation, and delay.
    """

    def __init__(
        self, config: LLMProviderConfig, mock_response: MockResponse | None = None
    ) -> None:
        """Initialize mock provider.

        Args:
            config: Provider configuration
            mock_response: Optional mock response (uses defaults if not provided)
        """
        self._config = config
        self._mock_response = mock_response or MockResponse()
        self._call_count = 0
        self._last_request: ChatRequest | None = None

    @property
    def name(self) -> str:
        return "mock"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_streaming=True,
            supports_functions=True,
            supports_vision=False,
            supports_json_mode=True,
            supports_reasoning=False,
            max_context_tokens=128000,
        )

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Send a mock chat request.

        Args:
            request: Chat request

        Returns:
            Mock chat response

        Raises:
            RetryableError: If error_mode is "retryable"
            NonRetryableError: If error_mode is "non_retryable"
        """
        self._call_count += 1
        self._last_request = request

        # Simulate delay if configured
        if self._mock_response.delay > 0:
            time.sleep(self._mock_response.delay)

        # Build usage dict
        usage = self._mock_response.usage
        if usage is None:
            # Estimate based on content
            prompt_tokens = sum(len(m.content.split()) for m in request.messages) * 2
            completion_tokens = len(self._mock_response.content.split()) * 2
            usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            }

        return ChatResponse(
            content=self._mock_response.content,
            model=request.model,
            usage=usage,
            finish_reason=self._mock_response.finish_reason,
            raw_response={"mock": True},
        )

    def validate_config(self) -> list[tuple[str, str | None, str]]:
        """Validate mock provider configuration.

        Mock provider is always valid since it doesn't need real credentials.

        Returns:
            List of (key, value_or_none, validation_reason) tuples
        """
        return [
            ("provider", self._config.provider, ValidationReason.VALID.value),
            ("model", self._config.model, ValidationReason.VALID.value),
            ("base_url", self._config.base_url, ValidationReason.VALID.value),
            ("api_key_env", self._config.api_key_env, ValidationReason.VALID.value),
            ("max_tokens", str(self._config.max_tokens), ValidationReason.VALID.value),
            ("temperature", str(self._config.temperature), ValidationReason.VALID.value),
            ("timeout", str(self._config.timeout), ValidationReason.VALID.value),
            ("max_retries", str(self._config.max_retries), ValidationReason.VALID.value),
        ]

    @property
    def call_count(self) -> int:
        """Number of calls made to this provider."""
        return self._call_count

    @property
    def last_request(self) -> ChatRequest | None:
        """Last request sent to this provider."""
        return self._last_request

    def reset(self) -> None:
        """Reset call count and last request."""
        self._call_count = 0
        self._last_request = None


def create_mock_provider(
    config: LLMProviderConfig | None = None,
    response_content: str = "This is a mock response.",
    delay: float = 0.0,
) -> MockLLMProvider:
    """Create a mock provider with custom response.

    Args:
        config: Provider configuration (uses defaults if not provided)
        response_content: Content of mock response
        delay: Simulated delay in seconds

    Returns:
        Configured MockLLMProvider
    """
    if config is None:
        config = LLMProviderConfig()
    mock_response = MockResponse(content=response_content, delay=delay)
    return MockLLMProvider(config, mock_response)
