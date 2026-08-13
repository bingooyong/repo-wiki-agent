"""Packaged Jinja templates must be available without a source checkout."""

from __future__ import annotations

import importlib.resources
from pathlib import Path

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.generator.contracts import validate_contract_coverage
from repo_wiki.orchestration.service import RepoWikiService


def test_importlib_resources_exposes_overview_template() -> None:
    packaged = importlib.resources.files("repo_wiki") / "templates"
    overview = packaged / "docs" / "00-overview.md.j2"
    assert overview.is_file()


def test_service_template_root_without_target_templates(tmp_path: Path) -> None:
    cfg = RepoWikiConfig()
    cfg.project.root = str(tmp_path)
    svc = RepoWikiService(cfg)

    assert not (tmp_path / "templates").exists()
    root = Path(svc._template_root())
    packaged = Path(str(importlib.resources.files("repo_wiki") / "templates"))
    assert root.resolve() == packaged.resolve()
    assert (root / "docs" / "00-overview.md.j2").is_file()
    assert validate_contract_coverage(root) == []

    engine = svc._generation_engine()
    assert (engine.template_root / "docs" / "00-overview.md.j2").is_file()
    assert engine.validate_templates() == []


def test_vendored_templates_match_repo_root_templates() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    checkout = repo_root / "templates"
    vendored = repo_root / "repo_wiki" / "templates"
    checkout_files = {
        p.relative_to(checkout).as_posix(): p.read_bytes()
        for p in checkout.rglob("*")
        if p.is_file()
    }
    vendored_files = {
        p.relative_to(vendored).as_posix(): p.read_bytes()
        for p in vendored.rglob("*")
        if p.is_file()
    }
    assert checkout_files == vendored_files
