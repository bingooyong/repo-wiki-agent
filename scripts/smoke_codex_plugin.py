#!/usr/bin/env python3
"""Install and discover the Repo Wiki plugin with an isolated Codex home."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_NAME = "repo-wiki"
MARKETPLACE_NAME = "repo-wiki-local"


def run_codex(codex: str, codex_home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["CODEX_HOME"] = str(codex_home)
    return subprocess.run(
        [codex, *args],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def require_success(result: subprocess.CompletedProcess[str], stage: str) -> None:
    if result.returncode:
        raise RuntimeError(f"{stage} failed:\n{result.stdout}{result.stderr}")


def parse_json_result(result: subprocess.CompletedProcess[str], stage: str) -> dict[str, object]:
    require_success(result, stage)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{stage} did not return JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{stage} returned a non-object JSON value")
    return payload


def main() -> int:
    codex = shutil.which("codex")
    if codex is None:
        print("SKIP: Codex binary is unavailable")
        return 0

    with tempfile.TemporaryDirectory(prefix="repo-wiki-codex-plugin-") as directory:
        codex_home = Path(directory) / "codex-home"
        codex_home.mkdir()

        marketplace = parse_json_result(
            run_codex(codex, codex_home, "plugin", "marketplace", "add", str(REPO_ROOT), "--json"),
            "marketplace add",
        )
        if marketplace.get("marketplaceName") != MARKETPLACE_NAME:
            raise RuntimeError("Codex discovered an unexpected marketplace name")

        installed = parse_json_result(
            run_codex(
                codex,
                codex_home,
                "plugin",
                "add",
                f"{PLUGIN_NAME}@{MARKETPLACE_NAME}",
                "--json",
            ),
            "plugin add",
        )
        installed_path = Path(str(installed.get("installedPath", "")))
        if installed.get("pluginId") != f"{PLUGIN_NAME}@{MARKETPLACE_NAME}":
            raise RuntimeError("Codex installed an unexpected plugin identity")
        if not installed_path.is_dir() or not installed_path.resolve().is_relative_to(
            codex_home.resolve()
        ):
            raise RuntimeError("Codex installed the plugin outside the isolated home")

        listing = run_codex(codex, codex_home, "plugin", "list")
        require_success(listing, "plugin list")
        expected_listing = f"{PLUGIN_NAME}@{MARKETPLACE_NAME}"
        if expected_listing not in listing.stdout or "installed, enabled" not in listing.stdout:
            raise RuntimeError("Installed plugin was not enabled or discoverable")

        expected_skills = {
            "repo-wiki",
            "repo-wiki-generate",
            "repo-wiki-maintain",
            "repo-wiki-verify",
        }
        installed_skills = {
            path.parent.name for path in (installed_path / "skills").glob("*/SKILL.md")
        }
        if installed_skills != expected_skills:
            raise RuntimeError("Installed skill set does not match the plugin contract")

        doctor = subprocess.run(
            [
                sys.executable,
                str(installed_path / "scripts" / "workflow.py"),
                "doctor",
                "--cwd",
                str(REPO_ROOT),
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        require_success(doctor, "installed runner doctor")
        doctor_payload = json.loads(doctor.stdout)
        if doctor_payload.get("status") != "PASS" or doctor_payload.get("stage") != "doctor":
            raise RuntimeError("Installed runner doctor did not pass")

    print("PASS: isolated Codex marketplace install, skill discovery, and runner doctor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
