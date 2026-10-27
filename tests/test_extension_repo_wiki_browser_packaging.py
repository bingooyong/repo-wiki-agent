"""Smoke: TypeScript extension compiles and VSIX packages (requires Node/npm)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
EXT_DIR = REPO_ROOT / "extensions" / "repo-wiki-browser"
PACKAGE_JSON = EXT_DIR / "package.json"
EXTENSION_TS = EXT_DIR / "src" / "extension.ts"


def _run_in_extension(args: list[str]) -> None:
    result = subprocess.run(args, cwd=EXT_DIR, capture_output=True, text=True)
    if result.returncode:
        pytest.fail(
            f"{' '.join(args)} failed with exit {result.returncode}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def _ensure_extension_node_modules() -> None:
    if (EXT_DIR / "node_modules" / "typescript").is_dir():
        return
    _run_in_extension(["npm", "ci"])


@pytest.mark.skipif(shutil.which("npm") is None, reason="npm not on PATH")
def test_repo_wiki_browser_npm_compile() -> None:
    _ensure_extension_node_modules()
    _run_in_extension(["npm", "run", "compile"])


@pytest.mark.skipif(shutil.which("npx") is None, reason="npx not on PATH")
def test_repo_wiki_browser_vsce_package(tmp_path: Path) -> None:
    _ensure_extension_node_modules()
    vsix = tmp_path / "repo-wiki-browser-0.1.0.vsix"
    _run_in_extension(["npx", "--yes", "@vscode/vsce", "package", "--out", str(vsix)])
    assert vsix.is_file()
    assert vsix.stat().st_size > 10_000


def test_repo_wiki_browser_llm_manifest_defaults_are_non_secret_and_non_overriding() -> None:
    manifest = json.loads(PACKAGE_JSON.read_text())
    props = manifest["contributes"]["configuration"]["properties"]

    assert props["repoWikiBrowser.llm.provider"]["default"] == ""
    assert props["repoWikiBrowser.llm.model"]["default"] == ""
    assert props["repoWikiBrowser.llm.baseUrl"]["default"] == ""
    assert props["repoWikiBrowser.llm.apiKeyEnv"]["default"] == "REPO_WIKI_LLM_API_KEY"
    assert props["repoWikiBrowser.llm.source"]["default"] == "extension"
    assert set(props["repoWikiBrowser.llm.source"]["enum"]) >= {"extension", "yaml", "environment"}
    assert "repoWikiBrowser.llm.apiKey" not in props


def test_repo_wiki_browser_llm_env_injection_is_conditional() -> None:
    source = EXTENSION_TS.read_text()

    assert "const DEFAULT_LLM_PROVIDER" not in source
    assert "const DEFAULT_LLM_MODEL" not in source
    assert "LLM_PROVIDER: cfg.provider" not in source
    assert "LLM_MODEL: cfg.model" not in source
    assert "if (cfg.provider)" in source
    assert "env.LLM_PROVIDER = cfg.provider;" in source
    assert "if (cfg.model)" in source
    assert "env.LLM_MODEL = cfg.model;" in source
    assert "cfg.source === 'environment'" in source
    assert "cfg.source === 'extension'" in source


def test_repo_wiki_browser_invalid_api_key_env_blocks_update_and_test() -> None:
    source = EXTENSION_TS.read_text()

    update_body = re.search(
        r"async function runUpdateWiki[\s\S]+?\n}\n\nfunction getRepoWikiOutput", source
    )
    assert update_body is not None
    assert "try" in update_body.group(0)
    assert "const env = await buildLlmTerminalEnv(secrets);" in update_body.group(0)
    assert "vscode.window.showErrorMessage" in update_body.group(0)
    assert update_body.group(0).find(
        "const env = await buildLlmTerminalEnv(secrets);"
    ) < update_body.group(0).find("runTrackedCliCommand")

    tracked = re.search(
        r"async function runTrackedCliCommand[\s\S]+?\n}\n\nfunction getWorkspaceRoot", source
    )
    assert tracked is not None
    assert "ensureWorkspaceTrusted()" in tracked.group(0)
    assert "summarizeCliOutput" in tracked.group(0)
    assert "failureReason" in tracked.group(0)
    assert "childProcess.spawn" in tracked.group(0)

    test_body = re.search(
        r"async function testLlmConfig[\s\S]+?\n}\n\nfunction redactDiagnostics", source
    )
    assert test_body is not None
    assert "ensureValidApiKeyEnv(cfg)" in test_body.group(0)
    assert "vscode.window.showErrorMessage" in test_body.group(0)
    assert test_body.group(0).find("ensureValidApiKeyEnv(cfg)") < test_body.group(0).find(
        "childProcess.execFile"
    )
    assert test_body.group(0).find("await buildLlmTerminalEnv(secrets)") < test_body.group(0).find(
        "childProcess.execFile"
    )


def test_repo_wiki_browser_blocks_untrusted_workspace_execution_and_confirms_secret_use() -> None:
    manifest = json.loads(PACKAGE_JSON.read_text())
    untrusted = manifest["capabilities"]["untrustedWorkspaces"]
    assert untrusted["supported"] == "limited"

    source = EXTENSION_TS.read_text()
    assert "vscode.workspace.isTrusted" in source
    assert "function ensureWorkspaceTrusted" in source
    assert "async function confirmSecretInjection" in source
    assert "modal: true" in source

    env_builder = re.search(
        r"async function buildLlmTerminalEnv[\s\S]+?\n}\n\nfunction ensureValidApiKeyEnv",
        source,
    )
    assert env_builder is not None
    body = env_builder.group(0)
    assert body.find("ensureWorkspaceTrusted()") < body.find("await secrets.get")
    assert body.find("await confirmSecretInjection") < body.find("env[cfg.apiKeyEnv] = apiKey")

    terminal_runner = re.search(r"function runTerminalCommand[\s\S]+?\n}", source)
    assert terminal_runner is not None
    assert "ensureWorkspaceTrusted()" in terminal_runner.group(0)
