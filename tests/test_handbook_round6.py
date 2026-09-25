"""Round 6 handbook gates: mermaid copies, cites, ER FKs, conflicts, install."""

from __future__ import annotations

from pathlib import Path

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.evidence.citation_renderer import normalize_citation_markup
from repo_wiki.generator.mermaid_planner import (
    MermaidDiagramType,
    extract_python_app_import_edges,
    mermaid_ident,
    validate_mermaid_syntax,
)
from repo_wiki.orchestration.service import RepoWikiService
from repo_wiki.planner.identity import resolve_repository_identity
from repo_wiki.planner.rule_first import RuleFirstPlanner
from repo_wiki.scanner.conflict_resolver import (
    MISSING_SOURCE_CONFIRMATION,
    SOURCE_DOC_MISMATCH,
    resolve_source_docs_conflicts,
)
from repo_wiki.scanner.go_routes import extract_go_data_models, extract_sql_foreign_keys
from repo_wiki.scanner.repository_scanner import RepositoryScanner
from repo_wiki.verifier.handbook import (
    collect_repo_install_commands,
    handbook_duplicate_mermaid_groups,
    handbook_duplicate_schema_groups,
    handbook_reserved_mermaid_id_pages,
    handbook_thin_mermaid_pages,
    has_data_model_source_citation,
    has_readme_run_section_citation,
    mermaid_block_is_generic_placeholder,
    normalize_mermaid_block,
)
from repo_wiki.verifier.qoder_parity_metrics import ParityMetricExtractor
from repo_wiki.verifier.qoder_strict_verifier import QoderLikeVerifierService


def _go_schema() -> str:
    return """
CREATE TABLE IF NOT EXISTS probe_endpoints (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    probe_type ENUM('blackbox', 'custom', 'local') NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS probe_tags (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    endpoint_id BIGINT NOT NULL,
    FOREIGN KEY (endpoint_id) REFERENCES probe_endpoints(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS biz_tree_node (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    parent_id BIGINT NULL,
    FOREIGN KEY (parent_id) REFERENCES biz_tree_node(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS biz_instance_endpoint (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    service_id BIGINT NOT NULL,
    FOREIGN KEY (service_id) REFERENCES biz_tree_node(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS probe_policy (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    service_id BIGINT NOT NULL,
    FOREIGN KEY (service_id) REFERENCES biz_tree_node(id) ON DELETE CASCADE
) ENGINE=InnoDB;
"""


def _go_models() -> str:
    return """
package models

type ProbeEndpoint struct {
    ID   int64      `gorm:"primaryKey;column:id"`
    Tags []ProbeTag `gorm:"foreignKey:EndpointID"`
}
func (ProbeEndpoint) TableName() string { return "probe_endpoints" }

type ProbeTag struct {
    ID         int64          `gorm:"primaryKey;column:id"`
    EndpointID int64          `gorm:"column:endpoint_id"`
    Endpoint   *ProbeEndpoint `gorm:"foreignKey:EndpointID"`
}
func (ProbeTag) TableName() string { return "probe_tags" }

type BizTreeNode struct {
    ID       int64  `gorm:"primaryKey;column:id"`
    ParentID *int64 `gorm:"column:parent_id"`
}
func (BizTreeNode) TableName() string { return "biz_tree_node" }

type BizInstanceEndpoint struct {
    ID        int64 `gorm:"primaryKey;column:id"`
    ServiceID int64 `gorm:"column:service_id"`
}
func (BizInstanceEndpoint) TableName() string { return "biz_instance_endpoint" }

type ProbePolicy struct {
    ID        int64 `gorm:"primaryKey;column:id"`
    ServiceID int64 `gorm:"column:service_id"`
}
func (ProbePolicy) TableName() string { return "probe_policy" }

type ProbeResult struct {
    ID         int64 `gorm:"primaryKey;column:id"`
    EndpointID int64 `gorm:"column:endpoint_id"`
}
func (ProbeResult) TableName() string { return "probe_results" }
"""


