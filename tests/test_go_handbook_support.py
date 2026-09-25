"""Go handbook extraction, install clues, folding, and source-evidence gates."""

from __future__ import annotations

import json
from pathlib import Path

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.core.contracts import (
    Module,
    RepositoryInfo,
    RepositorySnapshot,
)
from repo_wiki.evidence.citation_renderer import (
    normalize_citation_markup,
    sanitize_citation_payloads,
)
from repo_wiki.evidence.ranking import rank_evidence_for_page
from repo_wiki.generator.code_safe import sacred_code_offenders
from repo_wiki.generator.mermaid_planner import (
    MermaidDiagramType,
    create_planner,
    create_renderer,
    validate_mermaid_syntax,
)
from repo_wiki.orchestration.runtime_store import EvidenceSpanRecord
from repo_wiki.orchestration.service import RepoWikiService, _is_filename_like_handbook_title
from repo_wiki.planner.identity import resolve_repository_identity
from repo_wiki.planner.rule_first import RuleFirstPlanner, _is_filename_like_module_name
from repo_wiki.planner.schema import (
    RepositoryIdentity,
    SourceRequirement,
    WikiPagePlan,
    WikiTaxonomyCategory,
)
from repo_wiki.scanner.docs_scanner import (
    _is_inventory_shaped_name,
    _is_source_file_claim,
    _repo_path_exists,
    is_eval_or_agent_instruction_doc,
    is_product_citation_source,
    scan_repository_docs_inventory,
)
from repo_wiki.scanner.go_routes import (
    extract_go_data_models,
    extract_go_endpoints,
    extract_go_internal_import_edges,
    http_method_from_request_type,
    is_go_test_path,
)
from repo_wiki.scanner.multi_runtime_scanner_v3 import (
    MultiRuntimeSourceScannerV3,
    scan_single_file,
)
from repo_wiki.scanner.repository_scanner import RepositoryScanner
from repo_wiki.scanner.source_spans import SourceSpanExtractor
from repo_wiki.verifier.api_claim_inventory import api_claim_in_inventory
from repo_wiki.verifier.handbook import (
    collect_repo_install_commands,
    collect_source_listen_ports,
    handbook_placeholder_mermaid_pages,
    has_api_routes_citation,
    has_architecture_core_citation,
    has_data_model_source_citation,
    has_fenced_install_run_command,
    has_readme_run_section_citation,
    install_fenced_commands_are_grounded,
    install_go_builds_use_package_dir,
    install_run_clue_count,
    readme_run_section_ranges,
    repo_run_clue_names,
)
from repo_wiki.verifier.qoder_strict_verifier import (
    QoderLikeVerifierService,
    is_qoder_page_dump,
    page_has_prompt_leakage,
    page_has_repeated_filler,
)
from repo_wiki.verifier.source_evidence import (
    PRODUCT_SOURCE_EXTS,
    handbook_source_citation_stats,
    source_evidence_should_apply,
)

_SERV_GO = """
package ccagent

func RegisterService(baseRouterPath string, service any) {}
func RegisterRawRoute(method, path string, handler any) {}
"""

_CONTROLLER_GO = """
package ccagent

import "github.com/gin-gonic/gin"

func (c *Controller) Run() {
    r := gin.New()
    r.GET("/health", handleLive)
    r.GET("/live", handleLive)
    r.GET("/ready", handleReady)
    r.GET("/version", handleVersion)
    r.Handle("GET", "/debug/statsviz/*filepath", statsviz)
}
"""

_SERV_PROBE_GO = """
package services

import "ccagent"

type ServiceProbeEndpoint struct{}

func NewServiceProbeEndpoint() *ServiceProbeEndpoint { return &ServiceProbeEndpoint{} }

func init() {
    ccagent.RegisterService("/probe/endpoint", NewServiceProbeEndpoint())
    ccagent.RegisterService("/biz/instance", NewServiceBizTree())
}

type ServiceBizTree struct{}

func NewServiceBizTree() *ServiceBizTree { return &ServiceBizTree{} }

type ServeCreateRequest struct {
    Name string `json:"name"`
}

type ServeGetRequest struct {
    ID int64 `json:"id" path:"id"`
}

type ServeListRequest struct{}

type ServeDeleteRequest struct {
    ID int64 `path:"id"`
}

func (s *ServiceBizTree) ServeCreate(req *ServeCreateRequest) (*ServeCreateResponse, error) {
    return nil, nil
}

func (s *ServiceProbeEndpoint) ServeCreate(req *ServeCreateRequest) (*ServeCreateResponse, error) {
    return nil, nil
}
func (s *ServiceProbeEndpoint) ServeGet(req *ServeGetRequest) (*ServeGetResponse, error) {
    return nil, nil
}
func (s *ServiceProbeEndpoint) ServeList(req *ServeListRequest) (*ServeListResponse, error) {
    return nil, nil
}
func (s *ServiceProbeEndpoint) ServeDelete(req *ServeDeleteRequest) (*ServeDeleteResponse, error) {
    return nil, nil
}

type ServeCreateResponse struct{}
type ServeGetResponse struct{}
type ServeListResponse struct{}
type ServeDeleteResponse struct{}
"""

_SERV_TAG_GO = """
package services

import "ccagent"

type ServiceTag struct{}

func NewServiceTag() *ServiceTag { return &ServiceTag{} }

func init() {
    ccagent.RegisterService("/tag", NewServiceTag())
}

type ServeListRequest struct{}

func (s *ServiceTag) ServeList(req *ServeListRequest) (*ServeListResponse, error) { return nil, nil }

type ServeListResponse struct{}
"""

_RAW_ROUTE_GO = """
package services

import (
    "ccagent"
    "net/http"
)

func init() {
    ccagent.RegisterRawRoute(http.MethodGet, "/metrics", handler)
}
"""

_APIAUTH_TEST_GO = """
package ccagent

import "github.com/gin-gonic/gin"

func TestAuth(t *testing.T) {
    r := gin.New()
    r.GET("/api/v1/secrets", func(c *gin.Context) {})
    r.GET("/static/app.js", func(c *gin.Context) {})
}
"""

_ENDPOINT_MODEL_GO = """
package models

type ProbeEndpoint struct {
    ID   int64     `gorm:"primaryKey;column:id" json:"id"`
    Name string    `gorm:"column:name" json:"name"`
    Tags []ProbeTag `gorm:"many2many:endpoint_tags"`
}

func (ProbeEndpoint) TableName() string {
    return "probe_endpoints"
}

type ProbeTag struct {
    ID         int64          `gorm:"primaryKey;column:id"`
    EndpointID int64          `gorm:"index;column:endpoint_id"`
    Endpoint   *ProbeEndpoint `gorm:"foreignKey:EndpointID"`
}

type AuthConfig struct {
    Type string `json:"type"`
}

type DatabaseConfig struct {
    DSN string
}

type bufWriter struct {
    buf []byte
}

type UserRow struct {
    ID int `db:"id"`
}
"""

_SYNTHETIC_WORKFLOW_ABSENT = "type SyntheticWorkflow struct"


