"""Smoke tests for packaged CLI entrypoints (no network; Typer invoker)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from repo_wiki.cli import app

runner = CliRunner()


def test_cli_root_help_exits_zero() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "repo-wiki" in result.stdout


@pytest.mark.parametrize(
    "args",
    [
        ["init", "--help"],
        ["generate", "--help"],
        ["verify", "--help"],
        ["update", "--help"],
        ["config", "--help"],
    ],
)
def test_subcommand_help_exits_zero(args: list[str]) -> None:
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.stdout + result.stderr


def test_improve_max_tokens_default_is_not_starved() -> None:
    """improve --max-tokens must default to 16384, matching generate's first-call floor."""
    import inspect

    from typer.models import OptionInfo

    from repo_wiki.cli import improve_command

    option = inspect.signature(improve_command).parameters["max_tokens"].default
    assert isinstance(option, OptionInfo)
    assert int(option.default) == 16384
    assert int(option.default) != 1000
    assert int(option.default) != 4096


def test_last_run_degraded_page_ids_are_preferred_when_flag_omitted(tmp_path: Path) -> None:
    from repo_wiki.cli import _last_run_degraded_page_ids

    run = tmp_path / "handbook-2026-08-23a"
    meta = run / "repowiki" / "zh" / "meta"
    meta.mkdir(parents=True)
    (run / "manifest.json").write_text('{"run_id": "handbook-2026-08-23a"}', encoding="utf-8")
    (meta / "quality-report.json").write_text(
        json.dumps(
            {
                "page_quality": [
                    {"page_id": "quick-start", "quality_state": "DEGRADED"},
                    {"page_id": "overview", "quality_state": "PASS"},
                    {"page_id": "database-issues", "quality_state": "DEGRADED"},
                ]
            }
        ),
        encoding="utf-8",
    )
    assert _last_run_degraded_page_ids(tmp_path) == ["quick-start", "database-issues"]


def test_repo_wiki_main_module_help_smoke() -> None:
    """Ensure `python -m repo_wiki.main --help` works (documented fallback when console_scripts unavailable)."""
    repo_root = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, "-m", "repo_wiki.main", "--help"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "repo-wiki" in proc.stdout or "Commands" in proc.stdout
