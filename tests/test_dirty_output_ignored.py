"""Isolated --output dirs must not trip dirty-worktree or stale target_dirty readiness."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from repo_wiki.cli import app
from repo_wiki.orchestration.eval_layout import is_git_dirty
from repo_wiki.verifier.qoder_strict_verifier import (
    QoderLikeVerifierService,
    verify_qoder_like,
)

runner = CliRunner()

_PASSING_PAGE = """# {title}

## Table of Contents
- [Intro](#intro)

## Intro

This is sufficient prose content for strict checks with citations and diagrams.

GET /health POST /users PUT /users/{{id}} are owned by Service `api-gateway`.
The schema is documented below.

```json
{{"type": "object"}}
```

```mermaid
graph LR
  A --> B
```

Relationship entity ERD schema 关系 实体 数据库 表 字段.

<cite>src/app.py:12</cite>
"""


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init_repo(repo: Path) -> None:
    _git(repo, "init")
    _git(repo, "config", "user.email", "handbook@example.com")
    _git(repo, "config", "user.name", "Handbook Tests")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("sample\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text(
        "\n".join(f"line {i}" for i in range(1, 41)), encoding="utf-8"
    )
    (repo / "repo-wiki.yaml").write_text(f"project:\n  root: {repo}\n", encoding="utf-8")
    _git(repo, "add", "README.md", "src/app.py", "repo-wiki.yaml")
    _git(repo, "commit", "-m", "init")


def _write_stale_isolated_run(
    repo: Path,
    *,
    readiness_state: str = "NOT_READY",
    readiness_reasons: list[str] | None = None,
    target_dirty: bool = True,
    git_fresh: bool = True,
) -> tuple[Path, Path]:
    """18h-style isolated run whose on-disk manifest still says target_dirty."""
    output = repo / ".repo-agent-eval"
    run_id = "handbook-2026-08-18h"
    run_dir = output / "runs" / run_id
    content = run_dir / "repowiki" / "zh" / "content"
    meta = run_dir / "repowiki" / "zh" / "meta"
    content.mkdir(parents=True)
    meta.mkdir(parents=True)
    (content / "00-overview.md").write_text(
        _PASSING_PAGE.format(title="Project Overview"), encoding="utf-8"
    )
    (content / "04-api.md").write_text(_PASSING_PAGE.format(title="API Overview"), encoding="utf-8")
    (content / "data-models.md").write_text(
        _PASSING_PAGE.format(title="Data Models"), encoding="utf-8"
    )
    (run_dir / "fixture_metadata.json").write_text("{}", encoding="utf-8")
    reasons = ["target_dirty=true"] if readiness_reasons is None else readiness_reasons
    payload = {
        "version": "1.1",
        "run_id": run_id,
        "readiness_state": readiness_state,
        "readiness_reasons": reasons,
        "target_dirty": target_dirty,
        "git_fresh": git_fresh,
        "candidate_repowiki_zh_root": str(run_dir / "repowiki" / "zh"),
        "candidate_content_root": str(content),
        "candidate_meta_root": str(meta),
        "report_paths": {"verify_report": "reports/strict-verify-output.json"},
        "files": [{"path": "reports/strict-verify-output.json"}],
        "evidence": [],
        "target_repo": str(repo),
    }
    (run_dir / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
    return output, run_dir


def _check(result: dict, name: str) -> dict:
    return next(item for item in result["checks"] if item["name"] == name)


def _invoke_verify_ci(repo: Path, output: Path):
    return runner.invoke(
        app,
        [
            "verify",
            "--profile",
            "qoder-like",
            "--ci",
            "--output",
            str(output),
            "--config",
            str(repo / "repo-wiki.yaml"),
        ],
    )


def test_output_only_dirty_passes(tmp_path: Path) -> None:
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


def test_is_git_dirty_ignores_isolated_eval_output(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    output = tmp_path / ".repo-agent-eval"
    (output / "runs" / "r1").mkdir(parents=True)
    (output / "wiki.txt").write_text("generated\n", encoding="utf-8")
    assert is_git_dirty(tmp_path) is False
    assert is_git_dirty(tmp_path, isolated_output=output) is False

    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "secret.py").write_text("SECRET = 1\n", encoding="utf-8")
    assert is_git_dirty(tmp_path) is True
    assert is_git_dirty(tmp_path, isolated_output=output) is True


def test_isolated_output_stale_target_dirty_is_ready_and_ci_exits_zero(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    output, run_dir = _write_stale_isolated_run(tmp_path)

    verifier = QoderLikeVerifierService(run_dir, strict=True, isolated_output=output)
    dirty = verifier._check_qoder_dirty_worktree()
    readiness = verifier._check_qoder_manifest_readiness_contract()
    assert dirty.status == "PASS"
    assert dirty.reason_code != "QODER_DIRTY_WORKTREE"
    assert readiness.status == "PASS"
    assert readiness.reason_code != "QODER_MANIFEST_NOT_READY"
    assert readiness.details.get("readiness_state") == "READY"
    assert readiness.details.get("target_dirty") is False

    result = verify_qoder_like(run_dir, ci=True, strict=True, isolated_output=output)
    assert result.get("hard_gate_codes") == []
    assert "QODER_MANIFEST_NOT_READY" not in result.get("reason_codes", [])
    assert _check(result, "qoder-dirty-worktree")["status"] == "PASS"
    assert _check(result, "qoder-manifest-readiness")["status"] == "PASS"
    assert result["grade"] == "PASS"
    assert result["exit_code"] == 0

    cli = _invoke_verify_ci(tmp_path, output)
    assert cli.exit_code == 0, cli.output
    payload = json.loads(cli.output)
    assert payload["grade"] == "PASS"
    assert payload.get("status") != "NOT_READY"


def test_extra_app_secret_still_fails(tmp_path: Path) -> None:
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


def test_extra_app_secret_keeps_manifest_not_ready(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    output, run_dir = _write_stale_isolated_run(tmp_path)
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "secret.py").write_text("SECRET = 1\n", encoding="utf-8")

    verifier = QoderLikeVerifierService(run_dir, strict=True, isolated_output=output)
    dirty = verifier._check_qoder_dirty_worktree()
    readiness = verifier._check_qoder_manifest_readiness_contract()
    assert dirty.status == "FAIL"
    assert dirty.reason_code == "QODER_DIRTY_WORKTREE"
    assert readiness.status == "WARN"
    assert readiness.reason_code == "QODER_MANIFEST_NOT_READY"

    result = verify_qoder_like(run_dir, ci=True, strict=True, isolated_output=output)
    assert "QODER_DIRTY_WORKTREE" in result.get("hard_gate_codes", [])
    assert result["grade"] == "FAIL"

    cli = _invoke_verify_ci(tmp_path, output)
    assert cli.exit_code != 0
    payload = json.loads(cli.output)
    assert payload["grade"] == "FAIL"
    assert payload.get("status") == "NOT_READY"


def test_other_not_ready_reasons_still_warn_when_output_is_clean(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    output, run_dir = _write_stale_isolated_run(
        tmp_path,
        target_dirty=False,
        git_fresh=True,
        readiness_reasons=["quality_gate.status=FAIL"],
    )
    verifier = QoderLikeVerifierService(run_dir, strict=True, isolated_output=output)
    readiness = verifier._check_qoder_manifest_readiness_contract()
    assert readiness.status == "WARN"
    assert readiness.reason_code == "QODER_MANIFEST_NOT_READY"
