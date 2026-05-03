"""Tests for CLI config doctor command."""

from __future__ import annotations

import pytest

from repo_wiki.llm import LLMProviderConfig
from repo_wiki.llm.diagnostics import (
    create_provider_from_config,
    format_diagnostics_json,
    format_diagnostics_text,
    run_llm_diagnostics,
)


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
