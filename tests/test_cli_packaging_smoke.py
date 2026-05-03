"""Smoke tests for packaged CLI entrypoints (no network; Typer invoker)."""

from __future__ import annotations

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
