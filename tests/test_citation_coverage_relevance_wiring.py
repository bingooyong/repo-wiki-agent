"""R11 leftover HARD: citation coverage window and relevance path overlap.

QODER_CITATION_FACT_COVERAGE_LOW and QODER_CITATION_RELEVANCE_MISMATCH were still
open after generate succeeded with 0 invalid cites. These tests pin the wiring bugs:

1. Coverage uses paragraph start only, so a cite immediately after a wrapped
   factual paragraph is not counted (the adjacency docstring already describes
   that generator pattern).
2. Relevance treats overlapping taxonomy keywords in real paths such as
   app/api/routes/authentication.py as a wrong-service bind.
3. Page-contract API grouping has file:line evidence but writes backticks
   instead of <cite>, so verifier-required claims are born uncovered.

Gates stay HARD. The 95% coverage threshold is not lowered. Uncited claims stay
uncovered. True wrong-service binds still fail.
"""

from __future__ import annotations

from pathlib import Path

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.generator.composer import ComposerContext
from repo_wiki.orchestration.service import RepoWikiService
from repo_wiki.planner.schema import WikiPagePlan, WikiTaxonomyCategory
from repo_wiki.verifier.citation_fact_coverage import (
    build_claim_coverage,
    extract_citation_refs_with_lines,
)
from repo_wiki.verifier.qoder_strict_verifier import (
    QoderLikeSeverityThreshold,
    QoderLikeVerifierService,
)


def _coverage(markdown: str, *, valid_lines: set[int] | None = None) -> dict[str, object]:
    if valid_lines is None:
        valid_lines = {ref.line for ref in extract_citation_refs_with_lines(markdown)}
    return build_claim_coverage(markdown, page="overview.md", valid_repo_citation_lines=valid_lines)


def test_wrapped_paragraph_with_trailing_cite_is_covered() -> None:
    """Cite immediately after a wrapped factual paragraph must count as covered."""
    markdown = """# Project Overview

The UserService implements authentication for Conduit users
and provides JWT token validation for GET /api/users login.
<cite>app/api/routes/authentication.py:1-20</cite>
"""
    result = _coverage(markdown)
    assert int(result["total"]) >= 1
    assert result["uncovered"] == []
    assert float(result["ratio"]) == 1.0


def test_uncited_claim_is_still_uncovered() -> None:
    """Do not count unverifiable claims as covered."""
    markdown = """# Project Overview

The UserService implements authentication for Conduit users
and provides JWT token validation for GET /api/users login.

A later section with no nearby citation.
"""
    result = _coverage(markdown)
    assert int(result["total"]) >= 1
    assert int(result["covered"]) == 0
    assert float(result["ratio"]) == 0.0
    assert result["uncovered"]


def test_single_line_claim_still_requires_adjacent_cite() -> None:
    """A cite far below a one-line claim is not coverage."""
    markdown = """# Project Overview

The UserService implements authentication for GET /api/users.

## Later

Filler paragraph without factual signals.

<cite>app/api/routes/authentication.py:1-20</cite>
"""
    result = _coverage(markdown)
    assert int(result["total"]) >= 1
    assert any("UserService" in str(item.get("text", "")) for item in result["uncovered"])
    assert float(result["ratio"]) < 1.0


def test_fastapi_authentication_route_cite_is_not_relevance_mismatch(tmp_path: Path) -> None:
    """app/api/routes/authentication.py is the auth API, not a wrong-service bind."""
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "authentication-api.md").write_text(
        """# Authentication API

## Table of Contents
- [Login](#login)

## Login

POST /api/users/login authenticates Conduit users.

<cite>app/api/routes/authentication.py:1-20</cite>
""",
        encoding="utf-8",
    )

    result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)
    assert "QODER_CITATION_RELEVANCE_MISMATCH" not in result.get("hard_gate_codes", [])
    relevance = next(c for c in result["checks"] if c["name"] == "qoder-citation-relevance")
    assert relevance["status"] in {"PASS", "WARN", "SKIP"}


