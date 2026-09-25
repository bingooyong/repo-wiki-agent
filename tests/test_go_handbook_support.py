"""Go handbook extraction, install clues, folding, and source-evidence gates."""

from __future__ import annotations

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
from repo_wiki.generator.mermaid_planner import (
    MermaidDiagramType,
    create_planner,
    create_renderer,
    validate_mermaid_syntax,
)
from repo_wiki.orchestration.service import RepoWikiService, _is_filename_like_handbook_title
from repo_wiki.planner.identity import resolve_repository_identity
from repo_wiki.planner.rule_first import RuleFirstPlanner, _is_filename_like_module_name
from repo_wiki.planner.schema import (
    RepositoryIdentity,
    WikiPagePlan,
    WikiTaxonomyCategory,
)
from repo_wiki.scanner.docs_scanner import (
    is_eval_or_agent_instruction_doc,
    is_product_citation_source,
    scan_repository_docs_inventory,
)
from repo_wiki.scanner.go_routes import (
    extract_go_data_models,
    extract_go_endpoints,
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
    has_fenced_install_run_command,
    install_run_clue_count,
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
}

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
    ID   int64  `gorm:"primaryKey;column:id" json:"id"`
    Name string `gorm:"column:name" json:"name"`
}

func (ProbeEndpoint) TableName() string {
    return "probe_endpoints"
}

type AuthConfig struct {
    Type string `json:"type"`
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
        _SERV_PROBE_GO, encoding="utf-8"
    )
    (root / "internal" / "services" / "serv_tag.go").write_text(_SERV_TAG_GO, encoding="utf-8")
    (root / "internal" / "services" / "agent_ops.go").write_text(_RAW_ROUTE_GO, encoding="utf-8")
    (root / "internal" / "models" / "endpoint.go").write_text(_ENDPOINT_MODEL_GO, encoding="utf-8")
    (root / "internal" / "control" / "tunnel.go").write_text(
        "package control\nfunc Dial() {}\n", encoding="utf-8"
    )
    (root / "internal" / "probe" / "result_repo.go").write_text(
        "package probe\nfunc Load() {}\n", encoding="utf-8"
    )
    (root / "cmd" / "ccagent" / "main.go").write_text(
        "package main\nfunc main() {}\n", encoding="utf-8"
    )
    (root / "go.mod").write_text("module ccagent\n\ngo 1.22\n", encoding="utf-8")
    (root / "Makefile").write_text(
        "install:\n\tgo build -o bin/ccagent ./cmd/ccagent/main.go\ntest:\n\tgo test ./...\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        "# probe_exporter\n\n"
        "[![Go Version](https://img.shields.io/badge/Go-1.25+-00ADD8)](https://go.dev/)\n\n"
        "企业级服务探针拨测与结果导出平台。\n\n"
        "```bash\ngo build -o bin/ccagent ./cmd/ccagent/main.go\n```\n",
        encoding="utf-8",
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
    assert any(item.table_name == "probe_endpoints" for item in models)
    assert "UserRow" in names
    assert "AuthConfig" not in names
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
    (tmp_path / "docs").mkdir()
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
    assert section.count("/hello/ping") == 1


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
    assert any("cmd/ccagent/main.go" in item for item in commands)
    assert not any(item.strip() in {"go run .", "go build -o probe_exporter ."} for item in commands)


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
    assert validate_mermaid_syntax("erDiagram\n    X {{id}}\n", MermaidDiagramType.ER_DIAGRAM)[0] is False


def test_architecture_mermaid_prefers_internal_packages() -> None:
    planner = create_planner()
    renderer = create_renderer()
    diagrams = planner.plan_diagram_for_page(
        "architecture",
        "architecture",
        None,
        {
            "modules": [
                {"name": "control", "path": "internal/control"},
                {"name": "probe", "path": "internal/probe"},
                {"name": "services", "path": "internal/services"},
                {"name": "models", "path": "internal/models"},
                {"name": "agent", "path": "internal/agent"},
            ]
        },
    )
    rendered = renderer.render_diagram(diagrams[0])
    assert "internal/control" in rendered
    assert "internal/services" in rendered
    assert "仓库扫描" not in rendered
    assert "LLM生成" not in rendered


def test_repeated_filler_and_prompt_leak_are_page_dumps() -> None:
    pad = "当前证据需要把源码证据、模块职责和调用边界写清楚，读者应对照文中的源码引用核对实现。"
    page = "\n\n".join([pad] * 4)
    assert page_has_repeated_filler(page) is True
    assert page_has_prompt_leakage("端点由用户在请求中提供") is True
    assert is_qoder_page_dump("Tests 21/25 / Coverage 84%\n\n" + "一句说明。\n") is True
    assert is_qoder_page_dump("# 正常页\n\n这是一段足够说明的散文。\n") is False
