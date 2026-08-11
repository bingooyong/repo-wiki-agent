#!/usr/bin/env python3
"""Deterministic, secret-safe workflow wrapper for the Repo Wiki CLI."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

try:
    from importlib.metadata import version
except ImportError:  # pragma: no cover - Python 3.8 compatibility guard
    from importlib_metadata import version  # type: ignore[no-redef]

RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SECRET_RE = re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*([=:])\s*[^\s,]+")


class WorkflowError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class WorkflowContext:
    root: Path
    config: Path | None
    executable: str
    operation: str
    output_parent: Path
    run_id: str | None = None
    run_dir: Path | None = None
    allowed_signers: Path | None = None


def redact(value: Any) -> Any:
    if isinstance(value, str):
        return SECRET_RE.sub(lambda m: f"{m.group(1)}=***REDACTED***", value)
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items() if "api_key" not in key.lower()}
    return value


def emit(ctx: WorkflowContext | None, stage: str, status: str, **extra: Any) -> None:
    data: dict[str, Any] = {"operation": ctx.operation if ctx else "unknown", "stage": stage, "status": status}
    if ctx:
        data.update({"repository_root": str(ctx.root), "output_root": str(ctx.output_parent)})
        if ctx.run_id:
            data["run_id"] = ctx.run_id
    data.update(extra)
    print(json.dumps(redact(data), ensure_ascii=False, sort_keys=True))


def resolve_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    raise WorkflowError("repository_not_found", "No Git repository root was found")


def select_config(root: Path, explicit: str | None) -> Path | None:
    if explicit:
        path = Path(explicit)
        if not path.is_absolute():
            path = root / path
        if not path.is_file():
            raise WorkflowError("config_not_found", "Explicit config file does not exist")
        return path.resolve()
    for name in ("repo-wiki.yaml", ".repo-wiki.yaml"):
        path = root / name
        if path.is_file():
            return path.resolve()
    return None


def yaml_preflight(root: Path, config: Path | None) -> None:
    if config is None:
        return
    try:
        raw = yaml.safe_load(config.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise WorkflowError("invalid_config", "Config YAML cannot be read") from exc
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise WorkflowError("invalid_config", "Config YAML must contain an object")
    project = raw.get("project", {})
    if project is not None and not isinstance(project, dict):
        raise WorkflowError("invalid_config", "project must be an object")
    project_root = (project or {}).get("root", ".")
    if not isinstance(project_root, str):
        raise WorkflowError("invalid_config", "project.root must be a string")
    target = (root / project_root).resolve()
    if target != root:
        raise WorkflowError("foreign_project_root", "Config project.root must resolve to the active repository")


def validate_run_id(run_id: str) -> str:
    if not RUN_ID_RE.fullmatch(run_id) or run_id in {".", ".."} or any(c in run_id for c in "/\\"):
        raise WorkflowError("unsafe_run_id", "Run ID is not allowlisted")
    return run_id


def contained(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise WorkflowError("path_escapes_repository", "Workflow path escapes repository") from exc
    return resolved


def reject_symlinks(path: Path, root: Path) -> None:
    relative = path.relative_to(root)
    current = root
    for component in relative.parts:
        current = current / component
        if current.is_symlink():
            raise WorkflowError("symlink_path", "Workflow output path contains a symlink")


def reserve_run(root: Path, run_id: str) -> tuple[Path, Path]:
    output_parent = root / ".repo-agent-eval" / "runs"
    output_parent.mkdir(parents=True, exist_ok=True)
    reject_symlinks(output_parent, root)
    output_parent = contained(output_parent, root)
    run_dir = output_parent / run_id
    if run_dir.exists() or run_dir.is_symlink():
        raise WorkflowError("run_already_exists", "Run ID already exists")
    try:
        run_dir.mkdir()
    except FileExistsError as exc:
        raise WorkflowError("run_already_exists", "Run ID already exists") from exc
    reject_symlinks(run_dir, root)
    contained(run_dir, root)
    return output_parent, run_dir


def command(ctx: WorkflowContext, *args: str, config: bool = False) -> list[str]:
    argv = [ctx.executable, "-m", "repo_wiki.main", *args]
    if config and ctx.config:
        argv.extend(["--config", str(ctx.config)])
    return argv


def invoke(ctx: WorkflowContext, stage: str, argv: Sequence[str]) -> dict[str, Any]:
    if ctx.run_dir:
        reject_symlinks(ctx.run_dir, ctx.root)
        contained(ctx.run_dir, ctx.root)
    result = subprocess.run(argv, cwd=ctx.root, text=True, capture_output=True, check=False)
    if ctx.run_dir:
        reject_symlinks(ctx.run_dir, ctx.root)
        contained(ctx.run_dir, ctx.root)
    if result.returncode:
        raise WorkflowError(f"{stage}_failed", f"{stage} failed")
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise WorkflowError("malformed_json", f"{stage} did not return JSON") from exc
    if not isinstance(parsed, dict):
        raise WorkflowError("malformed_json", f"{stage} returned a non-object JSON value")
    return parsed


def doctor(ctx: WorkflowContext) -> None:
    try:
        installed_version = version("repo-wiki")
        parts = tuple(int(piece) for piece in installed_version.split(".")[:3])
    except Exception as exc:
        raise WorkflowError("incompatible_cli", "repo-wiki distribution version is unavailable") from exc
    if parts < (0, 1, 0):
        raise WorkflowError("incompatible_cli", "repo-wiki distribution must be version 0.1.0 or newer")
    probe = subprocess.run(command(ctx, "--help"), cwd=ctx.root, text=True, capture_output=True)
    if probe.returncode:
        raise WorkflowError("incompatible_cli", "repo_wiki.main is not executable")
    help_text = probe.stdout + probe.stderr
    required = ("config", "generate", "improve", "verify", "release-publish")
    missing = [item for item in required if item not in help_text]
    if missing:
        raise WorkflowError("incompatible_cli", "Required Repo Wiki commands are missing")
    option_probes = (
        ("generate", "--output", "--run-id", "--config"),
        ("improve", "--output", "--run-id", "--config"),
        ("verify", "--profile", "--output", "--ci", "--config"),
        ("release-publish", "--output", "--run", "--inspect-only", "--review-allowed-signers"),
    )
    for subcommand, *options in option_probes:
        check = subprocess.run(command(ctx, subcommand, "--help"), cwd=ctx.root, text=True, capture_output=True)
        if check.returncode or any(option not in check.stdout + check.stderr for option in options):
            raise WorkflowError("incompatible_cli", f"{subcommand} lacks required workflow options")
    config_result = invoke(ctx, "config", command(ctx, "config", "--ci", config=True))
    emit(ctx, "doctor", "PASS", cli="repo_wiki.main", version=installed_version, config_status=config_result.get("status", "ok"))


def verify(ctx: WorkflowContext) -> None:
    assert ctx.run_dir and ctx.run_id
    result = invoke(ctx, "verify", command(ctx, "verify", "--profile", "qoder-like", "--output", str(ctx.run_dir), "--ci", config=True))
    manifest = ctx.run_dir / "manifest.json"
    report = ctx.run_dir / "reports" / "strict-verify-output.json"
    expected_root = str(ctx.run_dir)
    if result.get("grade") != "PASS" or result.get("verify_root") not in {None, expected_root} or not manifest.is_file() or not report.is_file():
        raise WorkflowError("verification_failed", "Exact-run verification did not pass")
    manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
    if manifest_data.get("run_id") != ctx.run_id:
        raise WorkflowError("manifest_identity_mismatch", "Manifest run ID does not match selected run")
    emit(ctx, "verify", "PASS", report_path=str(report), verify_root=str(ctx.run_dir))


def generate_or_improve(ctx: WorkflowContext) -> None:
    assert ctx.run_id
    doctor(ctx)
    operation = ctx.operation
    result = invoke(ctx, operation, command(ctx, operation, "--profile", "qoder-like", "--output", ".repo-agent-eval/runs", "--run-id", ctx.run_id, config=True))
    manifest_path = Path(str(result.get("manifest_path", ""))).resolve()
    if manifest_path.parent != ctx.run_dir:
        raise WorkflowError("manifest_identity_mismatch", "Generation returned a different run")
    verify(ctx)
    emit(ctx, operation, "PASS", candidate_root=str(ctx.run_dir))


def require_g005(ctx: WorkflowContext) -> None:
    assert ctx.run_dir
    for name in ("strict-verify-output.json", "g005-quality-gates.json"):
        if not (ctx.run_dir / "reports" / name).is_file():
            raise WorkflowError("missing_g005_evidence", "Required independent G005 evidence is missing")


def publish(ctx: WorkflowContext, confirm: str | None) -> None:
    assert ctx.run_id and ctx.run_dir
    require_g005(ctx)
    verify(ctx)
    inspect = command(ctx, "release-publish", "--output", ".repo-agent-eval", "--run", ctx.run_id, "--inspect-only")
    if ctx.allowed_signers:
        inspect.extend(["--review-allowed-signers", str(ctx.allowed_signers)])
    result = invoke(ctx, "inspect", inspect)
    if result.get("status") != "READY_CANDIDATE" or result.get("run_id") != ctx.run_id:
        raise WorkflowError("inspect_not_ready", "Exact run is not a READY_CANDIDATE")
    if confirm is None:
        emit(ctx, "inspect", "PASS", confirmation_required=True)
        return
    if confirm != ctx.run_id:
        raise WorkflowError("confirmation_mismatch", "Confirmation run ID does not match selected run")
    final = command(ctx, "release-publish", "--output", ".repo-agent-eval", "--run", ctx.run_id)
    if ctx.allowed_signers:
        final.extend(["--review-allowed-signers", str(ctx.allowed_signers)])
    invoke(ctx, "publish", final)
    emit(ctx, "publish", "PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("doctor", "generate", "improve", "verify", "publish"))
    parser.add_argument("--run-id")
    parser.add_argument("--config")
    parser.add_argument("--confirm-run-id")
    parser.add_argument("--review-allowed-signers")
    parser.add_argument("--cwd", default=os.getcwd())
    args = parser.parse_args()
    ctx: WorkflowContext | None = None
    try:
        root = resolve_root(Path(args.cwd))
        config = select_config(root, args.config)
        yaml_preflight(root, config)
        output_parent = root / ".repo-agent-eval" / "runs"
        run_id = validate_run_id(args.run_id) if args.run_id else None
        if args.operation in {"generate", "improve"} and not run_id:
            raise WorkflowError("run_id_required", "Generation requires --run-id")
        if args.operation in {"verify", "publish"} and not run_id:
            raise WorkflowError("run_id_required", "This operation requires --run-id")
        run_dir = None
        if args.operation in {"generate", "improve"}:
            output_parent, run_dir = reserve_run(root, run_id or "")
        elif run_id:
            run_dir = contained(output_parent / run_id, root)
            if not run_dir.is_dir() or run_dir.is_symlink():
                raise WorkflowError("run_not_found", "Selected run does not exist or is unsafe")
            reject_symlinks(run_dir, root)
        signer = None
        if args.review_allowed_signers:
            signer = Path(args.review_allowed_signers).resolve()
            if not signer.is_file() or signer.is_relative_to(root / ".repo-agent-eval"):
                raise WorkflowError("unsafe_allowed_signers", "Allowed-signers file must exist outside eval output")
        ctx = WorkflowContext(root, config, sys.executable, args.operation, output_parent, run_id, run_dir, signer)
        if args.operation == "doctor":
            doctor(ctx)
        elif args.operation in {"generate", "improve"}:
            generate_or_improve(ctx)
        elif args.operation == "verify":
            verify(ctx)
        else:
            publish(ctx, args.confirm_run_id)
        return 0
    except WorkflowError as exc:
        emit(ctx, "error", "FAIL", reason_code=exc.code, message=str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
