from __future__ import annotations

from pathlib import Path

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.core.security import sanitize_text, should_scan


def test_should_scan_denies_env_files(tmp_path: Path) -> None:
    config = RepoWikiConfig()
    path = tmp_path / ".env.production"
    path.write_text("SECRET=abc", encoding="utf-8")
    assert should_scan(path, config, root=tmp_path) is False


def test_sanitize_text_redacts_sensitive_values() -> None:
    text = 'API_KEY="AKIAABCDEFGHIJKLMNOP"\npassword=supersecretvalue'
    sanitized, warnings = sanitize_text(text, path="app/.env")
    assert "[REDACTED]" in sanitized
    assert warnings
