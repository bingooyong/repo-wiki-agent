from __future__ import annotations

import tomllib
from pathlib import Path

from repo_wiki.core.config import LlmConfig
from repo_wiki.llm.config import resolve_llm_config

ROOT = Path(__file__).resolve().parents[1]


def test_llm_config_default_provider_is_openai() -> None:
    assert LlmConfig().provider == "openai"


def test_dumped_llm_config_resolves_to_openai_not_claude() -> None:
    cfg, _warnings = resolve_llm_config(config=LlmConfig().model_dump())
    assert cfg.provider == "openai"
    assert cfg.model == "gpt-4o-mini"
    assert not str(cfg.model).startswith("claude-")
    assert cfg.api_key_env == "OPENAI_API_KEY"


def test_pyproject_has_chromadb_vector_extra() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    vector = data["project"]["optional-dependencies"]["vector"]
    assert any(item.startswith("chromadb") for item in vector)


def test_readme_does_not_claim_chroma_is_unconditional() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "SQLite + ChromaDB 嵌入式运行" not in text
    assert "chromadb" in text.lower() or "Chroma" in text
    assert "vector" in text.lower() or "fallback" in text.lower() or "降级" in text or "可选" in text
