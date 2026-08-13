"""Contract tests for the Codex plugin lifecycle runner.

The runner deliberately stays outside the installed package. These tests combine
focused in-process doubles with a deterministic fake ``repo_wiki.main`` package
executed through real child processes, without reading ambient dotenv config.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / "plugins" / "repo-wiki" / "scripts" / "workflow.py"

FAKE_MAIN = r"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


def value_after(args: list[str], option: str, default: str = "") -> str:
    try:
        return args[args.index(option) + 1]
    except (ValueError, IndexError):
        return default


def record(args: list[str]) -> None:
    path = Path(os.environ["FAKE_CALL_LOG"])
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"cwd": os.getcwd(), "argv": args}) + "\n")


def maybe_wait(stage: str) -> None:
    if os.environ.get("FAKE_WAIT_STAGE") != stage:
        return
    signal = Path(os.environ["FAKE_WAIT_SIGNAL"])
    proceed = Path(os.environ["FAKE_WAIT_PROCEED"])
    signal.touch()
    deadline = time.monotonic() + 10
    while not proceed.exists():
        if time.monotonic() >= deadline:
            raise SystemExit(97)
        time.sleep(0.01)


def main() -> int:
    args = sys.argv[1:]
    record(args)
    stage = args[0] if args and args[0] != "--help" else "root"
    if "--help" in args:
        help_text = {
            "root": "config init index update sync quality-gate generate improve verify release-publish",
            "config": "--ci",
            "init": "--config",
            "index": "--config",
            "update": "--config",
            "sync": "--config",
            "quality-gate": "--output --run --review-allowed-signers",
            "generate": "--output --run-id --config",
            "improve": "--output --run-id --config",
            "verify": "--profile --output --ci --config",
            "release-publish": "--output --run --inspect-only --review-allowed-signers",
        }[stage]
        missing_stage = os.environ.get("FAKE_MISSING_FLAG_STAGE")
        if missing_stage == stage:
            help_text = help_text.replace("--ci", "").replace("--run-id", "")
        print(help_text)
        return 0
    maybe_wait(stage)
    if os.environ.get("FAKE_FAIL_STAGE") == stage:
        print(os.environ.get("FAKE_FAILURE_OUTPUT", "failed"))
        return 9
    if os.environ.get("FAKE_MALFORMED_STAGE") == stage:
        print("not-json")
        return 0

    cwd = Path.cwd()
    run_id = value_after(args, "--run-id") or value_after(args, "--run") or "run-42"
    if stage in {"generate", "improve"}:
        output = Path(value_after(args, "--output"))
        run_dir = (cwd / output / run_id).resolve()
        run_dir.mkdir(parents=True, exist_ok=True)
        manifest_run = os.environ.get("FAKE_MANIFEST_RUN", run_id)
        (run_dir / "manifest.json").write_text(
            json.dumps({"run_id": manifest_run}), encoding="utf-8"
        )
        returned_run = os.environ.get("FAKE_MANIFEST_PATH_RUN", run_id)
        payload = {"manifest_path": str((cwd / output / returned_run / "manifest.json").resolve())}
    elif stage == "verify":
        run_dir = Path(value_after(args, "--output")).resolve()
        report = run_dir / "reports" / "strict-verify-output.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("{}", encoding="utf-8")
        payload = {
            "grade": os.environ.get("FAKE_VERIFY_GRADE", "PASS"),
            "verify_root": os.environ.get("FAKE_VERIFY_ROOT", str(run_dir)),
            "canonical_report_path": os.environ.get("FAKE_REPORT_PATH", str(report)),
        }
    elif stage == "quality-gate":
        report = cwd / ".repo-agent-eval" / "runs" / run_id / "reports" / "g005-quality-gates.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("{}", encoding="utf-8")
        payload = {"status": "PASS", "run_id": run_id, "report_json": str(report)}
    elif stage == "release-publish":
        inspect_only = "--inspect-only" in args
        payload = {
            "status": os.environ.get(
                "FAKE_INSPECT_STATUS" if inspect_only else "FAKE_PUBLISH_STATUS",
                "READY_CANDIDATE" if inspect_only else "PUBLISHED",
            ),
            "run_id": os.environ.get(
                "FAKE_INSPECT_RUN" if inspect_only else "FAKE_PUBLISH_RUN", run_id
            ),
        }
    else:
        payload = json.loads(os.environ.get("FAKE_GENERIC_PAYLOAD", '{"status":"OK"}'))
    prefix = "INFO fake completed\n" if os.environ.get("FAKE_RICH_PREFIX") else ""
    print(prefix + json.dumps(payload))
    return 0


raise SystemExit(main())
"""


