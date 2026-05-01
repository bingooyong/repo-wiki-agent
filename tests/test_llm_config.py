"""Tests for LLM configuration and secret redaction."""

from __future__ import annotations

import os

import pytest

from repo_wiki.llm.config import (
    LLMProviderConfig,
    resolve_llm_config,
    redact_secrets,
    format_redacted_diagnostic,
    ValidationReason,
    get_api_key_from_env,
)


class TestLLMProviderConfig:
    """Tests for LLMProviderConfig schema."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = LLMProviderConfig()
        assert config.provider == "openai"
        assert config.model == "gpt-4o-mini"
        assert config.base_url is None
        assert config.api_key_env == "OPENAI_API_KEY"
        assert config.max_tokens == 4096
        assert config.temperature == 0.7
        assert config.timeout == 60.0
        assert config.max_retries == 3

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = LLMProviderConfig(
            provider="minimax",
            model="abab6-chat",
            base_url="https://api.minimax.chat/v1",
            api_key_env="MINIMAX_API_KEY",
            max_tokens=8192,
            temperature=0.5,
            timeout=120.0,
            max_retries=5,
        )
        assert config.provider == "minimax"
        assert config.model == "abab6-chat"
        assert config.base_url == "https://api.minimax.chat/v1"
        assert config.api_key_env == "MINIMAX_API_KEY"
        assert config.max_tokens == 8192
        assert config.temperature == 0.5
        assert config.timeout == 120.0
        assert config.max_retries == 5

    def test_config_validation_max_tokens(self) -> None:
        """Test max_tokens validation."""
        with pytest.raises(ValueError):
            LLMProviderConfig(max_tokens=0)  # Must be >= 1

        with pytest.raises(ValueError):
            LLMProviderConfig(max_tokens=200000)  # Must be <= 128000

    def test_config_validation_temperature(self) -> None:
        """Test temperature validation."""
        with pytest.raises(ValueError):
            LLMProviderConfig(temperature=-0.1)  # Must be >= 0.0

        with pytest.raises(ValueError):
            LLMProviderConfig(temperature=2.1)  # Must be <= 2.0

    def test_config_validation_timeout(self) -> None:
        """Test timeout validation."""
        with pytest.raises(ValueError):
            LLMProviderConfig(timeout=0)  # Must be > 0

        with pytest.raises(ValueError):
            LLMProviderConfig(timeout=400)  # Must be <= 300

    def test_config_validation_max_retries(self) -> None:
        """Test max_retries validation."""
        with pytest.raises(ValueError):
            LLMProviderConfig(max_retries=-1)  # Must be >= 0

        with pytest.raises(ValueError):
            LLMProviderConfig(max_retries=20)  # Must be <= 10


class TestResolveLLMConfig:
    """Tests for configuration resolution."""

    def test_resolve_from_empty_config(self) -> None:
        """Test resolving from empty config uses defaults."""
        config, warnings = resolve_llm_config()
        assert config.provider == "openai"
        assert config.model == "gpt-4o-mini"
        assert len(warnings) == 0

    def test_resolve_from_dict(self) -> None:
        """Test resolving from configuration dictionary."""
        config_dict = {
            "provider": "minimax",
            "model": "abab6-chat",
            "base_url": "https://api.minimax.chat/v1",
            "api_key_env": "MINIMAX_API_KEY",
        }
        config, warnings = resolve_llm_config(config=config_dict)
        assert config.provider == "minimax"
        assert config.model == "abab6-chat"
        assert config.base_url == "https://api.minimax.chat/v1"
        assert config.api_key_env == "MINIMAX_API_KEY"

    def test_resolve_cli_overrides(self) -> None:
        """Test CLI overrides take highest priority."""
        config_dict = {"provider": "openai", "model": "gpt-4o"}
        cli_overrides = {"model": "gpt-4o-32k"}
        config, warnings = resolve_llm_config(config=config_dict, cli_overrides=cli_overrides)
        assert config.model == "gpt-4o-32k"

    def test_resolve_partial_overrides(self) -> None:
        """Test partial overrides preserve other defaults."""
        cli_overrides = {"timeout": 30.0}
        config, warnings = resolve_llm_config(cli_overrides=cli_overrides)
        assert config.timeout == 30.0
        assert config.provider == "openai"  # Preserved default
        assert config.model == "gpt-4o-mini"  # Preserved default


class TestRedactSecrets:
    """Tests for secret redaction."""

    def test_redact_api_key(self) -> None:
        """Test API key redaction."""
        text = 'API_KEY="sk-1234567890abcdefghijklmnop"'
        redacted = redact_secrets(text)
        assert "sk-1234567890abcdefghijklmnop" not in redacted
        assert "[REDACTED]" in redacted

    def test_redact_bearer_token(self) -> None:
        """Test Bearer token redaction."""
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        redacted = redact_secrets(text)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in redacted
        assert "[REDACTED]" in redacted

    def test_redact_secret_key_value(self) -> None:
        """Test secret_key=value pattern redaction."""
        text = "secret_key=my_super_secret_value_here"
        redacted = redact_secrets(text)
        assert "my_super_secret_value_here" not in redacted
        assert "[REDACTED]" in redacted

    def test_redact_no_change_for_normal_text(self) -> None:
        """Test that normal text is not redacted."""
        text = "This is a normal message without secrets."
        redacted = redact_secrets(text)
        assert redacted == text


class TestFormatRedactedDiagnostic:
    """Tests for diagnostic formatting with redaction."""

    def test_format_secret_key(self) -> None:
        """Test formatting of secret keys."""
        result = format_redacted_diagnostic("api_key", "sk-1234567890", ValidationReason.REDACTED)
        assert "api_key" in result
        assert "[REDACTED]" in result
        assert "REDACTED" in result

    def test_format_normal_value(self) -> None:
        """Test formatting of non-secret values."""
        result = format_redacted_diagnostic("model", "gpt-4o-mini", ValidationReason.VALID)
        assert "model" in result
        assert "gpt-4o-mini" in result
        assert "VALID" in result

    def test_format_none_value(self) -> None:
        """Test formatting of None values."""
        result = format_redacted_diagnostic("base_url", None, ValidationReason.MISSING_MODEL)
        assert "base_url" in result
        assert "(not set)" in result


class TestGetApiKeyFromEnv:
    """Tests for API key environment resolution."""

    def test_get_existing_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test getting existing environment variable."""
        monkeypatch.setenv("TEST_API_KEY", "test-key-123")
        result = get_api_key_from_env("TEST_API_KEY")
        assert result == "test-key-123"

    def test_get_missing_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test getting missing environment variable returns None."""
        monkeypatch.delenv("NON_EXISTENT_KEY", raising=False)
        result = get_api_key_from_env("NON_EXISTENT_KEY")
        assert result is None


class TestValidationReason:
    """Tests for ValidationReason enum."""

    def test_validation_reason_values(self) -> None:
        """Test ValidationReason enum values are stable."""
        assert ValidationReason.VALID.value == "VALID"
        assert ValidationReason.MISSING_PROVIDER.value == "MISSING_PROVIDER"
        assert ValidationReason.MISSING_MODEL.value == "MISSING_MODEL"
        assert ValidationReason.MISSING_API_KEY.value == "MISSING_API_KEY"
        assert ValidationReason.RESOLVED_FROM_ENV.value == "RESOLVED_FROM_ENV"
        assert ValidationReason.REDACTED.value == "REDACTED"
