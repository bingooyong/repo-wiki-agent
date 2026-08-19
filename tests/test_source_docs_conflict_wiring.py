"""Scanner/resolver wiring: historical docs resolve; current mismatches still HARD."""

from __future__ import annotations

from pathlib import Path

from repo_wiki.scanner.conflict_resolver import (
    MISSING_SOURCE_CONFIRMATION,
    SOURCE_DOC_MISMATCH,
    STALE_DOC_REFERENCE,
    UNSUPPORTED_DOC_CLAIM,
    resolve_source_docs_conflicts,
)
from repo_wiki.scanner.docs_scanner import (
    _classify_doc_type,
    scan_repository_docs_inventory,
)
from repo_wiki.verifier.qoder_strict_verifier import (
    QoderLikeSeverityThreshold,
    QoderLikeVerifierService,
)


def _source_inventory() -> dict:
    return {
        "services": [{"service_id": "annals-service", "name": "AnnalsService"}],
        "api_surfaces": [{"path": "/health", "method": "GET", "service": "annals-service"}],
        "data_models": [{"name": "AnnalsModel"}],
        "frontend_callers": [],
        "deployment_assets": [],
        "tests": [],
    }


def _write_planning_tree(root: Path) -> None:
    (root / ".omc").mkdir()
    (root / ".omc" / "session.md").write_text(
        "# OMC notes\nPlanned `GhostService` at `src/ghost/service.py`.\n",
        encoding="utf-8",
    )
    (root / ".superpowers" / "sdd" / "briefs").mkdir(parents=True)
    (root / ".superpowers" / "sdd" / "briefs" / "brief.md").write_text(
        "# Brief\nFutureService will replace `src/legacy/gone.py`.\n",
        encoding="utf-8",
    )
    (root / ".superpowers" / "sdd" / "reviews").mkdir()
    (root / ".superpowers" / "sdd" / "reviews" / "review.md").write_text(
        "# Review\nDropped `src/old/plan.py`.\n",
        encoding="utf-8",
    )
    (root / "docs" / "superpowers" / "plans").mkdir(parents=True)
    (root / "docs" / "superpowers" / "plans" / "phase.md").write_text(
        "# Plan\nShip FutureService after `src/ghost/service.py`.\n",
        encoding="utf-8",
    )
    (root / "docs" / "superpowers" / "specs").mkdir()
    (root / "docs" / "superpowers" / "specs" / "design.md").write_text(
        "# Spec\nHistorical `src/legacy/gone.py` decision.\n",
        encoding="utf-8",
    )
    (root / "HANDOFF.md").write_text(
        "# Handoff\nPending `src/ghost/service.py`.\n",
        encoding="utf-8",
    )
    (root / "verification-report.md").write_text(
        "# Verification\nChecked `src/legacy/gone.py`.\n",
        encoding="utf-8",
    )


def test_planning_paths_classify_as_planning() -> None:
    samples = {
        ".omc/session.md": "notes",
        ".superpowers/sdd/briefs/brief.md": "brief",
        ".superpowers/sdd/reviews/review.md": "review",
        "docs/superpowers/plans/phase.md": "plan",
        "docs/superpowers/specs/design.md": "spec",
        "HANDOFF.md": "handoff",
        "verification-report.md": "verification",
    }
    for rel, body in samples.items():
        assert _classify_doc_type(rel, body) == "planning", rel


