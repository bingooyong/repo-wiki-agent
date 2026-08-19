"""Safe path-claim extraction so generate does not crash on changelog prose."""

from __future__ import annotations

from pathlib import Path

from repo_wiki.scanner import docs_scanner as ds
from repo_wiki.scanner.docs_scanner import (
    _extract_claims,
    scan_repository_docs_inventory,
)

# Flask CHANGES.rst-style backtick span: prose with '.' and '/' that is not a path.
# Keep a long first path-component (text before the first '/') so a naive
# (repo_root / excerpt).exists() raises ENAMETOOLONG on Linux.
LONG_CHANGELOG_EXCERPT = (
    "Flask 3.0 released with support for Python 3.8+. "
    + ("More notes about the release. " * 16)
    + "See also src/flask/app.py for the application object."
)


def _source_inventory() -> dict:
    return {
        "services": [],
        "api_surfaces": [],
        "data_models": [],
        "frontend_callers": [],
        "deployment_assets": [],
        "tests": [],
    }


def test_long_changelog_backtick_is_not_a_plausible_path() -> None:
    assert len(LONG_CHANGELOG_EXCERPT) > 300
    assert "." in LONG_CHANGELOG_EXCERPT
    assert "/" in LONG_CHANGELOG_EXCERPT
    assert not ds._is_plausible_rel_path(LONG_CHANGELOG_EXCERPT)


def test_extract_claims_skips_long_changelog_excerpt() -> None:
    text = f"See notes: `{LONG_CHANGELOG_EXCERPT}`\n"
    _names, path_like = _extract_claims(text)
    assert LONG_CHANGELOG_EXCERPT.lower() not in path_like
    assert not any(len(p) > 255 for p in path_like)


def test_short_source_path_still_extracts() -> None:
    text = "The app lives in `src/flask/app.py` and is imported at runtime.\n"
    _names, path_like = _extract_claims(text)
    assert "src/flask/app.py" in path_like
    assert ds._is_plausible_rel_path("src/flask/app.py")


def test_scan_with_changelog_excerpt_does_not_raise(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "changes.md").write_text(
        f"# Changes\n\n`{LONG_CHANGELOG_EXCERPT}`\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "flask").mkdir(parents=True)
    (tmp_path / "src" / "flask" / "app.py").write_text("app = True\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "Entry: `src/flask/app.py`\n",
        encoding="utf-8",
    )

    naive_raised = False
    try:
        (tmp_path / LONG_CHANGELOG_EXCERPT).exists()
    except OSError:
        naive_raised = True
    assert naive_raised

    inv = scan_repository_docs_inventory(
        tmp_path, _source_inventory(), incremental=False, persist_cache=False
    )
    assert inv["documents"]
    readme = next(d for d in inv["documents"] if d["path"].endswith("README.md"))
    assert "src/flask/app.py" not in readme["stale_references"]
    assert (tmp_path / "src" / "flask" / "app.py").exists()


def test_repo_path_exists_swallows_enametoolong(tmp_path: Path) -> None:
    huge = "a" * 300 + ".rst"
    raised = False
    try:
        (tmp_path / huge).exists()
    except OSError:
        raised = True
    assert raised
    assert ds._repo_path_exists(tmp_path, huge) is False


def test_repo_path_exists_oserror_on_plausible_path_is_missing(tmp_path: Path, monkeypatch) -> None:
    real_exists = Path.exists

    def wrapped(self: Path) -> bool:
        if str(self).endswith("app.py"):
            raise OSError(36, "File name too long")
        return real_exists(self)

    monkeypatch.setattr(Path, "exists", wrapped)
    assert ds._repo_path_exists(tmp_path, "src/flask/app.py") is False


def test_source_file_claim_rejects_slugs_git_refs_and_dotted_paths() -> None:
    assert ds._is_source_file_claim("src/flask/app.py")
    assert ds._is_source_file_claim("docs/ai_novel_agent_prd_architecture.md")
    assert not ds._is_source_file_claim("bingooyong/ai-open-writing")
    assert not ds._is_source_file_claim("origin/main")
    assert not ds._is_source_file_claim("feat/annals-chronotope")
    assert not ds._is_source_file_claim("353bcab..58c89e5")
    assert not ds._is_source_file_claim("ctx.annals.applicable")
    assert not ds._is_source_file_claim("sqlmodel.metadata.create_all")
    assert not ds._is_source_file_claim("package.annals")
    assert not ds._is_source_file_claim("16000/16000")
    assert not ds._is_source_file_claim("novel.db")
    assert not ds._is_source_file_claim(".env")
    assert not ds._is_source_file_claim("/docs")
    assert not ds._is_source_file_claim("/redoc")
    assert not ds._is_source_file_claim("workflows/Tests/badge.svg")


def test_extract_claims_skips_library_tokens_and_non_source_refs() -> None:
    text = (
        "Clone `bingooyong/ai-open-writing` from `origin/main` on "
        "`feat/annals-chronotope` covering `353bcab..58c89e5`.\n"
        "Use `sqlmodel`, `creative_model`, and `mock-model` with "
        "`ctx.annals.applicable` and `sqlmodel.metadata.create_all`.\n"
        "Copy `.env`, open `/docs` and `/redoc`, and store `novel.db`.\n"
        "Progress `16000/16000`. See `src/ghost/service.py` and FutureService.\n"
    )
    names, path_like = _extract_claims(text)
    assert "src/ghost/service.py" in path_like
    assert "futureservice" in names
    assert "bingooyong/ai-open-writing" not in path_like
    assert "origin/main" not in path_like
    assert "feat/annals-chronotope" not in path_like
    assert "353bcab..58c89e5" not in path_like
    assert "ctx.annals.applicable" not in path_like
    assert "sqlmodel.metadata.create_all" not in path_like
    assert "package.annals" not in path_like
    assert "16000/16000" not in path_like
    assert "novel.db" not in path_like
    assert ".env" not in path_like
    assert "/docs" not in path_like
    assert "/redoc" not in path_like
    assert "sqlmodel" not in names
    assert "creative_model" not in names
    assert "mock-model" not in names


def test_casefold_existing_doc_is_not_stale(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "AI_Novel_Agent_PRD_Architecture.md").write_text(
        "# Architecture\n", encoding="utf-8"
    )
    (tmp_path / "README.md").write_text(
        "See `docs/ai_novel_agent_prd_architecture.md`.\n",
        encoding="utf-8",
    )
    inv = scan_repository_docs_inventory(
        tmp_path, _source_inventory(), incremental=False, persist_cache=False
    )
    readme = next(d for d in inv["documents"] if d["path"].endswith("README.md"))
    assert "docs/ai_novel_agent_prd_architecture.md" not in readme["stale_references"]
