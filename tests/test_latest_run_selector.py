from __future__ import annotations

import json
from pathlib import Path

import pytest

from repo_wiki.orchestration.latest_run_selector import discover_runs, select_run


def _write_manifest(run_dir: Path, run_id: str) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text(
        json.dumps({"run_id": run_id, "readiness_state": "READY"}), encoding="utf-8"
    )


def test_select_run_prefers_newest_mtime_over_lexicographic_run_id(tmp_path: Path) -> None:
    import os

    eval_root = tmp_path / ".repo-agent-eval"
    older = eval_root / "runs" / "r16-eval-local"
    newer = eval_root / "runs" / "handbook-eval-local"
    _write_manifest(older, "r16-eval-local")
    _write_manifest(newer, "handbook-eval-local")
    older_mtime = 1_700_000_000.0
    newer_mtime = 1_800_000_000.0
    os.utime(older, (older_mtime, older_mtime))
    os.utime(older / "manifest.json", (older_mtime, older_mtime))
    os.utime(newer, (newer_mtime, newer_mtime))
    os.utime(newer / "manifest.json", (newer_mtime, newer_mtime))
    selected = select_run(eval_root)
    assert selected.name == "handbook-eval-local"


def test_select_run_explicit_override(tmp_path: Path) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    _write_manifest(eval_root / "run-a", "run-100")
    _write_manifest(eval_root / "run-b", "run-200")
    selected = select_run(eval_root, run_id="run-100")
    assert selected.name == "run-a"


def test_discover_runs_includes_nested_runs_bucket(tmp_path: Path) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    nested = eval_root / "runs" / "run-nested"
    _write_manifest(nested, "run-999")
    runs = discover_runs(eval_root)
    assert len(runs) == 1
    assert runs[0][0] == "run-999"
    assert runs[0][1] == nested


def test_select_run_nested_layout_by_manifest_run_id(tmp_path: Path) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    nested = eval_root / "runs" / "run-x"
    _write_manifest(nested, "my-run-id")
    selected = select_run(eval_root, run_id="my-run-id")
    assert selected == nested.resolve()


def test_discover_runs_excludes_release_dir(tmp_path: Path) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    _write_manifest(eval_root / "run-a", "run-100")
    release_dir = eval_root / "repowiki" / "zh"
    release_dir.mkdir(parents=True, exist_ok=True)
    (release_dir / "manifest.json").write_text("{}", encoding="utf-8")
    runs = discover_runs(eval_root)
    assert len(runs) == 1


def test_discover_runs_excludes_hidden_qoder_baseline_like_dirs(tmp_path: Path) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    _write_manifest(eval_root / "run-a", "run-100")
    hidden_qoder = eval_root / ".qoder" / "repowiki" / "zh"
    hidden_qoder.mkdir(parents=True, exist_ok=True)
    (hidden_qoder / "manifest.json").write_text("{}", encoding="utf-8")

    runs = discover_runs(eval_root)
    assert len(runs) == 1
    assert runs[0][0] == "run-100"


def test_select_run_raises_when_missing(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        select_run(tmp_path / ".repo-agent-eval")
