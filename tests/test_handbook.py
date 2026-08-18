"""Handbook wiki generator-meta helpers and HARD checks."""

from __future__ import annotations

from pathlib import Path

from repo_wiki.verifier.handbook import contains_generator_meta
from repo_wiki.verifier.qoder_strict_verifier import (
    QoderLikeSeverityThreshold,
    QoderLikeVerifierService,
)

HANDBOOK_HARD_CODES = (
    "QODER_HANDBOOK_GENERATOR_META",
    "QODER_HANDBOOK_OVERVIEW_IDENTITY",
    "QODER_HANDBOOK_INSTALL_RUN",
    "QODER_HANDBOOK_API_ROUTE_FILE",
)


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


def _write_page(root: Path, name: str, body: str) -> None:
    content = root / "content"
    content.mkdir(parents=True, exist_ok=True)
    (content / name).write_text(body, encoding="utf-8")


def test_handbook_hard_codes_are_strict(tmp_path: Path) -> None:
    codes = QoderLikeSeverityThreshold.STRICT_HARD_CODES
    for code in HANDBOOK_HARD_CODES:
        assert code in codes
    (tmp_path / "content").mkdir()
    names = [
        check["name"]
        for check in QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)["checks"]
    ]
    assert "qoder-handbook-generator-meta" in names
    assert "qoder-handbook-overview-identity" in names
    assert "qoder-handbook-install-run" in names
    assert "qoder-handbook-api-route-file" in names


def test_coverage_and_degraded_remain_hard() -> None:
    codes = QoderLikeSeverityThreshold.STRICT_HARD_CODES
    assert "QODER_CITATION_FACT_COVERAGE_LOW" in codes
    assert "QODER_PAGE_QUALITY_STATE_DEGRADED" in codes


def test_generator_meta_fails_when_phrase_present(tmp_path: Path) -> None:
    _write_page(tmp_path, "project-overview.md", "# 概述\n\n本页由 fallback composer 生成。\n")
    result = QoderLikeVerifierService(tmp_path, strict=True)._check_qoder_handbook_generator_meta()
    assert result.status == "FAIL"
    assert result.reason_code == "QODER_HANDBOOK_GENERATOR_META"


def test_generator_meta_skips_when_no_markdown(tmp_path: Path) -> None:
    (tmp_path / "content").mkdir()
    result = QoderLikeVerifierService(tmp_path, strict=True)._check_qoder_handbook_generator_meta()
    assert result.status == "PASS"
    assert result.reason_code in ("", "QODER_HANDBOOK_GENERATOR_META")


def test_overview_identity_skips_when_page_absent(tmp_path: Path) -> None:
    _write_page(tmp_path, "unrelated.md", "# Other\n")
    result = QoderLikeVerifierService(
        tmp_path, strict=True
    )._check_qoder_handbook_overview_identity()
    assert result.status == "PASS"
    assert result.reason_code != "QODER_HANDBOOK_OVERVIEW_IDENTITY" or "Skip" in result.message


def test_overview_identity_fails_without_identity(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "Conduit is a RealWorld FastAPI backend.\n", encoding="utf-8"
    )
    _write_page(tmp_path, "project-overview.md", "# 项目概述\n\n这是一个通用 API 服务。\n")
    result = QoderLikeVerifierService(
        tmp_path, strict=True
    )._check_qoder_handbook_overview_identity()
    assert result.status == "FAIL"
    assert result.reason_code == "QODER_HANDBOOK_OVERVIEW_IDENTITY"


def test_overview_identity_passes_with_identity(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "Conduit is a RealWorld FastAPI backend.\n", encoding="utf-8"
    )
    _write_page(
        tmp_path,
        "project-overview.md",
        "# 项目概述\n\nConduit 是 RealWorld 规范的 FastAPI 后端。\n",
    )
    result = QoderLikeVerifierService(
        tmp_path, strict=True
    )._check_qoder_handbook_overview_identity()
    assert result.status == "PASS"


def test_install_run_fails_without_run_clues(tmp_path: Path) -> None:
    (tmp_path / "README.rst").write_text(
        "Quickstart\n==========\n\ndocker compose\n", encoding="utf-8"
    )
    _write_page(
        tmp_path,
        "installation.md",
        "# 安装指南\n\n请阅读入口文件再追踪模型层。\n\n<cite>app/main.py:1-4</cite>\n",
    )
    result = QoderLikeVerifierService(tmp_path, strict=True)._check_qoder_handbook_install_run()
    assert result.status == "FAIL"
    assert result.reason_code == "QODER_HANDBOOK_INSTALL_RUN"


def test_install_run_passes_with_run_clues_and_readme_cite(tmp_path: Path) -> None:
    (tmp_path / "README.rst").write_text(
        "Quickstart\n==========\n\nSet DATABASE_URL then docker compose up.\n",
        encoding="utf-8",
    )
    _write_page(
        tmp_path,
        "installation.md",
        "# 安装指南\n\n设置 DATABASE_URL 后执行 docker compose up。 <cite>README.rst:3-5</cite>\n",
    )
    result = QoderLikeVerifierService(tmp_path, strict=True)._check_qoder_handbook_install_run()
    assert result.status == "PASS"


def test_api_route_file_requires_routes_cite(tmp_path: Path) -> None:
    _write_page(
        tmp_path,
        "core-service-apis.md",
        "# 核心服务API\n\n模型在数据库层。 <cite>app/db/queries.py:1-8</cite>\n",
    )
    fail = QoderLikeVerifierService(tmp_path, strict=True)._check_qoder_handbook_api_route_file()
    assert fail.status == "FAIL"
    assert fail.reason_code == "QODER_HANDBOOK_API_ROUTE_FILE"

    _write_page(
        tmp_path,
        "core-service-apis.md",
        "# 核心服务API\n\n登录路由在 <cite>app/api/routes/authentication.py:10-40</cite>。\n",
    )
    passed = QoderLikeVerifierService(tmp_path, strict=True)._check_qoder_handbook_api_route_file()
    assert passed.status == "PASS"
