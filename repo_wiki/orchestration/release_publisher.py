"""Publish READY qoder-like runs to fixed `.repo-agent-eval/repowiki/zh`."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from repo_wiki.orchestration.release_meta_schema import (
    SCHEMA_VERSION_META_RELEASE,
    validate_meta_file,
)


class ReleasePublishError(RuntimeError):
    """Raised when a candidate run cannot be published."""


def _hash_tree(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.exists():
        return digest.hexdigest()
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        digest.update(rel.encode("utf-8"))
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _as_clean_gate_status(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.upper() in {"PASS", "READY", "OK", "CLEAN"}
    return False


def _require_gate_clean(bundle: dict[str, Any], gate_name: str) -> dict[str, Any]:
    gates = bundle.get("gates")
    if not isinstance(gates, dict):
        raise ReleasePublishError("G005 quality-gate report missing gates object; cannot publish")
    gate = gates.get(gate_name)
    if not isinstance(gate, dict):
        raise ReleasePublishError(f"G005 quality-gate report missing {gate_name}; cannot publish")
    status = gate.get("status", gate.get("grade", gate.get("readiness_state")))
    if not _as_clean_gate_status(status):
        raise ReleasePublishError(f"G005 quality gate {gate_name} is not clean; cannot publish")
    for key in (
        "hard_gate_failures",
        "failure_count",
        "failures",
        "unresolved_count",
        "critical_false_fact_failures",
        "conflict_failures",
    ):
        value = gate.get(key)
        if isinstance(value, int) and value != 0:
            raise ReleasePublishError(f"G005 quality gate {gate_name} has failures; cannot publish")
        if isinstance(value, list) and value:
            raise ReleasePublishError(f"G005 quality gate {gate_name} has failures; cannot publish")
    return gate


def _quality_gate_report_path(run_dir: Path, payload: dict[str, Any]) -> Path:
    report_paths = payload.get("report_paths")
    if isinstance(report_paths, dict):
        for key in (
            "g005_quality_gates",
            "g005_quality_gate_report",
            "quality_gate_report",
            "release_quality_gate_report",
        ):
            value = report_paths.get(key)
            if isinstance(value, str) and value.strip():
                return _resolve_manifest_path(run_dir, value)
    return _resolve_path(
        run_dir / "reports" / "g005-quality-gates.json", "G005 quality-gate report"
    )


def _validate_g005_quality_gate_bundle(
    run_dir: Path,
    payload: dict[str, Any],
    *,
    content_root: Path,
    meta_root: Path,
    review_allowed_signers: Path | None = None,
) -> Path:
    """Validate G005 by reloading evidence and rerunning public validators.

    The bundle is an evidence index only; status strings inside it are never
    trusted for release decisions.
    """
    from repo_wiki.orchestration.g005_quality_gate import (
        G005QualityGateError,
        validate_g005_bundle,
    )

    run_root = _resolve_path(run_dir, "selected run")
    report = _quality_gate_report_path(run_root, payload)
    if not _path_is_relative_to(report, run_root):
        raise ReleasePublishError(
            "G005 quality-gate report must be inside selected run; cannot publish"
        )
    if not report.is_file():
        raise ReleasePublishError("G005 quality-gate report missing; cannot publish")
    bundle = _read_json(report)
    try:
        validate_g005_bundle(run_root, bundle, review_allowed_signers=review_allowed_signers)
    except G005QualityGateError as exc:
        raise ReleasePublishError(f"{exc}; cannot publish") from exc
    return report


def _rerun_authoritative_strict_verification(run_dir: Path) -> dict[str, Any]:
    from repo_wiki.verifier.qoder_strict_verifier import verify_qoder_like

    result = verify_qoder_like(run_dir, ci=True, strict=True)
    summary = result.get("summary") if isinstance(result, dict) else None
    gate_summary = result.get("gate_summary") if isinstance(result, dict) else None
    hard_failures = summary.get("hard_gate_failures") if isinstance(summary, dict) else None
    hard_blocking = (
        gate_summary.get("hard_gate_blocking") if isinstance(gate_summary, dict) else None
    )
    if (
        not isinstance(result, dict)
        or result.get("grade") != "PASS"
        or result.get("exit_code") not in (0, None)
        or hard_failures not in (0, None)
        or hard_blocking is True
        or result.get("hard_gate_codes")
    ):
        raise ReleasePublishError(
            "Authoritative qoder-like strict verification is not clean; cannot publish"
        )
    return result


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive guard
        raise ReleasePublishError(f"Invalid JSON manifest: {path}") from exc
    if not isinstance(payload, dict):
        raise ReleasePublishError(f"Manifest must be an object: {path}")
    return payload


def _is_ready_manifest(payload: dict[str, Any]) -> bool:
    readiness = payload.get("readiness_state")
    return isinstance(readiness, str) and readiness.upper() == "READY"


def _path_is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def _resolve_path(path: Path, description: str) -> Path:
    try:
        return path.resolve()
    except (OSError, RuntimeError) as exc:
        raise ReleasePublishError(f"Cannot resolve {description}: {path}") from exc


def _resolve_manifest_path(run_dir: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = run_dir / path
    return _resolve_path(path, "manifest path")


def _validate_candidate_tree_has_no_symlinks(root: Path, field_name: str) -> None:
    pending = [root]
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    entry_path = Path(entry.path)
                    if entry.is_symlink():
                        raise ReleasePublishError(
                            f"{field_name} contains symlink; cannot publish: {entry_path}"
                        )
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(entry_path)
        except OSError as exc:
            raise ReleasePublishError(
                f"Cannot inspect {field_name} before publish: {directory}"
            ) from exc


def _is_strict_verify_report_candidate(name: str, value: str) -> bool:
    normalized_name = name.lower().replace("-", "_")
    normalized_value = Path(value).name.lower().replace("-", "_")
    return (
        normalized_name in {"strict_verify", "strict_verify_json", "strict_verify_output.json"}
        or ("strict" in normalized_name and "verify" in normalized_name)
        or normalized_value == "strict_verify_output.json"
        or ("strict" in normalized_value and "verify" in normalized_value)
    )


def _validate_strict_report_passed(run_dir: Path, payload: dict[str, Any]) -> Path:
    run_root = _resolve_path(run_dir, "selected run")
    report_paths = payload.get("report_paths")
    if not isinstance(report_paths, dict) or not report_paths:
        raise ReleasePublishError("Strict verify report path missing; cannot publish")

    strict_report_raw: str | None = None
    for name, value in report_paths.items():
        if not isinstance(name, str) or not isinstance(value, str) or not value.strip():
            continue
        if _is_strict_verify_report_candidate(name, value):
            strict_report_raw = value
            break
    if strict_report_raw is None:
        raise ReleasePublishError("Strict verify report path missing; cannot publish")

    report = _resolve_manifest_path(run_root, strict_report_raw)
    if not _path_is_relative_to(report, run_root):
        raise ReleasePublishError(
            "Strict verify report must be inside selected run; cannot publish"
        )
    if not report.exists() or not report.is_file():
        raise ReleasePublishError("Strict verify PASS report missing; cannot publish")
    try:
        parsed = json.loads(report.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ReleasePublishError("Strict verify report is invalid JSON; cannot publish") from exc
    if not isinstance(parsed, dict) or parsed.get("grade") != "PASS":
        raise ReleasePublishError("Strict verify grade is not PASS; cannot publish")
    return report


def _validate_candidate_paths(run_dir: Path, payload: dict[str, Any]) -> tuple[Path, Path]:
    run_root = _resolve_path(run_dir, "selected run")
    canonical_root = _resolve_path(run_root / "repowiki" / "zh", "selected run canonical tree")
    if not _path_is_relative_to(canonical_root, run_root):
        raise ReleasePublishError(
            f"Selected run canonical tree escapes selected run: {canonical_root} is not under {run_root}"
        )

    candidate_root_raw = payload.get("candidate_repowiki_zh_root")
    if isinstance(candidate_root_raw, str) and candidate_root_raw.strip():
        candidate_root = _resolve_manifest_path(run_root, candidate_root_raw)
        if candidate_root != canonical_root:
            raise ReleasePublishError(
                f"candidate_repowiki_zh_root must equal selected run canonical root: {canonical_root}"
            )

    content_root_raw = payload.get("candidate_content_root")
    meta_root_raw = payload.get("candidate_meta_root")
    if not isinstance(content_root_raw, str) or not content_root_raw:
        raise ReleasePublishError("Manifest missing candidate_content_root")
    if not isinstance(meta_root_raw, str) or not meta_root_raw:
        raise ReleasePublishError("Manifest missing candidate_meta_root")

    content_root = _resolve_manifest_path(run_root, content_root_raw)
    meta_root = _resolve_manifest_path(run_root, meta_root_raw)

    if not _path_is_relative_to(content_root, canonical_root):
        raise ReleasePublishError(
            f"candidate_content_root escapes selected canonical run tree: {content_root} is not under {canonical_root}"
        )
    if not _path_is_relative_to(meta_root, canonical_root):
        raise ReleasePublishError(
            f"candidate_meta_root escapes selected canonical run tree: {meta_root} is not under {canonical_root}"
        )

    expected_content_root = _resolve_path(canonical_root / "content", "selected run content root")
    expected_meta_root = _resolve_path(canonical_root / "meta", "selected run meta root")
    if content_root != expected_content_root:
        raise ReleasePublishError(
            f"candidate_content_root must equal selected run content root: {expected_content_root}"
        )
    if meta_root != expected_meta_root:
        raise ReleasePublishError(
            f"candidate_meta_root must equal selected run meta root: {expected_meta_root}"
        )

    if not content_root.exists() or not content_root.is_dir():
        raise ReleasePublishError(f"candidate_content_root missing: {content_root}")
    if not meta_root.exists() or not meta_root.is_dir():
        raise ReleasePublishError(f"candidate_meta_root missing: {meta_root}")
    _validate_candidate_tree_has_no_symlinks(content_root, "candidate_content_root")
    _validate_candidate_tree_has_no_symlinks(meta_root, "candidate_meta_root")
    return content_root, meta_root


def _iter_meta_json_files(meta_root: Path) -> list[Path]:
    """Top-level ``*.json`` under meta (sidecar contract)."""
    if not meta_root.is_dir():
        return []
    return sorted(p for p in meta_root.iterdir() if p.is_file() and p.suffix.lower() == ".json")


def _validate_candidate_meta_sidecars(meta_root: Path) -> None:
    """Ensure every candidate meta JSON validates; raises before any release write."""
    for filename in ("page-registry.json", "evidence-index.json"):
        path = meta_root / filename
        if not path.is_file():
            raise ReleasePublishError(f"Required READY meta sidecar missing: {filename}")
    for path in _iter_meta_json_files(meta_root):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ReleasePublishError(f"Invalid JSON in meta file {path.name}: {exc}") from exc
        errors = validate_meta_file(path.name, payload)
        if errors:
            detail = "; ".join(errors[:5])
            if len(errors) > 5:
                detail += f" … (+{len(errors) - 5} more)"
            raise ReleasePublishError(f"Meta validation failed for {path.name}: {detail}")


def _write_release_history(eval_root: Path, release_entry: dict[str, Any]) -> None:
    """Append release history atomically or leave the previous file untouched."""
    history_path = eval_root / "release-history.json"
    history: list[dict[str, Any]] = []
    if history_path.exists():
        try:
            existing = json.loads(history_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
            raise ReleasePublishError("release history is unreadable or invalid JSON") from exc
        if not isinstance(existing, list):
            raise ReleasePublishError("release history must be a JSON array")
        if any(not isinstance(item, dict) for item in existing):
            raise ReleasePublishError("release history entries must be JSON objects")
        history = list(existing)
    history.append(release_entry)

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=str(eval_root),
            prefix=".release-history-",
            suffix=".tmp",
            delete=False,
        ) as tmp_file:
            tmp_path = Path(tmp_file.name)
            json.dump(history, tmp_file, ensure_ascii=False, indent=2)
        tmp_path.replace(history_path)
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink()


def _maybe_inject_publish_failure(stage: str, failure_injection: str | None) -> None:
    """Test-only failure hook for release transaction rollback boundaries."""
    if failure_injection == stage:
        raise ReleasePublishError(f"Injected release publish failure at {stage}")


def resolve_publish_run_dir(eval_root: Path, run_ref: str | Path) -> Path:
    """Resolve selected run by exact path identity or legacy run id."""
    eval_root = _resolve_path(eval_root, "eval root")
    raw_ref = Path(run_ref)

    if raw_ref.is_absolute() or len(raw_ref.parts) != 1:
        selected = _resolve_path(
            raw_ref if raw_ref.is_absolute() else eval_root / raw_ref, "selected run"
        )
        if not _path_is_relative_to(selected, eval_root):
            raise ReleasePublishError(f"run_ref path escapes eval root: {run_ref!r}")
        if not (selected / "manifest.json").is_file():
            raise ReleasePublishError(f"Run manifest not found: {selected / 'manifest.json'}")
        return selected

    ref = raw_ref
    if ref.name in {"", ".", ".."}:
        raise ReleasePublishError(
            f"run_ref must be a single relative run id without traversal: {str(run_ref)!r}"
        )

    nested_parent = eval_root / "runs"
    direct = _resolve_path(eval_root / ref.name, "flat selected run")
    nested = _resolve_path(nested_parent / ref.name, "nested selected run")

    if not _path_is_relative_to(nested, eval_root):
        raise ReleasePublishError(f"Selected run escapes eval root canonical runs tree: {nested}")
    if not _path_is_relative_to(direct, eval_root):
        raise ReleasePublishError(f"Selected run escapes eval root canonical flat tree: {direct}")

    if (nested / "manifest.json").exists():
        return nested
    if (direct / "manifest.json").exists():
        return direct
    return direct


def diagnose_eval_run_layouts(eval_root: Path) -> dict[str, Any]:
    """Report canonical vs legacy content layout under eval runs (no mutation).

    * **canonical**: ``<run>/repowiki/zh/content`` exists as a directory.
    * **legacy**: ``<run>/content`` exists as a directory (pre-Phase-41 flat layout).

    Runs are discovered the same way as ``discover_runs`` (manifest under
    ``runs/<id>`` or flat ``<id>``), excluding ``repowiki`` release tree.
    """
    from repo_wiki.orchestration.latest_run_selector import discover_runs

    eval_root = eval_root.resolve()
    entries: list[dict[str, Any]] = []
    for run_id, run_dir, _payload in discover_runs(eval_root):
        canonical = (run_dir / "repowiki" / "zh" / "content").is_dir()
        legacy_flat = (run_dir / "content").is_dir()
        if canonical and legacy_flat:
            layout = "mixed"
        elif canonical:
            layout = "canonical"
        elif legacy_flat:
            layout = "legacy"
        else:
            layout = "neither"
        entries.append(
            {
                "run_id": run_id,
                "run_dir": str(run_dir.resolve()),
                "canonical_content": canonical,
                "legacy_flat_content": legacy_flat,
                "layout": layout,
            }
        )
    return {"eval_root": str(eval_root), "runs": entries}


def publish_ready_run(
    eval_root: Path,
    run_ref: str | Path,
    *,
    dry_run: bool = False,
    review_allowed_signers: Path | None = None,
    _failure_injection: str | None = None,
) -> dict[str, Any]:
    """Publish a READY run to fixed `.repo-agent-eval/repowiki/zh` atomically."""
    eval_root = _resolve_path(eval_root, "eval root")
    eval_root.mkdir(parents=True, exist_ok=True)
    run_dir = resolve_publish_run_dir(eval_root, run_ref)
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise ReleasePublishError(f"Run manifest not found: {manifest_path}")
    resolved_manifest_path = _resolve_path(manifest_path, "selected run manifest")
    if not _path_is_relative_to(resolved_manifest_path, run_dir):
        raise ReleasePublishError("Run manifest must be inside selected run; cannot publish")

    payload = _read_json(resolved_manifest_path)
    source_run_id = str(payload.get("run_id") or run_ref)
    if not _is_ready_manifest(payload):
        raise ReleasePublishError("Run manifest is not READY (requires readiness_state=READY)")
    if bool(payload.get("target_dirty", False)):
        raise ReleasePublishError("Run target_dirty=true; cannot publish")
    if not bool(payload.get("git_fresh", True)):
        raise ReleasePublishError("Run git_fresh=false; cannot publish")

    content_root, meta_root = _validate_candidate_paths(run_dir, payload)
    _validate_candidate_meta_sidecars(meta_root)
    _validate_strict_report_passed(run_dir, payload)
    _validate_g005_quality_gate_bundle(
        run_dir,
        payload,
        content_root=content_root,
        meta_root=meta_root,
        review_allowed_signers=review_allowed_signers,
    )
    _rerun_authoritative_strict_verification(run_dir)
    release_root = eval_root / "repowiki" / "zh"
    release_manifest_path = release_root / "manifest.json"
    release_meta_dir = release_root / "meta"
    release_content_dir = release_root / "content"

    published_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    release_payload = dict(payload)
    release_payload.update(
        {
            "release_status": "READY",
            "readiness": "READY",
            "release_id": f"release-{source_run_id}",
            "source_run_id": source_run_id,
            "published_at": published_at,
            "content_root": "content",
            "meta_root": "meta",
        }
    )
    release_note = {
        "schema_version": SCHEMA_VERSION_META_RELEASE,
        "release_id": release_payload["release_id"],
        "source_run_id": source_run_id,
        "published_at": published_at,
        "release_status": "READY",
        "manifest_path": str(release_manifest_path),
        "target_git_commit": payload.get("target_git_commit"),
    }

    if dry_run:
        return {
            "status": "READY_CANDIDATE",
            "run_id": source_run_id,
            "release_root": str(release_root),
            "candidate_content_root": str(content_root),
            "candidate_meta_root": str(meta_root),
            "would_publish_manifest": release_payload,
        }

    with tempfile.TemporaryDirectory(prefix="repo-wiki-release-", dir=str(eval_root)) as temp_dir:
        staging_root = Path(temp_dir) / "repowiki" / "zh"
        staging_content = staging_root / "content"
        staging_meta = staging_root / "meta"
        shutil.copytree(content_root, staging_content, symlinks=True)
        shutil.copytree(meta_root, staging_meta, symlinks=True)
        _validate_candidate_tree_has_no_symlinks(staging_content, "staged content tree")
        _validate_candidate_tree_has_no_symlinks(staging_meta, "staged meta tree")
        (staging_root / "manifest.json").write_text(
            json.dumps(release_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (staging_meta / "release.json").write_text(
            json.dumps(release_note, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        release_errors = validate_meta_file("release.json", release_note)
        if release_errors:
            detail = "; ".join(release_errors[:5])
            raise ReleasePublishError(f"Internal release.json validation failed: {detail}")

        backup_root = eval_root / "repowiki" / "zh.__backup__"
        release_root.parent.mkdir(parents=True, exist_ok=True)
        if backup_root.exists():
            shutil.rmtree(backup_root)
        has_backup = release_root.exists()
        installed_new_release = False
        try:
            if has_backup:
                release_root.replace(backup_root)
                _maybe_inject_publish_failure(
                    "after_existing_release_moved_to_backup", _failure_injection
                )
            staging_root.replace(release_root)
            installed_new_release = True
            _write_release_history(eval_root, release_note)
        except BaseException:
            if installed_new_release and release_root.exists():
                shutil.rmtree(release_root)
            if has_backup and backup_root.exists():
                backup_root.replace(release_root)
            raise
        if backup_root.exists():
            shutil.rmtree(backup_root)

    return {
        "status": "PUBLISHED",
        "run_id": source_run_id,
        "release_root": str(release_root),
        "manifest_path": str(release_manifest_path),
        "release_meta_path": str(release_meta_dir / "release.json"),
        "release_content_path": str(release_content_dir),
    }
