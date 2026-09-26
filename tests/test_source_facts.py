"""Phase C: source facts must match parsed compose/tables/flags/idents/routes."""

from __future__ import annotations

from pathlib import Path

from repo_wiki.verifier.qoder_strict_verifier import (
    QoderLikeSeverityThreshold,
    QoderLikeVerifierService,
)
from repo_wiki.verifier.source_facts import (
    handbook_source_fact_offenders,
    load_cli_flag_help,
    load_compose_service_names,
    load_database_tables,
    load_health_routes,
    source_fact_prompt_block,
)


def _go_repo(root: Path) -> Path:
    (root / "docker-compose.yml").write_text(
        "services:\n  mysql:\n    image: mysql\n  blackbox-exporter:\n    image: bb\n"
        "  ccagent:\n    image: ccagent\n",
        encoding="utf-8",
    )
    (root / "cmd" / "ccprobe-control").mkdir(parents=True)
    (root / "cmd" / "ccagent").mkdir(parents=True)
    (root / "cmd" / "probe-agent").mkdir(parents=True)
    (root / "cmd" / "ccprobe-control" / "main.go").write_text(
        "package main\nfunc main() {\n"
        '  flag.String("agent-url", "http://127.0.0.1:19080", "probe-agent control URL (http transport)")\n'
        '  flag.String("agent-token", "", "probe-agent control token")\n}\n',
        encoding="utf-8",
    )
    (root / "cmd" / "ccagent" / "main.go").write_text(
        'package main\nfunc main() { http.HandleFunc("/health", h); http.HandleFunc("/healthz", z) }\n',
        encoding="utf-8",
    )
    (root / "controller.go").write_text(
        'mux.HandleFunc("/health", health)\nmux.HandleFunc("/create", create)\n',
        encoding="utf-8",
    )
    (root / "README.md").write_text("# probe\n", encoding="utf-8")
    return root


def _fa_repo(root: Path) -> Path:
    versions = root / "app" / "db" / "migrations" / "versions"
    versions.mkdir(parents=True)
    (root / "app" / "db" / "migrations" / "env.py").write_text(
        "target_metadata = None\n",
        encoding="utf-8",
    )
    (versions / "fdf8821871d7_main_tables.py").write_text(
        "def upgrade():\n"
        '    op.create_table("articles_to_tags")\n'
        '    op.create_table("commentaries")\n'
        '    op.create_table("followers_to_followings")\n'
        '    op.create_table("users")\n',
        encoding="utf-8",
    )
    (root / "app" / "api" / "routes").mkdir(parents=True)
    (root / "app" / "api" / "routes" / "articles.py").write_text(
        "def create_article():\n    return 1\n",
        encoding="utf-8",
    )
    (root / "README.rst").write_text(
        "ApplyAuth sample\n\n```python\nclass ApplyAuth:\n    pass\n```\n",
        encoding="utf-8",
    )
    return root


def test_compose_services_are_parsed_from_file(tmp_path: Path) -> None:
    _go_repo(tmp_path)
    assert load_compose_service_names(tmp_path) == {"mysql", "blackbox-exporter", "ccagent"}


def test_health_page_invented_compose_services_fail(tmp_path: Path) -> None:
    _go_repo(tmp_path)
    content = tmp_path / "content"
    content.mkdir()
    (content / "健康检查.md").write_text(
        "# 健康检查\n\n"
        "`docker-compose.yml` 服务定义覆盖 `mysql`、`redis`、`rabbitmq`、`minio`、"
        "`web`、`api`、`worker`、`custom-probe`。\n",
        encoding="utf-8",
    )
    found = handbook_source_fact_offenders(content, tmp_path)
    flat = [item for hits in found.values() for item in hits]
    assert "compose:redis" in flat
    assert "compose:rabbitmq" in flat
    assert "compose:minio" in flat
    assert "compose:web" in flat
    assert "compose:api" in flat
    assert "compose:worker" in flat
    assert "compose:custom-probe" in flat
    assert "compose:mysql" not in flat
    assert "health:missing-source-routes" in flat


def test_health_page_real_services_and_routes_pass(tmp_path: Path) -> None:
    _go_repo(tmp_path)
    content = tmp_path / "content"
    content.mkdir()
    (content / "健康检查.md").write_text(
        "# 健康检查\n\n"
        "`docker-compose.yml` 只有 `mysql`、`blackbox-exporter`、`ccagent`。\n"
        "探活走 `/health` 与 `/healthz`。\n",
        encoding="utf-8",
    )
    found = handbook_source_fact_offenders(content, tmp_path)
    assert found == {}


def test_migration_invented_tables_and_orm_fail(tmp_path: Path) -> None:
    _fa_repo(tmp_path)
    content = tmp_path / "content"
    content.mkdir()
    (content / "数据库迁移.md").write_text(
        "# 数据库迁移\n\n"
        "`env.py` 会 `target_metadata = Base.metadata`，导入 `app.db.models`，"
        "并用 `alembic revision --autogenerate`。\n"
        "表名：`article_tags`、`comments`、`user_followers`。"
        "真实对照应是 `articles_to_tags`。\n",
        encoding="utf-8",
    )
    found = handbook_source_fact_offenders(content, tmp_path)
    flat = [item for hits in found.values() for item in hits]
    assert "table:article_tags" in flat
    assert "table:comments" in flat
    assert "table:user_followers" in flat
    assert "table:articles_to_tags" not in flat
    assert "orm:Base.metadata" in flat
    assert "orm:autogenerate" in flat
    assert any(item.startswith("orm:") and "models" in item for item in flat)


