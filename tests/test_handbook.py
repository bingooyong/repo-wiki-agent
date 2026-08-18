"""Handbook wiki generator-meta helpers and HARD checks."""

from __future__ import annotations

from repo_wiki.verifier.handbook import contains_generator_meta


def test_contains_generator_meta_detects_fallback_composer() -> None:
    markdown = (
        "该页由 fallback composer 生成，用于补齐 LLM 失败后的页面。"
        "下面列出 evidence ranking 结果，并提到 repo-agent 流水线。"
    )
    assert contains_generator_meta(markdown) is True


def test_contains_generator_meta_detects_chinese_page_id_template() -> None:
    markdown = "该页面对应 `project-overview`，请对照 page_id 阅读。"
    assert contains_generator_meta(markdown) is True


def test_contains_generator_meta_ignores_innocent_readme() -> None:
    markdown = (
        "Conduit is a RealWorld example backend written with FastAPI.\n"
        "Install PostgreSQL, set DATABASE_URL, then run docker compose up.\n"
        "Authentication uses RWAPIKeyHeader in app/api/dependencies/authentication.py.\n"
    )
    assert contains_generator_meta(markdown) is False
