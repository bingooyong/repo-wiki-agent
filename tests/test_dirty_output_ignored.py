"""Isolated --output dirs must not trip QODER_DIRTY_WORKTREE."""

from __future__ import annotations

import subprocess
from pathlib import Path

from repo_wiki.verifier.qoder_strict_verifier import (
    QoderLikeVerifierService,
    verify_qoder_like,
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init_repo(repo: Path) -> None:
    _git(repo, "init")
    _git(repo, "config", "user.email", "handbook@example.com")
    _git(repo, "config", "user.name", "Handbook Tests")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("sample\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "init")


def test_isolated_output_only_is_not_dirty(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    output = tmp_path / ".repo-agent-eval"
    run_content = output / "runs" / "r1" / "content"
    run_content.mkdir(parents=True)
    (run_content / "page.md").write_text("# generated wiki\n", encoding="utf-8")

    verifier = QoderLikeVerifierService(tmp_path, strict=True, isolated_output=output)
    check = verifier._check_qoder_dirty_worktree()
    assert check.status == "PASS"
    assert check.reason_code != "QODER_DIRTY_WORKTREE"

    result = verify_qoder_like(tmp_path, ci=True, strict=True, isolated_output=output)
    assert "QODER_DIRTY_WORKTREE" not in result.get("hard_gate_codes", [])


def test_extra_source_file_still_fails_dirty(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    output = tmp_path / ".repo-agent-eval"
    (output / "runs" / "r1").mkdir(parents=True)
    (output / "wiki.txt").write_text("generated\n", encoding="utf-8")
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "secret.py").write_text("SECRET = 1\n", encoding="utf-8")

    verifier = QoderLikeVerifierService(tmp_path, strict=True, isolated_output=output)
    check = verifier._check_qoder_dirty_worktree()
    assert check.status == "FAIL"
    assert check.reason_code == "QODER_DIRTY_WORKTREE"