def test_sql_fks_respect_engine_tables_and_enums() -> None:
    fks = extract_sql_foreign_keys(_go_schema())
    pairs = {(src, col, dest) for src, col, dest in fks}
    assert ("probe_tags", "endpoint_id", "probe_endpoints") in pairs
    assert ("biz_instance_endpoint", "service_id", "biz_tree_node") in pairs
    assert ("probe_policy", "service_id", "biz_tree_node") in pairs
    assert ("probe_endpoints", "endpoint_id", "probe_endpoints") not in pairs
    assert not any(col in {"FOREIGN", "外键约束"} for _src, col, _dest in fks)


def test_real_style_gorm_fks_skip_endpoint_self_loop() -> None:
    models = extract_go_data_models(
        [
            ("internal/models/models.go", _go_models()),
            ("db/schema.sql", _go_schema()),
        ]
    )
    by_name = {model.name: model for model in models}
    assert "belongs_to:ProbeEndpoint" not in by_name["ProbeEndpoint"].relations
    assert "belongs_to:ProbeEndpoint" in by_name["ProbeTag"].relations
    assert "belongs_to:BizTreeNode" in by_name["BizInstanceEndpoint"].relations
    assert "belongs_to:BizTreeNode" in by_name["ProbePolicy"].relations
    assert "belongs_to:ProbeEndpoint" in by_name["ProbeResult"].relations


def test_duplicate_and_thin_mermaid_fail_placeholder_check(tmp_path: Path) -> None:
    content = tmp_path / "content"
    content.mkdir()
    copied = "```mermaid\nflowchart TD\n  A[internal/control] --> B[internal/services]\n  B --> C[internal/repository]\n```\n"
    thin = "```mermaid\nflowchart TD\n  routes[app/api/routes]\n```\n"
    for name in ("a.md", "b.md", "c.md"):
        (content / name).write_text("# x\n" + copied, encoding="utf-8")
    (content / "thin.md").write_text("# y\n" + thin, encoding="utf-8")
    groups = handbook_duplicate_mermaid_groups(content, max_copies=2)
    assert groups
    assert handbook_thin_mermaid_pages(content)
    verifier = QoderLikeVerifierService(tmp_path, strict=True)
    result = verifier._check_handbook_placeholder_mermaid()
    assert result.status == "FAIL"


def test_mermaid_ident_sanitizes_reserved_end() -> None:
    assert mermaid_ident("end").lower() != "end"
    ok, err = validate_mermaid_syntax(
        "flowchart TD\n  start((Start)) --> done((End))\n",
        MermaidDiagramType.FLOWCHART,
    )
    assert ok, err
    bad, message = validate_mermaid_syntax(
        "flowchart TD\n  start((Start)) --> end((End))\n",
        MermaidDiagramType.FLOWCHART,
    )
    assert bad is False
    assert "reserved" in message.lower() or "end" in message.lower()


def test_normalize_unwraps_backtick_wrapped_cite() -> None:
    import re

    text = "见 `<cite>app/api/routes/users.py:10-12</cite>` 与 `internal/models/tag.go:4-12`。"
    out = normalize_citation_markup(text)
    assert not re.search(r"`<cite>[^<]+</cite>`", out)
    assert "<cite>app/api/routes/users.py:10-12</cite>" in out
    assert "`internal/models/tag.go`" in out
    verifier = QoderLikeVerifierService(Path("."), strict=True)
    assert verifier._handbook_backtick_cite_pages  # attribute exists after impl


def test_critical_false_facts_ignore_http_status_and_service_method() -> None:
    verifier = QoderLikeVerifierService(Path("."), strict=True)
    services = verifier._extract_structured_name_claims(
        "The service method handles routing for the control plane.", "service"
    )
    models = verifier._extract_structured_name_claims(
        "Upload failed with 413 Request Entity Too Large when the body exceeded the limit.",
        "model",
    )
    assert "method" not in services
    assert "Too" not in models


