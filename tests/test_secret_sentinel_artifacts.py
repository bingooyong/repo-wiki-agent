from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.secret_sentinel_scan import SENTINEL_VALUES, scan_paths

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "secret_sentinel_scan.py"


def write_artifact_tree(root: Path) -> None:
    (root / ".repo-agent-eval" / "repowiki" / "zh").mkdir(parents=True)
    (root / ".repo-agent-eval" / "runs" / "run-001" / "logs").mkdir(parents=True)
    (root / ".repo-agent-eval" / "releases" / "ready" / "docs").mkdir(parents=True)
    (root / "docs").mkdir()

    (root / "repo-wiki.yaml").write_text(
        "llm:\n  provider: openai\n  api_key_env: REPO_WIKI_LLM_API_KEY\n",
        encoding="utf-8",
    )
    (root / ".repo-agent-eval" / "repowiki" / "zh" / "manifest.json").write_text(
        '{"status":"READY","llm":{"api_key_env":"REPO_WIKI_LLM_API_KEY"}}\n',
        encoding="utf-8",
    )
    (root / ".repo-agent-eval" / "runs" / "run-001" / "command.log").write_text(
        "LLM_API_KEY_ENV=REPO_WIKI_LLM_API_KEY repo-wiki generate --profile qoder-like\n",
        encoding="utf-8",
    )
    (root / ".repo-agent-eval" / "runs" / "run-001" / "logs" / "diagnostics.log").write_text(
        "api_key_env: [REDACTED]\napi_key_present: true\n",
        encoding="utf-8",
    )
    (root / ".repo-agent-eval" / "releases" / "ready" / "docs" / "index.md").write_text(
        "# Wiki\nGenerated content with no literal credential values.\n",
        encoding="utf-8",
    )
    (root / "docs" / "operator.md").write_text(
        "Use api_key_env and store the actual key outside artifacts.\n",
        encoding="utf-8",
    )


def run_cli(*paths: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *(str(path) for path in paths)],
        check=False,
        text=True,
        capture_output=True,
    )


def test_clean_artifacts_return_zero(tmp_path: Path) -> None:
    write_artifact_tree(tmp_path)

    result = run_cli(tmp_path)

    assert result.returncode == 0
    assert "OK (0 findings)" in result.stdout
    assert result.stderr == ""
    assert scan_paths([tmp_path]) == []


def test_explicit_sentinel_leak_is_detected_across_artifacts(tmp_path: Path) -> None:
    write_artifact_tree(tmp_path)
    leaked = SENTINEL_VALUES[0]
    leak_path = tmp_path / ".repo-agent-eval" / "repowiki" / "zh" / "manifest.json"
    leak_path.write_text('{"api_key":"' + leaked + '"}\n', encoding="utf-8")

    result = run_cli(tmp_path)

    assert result.returncode == 1
    combined = result.stdout + result.stderr
    assert "sentinel-value" in combined
    assert "manifest.json" in combined
    assert leaked not in combined
    assert "[REDACTED" in combined


def test_cli_redacts_secret_shaped_path_components(tmp_path: Path) -> None:
    write_artifact_tree(tmp_path)
    secret_dir_name = "sk-" + "1234567890abcdef1234567890abcdef"
    leak_path = tmp_path / ".repo-agent-eval" / "runs" / "run-001" / secret_dir_name / "leak.txt"
    leak_path.parent.mkdir(parents=True)
    leaked = SENTINEL_VALUES[0]
    leak_path.write_text(f"api_key={leaked}\n", encoding="utf-8")

    result = run_cli(tmp_path)

    assert result.returncode == 1
    combined = result.stdout + result.stderr
    assert "sentinel-value" in combined
    assert "leak.txt" in combined
    assert "secret-sentinel: FAIL" in combined
    assert secret_dir_name not in combined
    assert leaked not in combined
    assert "[REDACTED" in combined


def test_common_token_and_key_forms_are_detected(tmp_path: Path) -> None:
    write_artifact_tree(tmp_path)
    token = "tok_live_1234567890abcdef1234567890abcdef"
    openai_key = "sk-" + "1234567890abcdef1234567890abcdef"
    jwt = "eyJhbGciOiJIUzI1NiJ9" + "." + "eyJzdWIiOiJyZXBvLXdpa2kifQ" + ".signature123"
    log_path = tmp_path / ".repo-agent-eval" / "runs" / "run-001" / "logs" / "diagnostics.log"
    log_path.write_text(
        f"Authorization: Bearer {token}\napi_key={openai_key}\nJWT={jwt}\n",
        encoding="utf-8",
    )

    result = run_cli(tmp_path)

    assert result.returncode == 1
    combined = result.stdout + result.stderr
    assert "bearer-token" in combined
    assert "openai-style-sk" in combined
    assert "labeled-api-key" in combined
    assert "jwt-token" in combined
    assert token not in combined
    assert openai_key not in combined
    assert jwt not in combined


def test_binary_files_and_ignored_directories_are_skipped(tmp_path: Path) -> None:
    write_artifact_tree(tmp_path)
    leaked = SENTINEL_VALUES[1]
    node_modules = tmp_path / "node_modules" / "pkg"
    node_modules.mkdir(parents=True)
    (node_modules / "fixture.log").write_text(f"api_key={leaked}\n", encoding="utf-8")
    (tmp_path / ".repo-agent-eval" / "runs" / "run-001" / "binary.bin").write_bytes(
        b"\x00\x01" + leaked.encode("utf-8")
    )

    result = run_cli(tmp_path)

    assert result.returncode == 0
    assert "OK (0 findings)" in result.stdout
    assert leaked not in result.stdout + result.stderr


def test_output_redacts_multiple_secret_forms(tmp_path: Path) -> None:
    write_artifact_tree(tmp_path)
    leaked_sentinel = SENTINEL_VALUES[2]
    labeled_secret = "minimax-secret-1234567890abcdef123456"
    release_doc = tmp_path / ".repo-agent-eval" / "releases" / "ready" / "docs" / "index.md"
    release_doc.write_text(
        f"sentinel={leaked_sentinel}\nsecret_key: {labeled_secret}\n",
        encoding="utf-8",
    )

    result = run_cli(tmp_path)

    assert result.returncode == 1
    combined = result.stdout + result.stderr
    assert leaked_sentinel not in combined
    assert labeled_secret not in combined
    assert combined.count("[REDACTED") >= 2
    assert "secret-sentinel: FAIL" in combined
