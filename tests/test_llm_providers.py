"""Tests for LLM provider implementations."""

from __future__ import annotations

import json

import httpx
import pytest

from repo_wiki.llm import (
    ChatMessage,
    ChatRequest,
    LLMProviderConfig,
    MinimaxProvider,
    OpenAICompatibleProvider,
    create_minimax_provider,
    create_mock_provider,
    resolve_llm_config,
)


class TestOpenAICompatibleProvider:
    """Tests for OpenAICompatibleProvider."""

    @pytest.fixture
    def config(self) -> LLMProviderConfig:
        """Create test configuration."""
        return LLMProviderConfig(
            provider="openai",
            model="gpt-4o-mini",
            base_url="https://api.openai.com/v1",
            api_key_env="OPENAI_API_KEY",
        )

    def test_provider_name(self, config: LLMProviderConfig) -> None:
        """Test provider name."""
        provider = OpenAICompatibleProvider(config)
        assert provider.name == "openai"

    def test_capabilities(self, config: LLMProviderConfig) -> None:
        """Test provider capabilities."""
        provider = OpenAICompatibleProvider(config)
        caps = provider.capabilities
        assert caps.supports_streaming is True
        assert caps.supports_functions is True
        assert caps.supports_json_mode is True
        assert caps.max_context_tokens == 128000

    def test_validate_config_with_api_key(
        self, config: LLMProviderConfig, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test config validation with API key present."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test123456789")
        provider = OpenAICompatibleProvider(config)
        validations = provider.validate_config()

        # Find api_key_env validation
        api_key_validation = next(v for v in validations if v[0] == "api_key_env")
        assert api_key_validation[2] == "REDACTED"
        assert "sk-test1" in api_key_validation[1]

    def test_validate_config_without_api_key(
        self, config: LLMProviderConfig, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test config validation without API key."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        provider = OpenAICompatibleProvider(config)
        validations = provider.validate_config()

        # Find api_key_env validation
        api_key_validation = next(v for v in validations if v[0] == "api_key_env")
        assert api_key_validation[2] == "MISSING_API_KEY"

    def test_validate_config_missing_model(
        self, config: LLMProviderConfig, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test config validation with missing model."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test123")
        config.model = ""
        provider = OpenAICompatibleProvider(config)
        validations = provider.validate_config()

        model_validation = next(v for v in validations if v[0] == "model")
        assert model_validation[2] == "MISSING_MODEL"


class TestMinimaxProvider:
    """Tests for MinimaxProvider."""

    @pytest.fixture
    def config(self) -> LLMProviderConfig:
        """Create test configuration."""
        return LLMProviderConfig(
            provider="minimax",
            model="abab6-chat",
            base_url="https://api.minimax.chat/v1",
            api_key_env="MINIMAX_API_KEY",
        )

    def test_provider_name(self, config: LLMProviderConfig) -> None:
        """Test provider name."""
        provider = MinimaxProvider(config)
        assert provider.name == "minimax"

    def test_capabilities(self, config: LLMProviderConfig) -> None:
        """Test provider capabilities."""
        provider = MinimaxProvider(config)
        caps = provider.capabilities
        assert caps.supports_streaming is True
        assert caps.supports_functions is False
        assert caps.max_context_tokens == 163840

    def test_validate_config_with_api_key(
        self, config: LLMProviderConfig, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test config validation with API key present."""
        monkeypatch.setenv("MINIMAX_API_KEY", "test-api-key-123456")
        provider = MinimaxProvider(config)
        validations = provider.validate_config()

        api_key_validation = next(v for v in validations if v[0] == "api_key_env")
        assert api_key_validation[2] == "REDACTED"

    def test_validate_config_without_api_key(
        self, config: LLMProviderConfig, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test config validation without API key."""
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
        provider = MinimaxProvider(config)
        validations = provider.validate_config()

        api_key_validation = next(v for v in validations if v[0] == "api_key_env")
        assert api_key_validation[2] == "MISSING_API_KEY"

    def test_resolve_app_minimaxi_env_aliases(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test target .env APP_LLM_MINIMAXI aliases resolve to Minimax config."""
        monkeypatch.setenv("APP_LLM_MINIMAXI_API_KEY", "test-minimax-key-123456")
        monkeypatch.setenv("APP_LLM_MINIMAXI_BASE_URL", "https://api.example.test/v1")
        monkeypatch.setenv("APP_LLM_MINIMAXI_MODEL", "minimax-test-model")

        config, _warnings = resolve_llm_config(config={})

        assert config.provider == "minimax"
        assert config.api_key_env == "APP_LLM_MINIMAXI_API_KEY"
        assert config.base_url == "https://api.example.test/v1"
        assert config.model == "minimax-test-model"


class TestCreateMinimaxProvider:
    """Tests for create_minimax_provider factory."""

    def test_create_with_defaults(self) -> None:
        """Test create_minimax_provider with defaults."""
        provider = create_minimax_provider()
        assert provider.name == "minimax"
        assert provider._config.model == "abab6-chat"
        assert provider._config.api_key_env == "MINIMAX_API_KEY"

    def test_create_with_custom_model(self) -> None:
        """Test create_minimax_provider with custom model."""
        provider = create_minimax_provider(model="abab6.5-chat")
        assert provider._config.model == "abab6.5-chat"

    def test_create_with_custom_api_key_env(self) -> None:
        """Test create_minimax_provider with custom api_key_env."""
        provider = create_minimax_provider(api_key_env="CUSTOM_API_KEY")
        assert provider._config.api_key_env == "CUSTOM_API_KEY"

    def test_create_with_custom_base_url(self) -> None:
        """Test create_minimax_provider with custom base_url."""
        provider = create_minimax_provider(base_url="https://custom.endpoint.com/v1")
        assert provider._config.base_url == "https://custom.endpoint.com/v1"

    def test_create_with_additional_kwargs(self) -> None:
        """Test create_minimax_provider with additional config options."""
        provider = create_minimax_provider(
            max_tokens=8192,
            temperature=0.5,
            timeout=120.0,
            max_retries=5,
        )
        assert provider._config.max_tokens == 8192
        assert provider._config.temperature == 0.5
        assert provider._config.timeout == 120.0
        assert provider._config.max_retries == 5


class TestMockProviderWithProviders:
    """Tests for MockProvider behavior in provider context."""

    def test_mock_provider_chat_request_tracking(self) -> None:
        """Test that mock provider tracks chat requests correctly."""
        provider = create_mock_provider(response_content="Test response")

        request = ChatRequest(
            messages=[
                ChatMessage(role="system", content="You are helpful"),
                ChatMessage(role="user", content="Hello"),
            ],
            model="test-model",
            temperature=0.5,
        )

        import asyncio

        asyncio.run(provider.chat(request))

        assert provider.last_request is not None
        assert provider.last_request.model == "test-model"
        assert provider.last_request.temperature == 0.5
        assert len(provider.last_request.messages) == 2

    def test_mock_provider_call_counting(self) -> None:
        """Test that mock provider counts calls correctly."""
        provider = create_mock_provider()

        import asyncio

        request = ChatRequest(
            messages=[ChatMessage(role="user", content="Test")],
            model="test",
        )

        assert provider.call_count == 0

        asyncio.run(provider.chat(request))
        asyncio.run(provider.chat(request))
        asyncio.run(provider.chat(request))

        assert provider.call_count == 3


def _openai_success_json(content: str = "hello") -> dict:
    return {
        "choices": [
            {
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "model": "MiniMax-M3",
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


@pytest.mark.asyncio
async def test_openai_compat_forwards_extra_body(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json=_openai_success_json("ok"))

    config = LLMProviderConfig(
        provider="openai",
        model="MiniMax-M3",
        base_url="https://example.test/v1",
        api_key_env="OPENAI_API_KEY",
    )
    provider = OpenAICompatibleProvider(config)
    provider._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://example.test/v1",
    )
    response = await provider.chat(
        ChatRequest(
            messages=[ChatMessage(role="user", content="hi")],
            model="MiniMax-M3",
            max_tokens=16384,
            extra_body={"thinking": {"type": "disabled"}, "reasoning_split": True},
        )
    )
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["thinking"] == {"type": "disabled"}
    assert payload["reasoning_split"] is True
    assert payload["max_tokens"] == 16384
    assert response.content == "ok"
    await provider.close()


@pytest.mark.asyncio
async def test_openai_compat_empty_content_does_not_use_reasoning_as_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "reasoning_content": "# Fake page\n\nThink-only dump, not wiki markdown.",
                        },
                        "finish_reason": "length",
                    }
                ],
                "model": "MiniMax-M3",
                "usage": {"prompt_tokens": 10, "completion_tokens": 9000, "total_tokens": 9010},
            },
        )

    config = LLMProviderConfig(
        provider="openai",
        model="MiniMax-M3",
        base_url="https://example.test/v1",
        api_key_env="OPENAI_API_KEY",
    )
    provider = OpenAICompatibleProvider(config)
    provider._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://example.test/v1",
    )
    response = await provider.chat(
        ChatRequest(
            messages=[ChatMessage(role="user", content="hi")],
            model="MiniMax-M3",
            max_tokens=4096,
        )
    )
    assert not str(response.content or "").strip()
    await provider.close()


@pytest.mark.asyncio
async def test_minimax_anthropic_does_not_clamp_max_tokens_to_2048(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MINIMAX_API_KEY", "test-minimax-key")
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "ok"}],
                "model": "MiniMax-M3",
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    config = LLMProviderConfig(
        provider="minimax",
        model="MiniMax-M3",
        base_url="https://api.minimaxi.com/anthropic",
        api_key_env="MINIMAX_API_KEY",
    )
    provider = MinimaxProvider(config)
    provider._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.minimaxi.com/anthropic",
    )
    response = await provider.chat(
        ChatRequest(
            messages=[ChatMessage(role="user", content="hi")],
            model="MiniMax-M3",
            max_tokens=16384,
            extra_body={"thinking": {"type": "disabled"}},
        )
    )
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["max_tokens"] == 16384
    assert payload["max_tokens"] != 2048
    assert payload.get("thinking") == {"type": "disabled"}
    assert response.content == "ok"
