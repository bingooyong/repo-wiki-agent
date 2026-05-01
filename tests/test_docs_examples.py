"""Tests for docs examples validation."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


class TestDocsExamplesValidation:
    """Tests for validating documentation examples."""

    def test_llm_provider_config_doc_exists(self):
        """Test that LLM provider configuration doc exists."""
        # Use absolute path to avoid CWD dependency
        repo_root = Path(__file__).parent.parent
        doc_path = repo_root / "docs" / "operations" / "llm-provider-configuration.md"
        assert doc_path.exists(), f"Config doc not found at {doc_path}"

    def test_llm_config_yaml_examples_valid(self, tmp_path):
        """Test that YAML examples in docs can be parsed."""
        from repo_wiki.llm.config import LLMProviderConfig

        # Test Minimax YAML example structure
        minimax_config = {
            "provider": "minimax",
            "model": "abab6-chat",
            "api_key_env": "MINIMAX_API_KEY",
            "max_tokens": 4096,
            "temperature": 0.7,
            "timeout": 60.0,
            "max_retries": 3,
        }
        config = LLMProviderConfig.model_validate(minimax_config)
        assert config.provider == "minimax"
        assert config.model == "abab6-chat"

    def test_openai_compatible_config_valid(self, tmp_path):
        """Test OpenAI-compatible config example."""
        from repo_wiki.llm.config import LLMProviderConfig

        config_data = {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "base_url": "https://api.openai.com/v1",
            "api_key_env": "OPENAI_API_KEY",
        }
        config = LLMProviderConfig.model_validate(config_data)
        assert config.base_url == "https://api.openai.com/v1"

    def test_anthropic_config_valid(self, tmp_path):
        """Test Anthropic config example."""
        from repo_wiki.llm.config import LLMProviderConfig

        config_data = {
            "provider": "anthropic",
            "model": "claude-3-5-sonnet-20241022",
            "api_key_env": "ANTHROPIC_API_KEY",
        }
        config = LLMProviderConfig.model_validate(config_data)
        assert config.provider == "anthropic"

    def test_local_ollama_config_valid(self, tmp_path):
        """Test local Ollama config example."""
        from repo_wiki.llm.config import LLMProviderConfig

        config_data = {
            "provider": "openai",
            "model": "llama3.3",
            "base_url": "http://localhost:11434/v1",
            "api_key_env": "OLLAMA_API_KEY",
        }
        config = LLMProviderConfig.model_validate(config_data)
        assert config.model == "llama3.3"
        assert config.base_url == "http://localhost:11434/v1"

    def test_config_diagnostic_shows_redacted(self, monkeypatch):
        """Test that diagnostic output redacts API keys."""
        # Set env BEFORE importing modules
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret-key-123456789")

        # Import AFTER env is set
        from repo_wiki.llm import LLMProviderConfig
        from repo_wiki.llm.diagnostics import run_llm_diagnostics, format_diagnostics_text

        config = LLMProviderConfig()
        result = run_llm_diagnostics(config=config)
        text = format_diagnostics_text(result)

        # Should not contain actual key
        assert "sk-test-secret-key-123456789" not in text
        assert "[REDACTED]" in text or "REDACTED" in text

    def test_config_resolution_priority(self, monkeypatch):
        """Test config resolution priority (env > config > defaults)."""
        from repo_wiki.llm.config import resolve_llm_config

        monkeypatch.setenv("LLM_PROVIDER", "minimax")
        monkeypatch.setenv("LLM_MODEL", "abab6.5-chat")

        config, warnings = resolve_llm_config(config={"provider": "openai", "model": "gpt-4o-mini"})
        assert config.provider == "minimax"
        assert config.model == "abab6.5-chat"

    def test_cli_override_takes_precedence(self, monkeypatch):
        """Test CLI overrides take highest priority."""
        from repo_wiki.llm.config import resolve_llm_config

        monkeypatch.setenv("LLM_PROVIDER", "openai")

        config, warnings = resolve_llm_config(
            config={"provider": "openai", "model": "gpt-4o-mini"},
            cli_overrides={"provider": "anthropic"},
        )
        assert config.provider == "anthropic"

    def test_missing_api_key_flagged_in_diagnostics(self, monkeypatch):
        """Test missing API key is flagged in diagnostics."""
        from repo_wiki.llm import LLMProviderConfig
        from repo_wiki.llm.diagnostics import run_llm_diagnostics

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        config = LLMProviderConfig()
        result = run_llm_diagnostics(config=config)

        assert result["summary"] == "FAIL"
        # Issues are strings like "api_key_env: MISSING_API_KEY"
        assert any("MISSING_API_KEY" in issue for issue in result["issues"])

    def test_llm_provider_config_handles_invalid_base_url(self):
        """Test config handles invalid base_url gracefully."""
        from repo_wiki.llm.config import LLMProviderConfig

        # Empty base_url is allowed (None)
        config = LLMProviderConfig(base_url=None)
        assert config.base_url is None

    def test_config_timeout_validation(self):
        """Test timeout validation."""
        from repo_wiki.llm.config import LLMProviderConfig
        from pydantic import ValidationError

        # Valid timeout
        config = LLMProviderConfig(timeout=120.0)
        assert config.timeout == 120.0

        # Invalid timeout (too high)
        with pytest.raises(ValidationError):
            LLMProviderConfig(timeout=500.0)  # Max is 300

    def test_config_temperature_validation(self):
        """Test temperature validation."""
        from repo_wiki.llm.config import LLMProviderConfig
        from pydantic import ValidationError

        # Valid temperature
        config = LLMProviderConfig(temperature=0.5)
        assert config.temperature == 0.5

        # Invalid temperature
        with pytest.raises(ValidationError):
            LLMProviderConfig(temperature=3.0)  # Max is 2.0