"""Tests for LLM provider interface and contract."""

from __future__ import annotations

import asyncio

import pytest

from repo_wiki.llm import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ErrorCode,
    LLMProviderConfig,
    LLMError,
    MockLLMProvider,
    NonRetryableError,
    ProviderCapabilities,
    RetryableError,
    create_mock_provider,
)


class TestMockProvider:
    """Tests for MockLLMProvider."""

    @pytest.fixture
    def provider(self) -> MockLLMProvider:
        """Create a mock provider for testing."""
        config = LLMProviderConfig(model="mock-gpt")
        return create_mock_provider(config, response_content="Hello, world!")

    @pytest.mark.asyncio
    async def test_chat_success(self, provider: MockLLMProvider) -> None:
        """Test successful chat request."""
        request = ChatRequest(
            messages=[ChatMessage(role="user", content="Say hello")],
            model="mock-gpt",
        )
        response = await provider.chat(request)

        assert response.content == "Hello, world!"
        assert response.model == "mock-gpt"
        assert response.finish_reason == "stop"
        assert response.error is None
        assert response.usage is not None
        assert "prompt_tokens" in response.usage
        assert "completion_tokens" in response.usage

    @pytest.mark.asyncio
    async def test_chat_increments_call_count(self, provider: MockLLMProvider) -> None:
        """Test that chat increments call count."""
        request = ChatRequest(
            messages=[ChatMessage(role="user", content="Test")],
            model="mock-gpt",
        )
        assert provider.call_count == 0

        await provider.chat(request)
        assert provider.call_count == 1

        await provider.chat(request)
        assert provider.call_count == 2

    @pytest.mark.asyncio
    async def test_chat_stores_last_request(self, provider: MockLLMProvider) -> None:
        """Test that chat stores the last request."""
        request = ChatRequest(
            messages=[ChatMessage(role="user", content="Test message")],
            model="mock-gpt",
            temperature=0.5,
        )
        await provider.chat(request)

        assert provider.last_request is not None
        assert provider.last_request.model == "mock-gpt"
        assert provider.last_request.temperature == 0.5
        assert len(provider.last_request.messages) == 1

    @pytest.mark.asyncio
    async def test_reset_clears_state(self, provider: MockLLMProvider) -> None:
        """Test that reset clears call count and last request."""
        request = ChatRequest(
            messages=[ChatMessage(role="user", content="Test")],
            model="mock-gpt",
        )
        await provider.chat(request)
        assert provider.call_count == 1
        assert provider.last_request is not None

        provider.reset()
        assert provider.call_count == 0
        assert provider.last_request is None

    def test_validate_config_returns_valid(self, provider: MockLLMProvider) -> None:
        """Test that validate_config returns valid for all fields."""
        validations = provider.validate_config()
        assert len(validations) == 8

        for key, value, reason in validations:
            assert reason == "VALID"


class TestProviderCapabilities:
    """Tests for ProviderCapabilities."""

    def test_default_capabilities(self) -> None:
        """Test default capabilities values."""
        caps = ProviderCapabilities()
        assert caps.supports_streaming is False
        assert caps.supports_functions is False
        assert caps.supports_vision is False
        assert caps.supports_json_mode is False
        assert caps.supports_reasoning is False
        assert caps.max_context_tokens == 128000

    def test_custom_capabilities(self) -> None:
        """Test custom capabilities values."""
        caps = ProviderCapabilities(
            supports_streaming=True,
            supports_functions=True,
            supports_vision=True,
            supports_json_mode=True,
            supports_reasoning=True,
            max_context_tokens=1000000,
        )
        assert caps.supports_streaming is True
        assert caps.supports_functions is True
        assert caps.supports_vision is True
        assert caps.supports_json_mode is True
        assert caps.supports_reasoning is True
        assert caps.max_context_tokens == 1000000


class TestChatMessage:
    """Tests for ChatMessage dataclass."""

    def test_user_message(self) -> None:
        """Test user message creation."""
        msg = ChatMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.name is None

    def test_system_message(self) -> None:
        """Test system message creation."""
        msg = ChatMessage(role="system", content="You are helpful")
        assert msg.role == "system"
        assert msg.content == "You are helpful"

    def test_assistant_message(self) -> None:
        """Test assistant message creation."""
        msg = ChatMessage(role="assistant", content="Hi there!", name="assistant")
        assert msg.role == "assistant"
        assert msg.content == "Hi there!"
        assert msg.name == "assistant"


