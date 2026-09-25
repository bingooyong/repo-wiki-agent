"""Go handbook extraction, install clues, folding, and source-evidence gates."""

from __future__ import annotations

from pathlib import Path

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.core.contracts import (
    Module,
    RepositoryInfo,
    RepositorySnapshot,
)
from repo_wiki.evidence.citation_renderer import normalize_citation_markup
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
from repo_wiki.verifier.handbook import (
    has_fenced_install_run_command,
    install_run_clue_count,
    repo_run_clue_names,
)
from repo_wiki.verifier.qoder_strict_verifier import QoderLikeVerifierService
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
