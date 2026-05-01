from __future__ import annotations

from pathlib import Path

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.scanner.repository_scanner import RepositoryScanner


def test_scanner_keeps_data_model_module_references_consistent(tmp_path: Path) -> None:
    (tmp_path / "ai-service" / "src" / "main" / "java" / "com" / "example").mkdir(parents=True)
    (tmp_path / "ai-service" / "src" / "main" / "resources" / "db" / "migration").mkdir(parents=True)
    (tmp_path / "ai-service" / "src" / "main" / "java" / "com" / "example" / "UserEntity.java").write_text(
        "public class UserEntity {}",
        encoding="utf-8",
    )
    (tmp_path / "ai-service" / "src" / "main" / "resources" / "db" / "migration" / "V1__init.sql").write_text(
        "CREATE TABLE IF NOT EXISTS users (id BIGINT);",
        encoding="utf-8",
    )

    cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
    snapshot = RepositoryScanner(cfg).scan()

    module_names = {m.name for m in snapshot.modules}
    assert "ai-service" in module_names
    for model in snapshot.data_models:
        assert model.module in module_names