def test_real_migration_tables_pass(tmp_path: Path) -> None:
    _fa_repo(tmp_path)
    assert load_database_tables(tmp_path) >= {
        "articles_to_tags",
        "commentaries",
        "followers_to_followings",
        "users",
    }
    content = tmp_path / "content"
    content.mkdir()
    (content / "数据库迁移.md").write_text(
        "# 数据库迁移\n\n"
        "`env.py` 写着 `target_metadata = None`。"
        "表是 `articles_to_tags`、`commentaries`、`followers_to_followings`。\n",
        encoding="utf-8",
    )
    found = handbook_source_fact_offenders(content, tmp_path)
    assert found == {}


def test_agent_url_must_follow_flag_help(tmp_path: Path) -> None:
    _go_repo(tmp_path)
    flags = load_cli_flag_help(tmp_path)
    assert "probe-agent" in flags["agent-url"]
    content = tmp_path / "content"
    content.mkdir()
    (content / "项目概述.md").write_text(
        "# 概述\n\n`ccprobe-control` 读取 `--agent-url` 向 ccagent 发起控制调用。\n",
        encoding="utf-8",
    )
    found = handbook_source_fact_offenders(content, tmp_path)
    flat = [item for hits in found.values() for item in hits]
    assert "flag:agent-url" in flat
    (content / "项目概述.md").write_text(
        "# 概述\n\n`--agent-url` 是 probe-agent 的控制面 URL。\n",
        encoding="utf-8",
    )
    assert handbook_source_fact_offenders(content, tmp_path) == {}


def test_missing_class_and_readme_sample_as_api(tmp_path: Path) -> None:
    _fa_repo(tmp_path)
    content = tmp_path / "content"
    content.mkdir()
    (content / "核心服务API.md").write_text(
        "# 核心服务API\n\n由 `AuthenticationRequired` 触发仓储注入。\n",
        encoding="utf-8",
    )
    (content / "身份认证.md").write_text(
        "# 身份认证\n\n接口合同是 `ApplyAuth`。\n",
        encoding="utf-8",
    )
    found = handbook_source_fact_offenders(content, tmp_path)
    flat = [item for hits in found.values() for item in hits]
    assert "ident:AuthenticationRequired" in flat
    assert "ident:ApplyAuth" in flat


def test_route_cite_must_point_at_handler_file(tmp_path: Path) -> None:
    _go_repo(tmp_path)
    content = tmp_path / "content"
    content.mkdir()
    (content / "API开发指南.md").write_text(
        "# API\n\nPOST /create <cite>cmd/custom-probe/main.go:10-12</cite>\n",
        encoding="utf-8",
    )
    endpoints = [{"method": "POST", "path": "/create", "file_path": "controller.go"}]
    found = handbook_source_fact_offenders(content, tmp_path, endpoints)
    flat = [item for hits in found.values() for item in hits]
    assert any(item.startswith("route-cite:POST /create") for item in flat)
    (content / "API开发指南.md").write_text(
        "# API\n\nPOST /create <cite>controller.go:1-1</cite>\n",
        encoding="utf-8",
    )
    assert handbook_source_fact_offenders(content, tmp_path, endpoints) == {}


def test_prompt_block_lists_parsed_facts(tmp_path: Path) -> None:
    _go_repo(tmp_path)
    assert source_fact_prompt_block(tmp_path) == ""
    block = source_fact_prompt_block(tmp_path, page_id="health-check", title="健康检查")
    assert "`--agent-url`" not in block
    assert "只能使用下列" not in block
    assert "`/health`" in block
    assert load_health_routes(tmp_path)


def test_compose_prompt_includes_parsed_facts(tmp_path: Path) -> None:
    from repo_wiki.generator.composer import ComposerContext, build_composer_input, create_composer
    from repo_wiki.planner.schema import WikiPagePlan, WikiTaxonomyCategory

    _go_repo(tmp_path)
    composer = create_composer()
    composer.workspace_root = tmp_path
    page = WikiPagePlan(
        page_id="health-check",
        title="健康检查",
        category=WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS,
        output_path="故障排除/健康检查.md",
    )
    ctx = ComposerContext(
        repository_name="probe",
        primary_language="go",
        framework="go",
        repository_root=str(tmp_path),
    )
    composer_input = build_composer_input(page, None, ctx)
    prompt = composer._build_compose_prompt(composer_input, composer._build_context(composer_input))
    assert "只能使用下列" not in prompt
    assert "仅出现在说明文档" not in prompt
    assert "probe-agent control URL" not in prompt
    assert "`/health`" in prompt


def test_source_facts_gate_is_registered_hard(tmp_path: Path) -> None:
    assert "QODER_HANDBOOK_SOURCE_FACTS" in QoderLikeSeverityThreshold.STRICT_HARD_CODES
    (tmp_path / "content").mkdir()
    names = [
        check["name"]
        for check in QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)["checks"]
    ]
    assert "qoder-handbook-source-facts" in names
    _go_repo(tmp_path)
    (tmp_path / "content" / "健康检查.md").write_text(
        "# 健康检查\n\n`docker-compose.yml` 覆盖 `redis`。\n",
        encoding="utf-8",
    )
    result = QoderLikeVerifierService(tmp_path, strict=True)._check_handbook_source_facts()
    assert result.status == "FAIL"
    assert result.reason_code == "QODER_HANDBOOK_SOURCE_FACTS"
