#!/usr/bin/env python3
"""Deterministic, secret-safe workflow wrapper for the Repo Wiki CLI."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import yaml

try:
    from importlib.metadata import distributions
except ImportError:  # pragma: no cover - Python 3.8 compatibility guard
    from importlib_metadata import distributions  # type: ignore[no-redef]


RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
STABLE_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$")
SECRET_RE = re.compile(r"(?i)(api[_-]?key|token|secret|password|authorization)\s*([=:])\s*[^\s,]+")
BEARER_RE = re.compile(r"(?i)\b(authorization\s*[:=]\s*)?bearer\s+[^\s,]+")
HIGH_CONFIDENCE_SECRET_RE = re.compile(
    r"(?ix)"
    r"\b(?:"
    r"sk-[a-z0-9_-]{20,}|"
    r"tok_live_[a-z0-9_-]{20,}|"
    r"(?:gh[pousr]|github_pat)_[a-z0-9_]{20,}|"
    r"xox[baprs]-[a-z0-9-]{20,}|"
    r"AKIA[0-9A-Z]{16}|"
    r"eyJ[a-z0-9_-]{8,}\.eyJ[a-z0-9_-]{8,}\.[a-z0-9_-]{8,}"
    r")\b"
)
SENSITIVE_KEY_RE = re.compile(r"(?i)(api[_-]?key|token|secret|password|authorization)")
REQUIRED_G005_ARTIFACTS = frozenset(
    {
        "strict_verify",
        "qoder_comparison",
        "blind_review_v3",
        "blind_review_attestation",
        "acceptance_fixture_registry",
        "citation_hard_gate_evidence",
        "critical_false_fact_evidence",
        "quality_hard_gate_evidence",
        "conflict_hard_gate_evidence",
    }
)
MAINTENANCE_OPERATIONS = frozenset({"init", "index", "update", "sync"})


class WorkflowError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class FileFingerprint:
    path: Path
    device: int
    inode: int
    size: int
    mtime_ns: int
    sha256: str


@dataclass(frozen=True)
class WorkflowContext:
    """The sole source for lifecycle command arguments and filesystem identity."""

    root: Path
    config: Path | None
    executable: str
    cli_version: str
    capabilities: frozenset[str]
    cli_module_origin: Path
    cli_import_root: Path
    cli_module_fingerprint: FileFingerprint
    operation: str
    output_parent: Path
    run_id: str | None = None
    run_dir: Path | None = None
    allowed_signers: Path | None = None
    config_explicit: bool = False
    config_fingerprint: FileFingerprint | None = None
    allowed_signers_fingerprint: FileFingerprint | None = None


def redact(value: Any) -> Any:
    """Keep structured events useful without allowing secret-shaped content through."""
    if isinstance(value, str):
        without_bearer = BEARER_RE.sub("Authorization=***REDACTED***", value)
        without_named_secret = SECRET_RE.sub(
            lambda match: f"{match.group(1)}=***REDACTED***", without_bearer
        )
        return HIGH_CONFIDENCE_SECRET_RE.sub("***REDACTED***", without_named_secret)
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        return {
            key: "***REDACTED***" if SENSITIVE_KEY_RE.search(str(key)) else redact(item)
            for key, item in value.items()
        }
    return value


def emit(ctx: WorkflowContext | None, stage: str, status: str, **extra: Any) -> None:
    data: dict[str, Any] = {
        "operation": ctx.operation if ctx else "unknown",
        "stage": stage,
        "status": status,
    }
    if ctx:
        data.update({"repository_root": str(ctx.root), "output_root": str(ctx.output_parent)})
        if ctx.run_id:
            data["run_id"] = ctx.run_id
    data.update(extra)
    print(json.dumps(redact(data), ensure_ascii=False, sort_keys=True))


def resolve_root(start: Path) -> Path:
    current = start.expanduser().resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    raise WorkflowError("repository_not_found", "No Git repository root was found")


def contained(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise WorkflowError("path_escapes_repository", "Workflow path escapes repository") from exc
    return resolved


def reject_symlinks(path: Path, root: Path) -> None:
    """Reject a link in every existing component, including an output parent race."""
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise WorkflowError("path_escapes_repository", "Workflow path escapes repository") from exc
    current = root
    if current.is_symlink():
        raise WorkflowError("symlink_path", "Repository root must not be a symlink")
    for component in relative.parts:
        current = current / component
        if current.is_symlink():
            raise WorkflowError("symlink_path", "Workflow output path contains a symlink")


def reject_descendant_symlinks(path: Path) -> None:
    if not path.exists():
        return
    for descendant in path.rglob("*"):
        if descendant.is_symlink():
            raise WorkflowError("symlink_path", "Selected run contains a symlink")


def fingerprint_file(path: Path, code: str) -> FileFingerprint:
    try:
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or path.is_symlink():
            raise WorkflowError(code, "Context file must be a regular nonsymlink file")
        payload = path.read_bytes()
        after = path.lstat()
    except OSError as exc:
        raise WorkflowError(code, "Context file cannot be read") from exc
    identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    if identity != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise WorkflowError(code, "Context file changed while it was read")
    return FileFingerprint(
        path=path,
        device=after.st_dev,
        inode=after.st_ino,
        size=after.st_size,
        mtime_ns=after.st_mtime_ns,
        sha256=hashlib.sha256(payload).hexdigest(),
    )


def assert_file_fingerprint(fingerprint: FileFingerprint, code: str) -> None:
    if fingerprint_file(fingerprint.path, code) != fingerprint:
        raise WorkflowError(code, "Context file identity or content changed during workflow")


def select_config(root: Path, explicit: str | None) -> Path | None:
    if explicit:
        candidate = Path(explicit).expanduser()
        path = candidate if candidate.is_absolute() else root / candidate
        if not path.is_file():
            raise WorkflowError("config_not_found", "Explicit config file does not exist")
        return path.resolve()
    for name in ("repo-wiki.yaml", ".repo-wiki.yaml"):
        path = root / name
        if path.is_file():
            return path.resolve()
    return None


def yaml_preflight(root: Path, config: Path | None) -> None:
    """Mirror CLI config selection without importing its config/dotenv machinery."""
    raw: Any = {}
    if config is not None:
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
        raise WorkflowError(
            "foreign_project_root", "Config project.root must resolve to the active repository"
        )


def preflight_config(root: Path, config: Path | None) -> FileFingerprint | None:
    """Validate one YAML file while proving it did not change during the read."""
    if config is None:
        yaml_preflight(root, None)
        return None
    before = fingerprint_file(config, "config_changed")
    yaml_preflight(root, config)
    after = fingerprint_file(config, "config_changed")
    if after != before:
        raise WorkflowError("config_changed", "Selected configuration changed during preflight")
    return after


def validate_run_id(run_id: str) -> str:
    if (
        not RUN_ID_RE.fullmatch(run_id)
        or run_id in {".", ".."}
        or any(char in run_id for char in "/\\")
        or any(ord(char) < 32 or ord(char) == 127 for char in run_id)
    ):
        raise WorkflowError("unsafe_run_id", "Run ID is not allowlisted")
    return run_id


def validate_output_parent(root: Path) -> Path:
    raw = root / ".repo-agent-eval" / "runs"
    reject_symlinks(raw, root)
    return contained(raw, root)


def reserve_run(root: Path, run_id: str) -> tuple[Path, Path]:
    output_parent = validate_output_parent(root)
    output_parent.mkdir(parents=True, exist_ok=True)
    # A concurrent replacement of a previously absent parent must be detected.
    output_parent = validate_output_parent(root)
    run_dir = output_parent / run_id
    reject_symlinks(run_dir, root)
    if run_dir.exists() or run_dir.is_symlink():
        raise WorkflowError("run_already_exists", "Run ID already exists")
    try:
        run_dir.mkdir()
    except FileExistsError as exc:
        raise WorkflowError("run_already_exists", "Run ID already exists") from exc
    reject_symlinks(run_dir, root)
    contained(run_dir, root)
    return output_parent, run_dir


def validate_existing_run(root: Path, run_id: str) -> tuple[Path, Path]:
    output_parent = validate_output_parent(root)
    run_dir = output_parent / run_id
    reject_symlinks(run_dir, root)
    run_dir = contained(run_dir, root)
    if not run_dir.is_dir() or run_dir.is_symlink():
        raise WorkflowError("run_not_found", "Selected run does not exist or is unsafe")
    reject_descendant_symlinks(run_dir)
    return output_parent, run_dir


def command(ctx: WorkflowContext, *args: str, config: bool = False) -> list[str]:
    argv = [ctx.executable, "-m", "repo_wiki.main", *args]
    if config and ctx.config:
        argv.extend(["--config", str(ctx.config)])
    return argv


def cli_environment(import_root: Path) -> dict[str, str]:
    """Bind ``-m repo_wiki.main`` to the selected distribution, not child cwd."""
    env = os.environ.copy()
    env["PYTHONSAFEPATH"] = "1"
    env["PYTHONPATH"] = str(import_root)
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONSTARTUP", None)
    return env


def _assert_context_paths(ctx: WorkflowContext) -> None:
    if ctx.run_dir is not None:
        validate_output_parent(ctx.root)
        reject_symlinks(ctx.run_dir, ctx.root)
        if contained(ctx.run_dir, ctx.root) != ctx.run_dir:
            raise WorkflowError("context_mutated", "Selected run path changed during workflow")
        reject_descendant_symlinks(ctx.run_dir)


def invoke(ctx: WorkflowContext, stage: str, argv: Sequence[str]) -> dict[str, Any]:
    """Run an immutable argv from the canonical repository, with race checks."""
    _assert_context_paths(ctx)
    try:
        result = subprocess.run(
            list(argv),
            cwd=ctx.root,
            env=cli_environment(ctx.cli_import_root),
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise WorkflowError("cli_unavailable", "repo_wiki.main could not be started") from exc
    _assert_context_paths(ctx)
    if result.returncode:
        raise WorkflowError(f"{stage}_failed", f"{stage} failed")
    return parse_cli_json(result.stdout, stage)


def parse_cli_json(stdout: str, stage: str) -> dict[str, Any]:
    """Parse the final JSON object after optional Rich informational lines."""
    decoder = json.JSONDecoder()
    for offset, character in enumerate(stdout):
        if character != "{":
            continue
        try:
            parsed, end = decoder.raw_decode(stdout, offset)
        except json.JSONDecodeError:
            continue
        if stdout[end:].strip() == "" and isinstance(parsed, dict):
            return parsed
    raise WorkflowError("malformed_json", f"{stage} did not return JSON")


def _version_at_least_010(raw: str) -> bool:
    match = STABLE_VERSION_RE.fullmatch(raw)
    return bool(match and tuple(int(part) for part in match.groups()) >= (0, 1, 0))


def _candidate_main_origin(candidate: Any) -> Path | None:
    main_files = [
        file
        for file in (candidate.files or ())
        if str(file).replace("\\", "/") == "repo_wiki/main.py"
    ]
    if len(main_files) == 1:
        return Path(candidate.locate_file(main_files[0])).resolve()
    raw_direct_url = candidate.read_text("direct_url.json")
    if not raw_direct_url:
        return None
    try:
        direct_url = json.loads(raw_direct_url)
        url = direct_url.get("url")
        if not isinstance(url, str) or urlparse(url).scheme != "file":
            return None
        source_root = Path(unquote(urlparse(url).path)).resolve()
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return None
    origin = source_root / "repo_wiki" / "main.py"
    return origin if origin.is_file() else None


def resolve_cli_distribution(root: Path | None = None) -> tuple[str, Path, Path, FileFingerprint]:
    original_sys_path = sys.path[:]
    if root is not None:
        canonical_root = root.resolve()
        safe_path: list[str] = []
        for entry in sys.path:
            if not entry:
                continue
            try:
                if Path(entry).resolve().is_relative_to(canonical_root):
                    continue
            except OSError:
                continue
            safe_path.append(entry)
        sys.path[:] = safe_path
    try:
        candidates = []
        for candidate in distributions():
            name = (candidate.metadata.get("Name") or "").lower().replace("_", "-")
            if name != "repo-wiki" or not _version_at_least_010(candidate.version):
                continue
            origin = _candidate_main_origin(candidate)
            if origin is None:
                continue
            if root is not None and origin.is_relative_to(root.resolve()):
                # A target-local egg-info/package is not an installed CLI identity.
                # Editable installs are still accepted when their direct_url points to
                # the runner's source tree and the candidate was discovered outside cwd.
                raw_direct_url = candidate.read_text("direct_url.json")
                if not raw_direct_url:
                    continue
            candidates.append((candidate, origin))
        try:
            selected_spec = importlib.util.find_spec("repo_wiki.main")
        except (ImportError, ModuleNotFoundError):
            selected_spec = None
        selected_origin = (
            Path(selected_spec.origin).resolve()
            if selected_spec is not None and selected_spec.origin
            else None
        )
    finally:
        sys.path[:] = original_sys_path
    if not candidates:
        raise WorkflowError("incompatible_cli", "repo-wiki distribution is unavailable")
    if selected_origin is not None:
        candidates = [
            (candidate, origin) for candidate, origin in candidates if origin == selected_origin
        ]
    unique_candidates: dict[tuple[str, Path], Any] = {}
    for candidate, origin in candidates:
        unique_candidates.setdefault((candidate.version, origin), candidate)
    if len(unique_candidates) != 1:
        raise WorkflowError("incompatible_cli", "repo-wiki distribution identity is ambiguous")
    (installed_version, module_origin), installed = next(iter(unique_candidates.items()))
    fingerprint = fingerprint_file(module_origin, "incompatible_cli")
    import_root = module_origin.parent.parent
    if not (import_root / "repo_wiki").is_dir():
        raise WorkflowError("incompatible_cli", "repo-wiki distribution import root is invalid")
    return installed_version, module_origin, import_root, fingerprint


def probe_module_origin(
    root: Path, executable: str, import_root: Path, expected_origin: Path
) -> None:
    script = (
        "import importlib.util,json,pathlib;"
        "s=importlib.util.find_spec('repo_wiki.main');"
        "print(json.dumps({'module_origin':str(pathlib.Path(s.origin).resolve()) "
        "if s and s.origin else None}))"
    )
    try:
        result = subprocess.run(
            [executable, "-c", script],
            cwd=root,
            env=cli_environment(import_root),
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise WorkflowError("incompatible_cli", "repo_wiki.main could not be located") from exc
    try:
        payload = parse_cli_json(result.stdout, "module-origin")
    except WorkflowError as exc:
        raise WorkflowError(
            "incompatible_cli", "repo_wiki.main module origin could not be verified"
        ) from exc
    if result.returncode or payload.get("module_origin") != str(expected_origin):
        raise WorkflowError(
            "incompatible_cli", "repo_wiki.main does not match the installed distribution"
        )


def probe_cli(
    root: Path,
    executable: str,
    module_origin: Path | None = None,
    import_root: Path | None = None,
) -> tuple[str, frozenset[str]]:
    installed_version, selected_origin, selected_root, _ = resolve_cli_distribution(root)
    if module_origin is not None and selected_origin != module_origin:
        raise WorkflowError("incompatible_cli", "repo_wiki.main distribution origin changed")
    if import_root is not None and selected_root != import_root:
        raise WorkflowError("incompatible_cli", "repo_wiki.main distribution root changed")
    probe_module_origin(root, executable, selected_root, selected_origin)

    base = [executable, "-m", "repo_wiki.main"]
    checks = {
        "root": ("--help",),
        "config": ("config", "--help"),
        "init": ("init", "--help"),
        "index": ("index", "--help"),
        "update": ("update", "--help"),
        "sync": ("sync", "--help"),
        "generate": ("generate", "--help"),
        "improve": ("improve", "--help"),
        "verify": ("verify", "--help"),
        "release-publish": ("release-publish", "--help"),
    }
    expected = {
        "root": (
            "config",
            "init",
            "index",
            "update",
            "sync",
            "generate",
            "improve",
            "verify",
            "release-publish",
        ),
        "config": ("--ci",),
        "init": ("--config",),
        "index": ("--config",),
        "update": ("--config",),
        "sync": ("--config",),
        "generate": ("--output", "--run-id", "--config"),
        "improve": ("--output", "--run-id", "--config"),
        "verify": ("--profile", "--output", "--ci", "--config"),
        "release-publish": ("--output", "--run", "--inspect-only", "--review-allowed-signers"),
    }
    capabilities: set[str] = set()
    for name, suffix in checks.items():
        try:
            result = subprocess.run(
                base + list(suffix),
                cwd=root,
                env=cli_environment(selected_root),
                text=True,
                capture_output=True,
                check=False,
            )
        except OSError as exc:
            raise WorkflowError("incompatible_cli", "repo_wiki.main could not be started") from exc
        text = result.stdout + result.stderr
        if result.returncode or any(token not in text for token in expected[name]):
            raise WorkflowError(
                "incompatible_cli", f"repo_wiki.main lacks required {name} capability"
            )
        capabilities.add(name)
    return installed_version, frozenset(capabilities)


def doctor(ctx: WorkflowContext) -> None:
    result = invoke(ctx, "config", command(ctx, "config", "--ci", config=True))
    emit(
        ctx,
        "doctor",
        "PASS",
        cli="repo_wiki.main",
        version=ctx.cli_version,
        config_status=result.get("status", "ok"),
    )


def _read_json(path: Path, code: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(code, "Required JSON artifact is unreadable") from exc
    if not isinstance(data, dict):
        raise WorkflowError(code, "Required JSON artifact must be an object")
    return data


def verify(ctx: WorkflowContext) -> None:
    assert ctx.run_dir and ctx.run_id
    recheck_context(ctx)
    result = invoke(
        ctx,
        "verify",
        command(
            ctx,
            "verify",
            "--profile",
            "qoder-like",
            "--output",
            str(ctx.run_dir),
            "--ci",
            config=True,
        ),
    )
    manifest = ctx.run_dir / "manifest.json"
    report = ctx.run_dir / "reports" / "strict-verify-output.json"
    expected_root = str(ctx.run_dir)
    if (
        result.get("grade") != "PASS"
        or result.get("verify_root") != expected_root
        or result.get("canonical_report_path") != str(report)
        or not manifest.is_file()
        or not report.is_file()
    ):
        raise WorkflowError("verification_failed", "Exact-run verification did not pass")
    manifest_data = _read_json(manifest, "manifest_identity_mismatch")
    if manifest_data.get("run_id") != ctx.run_id:
        raise WorkflowError(
            "manifest_identity_mismatch", "Manifest run ID does not match selected run"
        )
    _assert_context_paths(ctx)
    emit(ctx, "verify", "PASS", report_path=str(report), verify_root=expected_root)


def generate_or_improve(ctx: WorkflowContext) -> None:
    assert ctx.run_id and ctx.run_dir
    doctor(ctx)
    result = invoke(
        ctx,
        ctx.operation,
        command(
            ctx,
            ctx.operation,
            "--profile",
            "qoder-like",
            "--output",
            ".repo-agent-eval/runs",
            "--run-id",
            ctx.run_id,
            config=True,
        ),
    )
    manifest_raw = result.get("manifest_path")
    if not isinstance(manifest_raw, str) or not manifest_raw:
        raise WorkflowError(
            "manifest_identity_mismatch", "Generation did not return a manifest path"
        )
    manifest_path = Path(manifest_raw)
    manifest_path = manifest_path if manifest_path.is_absolute() else ctx.root / manifest_path
    if manifest_path.resolve() != ctx.run_dir / "manifest.json":
        raise WorkflowError("manifest_identity_mismatch", "Generation returned a different run")
    verify(ctx)
    emit(
        ctx,
        ctx.operation,
        "PASS",
        candidate_root=str(ctx.run_dir),
        run_parent=str(ctx.output_parent),
    )


def maintain(ctx: WorkflowContext) -> None:
    if ctx.operation not in MAINTENANCE_OPERATIONS:
        raise WorkflowError("unsupported_operation", "Unsupported maintenance operation")
    doctor(ctx)
    result = invoke(ctx, ctx.operation, command(ctx, ctx.operation, config=True))
    emit(ctx, ctx.operation, "PASS", result=result)


def require_g005(ctx: WorkflowContext) -> None:
    """Require a complete independent evidence index; publisher revalidates its hashes."""
    assert ctx.run_dir and ctx.run_id
    manifest = _read_json(ctx.run_dir / "manifest.json", "missing_g005_evidence")
    report_paths = manifest.get("report_paths")
    if (
        not isinstance(report_paths, dict)
        or report_paths.get("strict_verify") != "reports/strict-verify-output.json"
        or report_paths.get("g005_quality_gates") != "reports/g005-quality-gates.json"
    ):
        raise WorkflowError(
            "missing_g005_evidence", "Manifest does not reference canonical G005 reports"
        )
    strict = ctx.run_dir / "reports" / "strict-verify-output.json"
    bundle_path = ctx.run_dir / "reports" / "g005-quality-gates.json"
    if not strict.is_file() or not bundle_path.is_file():
        raise WorkflowError(
            "missing_g005_evidence", "Required independent G005 evidence is missing"
        )
    bundle = _read_json(bundle_path, "missing_g005_evidence")
    if bundle.get("run_id") != ctx.run_id or bundle.get("status") != "PASS":
        raise WorkflowError(
            "missing_g005_evidence", "G005 bundle is not a passing selected-run bundle"
        )
    refs = bundle.get("artifact_references")
    if not isinstance(refs, dict) or not REQUIRED_G005_ARTIFACTS.issubset(refs):
        raise WorkflowError(
            "missing_g005_evidence", "G005 bundle lacks required independent artifacts"
        )
    for name in REQUIRED_G005_ARTIFACTS:
        ref = refs[name]
        if not isinstance(ref, dict) or not isinstance(ref.get("path"), str):
            raise WorkflowError(
                "missing_g005_evidence", "G005 bundle contains an invalid artifact reference"
            )
        candidate = contained(ctx.run_dir / ref["path"], ctx.run_dir)
        if not candidate.is_file():
            raise WorkflowError(
                "missing_g005_evidence", "G005 bundle references a missing artifact"
            )


def recheck_context(ctx: WorkflowContext) -> None:
    """Detect post-inspection drift without rebuilding the immutable context."""
    selected = select_config(
        ctx.root, str(ctx.config) if ctx.config_explicit and ctx.config else None
    )
    if selected != ctx.config:
        raise WorkflowError("context_mutated", "Configuration selection changed during workflow")
    if ctx.config is not None:
        if ctx.config_fingerprint is None:
            raise WorkflowError("context_mutated", "Configuration fingerprint is missing")
        assert_file_fingerprint(ctx.config_fingerprint, "config_changed")
    elif ctx.config_fingerprint is not None:
        raise WorkflowError("context_mutated", "Unexpected configuration fingerprint")
    preflight_fingerprint = preflight_config(ctx.root, ctx.config)
    if preflight_fingerprint != ctx.config_fingerprint:
        raise WorkflowError("config_changed", "Selected configuration changed during workflow")
    if ctx.allowed_signers is not None:
        if ctx.allowed_signers_fingerprint is None:
            raise WorkflowError("context_mutated", "Allowed-signers fingerprint is missing")
        assert_file_fingerprint(ctx.allowed_signers_fingerprint, "allowed_signers_changed")
    elif ctx.allowed_signers_fingerprint is not None:
        raise WorkflowError("context_mutated", "Unexpected allowed-signers fingerprint")
    cli_version, capabilities = probe_cli(ctx.root, ctx.executable)
    if cli_version != ctx.cli_version or capabilities != ctx.capabilities:
        raise WorkflowError("context_mutated", "CLI capability identity changed during workflow")
    assert_file_fingerprint(ctx.cli_module_fingerprint, "context_mutated")
    _, module_origin, import_root, module_fingerprint = resolve_cli_distribution(ctx.root)
    if (
        module_origin != ctx.cli_module_origin
        or import_root != ctx.cli_import_root
        or module_fingerprint != ctx.cli_module_fingerprint
    ):
        raise WorkflowError("context_mutated", "CLI module identity changed during workflow")
    _assert_context_paths(ctx)


def _publish_argv(ctx: WorkflowContext, *, inspect_only: bool) -> list[str]:
    assert ctx.run_id
    argv = command(ctx, "release-publish", "--output", ".repo-agent-eval", "--run", ctx.run_id)
    if inspect_only:
        argv.append("--inspect-only")
    if ctx.allowed_signers:
        argv.extend(["--review-allowed-signers", str(ctx.allowed_signers)])
    return argv


def publish(ctx: WorkflowContext, confirm: str | None) -> None:
    assert ctx.run_id and ctx.run_dir
    recheck_context(ctx)
    require_g005(ctx)
    verify(ctx)
    recheck_context(ctx)
    result = invoke(ctx, "inspect", _publish_argv(ctx, inspect_only=True))
    if result.get("status") != "READY_CANDIDATE" or result.get("run_id") != ctx.run_id:
        raise WorkflowError("inspect_not_ready", "Exact run is not a READY_CANDIDATE")
    if confirm is None:
        emit(ctx, "inspect", "PASS", confirmation_required=True)
        return
    if confirm != ctx.run_id:
        raise WorkflowError(
            "confirmation_mismatch", "Confirmation run ID does not match selected run"
        )
    # Re-run every non-writing prerequisite just before the stable replacement.
    recheck_context(ctx)
    require_g005(ctx)
    verify(ctx)
    recheck_context(ctx)
    result = invoke(ctx, "inspect", _publish_argv(ctx, inspect_only=True))
    if result.get("status") != "READY_CANDIDATE" or result.get("run_id") != ctx.run_id:
        raise WorkflowError("inspect_not_ready", "Exact run is not a READY_CANDIDATE")
    recheck_context(ctx)
    result = invoke(ctx, "publish", _publish_argv(ctx, inspect_only=False))
    if result.get("status") != "PUBLISHED" or result.get("run_id") != ctx.run_id:
        raise WorkflowError(
            "publish_identity_mismatch", "Final publish result does not match selected run"
        )
    emit(ctx, "publish", "PASS")


def build_context(args: argparse.Namespace) -> WorkflowContext:
    root = resolve_root(Path(args.cwd))
    config = select_config(root, args.config)
    config_explicit = args.config is not None
    config_fingerprint = preflight_config(root, config)
    cli_version, module_origin, import_root, module_fingerprint = resolve_cli_distribution(root)
    probed_version, capabilities = probe_cli(
        root, sys.executable, module_origin=module_origin, import_root=import_root
    )
    if probed_version != cli_version:
        raise WorkflowError("incompatible_cli", "repo-wiki distribution version changed")
    run_id = validate_run_id(args.run_id) if args.run_id else None
    if args.operation in {"generate", "improve", "verify", "publish"} and not run_id:
        raise WorkflowError("run_id_required", "This operation requires --run-id")
    output_parent = validate_output_parent(root)
    run_dir: Path | None = None
    if args.operation in {"generate", "improve"}:
        output_parent, run_dir = reserve_run(root, run_id or "")
    elif run_id:
        output_parent, run_dir = validate_existing_run(root, run_id)
    signer: Path | None = None
    signer_fingerprint: FileFingerprint | None = None
    if args.review_allowed_signers:
        signer = Path(args.review_allowed_signers).expanduser().resolve()
        if not signer.is_file() or signer.is_relative_to(root / ".repo-agent-eval"):
            raise WorkflowError(
                "unsafe_allowed_signers", "Allowed-signers file must exist outside eval output"
            )
        signer_fingerprint = fingerprint_file(signer, "unsafe_allowed_signers")
    return WorkflowContext(
        root,
        config,
        sys.executable,
        cli_version,
        capabilities,
        module_origin,
        import_root,
        module_fingerprint,
        args.operation,
        output_parent,
        run_id,
        run_dir,
        signer,
        config_explicit,
        config_fingerprint,
        signer_fingerprint,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operation",
        choices=(
            "doctor",
            "init",
            "index",
            "update",
            "sync",
            "generate",
            "improve",
            "verify",
            "publish",
        ),
    )
    parser.add_argument("--run-id")
    parser.add_argument("--config")
    parser.add_argument("--confirm-run-id")
    parser.add_argument("--review-allowed-signers")
    parser.add_argument("--cwd", default=os.getcwd())
    args = parser.parse_args()
    ctx: WorkflowContext | None = None
    try:
        ctx = build_context(args)
        if args.operation == "doctor":
            doctor(ctx)
        elif args.operation in MAINTENANCE_OPERATIONS:
            maintain(ctx)
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
