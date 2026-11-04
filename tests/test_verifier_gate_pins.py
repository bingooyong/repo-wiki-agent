"""Pinned verifier thresholds. Any future loosening must show up as a test diff."""

from __future__ import annotations

from repo_wiki.verifier.handbook import (
    _DOC_MISMATCH_SKIP,
    _EVIDENCE_META_TALK_RE,
    MIN_HANDBOOK_BODY_CHARS,
    architecture_required_packages,
    contains_evidence_meta_talk,
    handbook_doc_code_mismatches,
    has_architecture_core_citation,
    overview_identity_satisfied,
)
from repo_wiki.verifier.qoder_strict_verifier import (
    REPEATED_FILLER_MIN_LINE_LEN,
    REPEATED_FILLER_MIN_LINE_REPEATS,
    REPEATED_FILLER_MIN_PARAGRAPH_LEN,
    REPEATED_FILLER_MIN_PARAGRAPH_REPEATS,
    QoderLikeSeverityThreshold,
    QoderLikeVerifierService,
)
from repo_wiki.verifier.source_evidence import MIN_HANDBOOK_CITATIONS
from repo_wiki.verifier.source_facts import (
    _GENERIC_COMPOSE,
    _GENERIC_TABLES,
    _GENERIC_TYPES,
    _NOT_SERVICE_TOKENS,
)


