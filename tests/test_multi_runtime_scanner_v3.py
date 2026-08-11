"""Unit tests for multi_runtime_scanner_v3 — scan_single_file per-language paths."""

from __future__ import annotations

from pathlib import Path

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.scanner.multi_runtime_scanner_v3 import (
    MultiRuntimeSourceScannerV3,
    _lang_from_suffix,
    _merge_lists,
    scan_single_file,
)

# -- _lang_from_suffix ---------------------------------------------------


class TestLangFromSuffix:
    def test_python(self):
        assert _lang_from_suffix(Path("app.py")) == "python"

    def test_java(self):
        assert _lang_from_suffix(Path("Ctrl.java")) == "java"

    def test_kotlin(self):
        assert _lang_from_suffix(Path("Svc.kt")) == "kotlin"

    def test_go(self):
        assert _lang_from_suffix(Path("main.go")) == "go"

    def test_typescript(self):
        assert _lang_from_suffix(Path("app.ts")) == "typescript"

    def test_tsx(self):
        assert _lang_from_suffix(Path("view.tsx")) == "tsx"

    def test_javascript(self):
        assert _lang_from_suffix(Path("app.js")) == "javascript"

    def test_yaml(self):
        assert _lang_from_suffix(Path("openapi.yaml")) == "yaml"

    def test_json(self):
        assert _lang_from_suffix(Path("spec.json")) == "json"

    def test_sql(self):
        assert _lang_from_suffix(Path("init.sql")) == "sql"

    def test_prisma(self):
        assert _lang_from_suffix(Path("schema.prisma")) == "prisma"

    def test_dockerfile_by_suffix(self):
        assert _lang_from_suffix(Path("prod.dockerfile")) == "dockerfile"

    def test_dockerfile_by_name(self):
        assert _lang_from_suffix(Path("Dockerfile")) == "dockerfile"

    def test_unknown(self):
        assert _lang_from_suffix(Path("style.css")) == "unknown"


# -- scan_single_file: Java/Spring ---------------------------------------


class TestScanJavaLike:
    def test_spring_controller_and_mappings(self):
        text = """
@RestController
@RequestMapping("/api")
class UserController {
    @GetMapping("/users")
    public List<User> list() { return null; }

    @PostMapping("/users")
    public User create() { return null; }

    @DeleteMapping("/users/{id}")
    public void delete() {}
}
"""
        r = scan_single_file(Path("src/UserController.java"), text)
        assert any(s["kind"] == "spring_component" for s in r.services)
        api_methods = {a["method"] for a in r.api_surfaces}
        assert "GET" in api_methods
        assert "POST" in api_methods
        assert "DELETE" in api_methods

    def test_jpa_entity(self):
        text = """
@Entity
class Order {
    @Id Long id;
}
"""
        r = scan_single_file(Path("src/Order.java"), text)
        models = {m["name"] for m in r.data_models}
        assert "Order" in models

    def test_empty_java_file(self):
        r = scan_single_file(Path("Empty.java"), "")
        assert r.services == []
        assert r.api_surfaces == []
        assert r.data_models == []


# -- scan_single_file: Python -------------------------------------------


class TestScanPython:
    def test_fastapi_routes(self):
        text = """
from fastapi import APIRouter

router = APIRouter()

@router.get("/items")
async def list_items(): pass

@router.post("/items")
def create_item(): pass
"""
        r = scan_single_file(Path("src/routes.py"), text)
        assert any(s["kind"] == "python_fastapi_app" for s in r.services)
        methods = {a["method"] for a in r.api_surfaces}
        assert "GET" in methods
        assert "POST" in methods

    def test_flask_app(self):
        text = "app = Flask(__name__)"
        r = scan_single_file(Path("app.py"), text)
        assert any(s["kind"] == "python_flask_app" for s in r.services)

    def test_pydantic_model(self):
        text = """
from pydantic import BaseModel

class ItemModel(BaseModel):
    id: int
"""
        r = scan_single_file(Path("models.py"), text)
        assert any(m["name"] == "ItemModel" for m in r.data_models)

    def test_pytest_detection(self):
        text = "import pytest\ndef test_something(): pass"
        r = scan_single_file(Path("tests/test_foo.py"), text)
        assert r.tests
        assert r.tests[0]["framework_guess"] == "pytest"


# -- scan_single_file: JS/TS -------------------------------------------


class TestScanJsTs:
    def test_express_routes_no_duplicate(self):
        text = """
const app = express();
app.get('/users', listUsers);
app.post('/users', createUser);
app.get('/users', listUsers);
"""
        r = scan_single_file(Path("src/server.ts"), text)
        assert any(s["kind"] == "nodejs_express" for s in r.services)
        unique_routes = {(a["method"], a["path"]) for a in r.api_surfaces}
        assert len(unique_routes) == 2
        assert ("GET", "/users") in unique_routes
        assert ("POST", "/users") in unique_routes
        get_route = [a for a in r.api_surfaces if a["method"] == "GET"][0]
        assert get_route["handler"] == "listUsers"

    def test_anonymous_handler(self):
        text = """app.get('/health', (req, res) => res.send('ok'));"""
        r = scan_single_file(Path("src/app.js"), text)
        assert r.api_surfaces
        assert r.api_surfaces[0]["handler"] == "anonymous"

    def test_frontend_callers(self):
        text = 'axios.get("/api/items")'
        r = scan_single_file(Path("web/client.ts"), text)
        assert r.frontend_callers
        assert r.frontend_callers[0]["target"] == "/api/items"