def _write_synthetic_go_repo(root: Path) -> None:
    (root / "cmd" / "ccagent").mkdir(parents=True)
    (root / "internal" / "services").mkdir(parents=True)
    (root / "internal" / "models").mkdir(parents=True)
    (root / "internal" / "control").mkdir(parents=True)
    (root / "internal" / "probe").mkdir(parents=True)
    (root / "internal" / "repository").mkdir(parents=True)
    (root / "internal" / "exporter").mkdir(parents=True)
    (root / "deploy" / "compose" / "vault").mkdir(parents=True)
    (root / ".trellis").mkdir()
    (root / ".trae").mkdir()
    (root / ".cursor").mkdir()
    (root / "serv.go").write_text(_SERV_GO, encoding="utf-8")
    (root / "serv_hello.go").write_text(
        'package ccagent\n\nfunc init() { RegisterService("/hello", NewServiceHello()) }\n'
        "type ServiceHello struct{}\nfunc NewServiceHello() *ServiceHello { return &ServiceHello{} }\n"
        "func (s *ServiceHello) ServePing(req *ServePingRequest) (*ServePingResponse, error) { return nil, nil }\n"
        "type ServePingRequest struct{}\ntype ServePingResponse struct{}\n",
        encoding="utf-8",
    )
    (root / "controller.go").write_text(_CONTROLLER_GO, encoding="utf-8")
    (root / "apiauth_test.go").write_text(_APIAUTH_TEST_GO, encoding="utf-8")
    (root / "internal" / "services" / "serv_probe_endpoint.go").write_text(
        _SERV_PROBE_GO.replace(
            'import "ccagent"',
            'import (\n    "ccagent"\n    "ccagent/internal/repository"\n)',
        ),
        encoding="utf-8",
    )
    (root / "internal" / "services" / "serv_tag.go").write_text(_SERV_TAG_GO, encoding="utf-8")
    (root / "internal" / "services" / "agent_ops.go").write_text(_RAW_ROUTE_GO, encoding="utf-8")
    (root / "internal" / "models" / "endpoint.go").write_text(_ENDPOINT_MODEL_GO, encoding="utf-8")
    (root / "internal" / "control" / "tunnel.go").write_text(
        "package control\nfunc Dial() {}\n", encoding="utf-8"
    )
    (root / "internal" / "probe" / "result_repo.go").write_text(
        'package probe\n\nimport "ccagent/internal/models"\n\nfunc Load() { _ = models.ProbeEndpoint{} }\n',
        encoding="utf-8",
    )
    (root / "internal" / "repository" / "store.go").write_text(
        'package repository\n\nimport "ccagent/internal/models"\n\nfunc Save() { _ = models.ProbeEndpoint{} }\n',
        encoding="utf-8",
    )
    (root / "internal" / "exporter" / "prom.go").write_text(
        'package exporter\n\nimport "ccagent/internal/repository"\n\nfunc Export() { repository.Save() }\n',
        encoding="utf-8",
    )
    (root / "cmd" / "ccagent" / "main.go").write_text(
        "package main\nfunc main() {}\n", encoding="utf-8"
    )
    (root / "cmd" / "ccprobe-control").mkdir(parents=True)
    (root / "cmd" / "ccprobe-control" / "main.go").write_text(
        "package main\nfunc main() { runGRPCServe() }\n", encoding="utf-8"
    )
    (root / "cmd" / "ccprobe-control" / "serve.go").write_text(
        "package main\nfunc runGRPCServe() {}\nfunc checkListenSecurity() {}\n",
        encoding="utf-8",
    )
    (root / "config.yaml").write_text('listen: "0.0.0.0:1900"\n', encoding="utf-8")
    (root / "internal" / "models" / "tree.go").write_text(
        """
package models

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
    ID         int64   `gorm:"primaryKey;column:id"`
    EndpointID int64   `gorm:"column:endpoint_id"`
    Latency    float64 `gorm:"column:latency"`
}
func (ProbeResult) TableName() string { return "probe_results" }
""",
        encoding="utf-8",
    )
    (root / "cmd" / "custom-probe").mkdir(parents=True)
    (root / "cmd" / "custom-probe" / "main.go").write_text(
        "package main\nfunc main() {}\n", encoding="utf-8"
    )
    (root / "go.mod").write_text("module ccagent\n\ngo 1.22\n", encoding="utf-8")
    (root / "Makefile").write_text(
        "install:\n\tgo build -o bin/ccagent ./cmd/ccagent/main.go\ntest:\n\tgo test ./...\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        "# probe_exporter\n\n"
        "[![Go Version](https://img.shields.io/badge/Go-1.25+-00ADD8)](https://go.dev/)\n"
        "[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)\n"
        "[![CI](https://img.shields.io/badge/CI-passing-brightgreen)](https://example.com)\n"
        "[![Release](https://img.shields.io/badge/release-stable-blue)](https://example.com)\n"
        "[![Docs](https://img.shields.io/badge/docs-latest-lightgrey)](https://example.com)\n"
        "[![Coverage](https://img.shields.io/badge/coverage-80-yellow)](https://example.com)\n"
        "[![Build](https://img.shields.io/badge/build-ok-success)](https://example.com)\n"
        "\n企业级服务探针拨测与结果导出平台。\n\n"
        "## 🚀 快速开始\n\n"
        "需要 MySQL，并先执行 `db/schema.sql`。\n\n"
        "```bash\n"
        "podman-compose up -d\n"
        "mysql < db/schema.sql\n"
        "make install\n"
        "go build -o bin/ccagent ./cmd/ccagent/main.go\n"
        "./bin/ccagent\n"
        "curl http://localhost:8000/health\n"
        "```\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs" / "PLAN.md").write_text("# Plan\nControl-plane rollout.\n", encoding="utf-8")
    (root / "db").mkdir(exist_ok=True)
    (root / "db" / "migrations").mkdir(exist_ok=True)
    (root / "db" / "schema.sql").write_text(
        "CREATE TABLE probe_endpoints (id BIGINT PRIMARY KEY, name VARCHAR(64));\n"
        "CREATE TABLE probe_tags (\n"
        "  id BIGINT PRIMARY KEY,\n"
        "  endpoint_id BIGINT,\n"
        "  FOREIGN KEY (endpoint_id) REFERENCES probe_endpoints(id)\n"
        ");\n"
        "CREATE TABLE probe_results (\n"
        "  id BIGINT PRIMARY KEY,\n"
        "  endpoint_id BIGINT,\n"
        "  FOREIGN KEY (endpoint_id) REFERENCES probe_endpoints(id)\n"
        ");\n"
        "CREATE TABLE biz_tree_node (\n"
        "  id BIGINT PRIMARY KEY,\n"
        "  parent_id BIGINT,\n"
        "  FOREIGN KEY (parent_id) REFERENCES biz_tree_node(id)\n"
        ");\n"
        "CREATE TABLE biz_instance_endpoint (\n"
        "  id BIGINT PRIMARY KEY,\n"
        "  service_id BIGINT,\n"
        "  FOREIGN KEY (service_id) REFERENCES biz_tree_node(id)\n"
        ");\n"
        "CREATE TABLE probe_policy (\n"
        "  id BIGINT PRIMARY KEY,\n"
        "  service_id BIGINT,\n"
        "  FOREIGN KEY (service_id) REFERENCES biz_tree_node(id)\n"
        ");\n",
        encoding="utf-8",
    )
    (root / "db" / "migrations" / "001_init.sql").write_text(
        "CREATE TABLE probe_endpoints (id BIGINT);\n", encoding="utf-8"
    )
    (root / "README-scaffold.md").write_text(
        "# ccagent\n\n基于 Go 的高性能 HTTP 服务框架，集成了自动服务注册。\n",
        encoding="utf-8",
    )
    (root / "README-podman.md").write_text(
        "# podman\n\n```bash\npodman-compose up -d\n```\n",
        encoding="utf-8",
    )
    (root / "QUICKSTART.md").write_text(
        "# Quickstart\n\nmake install && go test ./...\n",
        encoding="utf-8",
    )
    (root / "deploy" / "compose" / "vault" / "auth_target.py").write_text(
        "print('helper')\n", encoding="utf-8"
    )
    (root / ".trellis" / "plan.md").write_text(
        "Use user-service and order-service as examples. See tunnel.go.\n",
        encoding="utf-8",
    )
    (root / ".trae" / "notes.md").write_text("weather-service placeholder\n", encoding="utf-8")


def _go_files(root: Path) -> list[tuple[str, str]]:
    files: list[tuple[str, str]] = []
    for path in root.rglob("*.go"):
        files.append(
            (path.relative_to(root).as_posix(), path.read_text(encoding="utf-8", errors="ignore"))
        )
    return files


def test_is_go_test_path() -> None:
    assert is_go_test_path("apiauth_test.go")
    assert is_go_test_path("internal/auth/hmac_auth_test.go")
    assert not is_go_test_path("controller.go")
    assert not is_go_test_path("internal/services/serv_tag.go")


def test_http_method_from_request_type() -> None:
    assert http_method_from_request_type("ServeGetRequest") == "GET"
    assert http_method_from_request_type("ServeDeleteRequest") == "DELETE"
    assert http_method_from_request_type("ServeCreateRequest") == "ANY"
    assert http_method_from_request_type("QueryRouteGetRequest") == "GET"


