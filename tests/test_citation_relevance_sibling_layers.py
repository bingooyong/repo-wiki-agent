"""R15 leftover HARD: FastAPI sibling-layer citation relevance false positives.

QODER_CITATION_RELEVANCE_MISMATCH still fires when same-app FastAPI layers
cite each other: API pages cite query/schema/model files, and a Db page cites
domain models. Those are related evidence, not billing-citing-auth binds.

Gates stay HARD. True wrong-service binds still fail.
"""

from __future__ import annotations

from pathlib import Path

from repo_wiki.verifier.qoder_strict_verifier import (
    QoderLikeSeverityThreshold,
    QoderLikeVerifierService,
)


def _write_wiki_page(tmp_path: Path, relative_page: str, markdown: str) -> None:
    """Same tmp_path/content layout the existing relevance tests use."""
    page = tmp_path / "content" / relative_page
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(markdown, encoding="utf-8")


def _verify(tmp_path: Path) -> dict:
    return QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)


def _relevance_check(result: dict) -> dict:
    return next(c for c in result["checks"] if c["name"] == "qoder-citation-relevance")


def test_api_page_citing_query_tables_is_not_relevance_mismatch(tmp_path: Path) -> None:
    """API wiki page citing app/db/queries/tables.py is the query layer, not a wrong service."""
    _write_wiki_page(
        tmp_path,
        "核心服务/API.md",
        """# API

## Endpoints

Conduit HTTP handlers persist through the query tables layer.

<cite>app/db/queries/tables.py:1</cite>
""",
    )

    result = _verify(tmp_path)
    assert "QODER_CITATION_RELEVANCE_MISMATCH" not in result.get("hard_gate_codes", [])
    assert _relevance_check(result)["status"] in {"PASS", "WARN", "SKIP"}


def test_api_page_citing_domain_users_model_is_not_relevance_mismatch(tmp_path: Path) -> None:
    """API wiki page citing app/models/domain/users.py is sibling evidence."""
    _write_wiki_page(
        tmp_path,
        "API参考/API参考.md",
        """# API参考

## Users

User payloads are defined by the domain user model.

<cite>app/models/domain/users.py:1</cite>
""",
    )

    result = _verify(tmp_path)
    assert "QODER_CITATION_RELEVANCE_MISMATCH" not in result.get("hard_gate_codes", [])
    assert _relevance_check(result)["status"] in {"PASS", "WARN", "SKIP"}


def test_api_page_citing_schema_test_is_not_relevance_mismatch(tmp_path: Path) -> None:
    """API wiki page citing tests/test_schemas/test_rw_model.py is schema evidence."""
    _write_wiki_page(
        tmp_path,
        "API参考/核心服务API/核心服务API.md",
        """# 核心服务API

## Schema

RWModel schema tests cover the API payload contract.

<cite>tests/test_schemas/test_rw_model.py:1</cite>
""",
    )

    result = _verify(tmp_path)
    assert "QODER_CITATION_RELEVANCE_MISMATCH" not in result.get("hard_gate_codes", [])
    assert _relevance_check(result)["status"] in {"PASS", "WARN", "SKIP"}


def test_db_page_citing_domain_users_model_is_not_relevance_mismatch(tmp_path: Path) -> None:
    """Db.md maps to database; citing domain models is related persistence evidence."""
    _write_wiki_page(
        tmp_path,
        "核心服务/Db.md",
        """# Db

## Users table

The users table is backed by the domain user model.

<cite>app/models/domain/users.py:1</cite>
""",
    )

    result = _verify(tmp_path)
    assert "QODER_CITATION_RELEVANCE_MISMATCH" not in result.get("hard_gate_codes", [])
    assert _relevance_check(result)["status"] in {"PASS", "WARN", "SKIP"}


def test_billing_page_citing_auth_only_path_still_relevance_mismatch(tmp_path: Path) -> None:
    """True wrong-service binds stay HARD. Do not relax the gate."""
    _write_wiki_page(
        tmp_path,
        "billing-service.md",
        """# Billing Service

The billing service handles payments and subscriptions.

<cite>src/auth/session.py:1</cite>
""",
    )

    result = _verify(tmp_path)
    assert "QODER_CITATION_RELEVANCE_MISMATCH" in result.get("hard_gate_codes", [])
    relevance = _relevance_check(result)
    assert relevance["status"] == "FAIL"
    assert relevance["reason_code"] == "QODER_CITATION_RELEVANCE_MISMATCH"
    assert relevance["gate_type"] == "HARD"


def test_unrelated_service_page_citing_other_service_still_relevance_mismatch(
    tmp_path: Path,
) -> None:
    """Unrelated service A citing service B implementation still HARD-fails."""
    _write_wiki_page(
        tmp_path,
        "api-overview.md",
        """# API Overview

## Services

<cite>src/billing/subscription.py:5</cite>
""",
    )

    result = _verify(tmp_path)
    assert "QODER_CITATION_RELEVANCE_MISMATCH" in result.get("hard_gate_codes", [])
    relevance = _relevance_check(result)
    assert relevance["status"] == "FAIL"
    assert relevance["reason_code"] == "QODER_CITATION_RELEVANCE_MISMATCH"


def test_citation_relevance_mismatch_gate_remains_hard() -> None:
    """Do not drop, rename, or soften QODER_CITATION_RELEVANCE_MISMATCH."""
    threshold = QoderLikeSeverityThreshold()
    assert "QODER_CITATION_RELEVANCE_MISMATCH" in threshold.STRICT_HARD_CODES
