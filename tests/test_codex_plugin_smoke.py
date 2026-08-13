"""Regression wrapper for the standalone Codex plugin smoke contract."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


def test_standalone_codex_plugin_smoke() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "scripts/smoke_codex_plugin.py"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    if result.stdout.startswith("SKIP:"):
        pytest.skip(result.stdout.removeprefix("SKIP:").strip())
    assert "PASS:" in result.stdout
