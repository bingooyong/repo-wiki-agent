"""Minimax LLM provider adapter."""

from __future__ import annotations

from typing import Any

import httpx

from repo_wiki.llm.config import LLMProviderConfig, ValidationReason, get_api_key_from_env
from repo_wiki.llm.models import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ErrorCode,
    LLMProvider,
    NonRetryableError,
    ProviderCapabilities,
    RetryableError,
)


class MinimaxProvider(LLMProvider):
    """Minimax LLM provider adapter.

    API Reference: https://platform.minimaxi.com/document
    """

    def __init__(self, config: LLMProviderConfig) -> None:
        """Initialize Minimax provider.

        Args:
            config: Provider configuration with api_key_env
        """
        self._config = config
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        return "minimax"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_streaming=True,
            supports_functions=False,
            supports_vision=False,
            supports_json_mode=False,
            supports_reasoning=False,
            max_context_tokens=163840,
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
                base_url=self._config.base_url or "https://api.minimax.chat/v1",
                timeout=httpx.Timeout(self._config.timeout),
                headers=headers,
            )
        return self._client

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Send a chat request to Minimax API.

        Args:
            request: Chat request

        Returns:
            Chat response

        Raises:
            RetryableError: For timeout, rate limit, server errors
            NonRetryableError: For auth failure, invalid request
        """
        try:
            if self._uses_anthropic_compatible_api():
                return await self._chat_anthropic_compatible(request)

            client = self._get_client()

            # Build request payload for Minimax
            payload: dict[str, Any] = {
                "model": request.model,
                "messages": [self._format_message(m) for m in request.messages],
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
            }

            # Make request
            response = await client.post("/text/chatcompletion_v2", json=payload)

            # Handle error responses
            if response.status_code == 401:
                raise NonRetryableError(
                    message="Authentication failed - check API key",
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
                raise RetryableError(
                    message="Rate limit exceeded",
                    code=ErrorCode.RATE_LIMIT,
                    details={"status": 429},
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
                    message=error_data.get("base_resp", {}).get(
                        "translated_error_message", f"Request failed: {response.status_code}"
                    ),
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

    def _uses_anthropic_compatible_api(self) -> bool:
        return bool(self._config.base_url and "/anthropic" in self._config.base_url.rstrip("/"))

    async def _chat_anthropic_compatible(self, request: ChatRequest) -> ChatResponse:
        """Send a request to MiniMax's Anthropic-compatible Messages API."""
        try:
            client = self._get_client()
            system_messages = [m.content for m in request.messages if m.role == "system"]
            chat_messages = [m for m in request.messages if m.role != "system"]
            payload: dict[str, Any] = {
                "model": request.model,
                "messages": [self._format_message(m) for m in chat_messages],
                "max_tokens": min(request.max_tokens, 2048),
                "temperature": request.temperature,
            }
            if system_messages:
                payload["system"] = "\n\n".join(system_messages)

            response = await client.post("/v1/messages", json=payload)
            if response.status_code == 401:
                raise NonRetryableError(
                    message="Authentication failed - check API key",
                    code=ErrorCode.AUTH_FAILURE,
                    details={"status": 401},
                )
            if response.status_code == 403:
                raise NonRetryableError(
                    message="Forbidden - check API key permissions",
                    code=ErrorCode.AUTH_FAILURE,
                    details={"status": 403},
                )
            if response.status_code == 429:
                raise RetryableError(
                    message="Rate limit exceeded",
                    code=ErrorCode.RATE_LIMIT,
                    details={"status": 429},
                )
            if response.status_code >= 500:
                raise RetryableError(
                    message=f"Server error: {response.status_code}",
                    code=ErrorCode.SERVER_ERROR,
                    details={"status": response.status_code},
                )
            if response.status_code != 200:
                error_data = response.json() if response.content else {}
                raise NonRetryableError(
                    message=error_data.get("error", {}).get(
                        "message", f"Request failed: {response.status_code}"
                    ),
                    code=ErrorCode.UNKNOWN,
                    details={"status": response.status_code, "response": error_data},
                )

            return self._parse_anthropic_response(response.json(), request.model)

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
        """Format ChatMessage for Minimax API."""
        result: dict[str, Any] = {
            "role": message.role,
            "content": message.content,
        }
        if message.name:
            result["name"] = message.name
        return result

    def _parse_response(self, data: dict[str, Any], model: str) -> ChatResponse:
        """Parse Minimax API response into ChatResponse."""
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

        # Extract usage from Minimax response format
        usage = data.get("usage", {})
        if usage:
            usage = {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            }

        return ChatResponse(
            content=content,
            model=model,
            usage=usage,
            finish_reason=choice.get("finish_reason"),
            raw_response=data,
        )

    def _parse_anthropic_response(self, data: dict[str, Any], model: str) -> ChatResponse:
        """Parse MiniMax Anthropic-compatible response into ChatResponse."""
        content_blocks = data.get("content", [])
        text_parts: list[str] = []
        if isinstance(content_blocks, list):
            for block in content_blocks:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text")
                    if isinstance(text, str):
                        text_parts.append(text)
        content = "\n\n".join(text_parts)

        usage_raw = data.get("usage", {}) or {}
        prompt_tokens = int(usage_raw.get("input_tokens", 0) or 0)
        completion_tokens = int(usage_raw.get("output_tokens", 0) or 0)
        usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }

        return ChatResponse(
            content=content,
            model=data.get("model", model),
            usage=usage,
            finish_reason=data.get("stop_reason"),
            raw_response=data,
        )

    def validate_config(self) -> list[tuple[str, str | None, str]]:
        """Validate Minimax provider configuration.

        Returns:
            List of (key, value_or_none, validation_reason) tuples
        """
        validations: list[tuple[str, str | None, str]] = []

        # Provider
        validations.append(("provider", self.name, ValidationReason.VALID.value))

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
            redacted_key = api_key[:8] + "..." if len(api_key) > 8 else "***"
            validations.append(("api_key_env", redacted_key, ValidationReason.REDACTED.value))

        # Max tokens
        validations.append(
            ("max_tokens", str(self._config.max_tokens), ValidationReason.VALID.value)
        )

        # Temperature
        validations.append(
            ("temperature", str(self._config.temperature), ValidationReason.VALID.value)
        )

        # Timeout
        validations.append(("timeout", str(self._config.timeout), ValidationReason.VALID.value))

        # Max retries
        validations.append(
            ("max_retries", str(self._config.max_retries), ValidationReason.VALID.value)
        )

        return validations

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


def create_minimax_provider(
    api_key_env: str = "MINIMAX_API_KEY",
    model: str = "abab6-chat",
    base_url: str | None = None,
    **kwargs: Any,
) -> MinimaxProvider:
    """Create a Minimax provider with configuration.

    Args:
        api_key_env: Environment variable name for API key
        model: Model identifier
        base_url: Optional custom base URL
        **kwargs: Additional configuration options

    Returns:
        Configured MinimaxProvider
    """
    config = LLMProviderConfig(
        provider="minimax",
        model=model,
        base_url=base_url,
        api_key_env=api_key_env,
        **kwargs,
    )
    return MinimaxProvider(config)