def test_listen_port_conflict_is_not_double_counted() -> None:
    source = {
        "services": [],
        "api_surfaces": [],
        "data_models": [],
        "frontend_callers": [],
        "deployment_assets": [],
        "tests": [],
    }
    docs = {
        "documents": [
            {
                "path": "README.md",
                "doc_type": "overview",
                "conflict_level": "conflicting",
                "stale_references": [],
                "conflicting_claims": ["listen-port:8000"],
            }
        ]
    }
    report = resolve_source_docs_conflicts(source, docs)
    items = [
        item
        for item in report["deferred_items"]
        if item["doc_path"] == "README.md" and "listen-port:8000" in str(item.get("evidence"))
    ]
    assert len(items) == 1
    assert items[0]["reason_code"] == SOURCE_DOC_MISMATCH
    assert not any(item["reason_code"] == MISSING_SOURCE_CONFIRMATION for item in items)


def test_data_model_citation_requires_struct_range(tmp_path: Path) -> None:
    models = tmp_path / "internal" / "models"
    models.mkdir(parents=True)
    (models / "agent_ops_sample.go").write_text(
        "package models\n\n// sample\n\nfunc Hint() {}\n",
        encoding="utf-8",
    )
    (models / "endpoint.go").write_text(
        'package models\n\ntype ProbeEndpoint struct {\n    ID int64 `gorm:"primaryKey"`\n}\n',
        encoding="utf-8",
    )
    header_only = "# 数据模型\n<cite>internal/models/agent_ops_sample.go:1-8</cite>\n"
    assert has_data_model_source_citation(header_only, tmp_path) is False
    struct_cite = "# 数据模型\n<cite>internal/models/endpoint.go:3-6</cite>\n"
    assert has_data_model_source_citation(struct_cite, tmp_path) is True


def test_heading_only_readme_cite_fails_install_run(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "# demo\n\n"
        "## 快速开始\n"
        "\n"
        "按下列命令启动：\n"
        "\n"
        "```bash\n"
        "podman-compose up -d\n"
        "go build -o bin/ccagent ./cmd/ccagent\n"
        "```\n",
        encoding="utf-8",
    )
    (tmp_path / "cmd" / "ccagent").mkdir(parents=True)
    (tmp_path / "cmd" / "ccagent" / "main.go").write_text("package main\n", encoding="utf-8")
    heading = "安装见 README。 <cite>README.md:3-5</cite>\n"
    assert has_readme_run_section_citation(heading, tmp_path) is False
    commands = "安装见 README。 <cite>README.md:7-10</cite>\n"
    assert has_readme_run_section_citation(commands, tmp_path) is True


def test_collect_install_does_not_mix_compose_and_local_ccagent(tmp_path: Path) -> None:
    (tmp_path / "cmd" / "ccagent").mkdir(parents=True)
    (tmp_path / "cmd" / "ccagent" / "main.go").write_text("package main\n", encoding="utf-8")
    (tmp_path / "podman-compose.yml").write_text(
        "services:\n  ccagent:\n    image: x\n", encoding="utf-8"
    )
    (tmp_path / "db").mkdir()
    (tmp_path / "db" / "schema.sql").write_text("SELECT 1;\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "## 快速开始\n\npodman-compose up -d\nmysql < db/schema.sql\n",
        encoding="utf-8",
    )
    commands = collect_repo_install_commands(tmp_path)
    compose_cmds = [item for item in commands if "podman-compose" in item]
    schema_cmds = [item for item in commands if "schema.sql" in item]
    assert compose_cmds
    assert len(schema_cmds) == 1
    assert not any("./bin/ccagent" in item for item in commands)