def test_pinned_verifier_gate_thresholds() -> None:
    """Read the live constants. Both sides of each assert come from code."""
    service = QoderLikeVerifierService
    threshold = QoderLikeSeverityThreshold
    assert MIN_HANDBOOK_BODY_CHARS == 800
    assert service.MIN_PROSE_DENSITY == 0.30
    assert service.MAX_LIST_RATIO == 0.6
    assert service.MIN_MERMAID_COVERAGE == 0.3
    assert service.MIN_TOC_COVERAGE == 0.8
    assert service.MIN_FILE_LINE_COVERAGE == 0.7
    assert MIN_HANDBOOK_CITATIONS == 20
    assert service.CLAIM_CITATION_FLOOR == 0.95
    assert service.DEGRADED_STATE_TOKENS == ("fallback", "degraded")
    assert REPEATED_FILLER_MIN_PARAGRAPH_LEN == 40
    assert REPEATED_FILLER_MIN_PARAGRAPH_REPEATS == 4
    assert REPEATED_FILLER_MIN_LINE_LEN == 40
    assert REPEATED_FILLER_MIN_LINE_REPEATS == 8
    assert set(threshold.STRICT_HARD_CODES) == threshold.STRICT_HARD_CODES
    assert {
        "QODER_CONTENT_EMPTY",
        "QODER_CITATION_MISSING",
        "QODER_CITATION_RELEVANCE_MISMATCH",
        "QODER_TOC_MISSING",
        "QODER_FILE_REF_BROKEN",
        "QODER_PAGE_DUMP",
        "QODER_PROSE_TOO_LOW",
        "QODER_FILE_LINE_REF_LOW",
        "QODER_MERMAID_LOW",
        "QODER_API_AGGREGATION_LOW",
        "QODER_DATA_MODEL_AGGREGATION_LOW",
        "QODER_STALE_GIT_COMMIT",
        "QODER_DIRTY_WORKTREE",
        "QODER_ENDPOINT_PAGE_DUMP",
        "QODER_RAW_MODEL_PAGE_DUMP",
        "QODER_MANIFEST_NOT_READY",
        "QODER_MANIFEST_PATH_INVALID",
        "QODER_CONTENT_ROOT_MISSING",
        "QODER_META_ROOT_MISSING",
        "QODER_REPORT_MISMATCH",
        "QODER_API_MERMAID_MISSING",
        "QODER_ENDPOINT_LIFECYCLE_MERMAID_MISSING",
        "QODER_DATA_MODEL_ER_MERMAID_MISSING",
        "QODER_MANIFEST_MISSING",
        "QODER_QUALITY_ARTIFACT_MISSING",
        "QODER_QUALITY_ARTIFACT_INVALID",
        "QODER_PAGE_QUALITY_STATE_MISSING",
        "QODER_PAGE_QUALITY_STATE_DEGRADED",
        "QODER_UNRESOLVED_FACT_CONFLICT",
        "QODER_CRITICAL_FALSE_FACT",
        "QODER_CITATION_INVALID",
        "QODER_CITATION_FACT_COVERAGE_LOW",
        "QODER_REQUIRED_INVENTORY_MISSING",
        "QODER_OWNER_COVERAGE_MISSING",
        "QODER_CONFLICT_ARTIFACT_MISSING",
        "QODER_CONFLICT_ARTIFACT_INVALID",
        "QODER_HANDBOOK_GENERATOR_META",
        "QODER_HANDBOOK_OVERVIEW_IDENTITY",
        "QODER_HANDBOOK_INSTALL_RUN",
        "QODER_HANDBOOK_INSTALL_FENCE",
        "QODER_HANDBOOK_API_ROUTE_FILE",
        "QODER_HANDBOOK_ARCHITECTURE_CORE",
        "QODER_HANDBOOK_DATA_MODEL_SOURCE",
        "QODER_HANDBOOK_PLACEHOLDER_MERMAID",
        "QODER_HANDBOOK_READER_HYGIENE",
        "QODER_HANDBOOK_UNKNOWN_PROCESS",
        "QODER_HANDBOOK_CODE_INTEGRITY",
        "QODER_HANDBOOK_DOC_CODE_MISMATCH",
        "QODER_HANDBOOK_DIAGRAM_EVIDENCE",
        "QODER_HANDBOOK_INSTALL_PATH",
        "QODER_HANDBOOK_IMPORT_CONSISTENCY",
        "QODER_HANDBOOK_ROLE_CONSISTENCY",
        "QODER_HANDBOOK_SOURCE_FACTS",
        "QODER_HANDBOOK_ROUTE_CROSSCHECK",
        "QODER_HANDBOOK_DROPPED_CORE",
        "QODER_SOURCE_EVIDENCE_LOW",
        "SOURCE_DOC_MISMATCH",
        "STALE_DOC_REFERENCE",
        "UNSUPPORTED_DOC_CLAIM",
        "MISSING_SOURCE_CONFIRMATION",
    } == threshold.STRICT_HARD_CODES
    assert {
        "CONTENT_LIST_ONLY",
        "CONTENT_TOO_SHORT",
        "CONTENT_MISSING_SECTIONS",
        "AGG_API_NOT_GROUPED",
        "AGG_API_ENDPOINT_DUMP",
        "AGG_DM_NOT_GROUPED",
        "AGG_DM_MODEL_DUMP",
        "CITATION_MISSING",
        "CITATION_BROKEN_PATH",
    } == threshold.STRICT_SOFT_TO_HARD
    assert (
        frozenset(
            {
                "Docker",
                "GitHub",
                "LICENSE",
                "Makefile",
                "Caddyfile",
                "TestClient",
                "Readme",
                "Bearer",
            }
        )
        == _DOC_MISMATCH_SKIP
    )
    assert (
        frozenset(
            {
                "FastAPI",
                "PostgreSQL",
                "SQLAlchemy",
                "Alembic",
                "HTTPException",
                "Depends",
                "Docker",
                "GitHub",
                "Dockerfile",
                "Makefile",
                "Handle",
            }
        )
        == _GENERIC_TYPES
    )
    assert "schema" in _GENERIC_TABLES
    assert "healthcheck" in _GENERIC_COMPOSE
    assert "depends" in _NOT_SERVICE_TOKENS


