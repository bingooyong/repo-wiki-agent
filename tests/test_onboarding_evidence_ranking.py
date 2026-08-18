"""Onboarding pages must rank README / settings / main / auth files first."""

from __future__ import annotations

from repo_wiki.evidence.ranking import score_evidence_for_page
from repo_wiki.orchestration.runtime_store import EvidenceSpanRecord
from repo_wiki.planner.schema import WikiPagePlan, WikiTaxonomyCategory


def _page(page_id: str, title: str, category: WikiTaxonomyCategory) -> WikiPagePlan:
    return WikiPagePlan(
        page_id=page_id,
        title=title,
        category=category,
        output_path=f"docs/pages/{page_id}.md",
    )


def _span(file_path: str, *, symbol: str = "", span_text: str = "span") -> EvidenceSpanRecord:
    return EvidenceSpanRecord(
        digest=file_path,
        file_path=file_path,
        line_start=1,
        line_end=12,
        language="python" if file_path.endswith(".py") else "text",
        symbol=symbol,
        span_text=span_text,
    )


def test_overview_ranks_readme_settings_and_main() -> None:
    page = _page("project-overview", "项目概述", WikiTaxonomyCategory.PROJECT_OVERVIEW)
    readme_score, _ = score_evidence_for_page(
        page, _span("README.rst", symbol="Quickstart", span_text="docker compose DATABASE_URL")
    )
    settings_score, _ = score_evidence_for_page(
        page,
        _span(
            "app/core/settings.py",
            symbol="database_url",
            span_text="DATABASE_URL = postgres://",
        ),
    )
    main_score, _ = score_evidence_for_page(
        page, _span("app/main.py", symbol="app", span_text="FastAPI()")
    )
    unrelated_score, _ = score_evidence_for_page(
        page, _span("app/models/article.py", symbol="Article", span_text="class Article")
    )
    assert readme_score > unrelated_score
    assert settings_score > unrelated_score
    assert main_score > unrelated_score


def test_installation_ranks_readme_and_main() -> None:
    page = _page("installation", "安装指南", WikiTaxonomyCategory.PROJECT_OVERVIEW)
    readme_score, _ = score_evidence_for_page(
        page, _span("README.rst", symbol="Quickstart", span_text="docker compose up")
    )
    main_score, _ = score_evidence_for_page(
        page, _span("app/main.py", symbol="app", span_text="create_application()")
    )
    unrelated_score, _ = score_evidence_for_page(
        page, _span("tests/test_unrelated.py", symbol="test_x", span_text="assert True")
    )
    assert readme_score > unrelated_score
    assert main_score > unrelated_score


def test_security_ranks_authentication_over_readme() -> None:
    page = _page("security-overview", "安全合规概览", WikiTaxonomyCategory.SECURITY_COMPLIANCE)
    auth_score, _ = score_evidence_for_page(
        page,
        _span(
            "app/api/dependencies/authentication.py",
            symbol="RWAPIKeyHeader",
            span_text="class RWAPIKeyHeader",
        ),
    )
    readme_score, _ = score_evidence_for_page(
        page, _span("README.rst", symbol="Quickstart", span_text="docker compose DATABASE_URL")
    )
    assert auth_score > readme_score

    api_page = _page("core-service-apis", "核心服务API", WikiTaxonomyCategory.API_REFERENCE)
    api_readme, _ = score_evidence_for_page(
        api_page, _span("README.rst", symbol="Quickstart", span_text="docker compose")
    )
    api_routes, _ = score_evidence_for_page(
        api_page,
        _span("app/api/routes/authentication.py", symbol="login", span_text="def login()"),
    )
    assert api_routes >= api_readme