@pytest.fixture(scope="module")
def workflow() -> ModuleType:
    spec = importlib.util.spec_from_file_location("codex_plugin_workflow", WORKFLOW_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    return tmp_path


def _context(workflow: ModuleType, root: Path, operation: str, run_id: str = "run-42"):
    run_dir = root / ".repo-agent-eval" / "runs" / run_id
    _, module_origin, import_root, module_fingerprint = workflow.resolve_cli_distribution(root)
    return workflow.WorkflowContext(
        root=root,
        config=None,
        executable=sys.executable,
        cli_version="0.1.0",
        capabilities=frozenset(
            {
                "root",
                "config",
                "init",
                "index",
                "update",
                "sync",
                "quality-gate",
                "generate",
                "improve",
                "verify",
                "release-publish",
            }
        ),
        cli_module_origin=module_origin,
        cli_import_root=import_root,
        cli_module_fingerprint=module_fingerprint,
        operation=operation,
        output_parent=run_dir.parent,
        run_id=run_id,
        run_dir=run_dir,
    )


class FakeModule:
    """A subprocess-level fake for ``python -m repo_wiki.main``."""

    def __init__(self, root: Path, run_id: str = "run-42") -> None:
        self.root = root
        self.run_id = run_id
        self.calls: list[list[str]] = []
        self.return_codes: dict[str, int] = {}
        self.malformed: set[str] = set()
        self.prefixed: set[str] = set()
        self.inspect_status = "READY_CANDIDATE"

    def install(self, monkeypatch: pytest.MonkeyPatch, workflow: ModuleType) -> None:
        monkeypatch.setattr(workflow.subprocess, "run", self.run)
        monkeypatch.setattr(workflow, "probe_module_origin", lambda *args: None)

    def run(self, argv: list[str], **kwargs: object) -> SimpleNamespace:
        assert kwargs["cwd"] == self.root
        assert argv[:3] == [sys.executable, "-m", "repo_wiki.main"]
        self.calls.append(argv)
        tail = argv[3:]
        stage = tail[0] if tail and tail[0] != "--help" else "root"
        if "--help" in tail:
            help_text = {
                "root": "config init index update sync quality-gate generate improve verify release-publish",
                "config": "--ci",
                "init": "--config",
                "index": "--config",
                "update": "--config",
                "sync": "--config",
                "quality-gate": "--output --run --review-allowed-signers",
                "generate": "--output --run-id --config",
                "improve": "--output --run-id --config",
                "verify": "--profile --output --ci --config",
                "release-publish": "--output --run --inspect-only --review-allowed-signers",
            }[stage]
            return SimpleNamespace(returncode=0, stdout=help_text, stderr="")
        if self.return_codes.get(stage, 0):
            return SimpleNamespace(
                returncode=self.return_codes[stage], stdout="token=not-for-logs", stderr=""
            )
        if stage in self.malformed:
            return SimpleNamespace(returncode=0, stdout="not-json", stderr="")
        run_dir = self.root / ".repo-agent-eval" / "runs" / self.run_id
        if stage in {"generate", "improve"}:
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "manifest.json").write_text(
                json.dumps({"run_id": self.run_id}), encoding="utf-8"
            )
            payload = {"manifest_path": str(run_dir / "manifest.json")}
        elif stage == "verify":
            report = run_dir / "reports" / "strict-verify-output.json"
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text("{}", encoding="utf-8")
            payload = {
                "grade": "PASS",
                "verify_root": str(run_dir),
                "canonical_report_path": str(report),
            }
        elif stage == "quality-gate":
            report = run_dir / "reports" / "g005-quality-gates.json"
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text("{}", encoding="utf-8")
            payload = {"status": "PASS", "run_id": self.run_id, "report_json": str(report)}
        elif stage == "release-publish":
            payload = {
                "status": self.inspect_status if "--inspect-only" in tail else "PUBLISHED",
                "run_id": self.run_id,
            }
        else:
            payload = {"status": "OK"}
        stdout = json.dumps(payload)
        if stage in self.prefixed:
            stdout = f"INFO {stage} completed\n{stdout}\n"
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")


def _lifecycle_calls(fake: FakeModule) -> list[list[str]]:
    return [call for call in fake.calls if "--help" not in call]


def _write_g005(ctx: Any, workflow: ModuleType) -> None:
    run_dir = ctx.run_dir
    assert run_dir
    reports = run_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    references = {}
    for name in workflow.REQUIRED_G005_ARTIFACTS:
        filename = f"{name}.json"
        (reports / filename).write_text("{}", encoding="utf-8")
        references[name] = {"path": f"reports/{filename}"}
    (reports / "strict-verify-output.json").write_text("{}", encoding="utf-8")
    (reports / "g005-quality-gates.json").write_text(
        json.dumps({"run_id": ctx.run_id, "status": "PASS", "artifact_references": references}),
        encoding="utf-8",
    )
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": ctx.run_id,
                "report_paths": {
                    "strict_verify": "reports/strict-verify-output.json",
                    "g005_quality_gates": "reports/g005-quality-gates.json",
                },
            }
        ),
        encoding="utf-8",
    )


def _install_fake_module(tmp_path: Path, version: str = "0.1.0") -> Path:
    fake_root = tmp_path.parent / f"{tmp_path.name}-fake-pythonpath"
    package = fake_root / "repo_wiki"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "main.py").write_text(FAKE_MAIN, encoding="utf-8")
    metadata = fake_root / f"repo_wiki-{version}.dist-info"
    metadata.mkdir()
    (metadata / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: repo-wiki\nVersion: {version}\n",
        encoding="utf-8",
    )
    (metadata / "RECORD").write_text(
        "repo_wiki/__init__.py,,\nrepo_wiki/main.py,,\n",
        encoding="utf-8",
    )
    return fake_root


