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