class TestChatRequest:
    """Tests for ChatRequest dataclass."""

    def test_default_request(self) -> None:
        """Test default request values."""
        request = ChatRequest(
            messages=[ChatMessage(role="user", content="Test")],
            model="gpt-4",
        )
        assert request.temperature == 0.7
        assert request.max_tokens == 4096
        assert request.timeout == 60.0
        assert request.stream is False
        assert request.extra_headers == {}
        assert request.extra_body == {}

    def test_custom_request(self) -> None:
        """Test custom request values."""
        request = ChatRequest(
            messages=[ChatMessage(role="user", content="Test")],
            model="gpt-4",
            temperature=0.5,
            max_tokens=8192,
            timeout=120.0,
            stream=True,
            extra_headers={"Custom-Header": "value"},
            extra_body={"custom_field": "value"},
        )
        assert request.temperature == 0.5
        assert request.max_tokens == 8192
        assert request.timeout == 120.0
        assert request.stream is True
        assert request.extra_headers == {"Custom-Header": "value"}
        assert request.extra_body == {"custom_field": "value"}


class TestChatResponse:
    """Tests for ChatResponse dataclass."""

    def test_success_response(self) -> None:
        """Test success response creation."""
        response = ChatResponse(
            content="Hello, world!",
            model="gpt-4",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            finish_reason="stop",
        )
        assert response.content == "Hello, world!"
        assert response.model == "gpt-4"
        assert response.finish_reason == "stop"
        assert response.error is None

    def test_error_response(self) -> None:
        """Test error response creation."""
        error = LLMError(message="Test error", code="TEST_ERROR")
        response = ChatResponse(
            content="",
            model="gpt-4",
            error=error,
        )
        assert response.content == ""
        assert response.error is not None
        assert response.error.message == "Test error"


class TestLLMErrors:
    """Tests for LLM error types."""

    def test_llm_error(self) -> None:
        """Test base LLMError."""
        error = LLMError(message="Test error", code="TEST_CODE", details={"key": "value"})
        assert error.message == "Test error"
        assert error.code == "TEST_CODE"
        assert error.details == {"key": "value"}

    def test_retryable_error(self) -> None:
        """Test RetryableError."""
        error = RetryableError(message="Timeout", code=ErrorCode.TIMEOUT)
        assert isinstance(error, LLMError)
        assert error.message == "Timeout"

    def test_non_retryable_error(self) -> None:
        """Test NonRetryableError."""
        error = NonRetryableError(message="Auth failed", code=ErrorCode.AUTH_FAILURE)
        assert isinstance(error, LLMError)
        assert error.message == "Auth failed"


class TestErrorCode:
    """Tests for ErrorCode enum."""

    def test_error_code_values(self) -> None:
        """Test ErrorCode enum values."""
        assert ErrorCode.SUCCESS.value == "SUCCESS"
        assert ErrorCode.TIMEOUT.value == "TIMEOUT"
        assert ErrorCode.RATE_LIMIT.value == "RATE_LIMIT"
        assert ErrorCode.AUTH_FAILURE.value == "AUTH_FAILURE"
        assert ErrorCode.MISSING_API_KEY.value == "MISSING_API_KEY"


class TestCreateMockProvider:
    """Tests for create_mock_provider factory function."""

    def test_create_with_defaults(self) -> None:
        """Test create_mock_provider with defaults."""
        provider = create_mock_provider()
        assert provider.name == "mock"
        assert provider.capabilities.supports_streaming is True

    def test_create_with_custom_content(self) -> None:
        """Test create_mock_provider with custom content."""
        provider = create_mock_provider(response_content="Custom response")
        assert provider._mock_response.content == "Custom response"

    def test_create_with_delay(self) -> None:
        """Test create_mock_provider with delay."""
        provider = create_mock_provider(delay=0.1)
        assert provider._mock_response.delay == 0.1

    def test_create_with_config(self) -> None:
        """Test create_mock_provider with custom config."""
        config = LLMProviderConfig(provider="custom", model="custom-model")
        provider = create_mock_provider(config=config)
        assert provider._config.provider == "custom"
        assert provider._config.model == "custom-model"
