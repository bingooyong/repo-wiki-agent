"""OpenAI-compatible LLM provider adapter."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from repo_wiki.llm.config import LLMProviderConfig, ValidationReason, get_api_key_from_env
from repo_wiki.llm.models import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ErrorCode,
    LLMProvider,
    LLMError,
    NonRetryableError,
    ProviderCapabilities,
    RetryableError,
)


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI-compatible LLM provider adapter.

    Works with any OpenAI-compatible API (OpenAI, Azure, local models, etc.)
    """

    def __init__(self, config: LLMProviderConfig) -> None:
        """Initialize OpenAI-compatible provider.

        Args:
            config: Provider configuration with base_url and api_key_env
        """
        self._config = config
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        return self._config.provider

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

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            api_key = get_api_key_from_env(self._config.api_key_env)
            headers: dict[str, str] = {
                "Content-Type": "application/json",
            }
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            self._client = httpx.AsyncClient(
                base_url=self._config.base_url or "https://api.openai.com/v1",
                timeout=httpx.Timeout(self._config.timeout),
                headers=headers,
            )
        return self._client

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Send a chat request to OpenAI-compatible API.

        Args:
            request: Chat request

        Returns:
            Chat response

        Raises:
            RetryableError: For timeout, rate limit, server errors
            NonRetryableError: For auth failure, invalid request
        """
        try:
            client = self._get_client()

            # Build request payload
            payload: dict[str, Any] = {
                "model": request.model,
                "messages": [self._format_message(m) for m in request.messages],
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
            }

            # Merge extra body
            if request.extra_body:
                payload.update(request.extra_body)

            # Make request
            response = await client.post("/chat/completions", json=payload)

            # Handle error responses
            if response.status_code == 401:
                error_data = response.json() if response.content else {}
                raise NonRetryableError(
                    message=error_data.get("error", {}).get("message", "Authentication failed"),
                    code=ErrorCode.AUTH_FAILURE,
                    details={"status": 401},
                )
            elif response.status_code == 403:
                raise NonRetryableError(
                    message="Forbidden - check API key permissions",
                    code=ErrorCode.AUTH_FAILURE,
                    details={"status": 403},
                )
            elif response.status_code == 429:
                retry_after = response.headers.get("retry-after", "1")
                raise RetryableError(
                    message="Rate limit exceeded",
                    code=ErrorCode.RATE_LIMIT,
                    details={"status": 429, "retry_after": retry_after},
                )
            elif response.status_code >= 500:
                raise RetryableError(
                    message=f"Server error: {response.status_code}",
                    code=ErrorCode.SERVER_ERROR,
                    details={"status": response.status_code},
                )
            elif response.status_code != 200:
                error_data = response.json() if response.content else {}
                raise NonRetryableError(
                    message=error_data.get("error", {}).get("message", f"Request failed: {response.status_code}"),
                    code=ErrorCode.UNKNOWN,
                    details={"status": response.status_code},
                )

            # Parse successful response
            data = response.json()
            return self._parse_response(data, request.model)

        except httpx.TimeoutException as exc:
            raise RetryableError(
                message=f"Request timeout after {self._config.timeout}s",
                code=ErrorCode.TIMEOUT,
                details={"timeout": self._config.timeout},
            ) from exc
        except httpx.NetworkError as exc:
            raise RetryableError(
                message=f"Network error: {exc}",
                code=ErrorCode.NETWORK_ERROR,
            ) from exc

    def _format_message(self, message: ChatMessage) -> dict[str, Any]:
        """Format ChatMessage for API payload."""
        result: dict[str, Any] = {
            "role": message.role,
            "content": message.content,
        }
        if message.name:
            result["name"] = message.name
        return result

    def _parse_response(self, data: dict[str, Any], model: str) -> ChatResponse:
        """Parse API response into ChatResponse."""
        choices = data.get("choices", [])
        if not choices:
            return ChatResponse(
                content="",
                model=model,
                error=NonRetryableError(
                    message="No choices in response",
                    code=ErrorCode.UNKNOWN,
                ),
            )

        choice = choices[0]
        message = choice.get("message", {})
        content = message.get("content", "")

        return ChatResponse(
            content=content,
            model=model,
            usage=data.get("usage"),
            finish_reason=choice.get("finish_reason"),
            raw_response=data,
        )

    def validate_config(self) -> list[tuple[str, str | None, str]]:
        """Validate OpenAI-compatible provider configuration.

        Returns:
            List of (key, value_or_none, validation_reason) tuples
        """
        validations: list[tuple[str, str | None, str]] = []

        # Provider
        if not self._config.provider:
            validations.append(("provider", None, ValidationReason.MISSING_PROVIDER.value))
        else:
            validations.append(("provider", self._config.provider, ValidationReason.VALID.value))

        # Model
        if not self._config.model:
            validations.append(("model", None, ValidationReason.MISSING_MODEL.value))
        else:
            validations.append(("model", self._config.model, ValidationReason.VALID.value))

        # Base URL
        if self._config.base_url:
            validations.append(("base_url", self._config.base_url, ValidationReason.VALID.value))
        else:
            validations.append(("base_url", None, ValidationReason.VALID.value))

        # API key
        api_key = get_api_key_from_env(self._config.api_key_env)
        if not api_key:
            validations.append(("api_key_env", None, ValidationReason.MISSING_API_KEY.value))
        else:
            # Partial redaction for display
            redacted_key = api_key[:8] + "..." if len(api_key) > 8 else "***"
            validations.append(("api_key_env", redacted_key, ValidationReason.REDACTED.value))

        # Max tokens
        validations.append(("max_tokens", str(self._config.max_tokens), ValidationReason.VALID.value))

        # Temperature
        validations.append(("temperature", str(self._config.temperature), ValidationReason.VALID.value))

        # Timeout
        validations.append(("timeout", str(self._config.timeout), ValidationReason.VALID.value))

        # Max retries
        validations.append(("max_retries", str(self._config.max_retries), ValidationReason.VALID.value))

        return validations

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
