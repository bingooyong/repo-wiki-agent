"""Tests for CLI config doctor command."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from repo_wiki.cli import app
from repo_wiki.llm import LLMProviderConfig
from repo_wiki.llm.diagnostics import (
    create_provider_from_config,
    format_diagnostics_json,
    format_diagnostics_text,
    run_llm_diagnostics,
)

runner = CliRunner()

_LLM_ENV_KEYS = (
    "LLM_PROVIDER",
    "LLM_MODEL",
    "LLM_BASE_URL",
    "LLM_API_KEY_ENV",
    "LLM_MAX_TOKENS",
    "LLM_TEMPERATURE",
    "LLM_TIMEOUT",
    "LLM_MAX_RETRIES",
    "OPENAI_API_KEY",
    "MINIMAX_API_KEY",
    "APP_LLM_MINIMAXI_API_KEY",
    "APP_LLM_MINIMAXI_BASE_URL",
    "APP_LLM_MINIMAXI_MODEL",
    "APP_LLM_MINIMAX_API_KEY",
    "APP_LLM_MINIMAX_BASE_URL",
    "APP_LLM_MINIMAX_MODEL",
)


def _clear_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _LLM_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def _ignore_repo_config(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_no_config(*_args: object, **_kwargs: object) -> None:
        raise FileNotFoundError("ignore repo config for env-only CLI test")

    monkeypatch.setattr("repo_wiki.cli.load_config", _raise_no_config)


def _fake_secret() -> str:
    return "sk-" + "repo" + "wiki" + "test" + "token" + "abcdef123456"


class TestConfigCommandCI:
    """Regression tests for machine-readable CLI config diagnostics."""

    def test_ci_outputs_parseable_json_on_missing_key_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`repo-wiki config --ci` must stay parseable even when it exits nonzero."""
        _clear_llm_env(monkeypatch)
        _ignore_repo_config(monkeypatch)
        missing_env = "REPO_WIKI_TEST_MISSING_LLM_KEY"
        raw_secret = _fake_secret()

        result = runner.invoke(
            app,
            [
                "config",
                "--ci",
                "--provider",
                "openai",
                "--model",
                "gpt-test-model",
                "--api-key-env",
                missing_env,
            ],
        )

        assert result.exit_code == 1
        diagnostics = json.loads(result.output)
        assert diagnostics["summary"] == "FAIL"
        assert diagnostics["api_key_present"] is False
        assert "api_key_env: MISSING_API_KEY" in diagnostics["issues"]
        assert missing_env not in result.output
        assert raw_secret not in result.output

    def test_ci_accepts_extension_style_env_only_config(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """VS Code can pass non-secret config in env and keep the secret in its named env var."""
        _clear_llm_env(monkeypatch)
        _ignore_repo_config(monkeypatch)
        key_env = "REPO_WIKI_TEST_EXTENSION_LLM_KEY"
        raw_secret = _fake_secret()
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.setenv("LLM_MODEL", "gpt-extension-test")
        monkeypatch.setenv("LLM_BASE_URL", "https://llm.example.test/v1")
        monkeypatch.setenv("LLM_API_KEY_ENV", key_env)
        monkeypatch.setenv(key_env, raw_secret)

        result = runner.invoke(app, ["config", "--ci"])

        assert result.exit_code == 0
        diagnostics = json.loads(result.output)
        assert diagnostics["summary"] == "OK"
        assert diagnostics["api_key_present"] is True
        assert diagnostics["provider"] == "openai"
        assert diagnostics["model"] == "gpt-extension-test"
        assert diagnostics["base_url"] == "https://llm.example.test/v1"
        assert diagnostics["api_key_env"] == "[REDACTED]"
        assert key_env not in result.output
        assert raw_secret not in result.output


class TestRunLLMDiagnostics:
    """Tests for run_llm_diagnostics."""

    def test_diagnostics_default_config(self) -> None:
        """Test diagnostics with default config."""
        config = LLMProviderConfig()
        result = run_llm_diagnostics(config=config)

        assert "provider" in result
        assert "model" in result
        assert "validations" in result
        assert "issues" in result
        assert "summary" in result

    def test_diagnostics_with_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test diagnostics with API key present."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test123456789")
        config = LLMProviderConfig(api_key_env="OPENAI_API_KEY")
        result = run_llm_diagnostics(config=config)

        assert result["api_key_present"] is True

    def test_diagnostics_without_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test diagnostics without API key."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        config = LLMProviderConfig(api_key_env="OPENAI_API_KEY")
        result = run_llm_diagnostics(config=config)

        assert result["api_key_present"] is False

    def test_diagnostics_missing_api_key_flagged(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that missing API key is flagged as issue."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        config = LLMProviderConfig(api_key_env="OPENAI_API_KEY")
        result = run_llm_diagnostics(config=config)

        assert result["summary"] == "FAIL"
        assert len(result["issues"]) > 0


class TestFormatDiagnosticsText:
    """Tests for text formatting."""

    def test_format_text_output(self) -> None:
        """Test text formatting."""
        diagnostics = run_llm_diagnostics(config=LLMProviderConfig())
        text = format_diagnostics_text(diagnostics)

        assert "LLM Configuration Diagnostics" in text
        assert "Provider:" in text
        assert "Model:" in text

    def test_format_shows_redacted_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test API key is redacted in text output."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-secret123456789")
        diagnostics = run_llm_diagnostics(config=LLMProviderConfig())
        text = format_diagnostics_text(diagnostics)

        # Should not contain actual key
        assert "sk-secret123456789" not in text
        # Should contain REDACTED
        assert "[REDACTED]" in text or "REDACTED" in text


class TestFormatDiagnosticsJson:
    """Tests for JSON formatting."""

    def test_format_json_output(self) -> None:
        """Test JSON formatting."""
        diagnostics = run_llm_diagnostics(config=LLMProviderConfig())
        json_str = format_diagnostics_json(diagnostics)

        import json

        parsed = json.loads(json_str)
        assert parsed["provider"] == "openai"

    def test_format_json_redacts_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test API key is redacted in JSON output."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-secret123456789")
        diagnostics = run_llm_diagnostics(config=LLMProviderConfig())
        json_str = format_diagnostics_json(diagnostics)

        # Should not contain actual key
        assert "sk-secret123456789" not in json_str


class TestCreateProviderFromConfig:
    """Tests for provider creation."""

    def test_create_openai_provider(self) -> None:
        """Test creating OpenAI provider."""
        config = LLMProviderConfig(provider="openai", model="gpt-4")
        from repo_wiki.llm import OpenAICompatibleProvider

        provider = create_provider_from_config(config)
        assert isinstance(provider, OpenAICompatibleProvider)

    def test_create_minimax_provider(self) -> None:
        """Test creating Minimax provider."""
        config = LLMProviderConfig(provider="minimax", model="abab6-chat")
        from repo_wiki.llm import MinimaxProvider

        provider = create_provider_from_config(config)
        assert isinstance(provider, MinimaxProvider)

    def test_unknown_provider_defaults_to_openai(self) -> None:
        """Test unknown provider defaults to OpenAI-compatible."""
        config = LLMProviderConfig(provider="unknown")
        from repo_wiki.llm import OpenAICompatibleProvider

        provider = create_provider_from_config(config)
        assert isinstance(provider, OpenAICompatibleProvider)
