"""Honor configured LLM page-compose timeout instead of a 20s cap."""

from __future__ import annotations

from types import SimpleNamespace

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.orchestration.service import RepoWikiService


def _service(tmp_path) -> RepoWikiService:
    cfg = RepoWikiConfig()
    cfg.project.root = str(tmp_path)
    return RepoWikiService(cfg)


def test_resolve_llm_page_timeout_honors_config(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("REPO_WIKI_LLM_PAGE_TIMEOUT_SECONDS", raising=False)
    svc = _service(tmp_path)

    assert svc._resolve_llm_page_timeout(SimpleNamespace(timeout=180)) == 180.0
    assert svc._resolve_llm_page_timeout(SimpleNamespace(timeout=60)) == 60.0
    assert svc._resolve_llm_page_timeout(SimpleNamespace(timeout=999)) == 300.0


def test_resolve_llm_page_timeout_env_override(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("REPO_WIKI_LLM_PAGE_TIMEOUT_SECONDS", "12")
    svc = _service(tmp_path)
    assert svc._resolve_llm_page_timeout(SimpleNamespace(timeout=180)) == 12.0