def test_extract_gin_and_register_service_excludes_test_routes(tmp_path: Path) -> None:
    _write_synthetic_go_repo(tmp_path)
    endpoints = extract_go_endpoints(_go_files(tmp_path))
    paths = {item.path for item in endpoints}
    methods = {(item.method, item.path) for item in endpoints}

    assert "/health" in paths
    assert "/probe/endpoint/create" in paths
    assert "/biz/instance/create" in paths
    assert "/probe/endpoint/list" in paths
    assert "/probe/endpoint/get/:id" in paths
    assert "/probe/endpoint/delete/:id" in paths
    assert "/tag/list" in paths
    assert "/hello/ping" in paths
    assert "/metrics" in paths
    assert ("GET", "/probe/endpoint/get/:id") in methods
    assert ("DELETE", "/probe/endpoint/delete/:id") in methods
    assert "/api/v1/secrets" not in paths
    assert "/static/app.js" not in paths


def test_extract_gorm_models_not_plain_structs(tmp_path: Path) -> None:
    _write_synthetic_go_repo(tmp_path)
    models = extract_go_data_models(_go_files(tmp_path))
    names = {item.name for item in models}
    assert "ProbeEndpoint" in names
    assert "ProbeTag" in names
    assert any(item.table_name == "probe_endpoints" for item in models)
    assert "UserRow" in names
    assert "AuthConfig" not in names
    assert "DatabaseConfig" not in names
    assert "bufWriter" not in names
    assert "SyntheticWorkflow" not in names


def test_inventory_v3_and_snapshot_count_go_routes(tmp_path: Path) -> None:
    _write_synthetic_go_repo(tmp_path)
    cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
    inventory = MultiRuntimeSourceScannerV3(cfg).scan(incremental=False, persist_state=False)
    paths = {item.get("path") for item in inventory["api_surfaces"]}
    model_names = {item.get("name") for item in inventory["data_models"]}
    assert "/probe/endpoint/create" in paths
    assert "/health" in paths
    assert "/api/v1/secrets" not in paths
    assert "ProbeEndpoint" in model_names
    assert "SyntheticWorkflow" not in model_names

    snapshot = RepositoryScanner(cfg).scan()
    snap_paths = {endpoint.path for endpoint in snapshot.endpoints}
    snap_models = {model.name for model in snapshot.data_models}
    assert "/probe/endpoint/list" in snap_paths
    assert "/api/v1/secrets" not in snap_paths
    assert "ProbeEndpoint" in snap_models
    assert "ProbeTag" in snap_models
    assert "DatabaseConfig" not in snap_models
    assert "bufWriter" not in snap_models
    assert "probe_endpoints" not in snap_models


def test_scan_single_file_gorm_and_gin() -> None:
    record = scan_single_file(Path("controller.go"), _CONTROLLER_GO)
    assert any(item.get("path") == "/health" for item in record.api_surfaces)
    record = scan_single_file(Path("internal/models/endpoint.go"), _ENDPOINT_MODEL_GO)
    assert any(item.get("name") == "ProbeEndpoint" for item in record.data_models)


def test_go_source_spans_extracted() -> None:
    spans = SourceSpanExtractor().extract_from_file(Path("serv.go"), _SERV_PROBE_GO)
    symbols = {span.symbol for span in spans}
    assert "ServiceProbeEndpoint" in symbols
    assert "ServeCreate" in symbols
    assert all(span.language == "go" for span in spans)


def test_install_clues_include_go_make_podman(tmp_path: Path) -> None:
    _write_synthetic_go_repo(tmp_path)
    names = set(repo_run_clue_names(tmp_path))
    assert "go build" in names
    assert "make" in names
    assert "podman-compose" in names
    page = (
        "# 安装\n\n```bash\n"
        "go build -o bin/ccagent ./cmd/ccagent/main.go\n"
        "make test\n"
        "podman-compose up -d\n"
        "```\n"
    )
    assert install_run_clue_count(page, tmp_path) >= 2
    assert has_fenced_install_run_command(page, tmp_path) is True


def test_filename_like_go_modules_fold() -> None:
    assert _is_filename_like_module_name("serv_hello.go")
    assert _is_filename_like_module_name("Serv Hello.go")
    assert _is_filename_like_handbook_title("Serv Hello.go")
    assert _is_filename_like_handbook_title("Serv Reflect.go")
    assert not _is_filename_like_module_name("probe-agent")

    identity = RepositoryIdentity(
        name="probe",
        display_name="probe",
        root_path="/tmp/probe",
        language="go",
        framework="gin",
    )
    snapshot = RepositorySnapshot(
        repository=RepositoryInfo(
            name="probe", root_path="/tmp/probe", language="go", framework="gin"
        ),
        modules=[
            Module(
                name="serv_hello.go",
                path="serv_hello.go",
                responsibility="hello",
                owner="unknown",
                doc_path="docs/modules/serv-hello.md",
                domain="core-platform",
                service_family="golang-service",
                runtime_role="api-server",
            ),
            Module(
                name="serv_reflect.go",
                path="serv_reflect.go",
                responsibility="reflect",
                owner="unknown",
                doc_path="docs/modules/serv-reflect.md",
                domain="core-platform",
                service_family="golang-service",
                runtime_role="api-server",
            ),
            Module(
                name="probe-agent",
                path="internal/agent",
                responsibility="agent",
                owner="unknown",
                doc_path="docs/modules/probe-agent.md",
                domain="core-platform",
                service_family="golang-service",
                runtime_role="api-server",
            ),
        ],
        endpoints=[],
        data_models=[],
    )
    pages = RuleFirstPlanner(identity, snapshot).generate().pages
    titles = [page.title for page in pages]
    assert "Serv Hello.go" not in titles
    assert "Serv Reflect.go" not in titles
    assert any("探针" in title or "Agent" in title or "agent" in title.lower() for title in titles)


def test_filter_drops_go_filename_pages(tmp_path: Path) -> None:
    cfg = RepoWikiConfig()
    cfg.project.root = str(tmp_path)
    service = RepoWikiService(cfg)
    pages = [
        WikiPagePlan(
            page_id="core-services-index",
            title="核心服务",
            category=WikiTaxonomyCategory.CORE_SERVICES,
            output_path="docs/pages/services/core-services-index.md",
        ),
        WikiPagePlan(
            page_id="serv_hello.go",
            title="Serv Hello.go",
            category=WikiTaxonomyCategory.CORE_SERVICES,
            output_path="docs/pages/services/Serv Hello.go.md",
        ),
    ]
    kept = service._filter_qoder_like_pages(pages)
    assert [page.title for page in kept] == ["核心服务"]


def test_ai_tool_folders_excluded_from_product_docs(tmp_path: Path) -> None:
    _write_synthetic_go_repo(tmp_path)
    assert is_eval_or_agent_instruction_doc(".trellis/plan.md")
    assert is_eval_or_agent_instruction_doc(".trae/notes.md")
    assert is_eval_or_agent_instruction_doc(".cursor/rules.md")
    assert not is_product_citation_source(".trellis/plan.md")
    inventory = scan_repository_docs_inventory(
        tmp_path,
        {"services": [], "api_surfaces": [], "data_models": []},
        incremental=False,
        persist_cache=False,
    )
    paths = {item["path"] for item in inventory["documents"]}
    assert not any(path.startswith(".trellis/") or path.startswith(".trae/") for path in paths)


def test_stale_resolver_finds_internal_go_files(tmp_path: Path) -> None:
    _write_synthetic_go_repo(tmp_path)
    (tmp_path / "docs").mkdir(exist_ok=True)
    (tmp_path / "docs" / "notes.md").write_text(
        "See `tunnel.go` and `result_repo.go` and missing `docs/xxx.md`.\n",
        encoding="utf-8",
    )
    inventory = scan_repository_docs_inventory(
        tmp_path,
        {"services": [], "api_surfaces": [], "data_models": []},
        incremental=False,
        persist_cache=False,
    )
    notes = next(item for item in inventory["documents"] if item["path"].endswith("docs/notes.md"))
    stale = set(notes["stale_references"])
    assert "tunnel.go" not in stale
    assert "result_repo.go" not in stale
    assert any("docs/xxx" in item for item in stale)


def test_primary_readme_identity_skips_scaffold_and_badges(tmp_path: Path) -> None:
    _write_synthetic_go_repo(tmp_path)
    identity = resolve_repository_identity(tmp_path)
    assert identity.description is not None
    assert "探针拨测" in identity.description
    assert "HTTP 服务框架" not in (identity.description or "")
    assert "shields.io" not in (identity.description or "")