def test_data_model_aggregation_ignores_troubleshooting_db_page(tmp_path: Path) -> None:
    content = tmp_path / "content"
    (content / "数据模型").mkdir(parents=True)
    (content / "故障排除").mkdir()
    (content / "数据模型" / "数据模型.md").write_text(
        "# 数据模型\n\n实体关系如下。\n\n```mermaid\nerDiagram\n  User ||--o{ Article : writes\n```\n",
        encoding="utf-8",
    )
    (content / "故障排除" / "数据库问题.md").write_text(
        "# 数据库问题\n\n查看 `db/schema.sql`。\n",
        encoding="utf-8",
    )
    extractor = ParityMetricExtractor(tmp_path)
    result = extractor._measure_data_model_aggregation()
    assert result.details["total_dm_pages"] == 1
    assert result.details["aggregated_dm"] == 1


def test_security_pages_fold_without_padding(tmp_path: Path) -> None:
    (tmp_path / "cmd" / "ccagent").mkdir(parents=True)
    (tmp_path / "cmd" / "ccagent" / "main.go").write_text(
        "package main\nfunc main() {}\n", encoding="utf-8"
    )
    (tmp_path / "apiauth.go").write_text("package ccagent\nfunc Auth() {}\n", encoding="utf-8")
    (tmp_path / "go.mod").write_text("module demo\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# demo\n", encoding="utf-8")
    planner = RuleFirstPlanner(
        resolve_repository_identity(tmp_path),
        RepositoryScanner(
            RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
        ).scan(),
    ).generate()
    security = [page for page in planner.pages if page.category.value == "安全合规"]
    titles = {page.title for page in security}
    assert "漏洞管理" not in titles
    assert "合规框架" not in titles
    assert len(security) <= 3


def test_normalize_mermaid_block_ignores_whitespace() -> None:
    a = "flowchart TD\n  A --> B\n"
    b = "flowchart TD\n\n  A --> B\n"
    assert normalize_mermaid_block(a) == normalize_mermaid_block(b)
    assert mermaid_block_is_generic_placeholder(
        'flowchart TD\nA["应用模块"] --> B["业务服务"]\nB --> C["数据与仓库"]\n'
    )


def test_python_import_edges_are_real_app_packages() -> None:
    files = [
        (
            "app/api/routes/articles.py",
            "from app.services import article_service\nfrom app.models.domain import Article\n",
        ),
        ("app/services/article_service.py", "from app.db.queries import fetch_article\n"),
        ("app/core/security.py", "from app.services.jwt import decode_token\n"),
    ]
    edges = set(extract_python_app_import_edges(files))
    assert ("app/api/routes", "app/services") in edges
    assert ("app/api/routes", "app/models/domain") in edges
    assert ("app/core", "app/services") in edges
    assert ("app/core", "app/models") not in edges


def test_reserved_and_duplicate_schema_fail_placeholder(tmp_path: Path) -> None:
    content = tmp_path / "content"
    content.mkdir()
    (content / "ops.md").write_text(
        "# ops\n```mermaid\nflowchart TD\n  start((Start)) --> end((End))\n```\n",
        encoding="utf-8",
    )
    schema = "```sql\nCREATE TABLE users (id INT);\n```\n"
    for name in ("a.md", "b.md", "c.md"):
        (content / name).write_text("# api\n" + schema, encoding="utf-8")
    assert handbook_reserved_mermaid_id_pages(content)
    assert handbook_duplicate_schema_groups(content, max_copies=2)


def test_page_contract_strips_english_note_and_empty_blockquote(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# x\n", encoding="utf-8")
    service = RepoWikiService(RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}}))
    raw = "# 安装\n\n**NOTE**: This repository is complete.\n\n> \n\n下一步见文档。\n"
    cleaned = service._strip_readme_english_note(raw)
    cleaned = service._strip_empty_blockquotes(cleaned)
    assert "**NOTE**" not in cleaned
    assert not any(line.strip() == ">" for line in cleaned.splitlines())