def _install_fake_distribution_without_module(tmp_path: Path) -> Path:
    fake_root = tmp_path.parent / f"{tmp_path.name}-fake-pythonpath"
    package = fake_root / "repo_wiki"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "main.py").write_text("", encoding="utf-8")
    metadata = fake_root / "repo_wiki-0.1.0.dist-info"
    metadata.mkdir()
    (metadata / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: repo-wiki\nVersion: 0.1.0\n",
        encoding="utf-8",
    )
    (metadata / "RECORD").write_text(
        "repo_wiki/__init__.py,,\nrepo_wiki/main.py,,\n",
        encoding="utf-8",
    )
    (fake_root / "sitecustomize.py").write_text(
        """
import sys


class BlockRepoWikiMain:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "repo_wiki.main":
            raise ModuleNotFoundError("blocked repo_wiki.main fixture")
        return None


sys.meta_path.insert(0, BlockRepoWikiMain())
""",
        encoding="utf-8",
    )
    return fake_root


def _runner_env(fake_root: Path, call_log: Path, **extra: str) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(fake_root), env.get("PYTHONPATH", "")]))
    env["FAKE_CALL_LOG"] = str(call_log)
    env.update(extra)
    return env


def _run_runner(
    repository: Path,
    fake_root: Path,
    call_log: Path,
    *args: str,
    **extra: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(WORKFLOW_PATH), *args, "--cwd", str(repository)],
        cwd=repository,
        env=_runner_env(fake_root, call_log, **extra),
        text=True,
        capture_output=True,
        check=False,
    )


def _recorded_calls(call_log: Path, *, lifecycle_only: bool = False) -> list[dict[str, Any]]:
    if not call_log.exists():
        return []
    calls = [json.loads(line) for line in call_log.read_text(encoding="utf-8").splitlines()]
    if lifecycle_only:
        calls = [call for call in calls if "--help" not in call["argv"]]
    return calls


