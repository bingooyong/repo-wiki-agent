from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
AGENTS = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

STALE_PHRASES = (
    "还不支持可视化配置 LLM",
    "尚不支持可视化配置 LLM",
    "尚不支持 SecretStorage",
    "do **not** yet provide visual LLM",
    "until SecretStorage support is implemented",
)


def test_root_docs_do_not_claim_llm_ui_is_missing() -> None:
    blob = README + "\n" + AGENTS
    hits = [phrase for phrase in STALE_PHRASES if phrase in blob]
    assert hits == [], f"stale LLM-UI denial still in README/AGENTS: {hits}"


def test_readme_documents_secretstorage_and_config_ci() -> None:
    assert "SecretStorage" in README
    assert "repo-wiki config --ci" in README
    assert ("Configure LLM" in README) or ("配置 LLM" in README)


def test_agents_says_extension_has_visual_llm() -> None:
    assert "SecretStorage" in AGENTS
    lowered = AGENTS.lower()
    assert "visual" in lowered or "可视化" in AGENTS
