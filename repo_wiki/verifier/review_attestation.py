"""Detached OpenSSH attestation for external G005 blind-review evidence."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

NAMESPACE = "repo-agent-g005-blind-review-v1"
DEFAULT_MAX_AGE_DAYS = 397


class ReviewAttestationError(ValueError):
    """Raised when blind-review attestation cannot be verified."""


def stable_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _reviewer_identity(review_payload: dict[str, Any]) -> str:
    for key in ("reviewer_identity_hash", "reviewer_identity", "reviewer_id"):
        value = review_payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    raise ReviewAttestationError("blind review missing reviewer identity")


def _rubric_revision(review_payload: dict[str, Any]) -> str:
    for key in ("rubric_revision", "rubric_version", "rubric_id", "schema_version"):
        value = review_payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    raise ReviewAttestationError("blind review missing rubric revision")


def _candidate_artifact_hashes(review_payload: dict[str, Any]) -> dict[str, str]:
    candidates = review_payload.get("candidates")
    if not isinstance(candidates, list):
        raise ReviewAttestationError("blind review missing candidates")
    result: dict[str, str] = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        system = str(candidate.get("system") or "").strip().lower()
        artifact_hash = candidate.get("artifact_hash")
        if system in {"repo-agent", "repo_agent", "repoagent"}:
            result["repo_agent"] = str(artifact_hash or "")
        elif system == "qoder":
            result["qoder"] = str(artifact_hash or "")
    if not result.get("repo_agent") or not result.get("qoder"):
        raise ReviewAttestationError(
            "blind review must include repo-agent and Qoder artifact hashes"
        )
    return result


def canonical_attestation_payload(
    *,
    review_payload: dict[str, Any],
    qoder_comparison_payload: dict[str, Any],
    signed_at: str,
) -> dict[str, Any]:
    """Build the exact payload that an external reviewer signs."""
    artifact_hashes = _candidate_artifact_hashes(review_payload)
    return {
        "schema_version": "repo_agent.g005_review_attestation/1.0",
        "namespace": NAMESPACE,
        "blind_review_payload_sha256": sha256_bytes(stable_json_bytes(review_payload)),
        "rubric_revision": _rubric_revision(review_payload),
        "reviewer_identity": _reviewer_identity(review_payload),
        "signed_at": signed_at,
        "artifact_hashes": {
            "repo_agent": artifact_hashes["repo_agent"],
            "qoder": artifact_hashes["qoder"],
            "qoder_comparison_report": sha256_bytes(stable_json_bytes(qoder_comparison_payload)),
        },
    }


def canonical_signed_bytes(
    *,
    review_payload: dict[str, Any],
    qoder_comparison_payload: dict[str, Any],
    signed_at: str,
) -> bytes:
    return stable_json_bytes(
        canonical_attestation_payload(
            review_payload=review_payload,
            qoder_comparison_payload=qoder_comparison_payload,
            signed_at=signed_at,
        )
    )


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReviewAttestationError(f"invalid attestation timestamp: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _max_age_days() -> int:
    raw = os.environ.get("REPO_WIKI_G005_REVIEW_ATTESTATION_MAX_AGE_DAYS")
    if not raw:
        return DEFAULT_MAX_AGE_DAYS
    try:
        value = int(raw)
    except ValueError as exc:
        raise ReviewAttestationError("invalid review attestation max age") from exc
    if value <= 0:
        raise ReviewAttestationError("review attestation max age must be positive")
    return value


def _ensure_fresh(signed_at: str) -> None:
    signed = _parse_timestamp(signed_at)
    now = datetime.now(UTC)
    if signed > now + timedelta(minutes=5):
        raise ReviewAttestationError("review attestation timestamp is in the future")
    if now - signed > timedelta(days=_max_age_days()):
        raise ReviewAttestationError("review attestation has expired")


def _resolve_inside_run(run_dir: Path, raw: str, description: str) -> Path:
    root = run_dir.resolve()
    path = Path(raw)
    resolved = (path if path.is_absolute() else root / path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ReviewAttestationError(
            f"{description} must be inside selected run: {resolved}"
        ) from exc
    if not resolved.is_file():
        raise ReviewAttestationError(f"{description} missing: {resolved}")
    return resolved


def _verify_openssh_signature(
    *,
    allowed_signers: Path,
    principal: str,
    signature_file: Path,
    message: bytes,
) -> None:
    if not allowed_signers.is_file():
        raise ReviewAttestationError(f"allowed signers file missing: {allowed_signers}")
    try:
        result = subprocess.run(
            [
                "ssh-keygen",
                "-Y",
                "verify",
                "-f",
                str(allowed_signers),
                "-I",
                principal,
                "-n",
                NAMESPACE,
                "-s",
                str(signature_file),
            ],
            input=message,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ReviewAttestationError(
            "ssh-keygen is required for review attestation verification"
        ) from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).decode("utf-8", errors="replace").strip()
        raise ReviewAttestationError(f"review attestation signature verification failed: {detail}")


def verify_review_attestation(
    *,
    run_dir: Path,
    review_payload: dict[str, Any],
    qoder_comparison_payload: dict[str, Any],
    attestation_payload: dict[str, Any],
    allowed_signers_path: Path,
) -> dict[str, Any]:
    """Verify detached external blind-review attestation and return bundle-safe refs."""
    principal = attestation_payload.get("principal")
    signed_at = attestation_payload.get("signed_at")
    signature_path_raw = attestation_payload.get("signature_path")
    if not isinstance(principal, str) or not principal.strip():
        raise ReviewAttestationError("review attestation missing principal")
    if not isinstance(signed_at, str) or not signed_at.strip():
        raise ReviewAttestationError("review attestation missing signed_at")
    if not isinstance(signature_path_raw, str) or not signature_path_raw.strip():
        raise ReviewAttestationError("review attestation missing detached signature path")
    if attestation_payload.get("namespace") != NAMESPACE:
        raise ReviewAttestationError("review attestation namespace mismatch")
    _ensure_fresh(signed_at)
    signature_file = _resolve_inside_run(run_dir, signature_path_raw, "review detached signature")
    message = canonical_signed_bytes(
        review_payload=review_payload,
        qoder_comparison_payload=qoder_comparison_payload,
        signed_at=signed_at,
    )
    expected_hash = sha256_bytes(message)
    declared_hash = attestation_payload.get("signed_payload_sha256")
    if declared_hash != expected_hash:
        raise ReviewAttestationError("review attestation signed payload hash mismatch")
    signature_b64 = attestation_payload.get("signature_base64")
    if isinstance(signature_b64, str) and signature_b64.strip():
        try:
            embedded_hash = sha256_bytes(
                base64.b64decode(signature_b64.encode("ascii"), validate=True)
            )
        except Exception as exc:
            raise ReviewAttestationError("review attestation signature_base64 is invalid") from exc
        if embedded_hash != sha256_file(signature_file):
            raise ReviewAttestationError("review attestation embedded signature mismatch")
    _verify_openssh_signature(
        allowed_signers=allowed_signers_path.resolve(),
        principal=principal,
        signature_file=signature_file,
        message=message,
    )
    canonical_payload = canonical_attestation_payload(
        review_payload=review_payload,
        qoder_comparison_payload=qoder_comparison_payload,
        signed_at=signed_at,
    )
    return {
        "status": "PASS",
        "namespace": NAMESPACE,
        "principal": principal,
        "signed_at": signed_at,
        "signed_payload_sha256": expected_hash,
        "attestation_payload_sha256": sha256_bytes(stable_json_bytes(attestation_payload)),
        "signature_path": str(signature_file.resolve().relative_to(run_dir.resolve())),
        "signature_sha256": sha256_file(signature_file),
        "allowed_signers_sha256": sha256_file(allowed_signers_path.resolve()),
        "canonical_payload": canonical_payload,
    }