def test_omc_and_superpowers_resolve_as_historical(tmp_path: Path) -> None:
    _write_planning_tree(tmp_path)
    (tmp_path / "docs").mkdir(exist_ok=True)
    (tmp_path / "docs" / "AI_Novel_Agent_PRD_Architecture.md").write_text(
        "# Architecture\nGhostService lives in `src/missing/ghost.py`.\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text(
        "# ai-open-writing\n"
        "Clone `bingooyong/ai-open-writing` from `origin/main` "
        "(`feat/annals-chronotope`, `353bcab..58c89e5`).\n"
        "Use `sqlmodel`, `creative_model`, `mock-model`, `ctx.annals.applicable`, "
        "`sqlmodel.metadata.create_all`, and `package.annals`.\n"
        "Copy `.env`, open `/docs` and `/redoc`, store `novel.db`, "
        "progress `16000/16000`.\n"
        ".. image:: https://github.com/bingooyong/ai-open-writing/workflows/Tests/badge.svg\n"
        "See `docs/ai_novel_agent_prd_architecture.md`.\n",
        encoding="utf-8",
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("app = True\n", encoding="utf-8")

    inv = scan_repository_docs_inventory(
        tmp_path, _source_inventory(), incremental=False, persist_cache=False
    )
    by_path = {doc["path"]: doc for doc in inv["documents"]}

    planning_paths = [
        ".omc/session.md",
        ".superpowers/sdd/briefs/brief.md",
        ".superpowers/sdd/reviews/review.md",
        "docs/superpowers/plans/phase.md",
        "docs/superpowers/specs/design.md",
        "HANDOFF.md",
        "verification-report.md",
    ]
    for rel in planning_paths:
        assert by_path[rel]["doc_type"] == "planning"
        assert by_path[rel]["authority_level"] == "historical"

    readme = by_path["README.md"]
    stale = set(readme["stale_references"])
    claims = set(readme["conflicting_claims"])
    assert "bingooyong/ai-open-writing" not in stale
    assert "origin/main" not in stale
    assert "feat/annals-chronotope" not in stale
    assert "353bcab..58c89e5" not in stale
    assert "ctx.annals.applicable" not in stale
    assert "sqlmodel.metadata.create_all" not in stale
    assert "package.annals" not in stale
    assert "16000/16000" not in stale
    assert "novel.db" not in stale
    assert ".env" not in stale
    assert "/docs" not in stale
    assert "/redoc" not in stale
    assert "docs/ai_novel_agent_prd_architecture.md" not in stale
    assert "sqlmodel" not in claims
    assert "creative_model" not in claims
    assert "mock-model" not in claims

    architecture = by_path["docs/AI_Novel_Agent_PRD_Architecture.md"]
    assert architecture["doc_type"] == "architecture"
    assert "src/missing/ghost.py" in architecture["stale_references"]
    assert any(claim.endswith("service") for claim in architecture["conflicting_claims"])

    report = resolve_source_docs_conflicts(_source_inventory(), inv)
    planning_items = [
        item for item in report["resolved_items"] if item["doc_path"] in planning_paths
    ]
    assert planning_items
    assert all(item["status"] == "resolved" for item in planning_items)
    assert all(item["classification"] == "historical" for item in planning_items)
    assert report["summary"]["resolved_count"] == len(report["resolved_items"])

    current_unresolved = report["deferred_items"] + report["flagged_items"]
    assert current_unresolved
    assert all(
        item["doc_path"] == "docs/AI_Novel_Agent_PRD_Architecture.md" for item in current_unresolved
    )
    assert {item["reason_code"] for item in current_unresolved} & {
        SOURCE_DOC_MISMATCH,
        STALE_DOC_REFERENCE,
        MISSING_SOURCE_CONFIRMATION,
    }

    verifier = QoderLikeVerifierService(tmp_path, strict=True)
    assert verifier._count_unresolved_conflicts(report) == len(current_unresolved)


def test_current_doc_mismatch_still_blocks_and_codes_stay_hard() -> None:
    threshold = QoderLikeSeverityThreshold()
    for code in (
        SOURCE_DOC_MISMATCH,
        STALE_DOC_REFERENCE,
        UNSUPPORTED_DOC_CLAIM,
        MISSING_SOURCE_CONFIRMATION,
    ):
        assert threshold.is_blocking(code) is True
        assert code in threshold.STRICT_HARD_CODES


def test_fastapi_leftover_readme_tokens_are_not_stale(tmp_path: Path) -> None:
    (tmp_path / "README.rst").write_text(
        "Conduit\n"
        "Copy `.env` then open `/docs` and `/redoc`.\n"
        ".. image:: https://github.com/example/fastapi-realworld-example-app/workflows/Tests/badge.svg\n"
        "    :target: https://github.com/example/fastapi-realworld-example-app\n",
        encoding="utf-8",
    )
    inv = scan_repository_docs_inventory(
        tmp_path, _source_inventory(), incremental=False, persist_cache=False
    )
    readme = next(doc for doc in inv["documents"] if doc["path"].startswith("README"))
    stale = " ".join(readme["stale_references"])
    assert ".env" not in stale
    assert "/docs" not in stale
    assert "/redoc" not in stale
    assert "badge.svg" not in stale
    report = resolve_source_docs_conflicts(_source_inventory(), inv)
    assert report["deferred_items"] == []
    assert report["flagged_items"] == []
