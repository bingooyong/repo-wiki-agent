"""Tests for qoder-like mock vs real LLM resolution."""

from __future__ import annotations

import pytest

from repo_wiki.llm import qoder_like_provider as qlp
from repo_wiki.llm.qoder_like_provider import resolve_qoder_like_llm

# Isolated env var for tests so developer OPENAI_API_KEY / LLM_* do not leak in.
_TEST_KEY_ENV = "REPO_WIKI_TEST_QODER_LLM_KEY"


def _clear_llm_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove env keys that :func:`resolve_llm_config` uses to override YAML dicts."""
    for name in (
        "LLM_PROVIDER",
        "LLM_MODEL",
        "LLM_BASE_URL",
        "LLM_API_KEY_ENV",
        "LLM_MAX_TOKENS",
        "LLM_TEMPERATURE",
        "LLM_TIMEOUT",
        "LLM_MAX_RETRIES",
        "APP_LLM_MINIMAXI_API_KEY",
        "APP_LLM_MINIMAX_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


def _base_llm_dict() -> dict:
    return {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "api_key_env": _TEST_KEY_ENV,
        "max_tokens": 4096,
        "temperature": 0.7,
        "timeout": 60.0,
        "max_retries": 3,
    }


def test_resolve_real_when_key_present(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_llm_env_overrides(monkeypatch)
    monkeypatch.delenv(qlp.ENV_FORCE_MOCK_LLM, raising=False)
    monkeypatch.setenv(_TEST_KEY_ENV, "sk-test-key")
    provider, cfg, summary = resolve_qoder_like_llm(
        llm_config_dict=_base_llm_dict(),
        force_mock_llm_config=False,
    )
    assert summary["mode"] == "real"
    assert summary["mock_reason"] is None
    assert cfg.provider == "openai"
    assert getattr(provider, "name", None) == "openai"


def test_resolve_mock_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_llm_env_overrides(monkeypatch)
    monkeypatch.delenv(qlp.ENV_FORCE_MOCK_LLM, raising=False)
    monkeypatch.delenv(_TEST_KEY_ENV, raising=False)
    provider, cfg, summary = resolve_qoder_like_llm(
        llm_config_dict=_base_llm_dict(),
        force_mock_llm_config=False,
    )
    assert summary["mode"] == "mock"
    assert summary["mock_reason"] == "missing_api_key"
    assert summary["fallback_warning"] is not None
    assert "MOCK" in summary["fallback_warning"]
    assert cfg.provider == "mock"


def test_resolve_mock_forced_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_llm_env_overrides(monkeypatch)
    monkeypatch.setenv(qlp.ENV_FORCE_MOCK_LLM, "1")
    monkeypatch.setenv(_TEST_KEY_ENV, "sk-test-key")
    _provider, cfg, summary = resolve_qoder_like_llm(
        llm_config_dict=_base_llm_dict(),
        force_mock_llm_config=False,
    )
    assert summary["mode"] == "mock"
    assert summary["mock_reason"] == "forced_env"
    assert cfg.provider == "mock"


def test_resolve_mock_forced_config(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_llm_env_overrides(monkeypatch)
    monkeypatch.delenv(qlp.ENV_FORCE_MOCK_LLM, raising=False)
    monkeypatch.setenv(_TEST_KEY_ENV, "sk-test-key")
    _provider, cfg, summary = resolve_qoder_like_llm(
        llm_config_dict=_base_llm_dict(),
        force_mock_llm_config=True,
    )
    assert summary["mode"] == "mock"
    assert summary["mock_reason"] == "forced_config"
    assert cfg.provider == "mock"


def test_minimax_real_with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_llm_env_overrides(monkeypatch)
    monkeypatch.delenv(qlp.ENV_FORCE_MOCK_LLM, raising=False)
    monkeypatch.setenv("MINIMAX_API_KEY", "mx-test")
    cfg_dict = {
        **_base_llm_dict(),
        "provider": "minimax",
        "model": "abab6-chat",
        "api_key_env": "MINIMAX_API_KEY",
        "base_url": "https://api.minimax.chat/v1",
    }
    _provider, cfg, summary = resolve_qoder_like_llm(
        llm_config_dict=cfg_dict, force_mock_llm_config=False
    )
    assert summary["mode"] == "real"
    assert cfg.provider == "minimax"