def test_planner_skips_k8s_python_and_ai_chapters_for_go_repo(tmp_path: Path) -> None:
    _write_synthetic_go_repo(tmp_path)
    cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
    snapshot = RepositoryScanner(cfg).scan()
    identity = resolve_repository_identity(tmp_path)
    identity.language = snapshot.repository.language
    identity.framework = snapshot.repository.framework
    pages = RuleFirstPlanner(identity, snapshot).generate().pages
    titles = [page.title for page in pages]
    assert "Kubernetes部署" not in titles
    assert "Python服务" not in titles
    assert "AI服务" not in titles
    assert "AI服务能力" not in titles


def test_drop_citations_to_missing_files(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("ok\n", encoding="utf-8")
    text = "见 <cite>README.md:1-1</cite> 和 <cite>docs/DOCUMENTING_SUMMARY.md:545-618</cite>。"
    cleaned = normalize_citation_markup(text, tmp_path)
    assert "README.md:1-1" in cleaned
    assert "<cite>docs/DOCUMENTING_SUMMARY.md:545-618</cite>" not in cleaned
    assert "DOCUMENTING_SUMMARY.md" not in cleaned


def test_source_evidence_fails_docs_only_handbook(tmp_path: Path) -> None:
    _write_synthetic_go_repo(tmp_path)
    content = tmp_path / "repowiki" / "zh" / "content"
    content.mkdir(parents=True)
    body = "\n".join("仓库有探针能力。 <cite>README.md:1-1</cite>" for _ in range(20))
    (content / "项目概述.md").write_text("# 概述\n\n" + body + "\n", encoding="utf-8")
    (tmp_path / "manifest.json").write_text(
        f'{{"readiness_state":"READY","target_repo":"{tmp_path.as_posix()}"}}',
        encoding="utf-8",
    )
    assert source_evidence_should_apply(tmp_path) is True
    stats = handbook_source_citation_stats(content, tmp_path)
    assert stats.total_citations >= 20
    assert stats.source_citations == 0
    result = QoderLikeVerifierService(tmp_path, strict=True)._check_qoder_source_evidence()
    assert result.status == "FAIL"
    assert result.reason_code == "QODER_SOURCE_EVIDENCE_LOW"


def test_source_evidence_passes_when_go_cited(tmp_path: Path) -> None:
    _write_synthetic_go_repo(tmp_path)
    content = tmp_path / "repowiki" / "zh" / "content"
    content.mkdir(parents=True)
    lines = ["路由在控制器。 <cite>controller.go:1-8</cite>" for _ in range(8)] + [
        "说明。 <cite>README.md:1-1</cite>" for _ in range(8)
    ]
    (content / "API参考.md").write_text("# API\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
    (tmp_path / "manifest.json").write_text(
        f'{{"readiness_state":"READY","target_repo":"{tmp_path.as_posix()}"}}',
        encoding="utf-8",
    )
    result = QoderLikeVerifierService(tmp_path, strict=True)._check_qoder_source_evidence()
    assert result.status == "PASS"
    assert ".go" in PRODUCT_SOURCE_EXTS


def test_source_evidence_skips_without_enough_source_files(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("docs only\n", encoding="utf-8")
    content = tmp_path / "content"
    content.mkdir()
    (content / "page.md").write_text("hi <cite>README.md:1-1</cite>\n", encoding="utf-8")
    result = QoderLikeVerifierService(tmp_path, strict=True)._check_qoder_source_evidence()
    assert result.status == "PASS"
    assert "Skip" in result.message or "Skipped" in result.message


def test_source_evidence_uses_eval_parent_when_target_repo_stale(tmp_path: Path) -> None:
    _write_synthetic_go_repo(tmp_path)
    run = tmp_path / ".repo-agent-eval" / "runs" / "old-run"
    content = run / "repowiki" / "zh" / "content"
    content.mkdir(parents=True)
    body = "\n".join("仓库有探针能力。 <cite>README.md:1-1</cite>" for _ in range(20))
    (content / "项目概述.md").write_text("# 概述\n\n" + body + "\n", encoding="utf-8")
    (run / "manifest.json").write_text(
        '{"readiness_state":"READY","target_repo":"/workspace/probe_exporter"}',
        encoding="utf-8",
    )
    result = QoderLikeVerifierService(run, strict=True)._check_qoder_source_evidence()
    assert result.status == "FAIL"
    assert result.reason_code == "QODER_SOURCE_EVIDENCE_LOW"


def test_any_method_stays_any_and_matches_concrete_claim() -> None:
    files = [
        (
            "serv.go",
            'package ccagent\nfunc init() { RegisterService("/probe/blackbox", NewSvc()) }\n'
            "type Svc struct{}\nfunc NewSvc() *Svc { return &Svc{} }\n"
            "func (s *Svc) ServeCreate(req *ServeCreateRequest) error { return nil }\n"
            "type ServeCreateRequest struct{}\n",
        )
    ]
    endpoints = extract_go_endpoints(files)
    assert any(item.method == "ANY" and item.path.endswith("/create") for item in endpoints)
    inventory = {(item.method, item.path) for item in endpoints}
    path = next(item.path for item in endpoints if item.method == "ANY")
    assert api_claim_in_inventory("POST", path, inventory) is True
    assert api_claim_in_inventory("GET", path, inventory) is True
    assert api_claim_in_inventory("GET", "/ghost", inventory) is False


def test_go122_mux_and_pprof_table_are_not_malformed() -> None:
    text = """
package pprof
func Register(mux *http.ServeMux) {
    mux.HandleFunc("GET /debug/pprof/", Index)
    mux.Handle("GET /debug/pprof/cmdline", http.HandlerFunc(Cmdline))
    routes := []struct{ Method, Path string }{
        {"GET", "/debug/pprof/profile"},
        {"GET", "/debug/pprof/symbol"},
        {"GET", "/debug/pprof/trace"},
        {"GET", "/debug/pprof/heap"},
        {"GET", "/debug/pprof/goroutine"},
        {"GET", "/debug/pprof/allocs"},
        {"GET", "/debug/pprof/block"},
    }
    _ = routes
}
"""
    endpoints = extract_go_endpoints([("internal/debug/pprof.go", text)])
    paths = {item.path for item in endpoints}
    assert "/GET /debug/pprof/" not in paths
    assert "/debug/pprof/" in paths
    assert "/debug/pprof/cmdline" in paths
    assert "/debug/pprof/profile" in paths
    assert "/debug/pprof/heap" in paths
    assert all(item.file_path == "internal/debug/pprof.go" for item in endpoints)


def test_api_pages_group_by_resource_and_cite_handler(tmp_path: Path) -> None:
    cfg = RepoWikiConfig()
    cfg.project.root = str(tmp_path)
    service = RepoWikiService(cfg)
    endpoints = [
        {
            "method": "GET",
            "path": "/hello/ping",
            "handler": "ServiceHello.ServePing",
            "file_path": "serv_hello.go",
            "line_number": 3,
        },
        {
            "method": "POST",
            "path": "/probe/endpoint/create",
            "handler": "ServiceProbeEndpoint.ServeCreate",
            "file_path": "internal/services/serv_probe_endpoint.go",
            "line_number": 12,
        },
        {
            "method": "GET",
            "path": "/probe/endpoint/list",
            "handler": "ServiceProbeEndpoint.ServeList",
            "file_path": "internal/services/serv_probe_endpoint.go",
            "line_number": 18,
        },
        {
            "method": "GET",
            "path": "/tag/list",
            "handler": "ServiceTag.ServeList",
            "file_path": "internal/services/serv_tag.go",
            "line_number": 8,
        },
    ]
    section = service._build_truthful_api_group_section(endpoints)
    assert section.index("### probe/endpoint") < section.index("### hello")
    assert "<cite>internal/services/serv_probe_endpoint.go:12</cite>" in section
    assert "`internal/services/serv_probe_endpoint.go`:12" not in section
    assert section.count("/hello/ping") == 1
    assert "以下端点来自仓库扫描证据上下文" not in section


def test_generated_pb_and_tests_are_not_source_evidence(tmp_path: Path) -> None:
    _write_synthetic_go_repo(tmp_path)
    (tmp_path / "api" / "proto").mkdir(parents=True)
    (tmp_path / "api" / "proto" / "control.pb.go").write_text("package proto\n", encoding="utf-8")
    content = tmp_path / "repowiki" / "zh" / "content"
    content.mkdir(parents=True)
    lines = ["生成代码。 <cite>api/proto/control.pb.go:1-1</cite>" for _ in range(10)]
    lines += ["测试。 <cite>apiauth_test.go:1-1</cite>" for _ in range(10)]
    (content / "API参考.md").write_text("# API\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
    stats = handbook_source_citation_stats(content, tmp_path)
    assert stats.total_citations == 20
    assert stats.source_citations == 0


def test_out_of_range_citation_dropped_at_generate_time(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("\n".join(f"line {i}" for i in range(1, 6)), encoding="utf-8")
    kept = sanitize_citation_payloads("README.md:821-824", workspace_root=tmp_path)
    assert kept == []
    kept = sanitize_citation_payloads("README.md:1-3", workspace_root=tmp_path)
    assert kept == ["README.md:1-3"]


def test_go_install_commands_come_from_makefile_and_cmd(tmp_path: Path) -> None:
    _write_synthetic_go_repo(tmp_path)
    cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
    snapshot = RepositoryScanner(cfg).scan()
    assert "go build -o bin/ccagent ./cmd/ccagent/main.go" in snapshot.commands.values() or (
        snapshot.commands.get("build") == "go build -o bin/ccagent ./cmd/ccagent/main.go"
    )
    assert "go run ." not in snapshot.commands.values()
    assert "go build ./..." not in snapshot.commands.values()
    service = RepoWikiService(cfg)
    commands = service._install_commands_from_repo_files()
    assert any("./cmd/ccagent" in item and "main.go" not in item for item in commands)
    assert not any(
        item.strip() in {"go run .", "go build -o probe_exporter ."} for item in commands
    )


def test_mermaid_er_rejects_brace_attribute_names() -> None:
    planner = create_planner()
    renderer = create_renderer()
    diagrams = planner.plan_diagram_for_page(
        "data-model",
        "data",
        None,
        {
            "data_models": [
                {
                    "name": "ProbeEndpoint",
                    "file_path": "internal/models/endpoint.go",
                    "primary_key": "{id}",
                    "attributes": ["{id}", "name"],
                },
                {
                    "name": "ProbeResult",
                    "file_path": "internal/models/result.go",
                    "primary_key": "id",
                },
            ]
        },
    )
    rendered, is_valid, _error = renderer.render_diagram_with_validation(diagrams[0])
    assert is_valid is True
    assert rendered is not None
    assert "{id}" not in rendered
    assert "ProbeEndpoint" in rendered
    assert (
        validate_mermaid_syntax("erDiagram\n    X {{id}}\n", MermaidDiagramType.ER_DIAGRAM)[0]
        is False
    )


def test_architecture_mermaid_prefers_internal_packages() -> None:
    planner = create_planner()
    renderer = create_renderer()
    diagrams = planner.plan_diagram_for_page(
        "architecture-overview",
        "architecture",
        None,
        {
            "modules": [
                {"name": "control", "path": "internal/control", "depends_on": ["internal/models"]},
                {"name": "probe", "path": "internal/probe", "depends_on": ["internal/models"]},
                {
                    "name": "services",
                    "path": "internal/services",
                    "depends_on": ["internal/repository"],
                },
                {"name": "models", "path": "internal/models", "depends_on": []},
                {"name": "agent", "path": "internal/agent", "depends_on": ["internal/control"]},
                {
                    "name": "repository",
                    "path": "internal/repository",
                    "depends_on": ["internal/models"],
                },
                {
                    "name": "exporter",
                    "path": "internal/exporter",
                    "depends_on": ["internal/repository"],
                },
            ]
        },
    )
    rendered = renderer.render_diagram(diagrams[0])
    assert "internal/control" in rendered
    assert "internal/services" in rendered
    assert "internal/repository" in rendered
    assert "internal/exporter" in rendered
    assert "internal/probe" in rendered
    assert "仓库扫描" not in rendered
    assert "LLM生成" not in rendered
    assert "repo --> internal" not in rendered


def test_repeated_filler_and_prompt_leak_are_page_dumps() -> None:
    pad = "当前证据需要把源码证据、模块职责和调用边界写清楚，读者应对照文中的源码引用核对实现。"
    page = "\n\n".join([pad] * 4)
    assert page_has_repeated_filler(page) is True
    assert page_has_prompt_leakage("端点由用户在请求中提供") is True
    assert page_has_prompt_leakage("以下端点来自仓库扫描证据上下文") is True
    assert page_has_prompt_leakage("evidence 中被截断") is True
    assert page_has_prompt_leakage("the repo gives no route table") is True
    assert page_has_prompt_leakage("没有发现顶层 README") is True
    assert page_has_prompt_leakage("当前证据未列出端口") is False
    assert is_qoder_page_dump("Tests 21/25 / Coverage 84%\n\n" + "一句说明。\n") is True
    assert is_qoder_page_dump("# 正常页\n\n这是一段足够说明的散文。\n") is False


def test_snapshot_preserves_go_handler_line_numbers(tmp_path: Path) -> None:
    _write_synthetic_go_repo(tmp_path)
    snapshot = RepositoryScanner(
        RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
    ).scan()
    create = next(ep for ep in snapshot.endpoints if ep.path.endswith("/create"))
    assert create.line_number > 1
    assert create.file_path.endswith("serv_probe_endpoint.go")


def test_install_and_overview_require_readme_files(tmp_path: Path) -> None:
    _write_synthetic_go_repo(tmp_path)
    cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
    snapshot = RepositoryScanner(cfg).scan()
    identity = resolve_repository_identity(tmp_path)
    pages = RuleFirstPlanner(identity, snapshot).generate().pages
    install = next(page for page in pages if page.page_id == "installation")
    overview = next(page for page in pages if page.page_id == "project-overview")
    assert "README.md" in install.source_requirements.files
    assert "README.md" in overview.source_requirements.files
    commands = RepoWikiService(cfg)._install_commands_from_repo_files()
    assert any("make install" in item or "go build" in item for item in commands)
    assert any("podman-compose" in item for item in commands)
    assert not any("-action probe" in item for item in commands)
    titles = [page.title for page in pages]
    assert "核心服务API" not in titles


def test_overview_ranking_pins_readme(tmp_path: Path) -> None:
    _write_synthetic_go_repo(tmp_path)
    page = WikiPagePlan(
        page_id="project-overview",
        title="项目概述",
        category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
        output_path="docs/pages/overview.md",
        source_requirements=SourceRequirement(files=["README.md"]),
        tags=["overview"],
    )
    spans = [
        EvidenceSpanRecord(
            digest="go",
            file_path="internal/control/tunnel.go",
            line_start=1,
            line_end=2,
            language="go",
            span_text="package control",
            symbol="Dial",
        ),
        EvidenceSpanRecord(
            digest="readme",
            file_path="README.md",
            line_start=1,
            line_end=8,
            language="markdown",
            span_text="## Run\nmake install\npodman-compose up -d",
            symbol="README",
        ),
    ]
    ranked = rank_evidence_for_page(page, spans)
    assert any(Path(item.span.file_path).name.lower() == "readme.md" for item in ranked)


def test_go_import_edges_include_repository_services_probe_exporter(tmp_path: Path) -> None:
    _write_synthetic_go_repo(tmp_path)
    edges = extract_go_internal_import_edges(_go_files(tmp_path))
    pairs = set(edges)
    assert ("internal/services", "internal/repository") in pairs
    assert ("internal/repository", "internal/models") in pairs
    assert ("internal/exporter", "internal/repository") in pairs
    assert ("internal/probe", "internal/models") in pairs
    snapshot = RepositoryScanner(
        RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
    ).scan()
    by_path = {module.path: module for module in snapshot.modules}
    assert "internal/repository" in by_path
    assert any(
        "internal/models" in dep or dep.endswith("models")
        for dep in by_path["internal/repository"].depends_on
    )
    assert any(
        "internal/repository" in dep or dep.endswith("repository")
        for dep in by_path["internal/exporter"].depends_on
    )
    endpoint = next(model for model in snapshot.data_models if model.name == "ProbeEndpoint")
    assert "ID" in endpoint.attributes
    assert endpoint.primary_key == "ID"
    assert any(item.endswith("ProbeTag") for item in endpoint.relationships)
    assert {model.name for model in snapshot.data_models} <= {
        "ProbeEndpoint",
        "ProbeTag",
        "UserRow",
        "BizTreeNode",
        "BizInstanceEndpoint",
        "ProbePolicy",
        "ProbeResult",
    }
    planner = create_planner()
    diagrams = planner.plan_diagram_for_page(
        "architecture-overview",
        "architecture",
        None,
        {"modules": [module.model_dump() for module in snapshot.modules]},
    )
    rendered = create_renderer().render_diagram(diagrams[0])
    assert "internal/repository" in rendered
    assert "internal/services" in rendered
    assert "internal/probe" in rendered
    assert "internal/exporter" in rendered
    assert "-->" in rendered
    assert "relates" not in rendered


def test_er_omits_invented_relates_and_uses_real_pk() -> None:
    planner = create_planner()
    renderer = create_renderer()
    diagrams = planner.plan_diagram_for_page(
        "data-model",
        "data",
        None,
        {
            "data_models": [
                {
                    "name": "ProbeEndpoint",
                    "type": "go_gorm",
                    "file_path": "internal/models/endpoint.go",
                    "primary_key": "ID",
                    "attributes": ["ID", "Name"],
                    "relationships": ["ProbeTag"],
                },
                {
                    "name": "ProbeTag",
                    "type": "go_gorm",
                    "file_path": "internal/models/endpoint.go",
                    "primary_key": "ID",
                    "attributes": ["ID", "EndpointID"],
                    "relationships": ["ProbeEndpoint"],
                },
            ]
        },
    )
    rendered = renderer.render_diagram(diagrams[0])
    assert "string id PK" not in rendered
    assert "ID PK" in rendered
    assert "relates" not in rendered
    assert "ProbeTag" in rendered
    assert "||--o{" in rendered


def test_api_route_file_accepts_go_handler_inventory(tmp_path: Path) -> None:
    content = tmp_path / "content"
    content.mkdir()
    (content / "core-service-apis.md").write_text(
        "# 核心服务API\n\n路由在 <cite>internal/services/serv_probe_endpoint.go:12-20</cite>。\n",
        encoding="utf-8",
    )
    (tmp_path / "source-inventory.json").write_text(
        json.dumps(
            {
                "schema_version": "repo_agent.source_inventory/1.0",
                "endpoints": [
                    {
                        "method": "POST",
                        "path": "/probe/endpoint/create",
                        "file_path": "internal/services/serv_probe_endpoint.go",
                        "line_number": 12,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    result = QoderLikeVerifierService(tmp_path, strict=True)._check_handbook_api_route_file()
    assert result.status == "PASS"
    assert has_api_routes_citation(
        "见 <cite>internal/services/serv_probe_endpoint.go:12</cite>",
        handler_files=["internal/services/serv_probe_endpoint.go"],
    )
    assert not has_api_routes_citation(
        "见 <cite>internal/models/endpoint.go:1</cite>",
        handler_files=["internal/services/serv_probe_endpoint.go"],
    )


def test_api_route_file_fastapi_inventory_still_requires_routes(tmp_path: Path) -> None:
    content = tmp_path / "content"
    content.mkdir()
    (content / "core-service-apis.md").write_text(
        "# 核心服务API\n\n模型在 <cite>app/models/domain.py:1-8</cite>。\n",
        encoding="utf-8",
    )
    (tmp_path / "source-inventory.json").write_text(
        json.dumps(
            {
                "schema_version": "repo_agent.source_inventory/1.0",
                "endpoints": [
                    {
                        "method": "POST",
                        "path": "/api/users/login",
                        "file_path": "app/api/routes/authentication.py",
                        "line_number": 10,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    result = QoderLikeVerifierService(tmp_path, strict=True)._check_handbook_api_route_file()
    assert result.status == "FAIL"
    assert result.reason_code == "QODER_HANDBOOK_API_ROUTE_FILE"


def test_backtick_path_line_stays_in_the_span() -> None:
    text = "路由在 `internal/services/serv_probe_endpoint.go:12`。"
    rewritten = normalize_citation_markup(text)
    assert "`internal/services/serv_probe_endpoint.go:12`" in rewritten


def test_fact_conflict_placeholders_and_docs_plan_lookup(tmp_path: Path) -> None:
    _write_synthetic_go_repo(tmp_path)
    assert _is_inventory_shaped_name("test-api") is False
    assert _is_inventory_shaped_name("external_api") is False
    assert _is_inventory_shaped_name("partner-api") is False
    assert _is_source_file_claim("app/config.yaml") is False
    assert _is_source_file_claim("app/logs/ccagent.log") is False
    assert _is_source_file_claim("app/api/routes/authentication.py") is True
    assert _repo_path_exists(tmp_path, "plan.md") is True
    assert _repo_path_exists(tmp_path, "docs/plan.md") is True
    assert _is_source_file_claim("docs/progress/phase7_p1-p5_") is False


_25D_INSTALL = """# 安装指南

probe_exporter 是探针平台 <cite>README.md:1-9</cite>。

## 安装步骤

```bash
go build -o bin/probe_exporter ./cmd/probe_exporter
go build -o bin/custom-probe ./cmd/custom-probe
mysql -uuser -p < db/migrations/*.sql
```

## 启动与验证

```bash
./bin/probe_exporter --config configs/config.yaml
./bin/custom-probe --target http://127.0.0.1:8080
```
"""

_25D_ARCH = """# 整体架构概览

系统由 QuickModule、DefaultModule、DeepModule 组成。
<cite>cmd/custom-probe/main.go:1-40</cite>
<cite>cmd/custom-probe/main.go:41-80</cite>
"""

_25D_MODEL = """# 数据模型

ProbeType 只有 http 与 script。AgentRegistry 定义在文档里。
<cite>docs/DESIGN.md:1-20</cite>
<cite>cmd/custom-probe/main.go:10-30</cite>
"""


def test_readme_run_section_is_not_badge_header(tmp_path: Path) -> None:
    _write_synthetic_go_repo(tmp_path)
    text = (tmp_path / "README.md").read_text(encoding="utf-8")
    ranges = readme_run_section_ranges(text)
    assert ranges
    start, _end = ranges[0]
    assert start > 9
    page = WikiPagePlan(
        page_id="installation",
        title="安装指南",
        category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
        output_path="docs/pages/install.md",
        source_requirements=SourceRequirement(files=["README.md"]),
        tags=["installation"],
    )
    spans = [
        EvidenceSpanRecord(
            digest="badge",
            file_path="README.md",
            line_start=1,
            line_end=9,
            language="markdown",
            span_text="\n".join(text.splitlines()[:9]),
            symbol="README",
        ),
        EvidenceSpanRecord(
            digest="run",
            file_path="README.md",
            line_start=start,
            line_end=start + 8,
            language="markdown",
            span_text="\n".join(text.splitlines()[start - 1 : start + 8]),
            symbol="快速开始",
        ),
    ]
    ranked = rank_evidence_for_page(page, spans)
    assert ranked
    top = ranked[0].span
    assert top.line_start >= start


def test_install_commands_prefer_core_over_demo(tmp_path: Path) -> None:
    _write_synthetic_go_repo(tmp_path)
    commands = collect_repo_install_commands(tmp_path)
    blob = "\n".join(commands)
    assert "podman-compose" in blob
    assert "schema.sql" in blob
    assert "ccagent" in blob
    assert any("localhost:" in item and "health" in item for item in commands)
    assert any("./cmd/ccagent" in item for item in commands)
    assert not any("ccprobe-control/main.go" in item for item in commands)
    assert not any("custom-probe" in item for item in commands)
    assert not any("probe_exporter" in item and "cmd/probe_exporter" in item for item in commands)
    planner = RuleFirstPlanner(
        resolve_repository_identity(tmp_path),
        RepositoryScanner(
            RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
        ).scan(),
    ).generate()
    install = next(page for page in planner.pages if page.page_id == "installation")
    overview = next(page for page in planner.pages if page.page_id == "project-overview")
    models = next(page for page in planner.pages if page.page_id == "data-models-overview")
    assert "README.md" in install.source_requirements.files
    assert any("ccagent" in item for item in overview.source_requirements.files)
    assert any(
        "internal/models" in item or item.endswith("schema.sql")
        for item in models.source_requirements.files
    )


def test_25d_like_pages_fail_tightened_handbook_checks(tmp_path: Path) -> None:
    _write_synthetic_go_repo(tmp_path)
    content = tmp_path / "content"
    content.mkdir()
    (content / "安装与配置.md").write_text(_25D_INSTALL, encoding="utf-8")
    (content / "整体架构概览.md").write_text(_25D_ARCH, encoding="utf-8")
    (content / "数据模型.md").write_text(_25D_MODEL, encoding="utf-8")
    verifier = QoderLikeVerifierService(tmp_path, strict=True)
    install = verifier._check_handbook_install_run()
    arch = verifier._check_handbook_architecture_core()
    model = verifier._check_handbook_data_model_source()
    assert install.status == "FAIL"
    assert install.reason_code == "QODER_HANDBOOK_INSTALL_RUN"
    assert arch.status == "FAIL"
    assert arch.reason_code == "QODER_HANDBOOK_ARCHITECTURE_CORE"
    assert model.status == "FAIL"
    assert model.reason_code == "QODER_HANDBOOK_DATA_MODEL_SOURCE"
    assert install_fenced_commands_are_grounded(_25D_INSTALL, tmp_path) is False
    assert has_readme_run_section_citation(_25D_INSTALL, tmp_path) is False
    assert has_architecture_core_citation(_25D_ARCH, tmp_path) is False
    assert has_data_model_source_citation(_25D_MODEL, tmp_path) is False


def test_page_contract_rewrites_install_and_attaches_core_cites(tmp_path: Path) -> None:
    _write_synthetic_go_repo(tmp_path)
    cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
    service = RepoWikiService(cfg)
    install_page = WikiPagePlan(
        page_id="installation",
        title="安装指南",
        category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
        output_path="docs/pages/install.md",
        tags=["installation"],
    )
    rewritten = service._enforce_qoder_page_contract(install_page, _25D_INSTALL, None, False)
    assert install_fenced_commands_are_grounded(rewritten, tmp_path) is False
    assert "podman-compose up -d --build --force-recreate" not in rewritten
    allowed = collect_repo_install_commands(tmp_path)
    assert any("podman-compose" in item for item in allowed)
    assert any("schema.sql" in item or "ccagent" in item for item in allowed)
    arch_page = WikiPagePlan(
        page_id="architecture-overview",
        title="架构设计",
        category=WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
        output_path="docs/pages/arch.md",
    )
    arch = service._enforce_qoder_page_contract(arch_page, _25D_ARCH, None, False)
    assert "是仓库中的实现包" not in arch
    from repo_wiki.verifier.handbook import architecture_required_packages

    required = architecture_required_packages(tmp_path)
    assert has_architecture_core_citation(
        arch + "".join(f"<cite>{rel}/x.go:1-1</cite>" for rel in required), tmp_path
    )
    model_page = WikiPagePlan(
        page_id="data-models-overview",
        title="数据模型",
        category=WikiTaxonomyCategory.DATA_MODELS,
        output_path="docs/pages/models.md",
    )
    model = service._enforce_qoder_page_contract(model_page, _25D_MODEL, None, False)
    assert has_data_model_source_citation(model, tmp_path) is True


def test_receiver_typed_handler_keeps_extractor_line(tmp_path: Path) -> None:
    _write_synthetic_go_repo(tmp_path)
    snapshot = RepositoryScanner(
        RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
    ).scan()
    probe = next(ep for ep in snapshot.endpoints if ep.path == "/probe/endpoint/create")
    biz = next(ep for ep in snapshot.endpoints if ep.path == "/biz/instance/create")
    assert probe.handler.endswith("ServiceProbeEndpoint.ServeCreate")
    assert biz.handler.endswith("ServiceBizTree.ServeCreate")
    assert probe.line_number > biz.line_number > 1


def test_er_uses_go_types_and_belongs_to_direction() -> None:
    planner = create_planner()
    renderer = create_renderer()
    diagrams = planner.plan_diagram_for_page(
        "data-model",
        "data",
        None,
        {
            "data_models": [
                {
                    "name": "ProbeEndpoint",
                    "type": "go_gorm",
                    "file_path": "internal/models/endpoint.go",
                    "primary_key": "ID",
                    "attributes": ["ID", "Name"],
                    "attribute_types": ["int64", "string"],
                    "relationships": ["has_many:ProbeTag"],
                },
                {
                    "name": "ProbeTag",
                    "type": "go_gorm",
                    "file_path": "internal/models/endpoint.go",
                    "primary_key": "ID",
                    "attributes": ["ID", "EndpointID"],
                    "attribute_types": ["int64", "int64"],
                    "relationships": ["belongs_to:ProbeEndpoint"],
                },
                {
                    "name": "BizTreeNode",
                    "type": "go_gorm",
                    "file_path": "internal/models/tree.go",
                    "primary_key": "ID",
                    "attributes": ["ID", "ParentID"],
                    "attribute_types": ["int64", "int64"],
                    "relationships": ["belongs_to:BizTreeNode"],
                },
            ]
        },
    )
    rendered = renderer.render_diagram(diagrams[0])
    assert "int ID PK" in rendered
    assert "string ID PK" not in rendered
    assert "ProbeEndpoint ||--o{ ProbeTag" in rendered
    assert "ProbeTag ||--o{ ProbeEndpoint" not in rendered
    assert "BizTreeNode ||--o{ BizTreeNode" in rendered


def test_schema_sql_foreign_keys_merge_into_snapshot(tmp_path: Path) -> None:
    _write_synthetic_go_repo(tmp_path)
    snapshot = RepositoryScanner(
        RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
    ).scan()
    endpoint = next(model for model in snapshot.data_models if model.name == "ProbeEndpoint")
    tag = next(model for model in snapshot.data_models if model.name == "ProbeTag")
    assert endpoint.attribute_types
    assert any(item != "string" for item in endpoint.attribute_types)
    assert any(item.startswith("belongs_to:ProbeEndpoint") for item in tag.relationships)


def test_backtick_path_then_line_leaves_span_bytes() -> None:
    raw = "见 `internal/models/endpoint.go`:12-20。"
    rewritten = normalize_citation_markup(raw)
    assert "`internal/models/endpoint.go`" in rewritten
    assert sacred_code_offenders(rewritten, raw) == []


def test_page_dump_detects_21_25_and_endpoint_leak() -> None:
    assert is_qoder_page_dump("Tests 21/25 / Coverage 84%\n\n说明。\n") is True
    assert page_has_prompt_leakage("以下端点来自扫描结果") is True


def test_schema_sql_alone_does_not_satisfy_go_data_model_check(tmp_path: Path) -> None:
    _write_synthetic_go_repo(tmp_path)
    page = "# 数据模型\n\n表结构见 schema。<cite>db/schema.sql:1-8</cite>\n"
    assert has_data_model_source_citation(page, tmp_path) is False
    from repo_wiki.generator.deterministic_sections import discover_go_struct_names, go_struct_cite

    page += "<cite>internal/models/endpoint.go:4-20</cite>\n"
    from repo_wiki.verifier.handbook import discover_model_classes

    page += "".join(
        go_struct_cite(tmp_path, name) + "\n" for name in discover_go_struct_names(tmp_path)
    )
    page += " ".join(name for name, _rel in discover_model_classes(tmp_path)) + "\n"
    assert has_data_model_source_citation(page, tmp_path) is True


def test_architecture_requires_exporter_and_python_routes(tmp_path: Path) -> None:
    _write_synthetic_go_repo(tmp_path)
    go_page = (
        "# 架构\n\n控制面。<cite>internal/control/tunnel.go:1-2</cite>"
        "<cite>internal/services/serv_probe_endpoint.go:1-4</cite>\n"
    )
    assert has_architecture_core_citation(go_page, tmp_path) is False
    go_page += "<cite>internal/exporter/prom.go:1-3</cite>\n"
    from repo_wiki.verifier.handbook import architecture_required_packages

    required = architecture_required_packages(tmp_path)
    assert has_architecture_core_citation(go_page, tmp_path) is False
    go_page += "".join(f"<cite>{rel}/x.go:1-1</cite>" for rel in required)
    assert has_architecture_core_citation(go_page, tmp_path) is True
    py_root = tmp_path / "pyapp"
    py_root.mkdir()
    (py_root / "app" / "api" / "routes").mkdir(parents=True)
    (py_root / "app" / "models").mkdir(parents=True)
    (py_root / "app" / "api" / "routes" / "users.py").write_text("x=1\n", encoding="utf-8")
    (py_root / "app" / "models" / "user.py").write_text("x=1\n", encoding="utf-8")
    py_page = "# 架构\n\n模型。<cite>app/models/user.py:1-1</cite>\n"
    assert has_architecture_core_citation(py_page, py_root) is False
    py_page += "<cite>app/api/routes/users.py:1-1</cite>\n"
    assert has_architecture_core_citation(py_page, py_root) is True


def test_go_build_main_with_siblings_fails_install_check(tmp_path: Path) -> None:
    _write_synthetic_go_repo(tmp_path)
    page = (
        "# 安装\n\n```bash\n"
        "go build -o bin/ccprobe-control ./cmd/ccprobe-control/main.go\n"
        "```\n<cite>README.md:12-20</cite>\n"
    )
    assert install_go_builds_use_package_dir(page, tmp_path) is False
    assert install_fenced_commands_are_grounded(page, tmp_path) is False
    fixed = page.replace("./cmd/ccprobe-control/main.go", "./cmd/ccprobe-control")
    assert install_go_builds_use_package_dir(fixed, tmp_path) is True


def test_heading_only_readme_cite_is_not_run_section(tmp_path: Path) -> None:
    _write_synthetic_go_repo(tmp_path)
    assert (
        has_readme_run_section_citation("# 安装\n<cite>README.md:11-12</cite>\n", tmp_path) is False
    )
    ranges = readme_run_section_ranges((tmp_path / "README.md").read_text(encoding="utf-8"))
    start, end = ranges[0]
    cited = f"# 安装\n<cite>README.md:{start}-{end}</cite>\n"
    assert has_readme_run_section_citation(cited, tmp_path) is True


def test_placeholder_mermaid_copied_across_pages_fails(tmp_path: Path) -> None:
    content = tmp_path / "content"
    content.mkdir()
    block = (
        "```mermaid\nflowchart TD\n"
        '    A["应用模块"] --> B["业务服务"]\n'
        '    B --> C["数据与仓库"]\n```\n'
    )
    (content / "a.md").write_text("# A\n\n" + block, encoding="utf-8")
    (content / "b.md").write_text("# B\n\n" + block, encoding="utf-8")
    pages = handbook_placeholder_mermaid_pages(content)
    assert len(pages) == 2
    verifier = QoderLikeVerifierService(tmp_path, strict=True)
    result = verifier._check_handbook_placeholder_mermaid()
    assert result.status == "FAIL"
    assert result.reason_code == "QODER_HANDBOOK_PLACEHOLDER_MERMAID"


def test_er_derives_real_fks_and_skips_endpoint_self_loop(tmp_path: Path) -> None:
    _write_synthetic_go_repo(tmp_path)
    snapshot = RepositoryScanner(
        RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
    ).scan()
    by_name = {model.name: model for model in snapshot.data_models}
    assert "belongs_to:BizTreeNode" in by_name["BizTreeNode"].relationships
    assert "belongs_to:BizTreeNode" in by_name["BizInstanceEndpoint"].relationships
    assert "belongs_to:BizTreeNode" in by_name["ProbePolicy"].relationships
    assert "belongs_to:ProbeEndpoint" in by_name["ProbeResult"].relationships
    assert "belongs_to:ProbeEndpoint" not in by_name["ProbeEndpoint"].relationships
    planner = create_planner()
    renderer = create_renderer()
    diagrams = planner.plan_diagram_for_page(
        "data-model",
        "data",
        None,
        {
            "data_models": [
                {
                    "name": model.name,
                    "type": model.type,
                    "file_path": model.file_path,
                    "primary_key": model.primary_key,
                    "attributes": model.attributes,
                    "attribute_types": model.attribute_types,
                    "relationships": model.relationships,
                }
                for model in snapshot.data_models
            ]
        },
    )
    rendered = renderer.render_diagram(diagrams[0])
    assert "ProbeEndpoint ||--o{ ProbeEndpoint" not in rendered
    assert "BizTreeNode ||--o{ BizTreeNode" in rendered
    assert "BizTreeNode ||--o{ BizInstanceEndpoint" in rendered
    assert "BizTreeNode ||--o{ ProbePolicy" in rendered
    assert "ProbeEndpoint ||--o{ ProbeResult" in rendered
    assert "float Latency" in rendered


def test_source_listen_port_prefers_config_over_readme(tmp_path: Path) -> None:
    _write_synthetic_go_repo(tmp_path)
    assert 1900 in collect_source_listen_ports(tmp_path)
    commands = collect_repo_install_commands(tmp_path)
    blob = "\n".join(commands)
    assert "localhost:" in blob
    # README listen ports are not rewritten onto a preferred source port.


def test_fastapi_install_collects_poetry_alembic_uvicorn(tmp_path: Path) -> None:
    (tmp_path / "app" / "api" / "routes").mkdir(parents=True)
    (tmp_path / "app" / "models").mkdir(parents=True)
    (tmp_path / "alembic" / "versions").mkdir(parents=True)
    (tmp_path / "app" / "main.py").write_text("app = None\n", encoding="utf-8")
    (tmp_path / "app" / "api" / "routes" / "users.py").write_text("x=1\n", encoding="utf-8")
    (tmp_path / "app" / "models" / "user.py").write_text("x=1\n", encoding="utf-8")
    (tmp_path / "alembic.ini").write_text("[alembic]\n", encoding="utf-8")
    (tmp_path / "alembic" / "versions" / "001_init.py").write_text("x=1\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[tool.poetry]\nname='x'\n", encoding="utf-8")
    (tmp_path / "README.rst").write_text(
        "Install\n=======\n\n::\n\n    poetry install\n    alembic upgrade head\n"
        "    uvicorn app.main:app --reload\n",
        encoding="utf-8",
    )
    commands = collect_repo_install_commands(tmp_path)
    blob = "\n".join(commands)
    assert "poetry install" in blob
    assert "alembic upgrade head" in blob
    assert "uvicorn app.main:app --reload" in blob
    model_page = "# 数据模型\n<cite>app/api/routes/users.py:1-1</cite>\n"
    assert has_data_model_source_citation(model_page, tmp_path) is False
    model_page += (
        "<cite>app/models/user.py:1-1</cite><cite>alembic/versions/001_init.py:1-1</cite>\n"
    )
    assert has_data_model_source_citation(model_page, tmp_path) is True


def test_page_contract_strips_note_and_reading_boilerplate(tmp_path: Path) -> None:
    _write_synthetic_go_repo(tmp_path)
    cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
    service = RepoWikiService(cfg)
    page = WikiPagePlan(
        page_id="data-models-overview",
        title="数据模型",
        category=WikiTaxonomyCategory.DATA_MODELS,
        output_path="docs/pages/models.md",
    )
    raw = (
        "# 数据模型\n\n**NOTE**: This repository is not actively maintained because "
        "this example is quite complete.\n\n"
        "实体已确认 <cite>docs/DESIGN.md:1-2</cite> 待确认。\n\n"
        "## 阅读说明\n\n这是套话。\n"
    )
    rewritten = service._enforce_qoder_page_contract(page, raw, None, False)
    assert "NOTE" not in rewritten
    assert "阅读说明" not in rewritten
    assert "待确认" not in rewritten
    assert has_data_model_source_citation(rewritten, tmp_path) is True


def test_planner_folds_thin_readme_and_demo_api_pages(tmp_path: Path) -> None:
    _write_synthetic_go_repo(tmp_path)
    planner = RuleFirstPlanner(
        resolve_repository_identity(tmp_path),
        RepositoryScanner(
            RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
        ).scan(),
    ).generate()
    ids = {page.page_id for page in planner.pages}
    assert "readme" not in ids
    assert "changelog" not in ids
    assert not any(page_id.endswith("custom-probe-api-reference") for page_id in ids)
