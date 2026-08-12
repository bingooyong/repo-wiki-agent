#!/usr/bin/env python3
"""Offline contract smoke test for the standalone Repo Wiki Codex plugin."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "repo-wiki"


def load_workflow():
    spec = importlib.util.spec_from_file_location(
        "repo_wiki_plugin_workflow", PLUGIN_ROOT / "scripts" / "workflow.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load plugin workflow")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_metadata() -> None:
    marketplace = json.loads((REPO_ROOT / ".agents" / "plugins" / "marketplace.json").read_text())
    plugin = json.loads((PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text())
    entry = marketplace["plugins"][0]
    require(entry["name"] == "repo-wiki", "marketplace must register repo-wiki")
    require(entry["source"] == {"source": "path", "path": "./plugins/repo-wiki"}, "invalid plugin path")
    require(entry["policy"]["authentication"] == "NONE", "plugin must not require credentials")
    require(plugin["name"] == "repo-wiki", "invalid plugin name")
    require(plugin["skills"] == "./skills/", "plugin must expose skills directory")


def test_skills() -> None:
    for name in ("repo-wiki", "repo-wiki-generate", "repo-wiki-maintain", "repo-wiki-verify"):
        content = (PLUGIN_ROOT / "skills" / name / "SKILL.md").read_text()
        require(content.startswith("---\nname: "), f"{name} lacks skill front matter")
        require("workflow.py" in content or name == "repo-wiki", f"{name} must use the workflow runner")


def test_workflow_guards() -> None:
    workflow = load_workflow()
    require(workflow.validate_run_id("release-2026.08") == "release-2026.08", "safe run ID rejected")
    for unsafe in ("", ".", "..", "../escape", "nested/run", "nested\\run"):
        try:
            workflow.validate_run_id(unsafe)
        except workflow.WorkflowError as exc:
            require(exc.code == "unsafe_run_id", f"unexpected unsafe ID result: {exc.code}")
        else:
            raise AssertionError(f"unsafe run ID accepted: {unsafe!r}")
    redacted = workflow.redact({"api_key": "hidden", "message": "token=secret-value"})
    require("api_key" not in redacted, "API-key fields must be removed")
    require("secret-value" not in redacted["message"], "secret text must be redacted")
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        child = root / "child"
        child.mkdir()
        require(workflow.contained(child, root) == child.resolve(), "contained path rejected")
        try:
            workflow.contained(root.parent, root)
        except workflow.WorkflowError as exc:
            require(exc.code == "path_escapes_repository", f"unexpected escape result: {exc.code}")
        else:
            raise AssertionError("path outside root was accepted")


def main() -> int:
    test_metadata()
    test_skills()
    test_workflow_guards()
    print("PASS: standalone Repo Wiki Codex plugin smoke checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
