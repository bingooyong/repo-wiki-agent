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
    assert contains_generator_meta("本页由 fallback composer 生成。") is True


def test_contains_generator_meta_detects_chinese_page_id_template() -> None:
    assert contains_generator_meta("该页面对应 `project-overview`，由 repo-agent 写出。") is True


def test_contains_generator_meta_ignores_innocent_readme() -> None:
    assert contains_generator_meta("按 README.rst Quickstart 安装 PostgreSQL。") is False


def _write_page(root: Path, name: str, body: str) -> None:
    path = root / "content" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_handbook_hard_codes_are_registered_strict(tmp_path: Path) -> None:
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
    result = QoderLikeVerifierService(tmp_path, strict=True)._check_handbook_generator_meta()
    assert result.status == "FAIL"
    assert result.reason_code == "QODER_HANDBOOK_GENERATOR_META"


def test_generator_meta_passes_clean_markdown(tmp_path: Path) -> None:
    _write_page(
        tmp_path,
        "project-overview.md",
        "# 项目概述\n\nConduit 是 RealWorld 规范的 FastAPI 后端。\n",
    )
    result = QoderLikeVerifierService(tmp_path, strict=True)._check_handbook_generator_meta()
    assert result.status == "PASS"
    assert result.reason_code != "QODER_HANDBOOK_GENERATOR_META"


def test_overview_identity_skips_when_absent(tmp_path: Path) -> None:
    _write_page(tmp_path, "unrelated.md", "# Other\n")
    result = QoderLikeVerifierService(tmp_path, strict=True)._check_handbook_overview_identity()
    assert result.status == "PASS"
    assert result.reason_code != "QODER_HANDBOOK_OVERVIEW_IDENTITY" or "Skip" in result.message


def test_overview_identity_fails_without_identity(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "Conduit is a RealWorld FastAPI backend.\n", encoding="utf-8"
    )
    _write_page(tmp_path, "project-overview.md", "# 项目概述\n\n这是一个通用 API 服务。\n")
    result = QoderLikeVerifierService(tmp_path, strict=True)._check_handbook_overview_identity()
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
    result = QoderLikeVerifierService(tmp_path, strict=True)._check_handbook_overview_identity()
    assert result.status == "PASS"