# -- scan_single_file: Go -----------------------------------------------


class TestScanGo:
    def test_main_and_http_handler(self):
        text = """
package main

func main() {
    http.HandleFunc("/ping", pingHandler)
}

func pingHandler(w http.ResponseWriter, r *http.Request) {}
"""
        r = scan_single_file(Path("main.go"), text)
        assert any(s["kind"] == "go_main" for s in r.services)
        assert any(a["path"] == "/ping" for a in r.api_surfaces)

    def test_db_struct(self):
        text = """
type User struct {
    ID   int    `db:"id"`
    Name string `db:"name"`
}
"""
        r = scan_single_file(Path("models.go"), text)
        assert any(m["name"] == "User" and m["kind"] == "go_struct_db" for m in r.data_models)

    def test_non_db_struct_excluded(self):
        text = "type Config struct { Timeout int }"
        r = scan_single_file(Path("config.go"), text)
        assert all(m["kind"] != "go_struct_db" for m in r.data_models)


# -- scan_single_file: YAML / Dockerfile / Prisma ----------------------


class TestScanYamlAndOthers:
    def test_openapi_yaml(self):
        text = """
openapi: 3.0.0
paths:
  /users:
    get:
      summary: list
  /items:
    post:
      summary: create
"""
        r = scan_single_file(Path("openapi.yaml"), text)
        assert any(a["path"] == "/users" for a in r.api_surfaces)

    def test_docker_compose(self):
        text = """
version: "3"
services:
  web:
    image: nginx
  db:
    image: postgres
"""
        r = scan_single_file(Path("docker-compose.yml"), text)
        svc_names = {s.get("name") or s.get("service") for s in r.deployment + r.services}
        assert "web" in svc_names
        assert "db" in svc_names

    def test_ci_workflow(self):
        text = """
on: push
jobs:
  build:
    steps:
      - run: echo hi
"""
        r = scan_single_file(Path(".github/workflows/ci.yml"), text)
        assert any(d["kind"] == "ci_workflow" for d in r.deployment)

    def test_dockerfile_base_image(self):
        text = "FROM python:3.12-slim\nRUN pip install app"
        r = scan_single_file(Path("Dockerfile"), text)
        assert r.deployment
        assert r.deployment[0]["base_image_hint"] == "python:3.12-slim"

    def test_prisma_models(self):
        text = """
model User {
  id Int @id
}
model Post {
  id Int @id
}
"""
        r = scan_single_file(Path("schema.prisma"), text)
        model_names = {m["name"] for m in r.data_models}
        assert "User" in model_names
        assert "Post" in model_names


# -- _merge_lists -------------------------------------------------------


class TestMergeLists:
    def test_deduplicates_identical_dicts(self):
        dst = [{"a": 1}]
        _merge_lists(dst, [{"a": 1}, {"b": 2}])
        assert len(dst) == 2
        assert {"b": 2} in dst

    def test_empty_src(self):
        dst = [{"x": 1}]
        _merge_lists(dst, [])
        assert dst == [{"x": 1}]

    def test_empty_dst(self):
        dst: list[dict] = []
        _merge_lists(dst, [{"a": 1}])
        assert dst == [{"a": 1}]


# -- health probe hint (any language) -----------------------------------


class TestHealthProbeHint:
    def test_health_probe_in_python(self):
        text = "def health_check(): pass"
        r = scan_single_file(Path("health.py"), text)
        assert any(d["kind"] == "health_probe_hint" for d in r.deployment)

    def test_readiness_in_go(self):
        text = "func readinessProbe() {}"
        r = scan_single_file(Path("probe.go"), text)
        assert any(d["kind"] == "health_probe_hint" for d in r.deployment)


# -- incremental scanner state/checkpoint --------------------------------


def test_v3_incremental_reuses_changes_and_deletes_with_checkpoint(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def health():\n    return 'ok'\n", encoding="utf-8")
    (tmp_path / "web.ts").write_text("fetch('/api/health')\n", encoding="utf-8")
    cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
    scanner = MultiRuntimeSourceScannerV3(cfg)

    first = scanner.scan(batch_size=1)
    assert first["scanner"]["stats"]["files_rescanned"] == 2
    assert first["scanner"]["checkpoint"]["batch_size"] == 1
    assert first["scanner"]["checkpoint"]["files_seen"] == 2
    assert first["scanner"]["checkpoint"]["scanner_config_fingerprint"]
    assert first["scanner"]["checkpoint"]["inventory_fingerprint"]

    second = scanner.scan(batch_size=1)
    assert second["scanner"]["stats"]["files_rescanned"] == 0
    assert second["scanner"]["stats"]["files_cached"] == 2

    (tmp_path / "app.py").write_text("def health():\n    return 'changed'\n", encoding="utf-8")
    third = scanner.scan(batch_size=1)
    assert third["scanner"]["stats"]["files_rescanned"] == 1
    assert third["scanner"]["stats"]["files_cached"] == 1

    (tmp_path / "web.ts").unlink()
    fourth = scanner.scan(batch_size=1)
    assert fourth["scanner"]["stats"]["files_deleted"] == 1
    assert {f["path"] for f in fourth["files"]} == {"app.py"}
    state = scanner._load_state()  # noqa: SLF001
    assert set(state["file_hashes"]) == {"app.py"}
    assert state["checkpoint"]["files_deleted"] == 1
