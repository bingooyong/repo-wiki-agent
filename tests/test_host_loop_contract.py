"""Host-loop contract: Codex marketplace install docs and VS Code READY gap UI."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
EXT_DIR = ROOT / "extensions" / "repo-wiki-browser"
PACKAGE_JSON = EXT_DIR / "package.json"
EXTENSION_TS = EXT_DIR / "src" / "extension.ts"
HOST_LOOP_TS = EXT_DIR / "src" / "hostLoop.ts"


def test_readme_codex_marketplace_install_is_copy_pasteable() -> None:
    text = README.read_text(encoding="utf-8")
    marketplace = json.loads(
        (ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8")
    )

    assert marketplace["name"] == "repo-wiki-local"
    assert "codex plugin marketplace add ." in text
    assert '"marketplaceName": "repo-wiki-local"' in text
    assert "codex plugin add repo-wiki@repo-wiki-local" in text
    assert "codex plugin list" in text
    assert "repo-wiki@repo-wiki-local" in text
    assert "installed, enabled" in text
    assert "repo-wiki-generate" in text
    assert "repo-wiki-maintain" in text
    assert "repo-wiki-verify" in text
    assert "codex plugin remove repo-wiki@repo-wiki-local" in text
    assert "codex plugin marketplace remove repo-wiki-local" in text
    assert "mcpServers" not in text.lower()
    assert "auto-publish" not in text.lower()


def test_extension_package_exposes_isolation_generate_verify_publish() -> None:
    package = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    commands = {item["command"] for item in package["contributes"]["commands"]}
    events = set(package["activationEvents"])
    default_generate = package["contributes"]["configuration"]["properties"][
        "repoWikiBrowser.generateCommand"
    ]["default"]

    assert default_generate == (
        "uv run repo-wiki generate --profile qoder-like --output .repo-agent-eval"
    )
    assert "repoWikiBrowser.releasePublish" in commands
    assert "onCommand:repoWikiBrowser.releasePublish" in events
    titles = {item["command"]: item["title"] for item in package["contributes"]["commands"]}
    assert titles["repoWikiBrowser.releasePublish"] == "Release Publish READY"


def test_extension_wires_progress_failure_and_publish_without_run_fallback() -> None:
    source = EXTENSION_TS.read_text(encoding="utf-8")
    host_loop = HOST_LOOP_TS.read_text(encoding="utf-8")

    assert "diagnoseReadyGap" in host_loop
    assert "summarizeCliOutput" in host_loop
    assert "DEFAULT_PUBLISH_COMMAND" in host_loop
    assert "diagnoseReadyGap" in source
    assert "summarizeCliOutput" in source
    assert "repoWikiBrowser.releasePublish" in source
    assert "runTrackedCliCommand" in source
    assert "failureReason" in source
    assert "discoverRun" not in source
    assert "path.join(workspaceRoot, 'docs')" not in source
    assert "mcpServers" not in source


def test_host_loop_node_contract() -> None:
    compiled = EXT_DIR / "out" / "hostLoop.js"
    assert compiled.exists(), "compile extensions/repo-wiki-browser before pytest"
    result = subprocess.run(
        ["node", "test/hostLoop.test.js"],
        cwd=EXT_DIR,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS" in result.stdout