def test_meta_talk_must_and_must_not_match() -> None:
    must_fail = (
        "提供的证据未覆盖中间件",
        "证据范围限定于认证依赖与路由装饰器。",
        "当前证据集中在迁移 revision 的 upgrade。",
        "虽然用户当前没有指定模块，仍按仓库扫描结果写。",
        "用户没有指定要展开的模块。",
        "用户未指定页面范围。",
        "证据片段不足以描述中间件。",
    )
    must_pass = (
        "认证依赖与路由装饰器共同完成登录。",
        "中间件在请求进入路由前解析令牌。",
        "用户注册成功后写入 followers 表。",
    )
    for sentence in must_fail:
        assert contains_evidence_meta_talk(sentence), sentence
    for sentence in must_pass:
        assert contains_evidence_meta_talk(sentence) is False, sentence
    assert "用户(?:当前)?(?:没有|未)指定" in _EVIDENCE_META_TALK_RE.pattern


def test_overview_identity_ignores_random_readme_words(tmp_path) -> None:
    (tmp_path / "README.md").write_text(
        "# Sample Service\n\nQuickstart image backend note documentation.\n",
        encoding="utf-8",
    )
    page = "# 项目概述\n\nThis image backend documentation is ready.\n"
    assert overview_identity_satisfied(page, tmp_path) is False
    assert overview_identity_satisfied("# 项目概述\n\nSample Service 面向开发者。\n", tmp_path)


def test_architecture_cores_are_entries_not_every_package(tmp_path) -> None:
    (tmp_path / "cmd" / "web").mkdir(parents=True)
    (tmp_path / "cmd" / "worker").mkdir(parents=True)
    (tmp_path / "cmd" / "example-probe").mkdir(parents=True)
    (tmp_path / "internal" / "services").mkdir(parents=True)
    (tmp_path / "cmd" / "web" / "main.go").write_text(
        'package main\nfunc main() { http.ListenAndServe(":80", mux) }\n'
        'mux.HandleFunc("/health", h)\n',
        encoding="utf-8",
    )
    (tmp_path / "cmd" / "worker" / "main.go").write_text(
        "package main\n// data-plane execution pool\nfunc main() { runPool() }\n",
        encoding="utf-8",
    )
    (tmp_path / "cmd" / "example-probe" / "main.go").write_text(
        "package main\n// example scaffold demo\nfunc main() {}\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# demo\n\nRun ./bin/web then curl.\n", encoding="utf-8")
    required = architecture_required_packages(tmp_path)
    assert "cmd/web" in required
    assert "cmd/example-probe" not in required
    assert "internal/services" not in required
    missing_entry = "# 架构\n<cite>cmd/example-probe/main.go:1-2</cite>\n"
    assert has_architecture_core_citation(missing_entry, tmp_path) is False
    complete = "# 架构\n" + "".join(f"<cite>{rel}/main.go:1-2</cite>\n" for rel in required)
    assert has_architecture_core_citation(complete, tmp_path) is True


def test_doc_mismatch_flags_readme_code_not_tool_names(tmp_path) -> None:
    (tmp_path / "README.md").write_text(
        "# Demo\n\n```go\nfunc (s *S) ApplyAuth() {}\ntype CustomAuth struct{}\n```\n"
        "See Docker GitHub LICENSE Makefile Caddyfile.\n",
        encoding="utf-8",
    )
    (tmp_path / "auth.go").write_text(
        "package auth\ntype Authenticator struct{}\nfunc (a Authenticator) Apply() {}\n",
        encoding="utf-8",
    )
    content = tmp_path / "content"
    content.mkdir()
    (content / "auth.md").write_text(
        "# 身份认证\n\n接口是 `ApplyAuth` 与 `CustomAuth`，"
        "也提到 `Docker` `GitHub` `LICENSE` `Makefile` `Caddyfile` `TestClient`。\n",
        encoding="utf-8",
    )
    found = handbook_doc_code_mismatches(content, tmp_path)
    names = found[str(content / "auth.md")]
    assert "ApplyAuth" in names
    assert "CustomAuth" in names
    assert "Docker" not in names
    assert "TestClient" not in names