def test_api_page_citing_authentication_route_is_not_relevance_mismatch(tmp_path: Path) -> None:
    """API pages citing app/api/routes/authentication.py are documenting that API."""
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "api-reference.md").write_text(
        """# API Reference

## Endpoints

POST /api/users/login is the Conduit login endpoint.

<cite>app/api/routes/authentication.py:10-40</cite>
""",
        encoding="utf-8",
    )

    result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)
    assert "QODER_CITATION_RELEVANCE_MISMATCH" not in result.get("hard_gate_codes", [])


def test_billing_page_citing_auth_only_path_still_relevance_mismatch(tmp_path: Path) -> None:
    """True wrong-service binds stay HARD. Do not relax the gate."""
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "billing-service.md").write_text(
        """# Billing Service

The billing service handles payments and subscriptions.

<cite>src/auth/session.py:1</cite>
""",
        encoding="utf-8",
    )

    result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)
    assert "QODER_CITATION_RELEVANCE_MISMATCH" in result.get("hard_gate_codes", [])
    relevance = next(c for c in result["checks"] if c["name"] == "qoder-citation-relevance")
    assert relevance["status"] == "FAIL"
    assert relevance["reason_code"] == "QODER_CITATION_RELEVANCE_MISMATCH"
    assert relevance["gate_type"] == "HARD"


def test_evidence_backed_api_group_emits_cite_for_endpoint_claim(tmp_path: Path) -> None:
    """Page contract already has file:line; emit <cite> so the GET claim is covered."""
    cfg = RepoWikiConfig()
    cfg.project.root = str(tmp_path)
    service = RepoWikiService(cfg)
    page = WikiPagePlan(
        page_id="inventory-api",
        title="Inventory API",
        category=WikiTaxonomyCategory.API_REFERENCE,
        output_path="docs/pages/api/inventory-api.md",
    )
    (tmp_path / "src" / "inventory").mkdir(parents=True)
    (tmp_path / "src" / "inventory" / "api.py").write_text(
        "\n".join(f"line {i}" for i in range(1, 50)),
        encoding="utf-8",
    )
    rendered = service._enforce_qoder_page_contract(
        page=page,
        markdown="# Inventory API\n\n## 简介\n\n短说明。",
        binding=None,
        add_mermaid=False,
        composition_context=ComposerContext(
            repository_name="repo",
            primary_language="python",
            framework="fastapi",
            repository_root=str(tmp_path),
            endpoints=[
                {
                    "method": "GET",
                    "path": "/inventory/items",
                    "module": "inventory",
                    "handler": "list_items",
                    "file_path": "src/inventory/api.py",
                    "line_number": 42,
                    "auth_type": "api-key",
                }
            ],
        ),
    )

    assert "GET /inventory/items" in rendered
    assert "<cite>src/inventory/api.py:42</cite>" in rendered

    coverage = build_claim_coverage(
        rendered,
        page="inventory-api.md",
        valid_repo_citation_lines={ref.line for ref in extract_citation_refs_with_lines(rendered)},
    )
    uncovered_text = " ".join(str(item.get("text", "")) for item in coverage["uncovered"])
    assert "GET /inventory/items" not in uncovered_text
    assert int(coverage["covered"]) >= 1


def test_coverage_and_relevance_gates_remain_hard() -> None:
    """Do not relax leftover citation HARD codes or the 95% coverage floor."""
    threshold = QoderLikeSeverityThreshold()
    assert "QODER_CITATION_FACT_COVERAGE_LOW" in threshold.STRICT_HARD_CODES
    assert "QODER_CITATION_RELEVANCE_MISMATCH" in threshold.STRICT_HARD_CODES

    from repo_wiki.verifier import qoder_strict_verifier as verifier_mod

    source = Path(verifier_mod.__file__).read_text(encoding="utf-8")
    assert "if ratio < 0.95:" in source
    assert 'reason_code="QODER_CITATION_FACT_COVERAGE_LOW"' in source
