"""Qoder-like verify must find quality artifacts where generate writes them."""

from __future__ import annotations

import json
from pathlib import Path

from repo_wiki.cli import _resolve_verify_root
from repo_wiki.verifier.qoder_strict_verifier import QoderLikeVerifierService

_PAGE_REL = "项目概述/00-overview.md"


def _write_quality_pair(meta_dir: Path, *, page_rel: str = _PAGE_REL) -> None:
    meta_dir.mkdir(parents=True, exist_ok=True)
    (meta_dir / "quality-report.json").write_text(
        json.dumps(
            {
                "schema_version": "repo_agent.quality_report/1.0",
                "summary": {"profile": "qoder-like", "grade": "PASS", "strict_mode": True},
                "page_quality": [{"relative_path": page_rel, "quality_state": "READY"}],
            }
        ),
        encoding="utf-8",
    )
    (meta_dir / "page-registry.json").write_text(
        json.dumps(
            {
                "schema_version": "repo_agent.page_registry/1.0",
                "generated_at": "2026-08-13T00:00:00Z",
                "pages": [
                    {
                        "page_id": "overview",
                        "relative_path": page_rel,
                        "category": "overview",
                        "page_type": "content",
                        "quality_state": "READY",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _write_run_content(run_dir: Path, *, page_rel: str = _PAGE_REL) -> None:
    page = run_dir / "repowiki" / "zh" / "content" / page_rel
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("# Overview\n\nFlask is a WSGI framework.\n", encoding="utf-8")


def test_verify_finds_quality_artifacts_under_repowiki_zh_meta(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-flask"
    _write_run_content(run_dir)
    _write_quality_pair(run_dir / "repowiki" / "zh" / "meta")
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "version": "1.1",
                "run_id": "run-flask",
                "readiness_state": "READY",
                "readiness_reasons": [],
                "candidate_repowiki_zh_root": str(
                    tmp_path / ".repo-agent-eval" / "runs" / "run-flask" / "repowiki" / "zh"
                ),
                "candidate_meta_root": str(
                    tmp_path
                    / ".repo-agent-eval"
                    / "runs"
                    / "run-flask"
                    / "repowiki"
                    / "zh"
                    / "meta"
                ),
            }
        ),
        encoding="utf-8",
    )

    result = QoderLikeVerifierService(run_dir, strict=True).verify(ci=True)
    assert "QODER_QUALITY_ARTIFACT_MISSING" not in result.get("hard_gate_codes", [])


def test_verify_still_fails_when_quality_artifacts_absent(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-empty"
    _write_run_content(run_dir)
    (run_dir / "repowiki" / "zh" / "meta").mkdir(parents=True)
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "version": "1.1",
                "run_id": "run-empty",
                "readiness_state": "READY",
                "readiness_reasons": [],
                "candidate_repowiki_zh_root": str(run_dir / "repowiki" / "zh"),
                "candidate_meta_root": str(run_dir / "repowiki" / "zh" / "meta"),
            }
        ),
        encoding="utf-8",
    )

    result = QoderLikeVerifierService(run_dir, strict=True).verify(ci=True)
    assert "QODER_QUALITY_ARTIFACT_MISSING" in result.get("hard_gate_codes", [])


def test_verify_output_eval_root_selects_latest_run(tmp_path: Path) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    older = eval_root / "run-100"
    newer = eval_root / "run-200"
    for run_dir, run_id in ((older, "run-100"), (newer, "run-200")):
        run_dir.mkdir(parents=True)
        (run_dir / "manifest.json").write_text(
            json.dumps({"run_id": run_id, "readiness_state": "READY"}),
            encoding="utf-8",
        )

    resolved = _resolve_verify_root(tmp_path, str(eval_root))
    assert resolved == newer.resolve()
