from __future__ import annotations

from pathlib import Path

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.scanner.repository_scanner import RepositoryScanner


def test_streaming_matches_collect_and_batches_respect_excludes(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "skip").mkdir()
    (tmp_path / "src" / "a.py").write_text("print('a')\n", encoding="utf-8")
    (tmp_path / "src" / "b.ts").write_text("export const b = 1\n", encoding="utf-8")
    (tmp_path / "skip" / "c.py").write_text("print('c')\n", encoding="utf-8")
    (tmp_path / "z.md").write_text("# docs\n", encoding="utf-8")

    cfg = RepoWikiConfig.model_validate(
        {
            "project": {"root": str(tmp_path)},
            "scan": {"exclude_dirs": ["skip"], "max_file_count": 3},
        }
    )

    collected, collect_stats = RepositoryScanner(cfg)._collect_files()  # noqa: SLF001
    streamed = list(RepositoryScanner(cfg).iter_scanned_files())
    batches = list(RepositoryScanner(cfg).iter_file_batches(batch_size=2))

    assert [f.path.as_posix() for f in streamed] == [f.path.as_posix() for f in collected]
    assert [f.path.as_posix() for batch in batches for f in batch] == [
        f.path.as_posix() for f in collected
    ]
    assert "skip/c.py" not in {f.path.as_posix() for f in streamed}
    assert len(streamed) == 3
    assert collect_stats.scanned_files == 3


def test_streaming_respects_max_file_count(tmp_path: Path) -> None:
    for name in ["a.py", "b.py", "c.py"]:
        (tmp_path / name).write_text("x = 1\n", encoding="utf-8")
    cfg = RepoWikiConfig.model_validate(
        {"project": {"root": str(tmp_path)}, "scan": {"max_file_count": 2}}
    )

    scanner = RepositoryScanner(cfg)
    streamed = list(scanner.iter_scanned_files())

    assert [f.path.as_posix() for f in streamed] == ["a.py", "b.py"]
    assert scanner.last_scan_stats.scanned_files == 2