def _last_event(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert lines, result.stderr
    return json.loads(lines[-1])


def test_yaml_preflight_uses_explicit_config_without_reading_foreign_dotenv(
    workflow: ModuleType, repository: Path
) -> None:
    (repository / ".env").write_text("REPO_WIKI_TEST_SECRET=must-not-be-read", encoding="utf-8")
    (repository / "repo-wiki.yaml").write_text("project:\n  root: .\n", encoding="utf-8")
    chosen = workflow.select_config(repository, "repo-wiki.yaml")
    assert chosen == (repository / "repo-wiki.yaml").resolve()
    workflow.yaml_preflight(repository, chosen)


def test_config_selection_prefers_repo_wiki_yaml_and_rejects_foreign_root(
    workflow: ModuleType, repository: Path
) -> None:
    (repository / ".repo-wiki.yaml").write_text("project: {root: .}", encoding="utf-8")
    preferred = repository / "repo-wiki.yaml"
    preferred.write_text("project: {root: ../outside}", encoding="utf-8")
    assert workflow.select_config(repository, None) == preferred.resolve()
    with pytest.raises(workflow.WorkflowError, match="active repository") as error:
        workflow.yaml_preflight(repository, preferred)
    assert error.value.code == "foreign_project_root"


@pytest.mark.parametrize(
    "run_id", ["..", "../escape", "with/slash", "with\\slash", "/absolute", "bad\x00id"]
)
def test_validate_run_id_rejects_traversal_separators_and_controls(
    workflow: ModuleType, run_id: str
) -> None:
    with pytest.raises(workflow.WorkflowError) as error:
        workflow.validate_run_id(run_id)
    assert error.value.code == "unsafe_run_id"


def test_reserve_run_rejects_symlinked_output_parent(
    workflow: ModuleType, repository: Path, tmp_path: Path
) -> None:
    target = tmp_path / "outside"
    target.mkdir()
    eval_root = repository / ".repo-agent-eval"
    eval_root.mkdir()
    try:
        (eval_root / "runs").symlink_to(target, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks unavailable: {exc}")
    with pytest.raises(workflow.WorkflowError) as error:
        workflow.reserve_run(repository, "safe-id")
    assert error.value.code == "symlink_path"


def test_command_uses_current_python_module_and_only_attaches_config_when_requested(
    workflow: ModuleType, repository: Path
) -> None:
    config = repository / "repo-wiki.yaml"
    config.write_text("{}", encoding="utf-8")
    ctx = _context(workflow, repository, "doctor")
    ctx = replace(
        ctx,
        config=config,
        config_explicit=True,
        config_fingerprint=workflow.fingerprint_file(config, "config_changed"),
    )
    assert workflow.command(ctx, "search", "needle") == [
        sys.executable,
        "-m",
        "repo_wiki.main",
        "search",
        "needle",
    ]
    assert workflow.command(ctx, "config", "--ci", config=True)[-2:] == ["--config", str(config)]


def test_command_omits_config_argv_for_auto_discovered_yaml(
    workflow: ModuleType, repository: Path
) -> None:
    config = repository / "repo-wiki.yaml"
    config.write_text("{}", encoding="utf-8")
    ctx = replace(_context(workflow, repository, "doctor"), config=config, config_explicit=False)

    assert workflow.command(ctx, "config", "--ci", config=True) == [
        sys.executable,
        "-m",
        "repo_wiki.main",
        "config",
        "--ci",
    ]


def test_cli_environment_removes_ambient_allowed_signers(
    workflow: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("REPO_WIKI_G005_REVIEW_ALLOWED_SIGNERS", str(tmp_path / "ambient"))

    env = workflow.cli_environment(tmp_path)

    assert "REPO_WIKI_G005_REVIEW_ALLOWED_SIGNERS" not in env


def test_probe_cli_checks_every_help_contract_and_ignores_path_binary(
    workflow: ModuleType, repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeModule(repository)
    fake.install(monkeypatch, workflow)
    monkeypatch.setattr(workflow, "probe_module_origin", lambda *args: None)
    version, capabilities = workflow.probe_cli(repository, sys.executable)
    assert version == "0.1.0"
    assert capabilities == {
        "root",
        "config",
        "init",
        "index",
        "update",
        "sync",
        "quality-gate",
        "generate",
        "improve",
        "verify",
        "release-publish",
    }
    assert all(call[:3] == [sys.executable, "-m", "repo_wiki.main"] for call in fake.calls)
    assert len(fake.calls) == 11


@pytest.mark.parametrize("operation", ["generate", "improve"])
def test_generation_workflow_runs_exact_identity_commands(
    workflow: ModuleType, repository: Path, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    ctx = _context(workflow, repository, operation)
    ctx.run_dir.mkdir(parents=True)
    fake = FakeModule(repository)
    fake.install(monkeypatch, workflow)
    workflow.generate_or_improve(ctx)
    calls = _lifecycle_calls(fake)
    stages = [call[3] for call in calls]
    assert stages == ["config", operation, "verify"]
    generated = calls[1]
    assert generated[3:] == [
        operation,
        "--profile",
        "qoder-like",
        "--output",
        ".repo-agent-eval/runs",
        "--run-id",
        "run-42",
    ]
    assert calls[-1][3:7] == ["verify", "--profile", "qoder-like", "--output"]


def test_generation_stops_before_verification_after_nonzero_command(
    workflow: ModuleType, repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(workflow, repository, "generate")
    ctx.run_dir.mkdir(parents=True)
    fake = FakeModule(repository)
    fake.return_codes["generate"] = 9
    fake.install(monkeypatch, workflow)
    with pytest.raises(workflow.WorkflowError) as error:
        workflow.generate_or_improve(ctx)
    assert error.value.code == "generate_failed"
    assert [call[3] for call in fake.calls] == ["config", "generate"]


def test_generation_stops_before_verification_after_malformed_json(
    workflow: ModuleType, repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(workflow, repository, "generate")
    ctx.run_dir.mkdir(parents=True)
    fake = FakeModule(repository)
    fake.malformed.add("generate")
    fake.install(monkeypatch, workflow)
    with pytest.raises(workflow.WorkflowError) as error:
        workflow.generate_or_improve(ctx)
    assert error.value.code == "malformed_json"
    assert [call[3] for call in fake.calls] == ["config", "generate"]


def test_generation_accepts_cli_info_prefix_before_final_json(
    workflow: ModuleType, repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(workflow, repository, "generate")
    ctx.run_dir.mkdir(parents=True)
    fake = FakeModule(repository)
    fake.prefixed.add("generate")
    fake.install(monkeypatch, workflow)

    workflow.generate_or_improve(ctx)

    assert [call[3] for call in _lifecycle_calls(fake)] == ["config", "generate", "verify"]


@pytest.mark.parametrize("operation", ["init", "index", "update", "sync"])
def test_maintenance_workflow_runs_config_then_exact_operation(
    workflow: ModuleType,
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    ctx = _context(workflow, repository, operation, run_id="run-unused")
    ctx = replace(ctx, run_id=None, run_dir=None)
    fake = FakeModule(repository)
    fake.prefixed.add(operation)
    fake.install(monkeypatch, workflow)

    workflow.maintain(ctx)

    assert [call[3] for call in fake.calls] == ["config", operation]
    assert fake.calls[-1][3:] == [operation]


def test_quality_gate_uses_exact_run_and_canonical_signer(
    workflow: ModuleType, repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(workflow, repository, "quality-gate")
    ctx.run_dir.mkdir(parents=True)
    signers = repository.parent / "quality-gate-signers"
    signers.write_text("reviewer", encoding="utf-8")
    ctx = replace(
        ctx,
        allowed_signers=signers.resolve(),
        allowed_signers_fingerprint=workflow.fingerprint_file(
            signers.resolve(), "unsafe_allowed_signers"
        ),
        quality_gate_args=("--review-allowed-signers", str(signers.resolve())),
    )
    fake = FakeModule(repository)
    fake.install(monkeypatch, workflow)
    monkeypatch.setattr(workflow, "select_config", lambda *_: None)
    monkeypatch.setattr(workflow, "probe_cli", lambda *_: ("0.1.0", ctx.capabilities))

    workflow.quality_gate(ctx)

    calls = _lifecycle_calls(fake)
    assert len(calls) == 1
    assert calls[0][3:] == [
        "quality-gate",
        "--output",
        ".repo-agent-eval",
        "--run",
        "run-42",
        "--review-allowed-signers",
        str(signers.resolve()),
    ]


def test_verify_rejects_manifest_for_a_different_run(
    workflow: ModuleType, repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(workflow, repository, "verify")
    ctx.run_dir.mkdir(parents=True)
    (ctx.run_dir / "manifest.json").write_text('{"run_id": "other"}', encoding="utf-8")
    fake = FakeModule(repository)
    fake.install(monkeypatch, workflow)
    with pytest.raises(workflow.WorkflowError) as error:
        workflow.verify(ctx)
    assert error.value.code == "manifest_identity_mismatch"


def test_publish_requires_g005_before_inspection(
    workflow: ModuleType, repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(workflow, repository, "publish")
    ctx.run_dir.mkdir(parents=True)
    fake = FakeModule(repository)
    fake.install(monkeypatch, workflow)
    with pytest.raises(workflow.WorkflowError) as error:
        workflow.publish(ctx, None)
    assert error.value.code == "missing_g005_evidence"
    assert _lifecycle_calls(fake) == []


def test_publish_without_confirmation_only_inspects(
    workflow: ModuleType, repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(workflow, repository, "publish")
    ctx.run_dir.mkdir(parents=True)
    _write_g005(ctx, workflow)
    fake = FakeModule(repository)
    fake.install(monkeypatch, workflow)
    workflow.publish(ctx, None)
    publish_calls = [call for call in _lifecycle_calls(fake) if call[3] == "release-publish"]
    assert len(publish_calls) == 1
    assert publish_calls[0][-1] == "--inspect-only"


def test_publish_rejects_wrong_confirmation_before_final_publish(
    workflow: ModuleType, repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(workflow, repository, "publish")
    ctx.run_dir.mkdir(parents=True)
    _write_g005(ctx, workflow)
    fake = FakeModule(repository)
    fake.install(monkeypatch, workflow)
    with pytest.raises(workflow.WorkflowError) as error:
        workflow.publish(ctx, "different-run")
    assert error.value.code == "confirmation_mismatch"
    assert len([call for call in _lifecycle_calls(fake) if call[3] == "release-publish"]) == 1


def test_publish_propagates_external_signers_to_inspects_and_final_publish(
    workflow: ModuleType, repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(workflow, repository, "publish")
    ctx.run_dir.mkdir(parents=True)
    _write_g005(ctx, workflow)
    signers = repository.parent / "allowed-signers"
    signers.write_text("reviewer", encoding="utf-8")
    ctx = replace(
        ctx,
        allowed_signers=signers.resolve(),
        allowed_signers_fingerprint=workflow.fingerprint_file(
            signers.resolve(), "unsafe_allowed_signers"
        ),
    )
    fake = FakeModule(repository)
    fake.install(monkeypatch, workflow)
    monkeypatch.setattr(workflow, "select_config", lambda *_: None)
    monkeypatch.setattr(workflow, "probe_cli", lambda *_: ("0.1.0", ctx.capabilities))
    workflow.publish(ctx, ctx.run_id)
    calls = [call for call in _lifecycle_calls(fake) if call[3] == "release-publish"]
    assert len(calls) == 3
    assert all(["--review-allowed-signers", str(signers.resolve())] == call[-2:] for call in calls)
    assert "--inspect-only" not in calls[-1]


def test_error_emission_redacts_secret_shaped_values(
    workflow: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    workflow.emit(
        None, "error", "FAIL", message="token=definitely-not-for-output", api_key="raw-secret"
    )
    output = capsys.readouterr().out
    assert "definitely-not-for-output" not in output
    assert "raw-secret" not in output
    assert "***REDACTED***" in output


@pytest.mark.parametrize("operation", ["generate", "improve"])
def test_subprocess_generation_runs_exact_module_sequence_and_cwd(
    repository: Path, tmp_path: Path, operation: str
) -> None:
    fake_root = _install_fake_module(tmp_path)
    call_log = tmp_path / "calls.jsonl"

    result = _run_runner(
        repository,
        fake_root,
        call_log,
        operation,
        "--run-id",
        "run-42",
        FAKE_RICH_PREFIX="1",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    calls = _recorded_calls(call_log, lifecycle_only=True)
    assert [call["argv"][0] for call in calls] == ["config", operation, "verify"]
    assert {call["cwd"] for call in calls} == {str(repository)}
    assert calls[1]["argv"] == [
        operation,
        "--profile",
        "qoder-like",
        "--output",
        ".repo-agent-eval/runs",
        "--run-id",
        "run-42",
    ]
    assert calls[2]["argv"][4] == str(repository / ".repo-agent-eval" / "runs" / "run-42")
    event = _last_event(result)
    assert event["status"] == "PASS"
    assert event["run_id"] == "run-42"


def test_subprocess_ignores_target_local_module_and_path_shadow(
    repository: Path, tmp_path: Path
) -> None:
    fake_root = _install_fake_module(tmp_path)
    call_log = tmp_path / "calls.jsonl"
    marker = tmp_path / "shadow-executed"
    local_package = repository / "repo_wiki"
    local_package.mkdir()
    (local_package / "__init__.py").write_text("", encoding="utf-8")
    (local_package / "main.py").write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('local module executed')\n"
        "raise SystemExit('shadow module must not run')\n",
        encoding="utf-8",
    )
    shadow_bin = tmp_path / "bin"
    shadow_bin.mkdir()
    shadow_command = shadow_bin / "repo-wiki"
    shadow_command.write_text(
        f"#!/bin/sh\nprintf '%s' 'path executable executed' > {str(marker)!r}\nexit 99\n",
        encoding="utf-8",
    )
    shadow_command.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join([str(shadow_bin), env.get("PATH", "")])
    result = subprocess.run(
        [
            sys.executable,
            str(WORKFLOW_PATH),
            "doctor",
            "--cwd",
            str(repository),
        ],
        cwd=repository,
        env=_runner_env(fake_root, call_log, PATH=env["PATH"]),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert not marker.exists()
    assert _last_event(result)["status"] == "PASS"
    calls = _recorded_calls(call_log)
    assert all(
        call["argv"]
        and call["argv"][0]
        in {
            "--help",
            "config",
            "init",
            "index",
            "update",
            "sync",
            "quality-gate",
            "generate",
            "improve",
            "verify",
            "release-publish",
        }
        for call in calls
    )


@pytest.mark.parametrize(
    ("operation", "extra", "reason", "lifecycle"),
    [
        ("generate", {"FAKE_FAIL_STAGE": "config"}, "config_failed", ["config"]),
        (
            "generate",
            {"FAKE_FAIL_STAGE": "generate"},
            "generate_failed",
            ["config", "generate"],
        ),
        (
            "generate",
            {"FAKE_MALFORMED_STAGE": "generate"},
            "malformed_json",
            ["config", "generate"],
        ),
        (
            "generate",
            {"FAKE_FAIL_STAGE": "verify"},
            "verify_failed",
            ["config", "generate", "verify"],
        ),
    ],
)
def test_subprocess_failures_stop_downstream_commands(
    repository: Path,
    tmp_path: Path,
    operation: str,
    extra: dict[str, str],
    reason: str,
    lifecycle: list[str],
) -> None:
    fake_root = _install_fake_module(tmp_path)
    call_log = tmp_path / "calls.jsonl"

    result = _run_runner(
        repository,
        fake_root,
        call_log,
        operation,
        "--run-id",
        "run-42",
        **extra,
    )

    assert result.returncode == 1
    assert _last_event(result)["reason_code"] == reason
    assert [call["argv"][0] for call in _recorded_calls(call_log, lifecycle_only=True)] == lifecycle


@pytest.mark.parametrize(
    ("version", "extra"),
    [
        ("0.0.9", {}),
        ("0.1.0", {"FAKE_MISSING_FLAG_STAGE": "generate"}),
    ],
)
def test_subprocess_incompatible_cli_stops_before_lifecycle_writes(
    repository: Path, tmp_path: Path, version: str, extra: dict[str, str]
) -> None:
    fake_root = _install_fake_module(tmp_path, version=version)
    call_log = tmp_path / "calls.jsonl"

    result = _run_runner(
        repository,
        fake_root,
        call_log,
        "generate",
        "--run-id",
        "run-42",
        **extra,
    )

    assert result.returncode == 1
    assert _last_event(result)["reason_code"] == "incompatible_cli"
    assert _recorded_calls(call_log, lifecycle_only=True) == []
    assert not (repository / ".repo-agent-eval" / "runs" / "run-42").exists()


def test_subprocess_missing_main_module_stops_before_lifecycle_writes(
    repository: Path, tmp_path: Path
) -> None:
    fake_root = _install_fake_distribution_without_module(tmp_path)
    call_log = tmp_path / "calls.jsonl"
    result = subprocess.run(
        [
            sys.executable,
            str(WORKFLOW_PATH),
            "generate",
            "--run-id",
            "run-42",
            "--cwd",
            str(repository),
        ],
        cwd=repository,
        env=_runner_env(fake_root, call_log),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert _last_event(result)["reason_code"] == "incompatible_cli"
    assert not (repository / ".repo-agent-eval" / "runs" / "run-42").exists()


def test_subprocess_invalid_config_stops_before_lifecycle_writes(
    repository: Path, tmp_path: Path
) -> None:
    fake_root = _install_fake_module(tmp_path)
    call_log = tmp_path / "calls.jsonl"
    (repository / "repo-wiki.yaml").write_text("project: [invalid", encoding="utf-8")

    result = _run_runner(
        repository,
        fake_root,
        call_log,
        "generate",
        "--run-id",
        "run-42",
    )

    assert result.returncode == 1
    assert _last_event(result)["reason_code"] == "invalid_config"
    assert _recorded_calls(call_log) == []
    assert not (repository / ".repo-agent-eval" / "runs" / "run-42").exists()


@pytest.mark.parametrize(
    ("extra", "reason"),
    [
        ({"FAKE_MANIFEST_PATH_RUN": "other"}, "manifest_identity_mismatch"),
        ({"FAKE_VERIFY_GRADE": "WARN"}, "verification_failed"),
        ({"FAKE_VERIFY_ROOT": "/tmp/wrong-root"}, "verification_failed"),
        ({"FAKE_REPORT_PATH": "/tmp/wrong-report.json"}, "verification_failed"),
    ],
)
def test_subprocess_identity_failures_are_rejected(
    repository: Path, tmp_path: Path, extra: dict[str, str], reason: str
) -> None:
    fake_root = _install_fake_module(tmp_path)
    call_log = tmp_path / "calls.jsonl"

    result = _run_runner(
        repository,
        fake_root,
        call_log,
        "generate",
        "--run-id",
        "run-42",
        **extra,
    )

    assert result.returncode == 1
    assert _last_event(result)["reason_code"] == reason


def test_subprocess_neutral_secret_output_is_redacted(repository: Path, tmp_path: Path) -> None:
    fake_root = _install_fake_module(tmp_path)
    call_log = tmp_path / "calls.jsonl"
    secret = "tok_live_1234567890abcdef1234567890abcdef"

    result = _run_runner(
        repository,
        fake_root,
        call_log,
        "sync",
        FAKE_GENERIC_PAYLOAD=json.dumps({"message": secret, "status": "OK"}),
    )

    assert result.returncode == 0
    assert secret not in result.stdout
    assert "***REDACTED***" in result.stdout


def test_subprocess_publish_rejects_not_ready_and_suppresses_final_publish(
    workflow: ModuleType, repository: Path, tmp_path: Path
) -> None:
    fake_root = _install_fake_module(tmp_path)
    call_log = tmp_path / "calls.jsonl"
    ctx = _context(workflow, repository, "publish")
    ctx.run_dir.mkdir(parents=True)
    _write_g005(ctx, workflow)

    result = _run_runner(
        repository,
        fake_root,
        call_log,
        "publish",
        "--run-id",
        "run-42",
        "--confirm-run-id",
        "run-42",
        FAKE_INSPECT_STATUS="NOT_READY",
    )

    assert result.returncode == 1
    assert _last_event(result)["reason_code"] == "inspect_not_ready"
    publish_calls = [
        call["argv"]
        for call in _recorded_calls(call_log, lifecycle_only=True)
        if call["argv"][0] == "release-publish"
    ]
    assert len(publish_calls) == 1
    assert "--inspect-only" in publish_calls[0]


def test_subprocess_publish_requires_g005_before_any_lifecycle_command(
    repository: Path, tmp_path: Path
) -> None:
    fake_root = _install_fake_module(tmp_path)
    call_log = tmp_path / "calls.jsonl"
    run_dir = repository / ".repo-agent-eval" / "runs" / "run-42"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text('{"run_id":"run-42"}', encoding="utf-8")

    result = _run_runner(
        repository,
        fake_root,
        call_log,
        "publish",
        "--run-id",
        "run-42",
    )

    assert result.returncode == 1
    assert _last_event(result)["reason_code"] == "missing_g005_evidence"
    assert _recorded_calls(call_log, lifecycle_only=True) == []


def test_subprocess_publish_rejects_wrong_confirmation_before_final_publish(
    workflow: ModuleType, repository: Path, tmp_path: Path
) -> None:
    fake_root = _install_fake_module(tmp_path)
    call_log = tmp_path / "calls.jsonl"
    ctx = _context(workflow, repository, "publish")
    ctx.run_dir.mkdir(parents=True)
    _write_g005(ctx, workflow)

    result = _run_runner(
        repository,
        fake_root,
        call_log,
        "publish",
        "--run-id",
        "run-42",
        "--confirm-run-id",
        "different-run",
    )

    assert result.returncode == 1
    assert _last_event(result)["reason_code"] == "confirmation_mismatch"
    publish_calls = [
        call["argv"]
        for call in _recorded_calls(call_log, lifecycle_only=True)
        if call["argv"][0] == "release-publish"
    ]
    assert len(publish_calls) == 1
    assert "--inspect-only" in publish_calls[0]


def test_subprocess_publish_success_propagates_one_signer_identity(
    workflow: ModuleType, repository: Path, tmp_path: Path
) -> None:
    fake_root = _install_fake_module(tmp_path)
    call_log = tmp_path / "calls.jsonl"
    signers = tmp_path / "allowed-signers"
    signers.write_text("reviewer stable\n", encoding="utf-8")
    ctx = _context(workflow, repository, "publish")
    ctx.run_dir.mkdir(parents=True)
    _write_g005(ctx, workflow)

    result = _run_runner(
        repository,
        fake_root,
        call_log,
        "publish",
        "--run-id",
        "run-42",
        "--confirm-run-id",
        "run-42",
        "--review-allowed-signers",
        str(signers),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert _last_event(result)["status"] == "PASS"
    publish_calls = [
        call["argv"]
        for call in _recorded_calls(call_log, lifecycle_only=True)
        if call["argv"][0] == "release-publish"
    ]
    assert len(publish_calls) == 3
    assert all(call[-2:] == ["--review-allowed-signers", str(signers)] for call in publish_calls)
    assert "--inspect-only" not in publish_calls[-1]


@pytest.mark.parametrize("run_id", ["../escape", "/absolute", "with/slash"])
def test_subprocess_unsafe_run_ids_stop_before_cli_probe_or_write(
    repository: Path, tmp_path: Path, run_id: str
) -> None:
    fake_root = _install_fake_module(tmp_path)
    call_log = tmp_path / "calls.jsonl"

    result = _run_runner(
        repository,
        fake_root,
        call_log,
        "generate",
        "--run-id",
        run_id,
    )

    assert result.returncode == 1
    assert _last_event(result)["reason_code"] == "unsafe_run_id"
    assert _recorded_calls(call_log, lifecycle_only=True) == []


@pytest.mark.parametrize("target_kind", ["parent", "run"])
def test_subprocess_existing_symlink_paths_stop_before_lifecycle_commands(
    repository: Path, tmp_path: Path, target_kind: str
) -> None:
    fake_root = _install_fake_module(tmp_path)
    call_log = tmp_path / "calls.jsonl"
    outside = tmp_path / "outside"
    outside.mkdir()
    runs = repository / ".repo-agent-eval" / "runs"
    runs.parent.mkdir(parents=True)
    try:
        if target_kind == "parent":
            runs.symlink_to(outside, target_is_directory=True)
        else:
            runs.mkdir()
            (runs / "run-42").symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks unavailable: {exc}")

    result = _run_runner(
        repository,
        fake_root,
        call_log,
        "generate",
        "--run-id",
        "run-42",
    )

    assert result.returncode == 1
    assert _last_event(result)["reason_code"] == "symlink_path"
    assert _recorded_calls(call_log, lifecycle_only=True) == []


def test_subprocess_concurrent_run_symlink_swap_is_detected_before_verify(
    repository: Path, tmp_path: Path
) -> None:
    fake_root = _install_fake_module(tmp_path)
    call_log = tmp_path / "calls.jsonl"
    signal = tmp_path / "signal"
    proceed = tmp_path / "proceed"
    outside = tmp_path / "outside"
    outside.mkdir()
    env = _runner_env(
        fake_root,
        call_log,
        FAKE_WAIT_STAGE="generate",
        FAKE_WAIT_SIGNAL=str(signal),
        FAKE_WAIT_PROCEED=str(proceed),
    )
    process = subprocess.Popen(
        [
            sys.executable,
            str(WORKFLOW_PATH),
            "generate",
            "--run-id",
            "run-42",
            "--cwd",
            str(repository),
        ],
        cwd=repository,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    deadline = time.monotonic() + 10
    while not signal.exists() and process.poll() is None:
        assert time.monotonic() < deadline
        time.sleep(0.01)
    run_dir = repository / ".repo-agent-eval" / "runs" / "run-42"
    run_dir.rmdir()
    try:
        run_dir.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        process.kill()
        process.communicate()
        pytest.skip(f"directory symlinks unavailable: {exc}")
    proceed.touch()
    stdout, stderr = process.communicate(timeout=15)
    result = subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)

    assert result.returncode == 1, stdout + stderr
    assert _last_event(result)["reason_code"] == "symlink_path"
    assert [call["argv"][0] for call in _recorded_calls(call_log, lifecycle_only=True)] == [
        "config",
        "generate",
    ]


def test_subprocess_signer_mutation_during_first_inspect_suppresses_final_publish(
    workflow: ModuleType, repository: Path, tmp_path: Path
) -> None:
    fake_root = _install_fake_module(tmp_path)
    call_log = tmp_path / "calls.jsonl"
    signal = tmp_path / "signal"
    proceed = tmp_path / "proceed"
    signers = tmp_path / "allowed-signers"
    signers.write_text("reviewer initial\n", encoding="utf-8")
    ctx = _context(workflow, repository, "publish")
    ctx.run_dir.mkdir(parents=True)
    _write_g005(ctx, workflow)
    env = _runner_env(
        fake_root,
        call_log,
        FAKE_WAIT_STAGE="release-publish",
        FAKE_WAIT_SIGNAL=str(signal),
        FAKE_WAIT_PROCEED=str(proceed),
    )
    process = subprocess.Popen(
        [
            sys.executable,
            str(WORKFLOW_PATH),
            "publish",
            "--run-id",
            "run-42",
            "--confirm-run-id",
            "run-42",
            "--review-allowed-signers",
            str(signers),
            "--cwd",
            str(repository),
        ],
        cwd=repository,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    deadline = time.monotonic() + 10
    while not signal.exists() and process.poll() is None:
        assert time.monotonic() < deadline
        time.sleep(0.01)
    signers.write_text("reviewer changed\n", encoding="utf-8")
    proceed.touch()
    stdout, stderr = process.communicate(timeout=15)
    result = subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)

    assert result.returncode == 1, stdout + stderr
    assert _last_event(result)["reason_code"] == "allowed_signers_changed"
    publish_calls = [
        call["argv"]
        for call in _recorded_calls(call_log, lifecycle_only=True)
        if call["argv"][0] == "release-publish"
    ]
    assert len(publish_calls) == 1
    assert "--inspect-only" in publish_calls[0]
    assert publish_calls[0][-2:] == ["--review-allowed-signers", str(signers)]


@pytest.mark.parametrize(
    "extra",
    [
        {"FAKE_PUBLISH_STATUS": "READY_CANDIDATE"},
        {"FAKE_PUBLISH_RUN": "different-run"},
    ],
)
def test_subprocess_final_publish_result_must_match_selected_run(
    workflow: ModuleType, repository: Path, tmp_path: Path, extra: dict[str, str]
) -> None:
    fake_root = _install_fake_module(tmp_path)
    call_log = tmp_path / "calls.jsonl"
    ctx = _context(workflow, repository, "publish")
    ctx.run_dir.mkdir(parents=True)
    _write_g005(ctx, workflow)

    result = _run_runner(
        repository,
        fake_root,
        call_log,
        "publish",
        "--run-id",
        "run-42",
        "--confirm-run-id",
        "run-42",
        **extra,
    )

    assert result.returncode == 1
    assert _last_event(result)["reason_code"] == "publish_identity_mismatch"
    publish_calls = [
        call["argv"]
        for call in _recorded_calls(call_log, lifecycle_only=True)
        if call["argv"][0] == "release-publish"
    ]
    assert len(publish_calls) == 3
    assert "--inspect-only" not in publish_calls[-1]