def test_overview_identity_passes_with_slug_matching_display_name(tmp_path: Path) -> None:
    """display_name 'Novel Agent' must match page token novel-agent."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "novel-agent"\n',
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# Novel Agent\n\nWriting desk.\n", encoding="utf-8")
    _write_page(
        tmp_path,
        "project-overview.md",
        "# 项目概述\n\nnovel-agent 提供本地写作工作台。\n",
    )
    result = QoderLikeVerifierService(tmp_path, strict=True)._check_handbook_overview_identity()
    assert result.status == "PASS"
    assert result.reason_code != "QODER_HANDBOOK_OVERVIEW_IDENTITY"


def test_overview_identity_passes_with_directory_identity_token(tmp_path: Path) -> None:
    repo = tmp_path / "ai-open-writing"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "novel-agent"\n', encoding="utf-8")
    (repo / "README.md").write_text("# Novel Agent\n\nWriting desk.\n", encoding="utf-8")
    _write_page(
        repo,
        "project-overview.md",
        "# 项目概述\n\nai-open-writing 是该仓库的产品身份。\n",
    )
    result = QoderLikeVerifierService(repo, strict=True)._check_handbook_overview_identity()
    assert result.status == "PASS"
    assert result.reason_code != "QODER_HANDBOOK_OVERVIEW_IDENTITY"


def test_overview_identity_ignores_key_features_sibling_under_overview_folder(
    tmp_path: Path,
) -> None:
    (tmp_path / "README.md").write_text(
        "Conduit is a RealWorld FastAPI backend.\n", encoding="utf-8"
    )
    _write_page(
        tmp_path,
        "项目概述/项目概述.md",
        "# 项目概述\n\nConduit 是 RealWorld 规范的 FastAPI 后端。\n",
    )
    _write_page(
        tmp_path,
        "项目概述/核心功能特性/核心功能特性.md",
        "# 核心功能特性\n\n本页目前无法根据仓库内容写成可用说明。\n",
    )
    result = QoderLikeVerifierService(tmp_path, strict=True)._check_handbook_overview_identity()
    assert result.status == "PASS"
    assert result.reason_code != "QODER_HANDBOOK_OVERVIEW_IDENTITY"


def test_overview_identity_skips_when_only_key_features_under_overview_folder(
    tmp_path: Path,
) -> None:
    _write_page(
        tmp_path,
        "项目概述/核心功能特性/核心功能特性.md",
        "# 核心功能特性\n\n没有身份陈述。\n",
    )
    result = QoderLikeVerifierService(tmp_path, strict=True)._check_handbook_overview_identity()
    assert result.status == "PASS"
    assert result.reason_code != "QODER_HANDBOOK_OVERVIEW_IDENTITY" or "Skip" in result.message


def test_install_run_fails_without_run_clues(tmp_path: Path) -> None:
    (tmp_path / "README.rst").write_text(
        "Quickstart\n==========\n\ndocker compose\n", encoding="utf-8"
    )
    _write_page(
        tmp_path,
        "installation.md",
        "# 安装指南\n\n请阅读入口文件再追踪模型层。\n\n<cite>app/main.py:1-4</cite>\n",
    )
    result = QoderLikeVerifierService(tmp_path, strict=True)._check_handbook_install_run()
    assert result.status == "FAIL"
    assert result.reason_code == "QODER_HANDBOOK_INSTALL_RUN"


def test_install_run_passes_with_run_clues(tmp_path: Path) -> None:
    (tmp_path / "README.rst").write_text(
        "Quickstart\n==========\n\nSet DATABASE_URL then docker compose up.\n",
        encoding="utf-8",
    )
    _write_page(
        tmp_path,
        "installation.md",
        "# 安装指南\n\n设置 DATABASE_URL 后执行 docker compose up。 <cite>README.rst:3-5</cite>\n",
    )
    result = QoderLikeVerifierService(tmp_path, strict=True)._check_handbook_install_run()
    assert result.status == "PASS"


def test_install_run_passes_with_uv_and_npm_from_readme(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "# Novel Agent\n\n```bash\nuv sync\nuv run novel init\ncd writing-desk && npm install\n```\n"
        "SQLite is the default database.\n",
        encoding="utf-8",
    )
    _write_page(
        tmp_path,
        "installation.md",
        "# 安装指南\n\n先 `uv sync`，再 `npm install` 启动 writing-desk。"
        " <cite>README.md:3-8</cite>\n",
    )
    result = QoderLikeVerifierService(tmp_path, strict=True)._check_handbook_install_run()
    assert result.status == "PASS"
    assert result.reason_code != "QODER_HANDBOOK_INSTALL_RUN"


def test_install_run_fails_when_page_only_says_clone(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "# Novel Agent\n\nClone the repo, then `uv sync` and `npm install`.\n",
        encoding="utf-8",
    )
    _write_page(
        tmp_path,
        "installation.md",
        "# 安装指南\n\nClone the repo and start reading.\n\n<cite>README.md:1-4</cite>\n",
    )
    result = QoderLikeVerifierService(tmp_path, strict=True)._check_handbook_install_run()
    assert result.status == "FAIL"
    assert result.reason_code == "QODER_HANDBOOK_INSTALL_RUN"


def test_api_route_file_requires_routes_cite(tmp_path: Path) -> None:
    _write_page(
        tmp_path,
        "core-service-apis.md",
        "# 核心服务API\n\n模型在数据库层。 <cite>app/db/queries.py:1-8</cite>\n",
    )
    fail = QoderLikeVerifierService(tmp_path, strict=True)._check_handbook_api_route_file()
    assert fail.status == "FAIL"
    assert fail.reason_code == "QODER_HANDBOOK_API_ROUTE_FILE"


def test_api_route_file_passes_with_routes_cite(tmp_path: Path) -> None:
    _write_page(
        tmp_path,
        "core-service-apis.md",
        "# 核心服务API\n\n登录路由在 <cite>app/api/routes/authentication.py:10-40</cite>。\n",
    )
    passed = QoderLikeVerifierService(tmp_path, strict=True)._check_handbook_api_route_file()
    assert passed.status == "PASS"
