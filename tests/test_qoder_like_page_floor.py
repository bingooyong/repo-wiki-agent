"""Tests for qoder-like min/max page budgets (no legacy 120 floor on max)."""

from __future__ import annotations

from pathlib import Path

import pytest

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.orchestration.service import RepoWikiService


@pytest.fixture
def tiny_project(tmp_path: Path) -> Path:
    (tmp_path / "README.md").write_text("# tiny\n", encoding="utf-8")
    return tmp_path


def test_default_min_max_from_config(tiny_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REPO_WIKI_QODER_LIKE_MIN_PAGES", raising=False)
    monkeypatch.delenv("REPO_WIKI_QODER_LIKE_MAX_PAGES", raising=False)
    cfg = RepoWikiConfig.model_validate({"project": {"root": str(tiny_project)}})
    svc = RepoWikiService(cfg)
    assert svc._resolve_qoder_like_min_pages() == 24
    assert svc._resolve_qoder_like_max_pages() == 220


def test_max_pages_env_not_lifted_to_120(
    tiny_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("REPO_WIKI_QODER_LIKE_MAX_PAGES", "30")
    cfg = RepoWikiConfig.model_validate({"project": {"root": str(tiny_project)}})
    svc = RepoWikiService(cfg)
    assert svc._resolve_qoder_like_max_pages() == 30


def test_yaml_qoder_like_overrides(tiny_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REPO_WIKI_QODER_LIKE_MIN_PAGES", raising=False)
    monkeypatch.delenv("REPO_WIKI_QODER_LIKE_MAX_PAGES", raising=False)
    cfg = RepoWikiConfig.model_validate(
        {
            "project": {"root": str(tiny_project)},
            "qoder_like": {"min_pages": 10, "max_pages": 40},
        }
    )
    svc = RepoWikiService(cfg)
    assert svc._resolve_qoder_like_min_pages() == 10
    assert svc._resolve_qoder_like_max_pages() == 40


def test_env_overrides_yaml_min(tiny_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPO_WIKI_QODER_LIKE_MIN_PAGES", "8")
    monkeypatch.delenv("REPO_WIKI_QODER_LIKE_MAX_PAGES", raising=False)
    cfg = RepoWikiConfig.model_validate(
        {
            "project": {"root": str(tiny_project)},
            "qoder_like": {"min_pages": 100},
        }
    )
    svc = RepoWikiService(cfg)
    assert svc._resolve_qoder_like_min_pages() == 8


def test_build_plan_uses_min_capped_by_max(
    tiny_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same rule as _build_qoder_like_page_plan: min cannot exceed max budget."""
    monkeypatch.delenv("REPO_WIKI_QODER_LIKE_MIN_PAGES", raising=False)
    monkeypatch.delenv("REPO_WIKI_QODER_LIKE_MAX_PAGES", raising=False)
    cfg = RepoWikiConfig.model_validate(
        {
            "project": {"root": str(tiny_project)},
            "qoder_like": {"min_pages": 500, "max_pages": 15},
        }
    )
    svc = RepoWikiService(cfg)
    max_b = svc._resolve_qoder_like_max_pages()
    assert min(svc._resolve_qoder_like_min_pages(), max_b) == 15
