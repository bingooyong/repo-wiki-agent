"""Round 26: checker false alarms seen in the Nov 10 live acceptance (stage 1-4 drafts).

Each case is a real line from a Nov 10 draft and the real repository line that proves it;
the checker must accept the real fact and still reject an invented one."""

from __future__ import annotations

from pathlib import Path

from repo_wiki.verifier.handbook_routes import extract_handbook_http_paths
from repo_wiki.verifier.source_facts import handbook_source_fact_offenders


def _repo(tmp: Path, files: dict[str, str]) -> Path:
    root = tmp / "repo"
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return root


def _offenders(tmp: Path, root: Path, page: str, name: str = "installation.md") -> list[str]:
    content = tmp / "content"
    content.mkdir(exist_ok=True)
    (content / name).write_text(page, encoding="utf-8")
    found = handbook_source_fact_offenders(content, root)
    return [h for hits in found.values() for h in hits]


COMPOSE = (
    "version: '3'\nservices:\n  server:\n    image: python:3.7\n    env_file:\n      - .env\n"
    "  db:\n    image: postgres:9.4\n    volumes_from:\n      - dbdata\n"
    "  dbdata:\n    image: busybox\n    volumes:\n      - /var/lib/postgresql/data\n"
)


def test_compose_image_named_on_the_page_is_not_an_invented_service(tmp_path: Path) -> None:
    # Flask install (Nov 10): "`dbdata` 服务使用 `busybox` 镜像" -> compose:busybox
    root = _repo(tmp_path, {"docker-compose.yml": COMPOSE, "README.md": "# x\n"})
    page = (
        "compose 中的 `server` 服务使用 `python:3.7` 镜像，`db` 服务使用 `postgres:9.4` 镜像，"
        "`dbdata` 服务使用 `busybox` 镜像保存数据库数据卷。\n"
    )
    assert not [h for h in _offenders(tmp_path, root, page) if h.startswith("compose:")]


def test_invented_compose_service_is_still_flagged(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"docker-compose.yml": COMPOSE, "README.md": "# x\n"})
    page = "compose 中还定义了 `cache` 服务。\n"
    assert "compose:cache" in _offenders(tmp_path, root, page)


def test_dockerfile_directive_is_a_source_identifier(tmp_path: Path) -> None:
    # Node install (Nov 10): "应用镜像通过 `EXPOSE` 暴露 `3000` 端口" -> ident:EXPOSE
    root = _repo(
        tmp_path,
        {"Dockerfile": "FROM node:alpine\nWORKDIR /app\nEXPOSE 3000\nCMD [\"yarn\", \"start\"]\n", "README.md": "# x\n"},
    )
    assert "ident:EXPOSE" not in _offenders(tmp_path, root, "- 应用镜像通过 `EXPOSE` 暴露 `3000` 端口。\n")


def test_javascript_class_and_binding_are_source_identifiers(tmp_path: Path) -> None:
    # probe overview: `APIClient` (static/script.js: class APIClient {), node API: `JwtStrategy`
    root = _repo(
        tmp_path,
        {
            "static/script.js": "class APIClient {\n  constructor() {}\n}\nnew APIClient();\n",
            "src/config/passport.js": "const { Strategy: JwtStrategy, ExtractJwt } = require('passport-jwt');\n",
            "README.md": "# x\n",
        },
    )
    page = (
        "`static/script.js` 中的 `APIClient` 负责加载接口列表并发起调用。\n"
        "鉴权使用 passport 的 `JwtStrategy`，处理函数类型见源码。\n"
    )
    hits = _offenders(tmp_path, root, page, "project-overview.md")
    assert "ident:APIClient" not in hits and "ident:JwtStrategy" not in hits


def test_invented_type_name_is_still_flagged(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"static/script.js": "class APIClient {}\n", "README.md": "# x\n"})
    hits = _offenders(tmp_path, root, "处理函数类型为 `RequestBroker`。\n", "project-overview.md")
    assert "ident:RequestBroker" in hits


def test_http_method_word_is_not_an_invented_identifier(tmp_path: Path) -> None:
    # node API (first Nov 10 run): "1 条 `OPTIONS` 路由" -> ident:OPTIONS
    root = _repo(tmp_path, {"src/app.js": "app.options('*', cors());\n", "README.md": "# x\n"})
    hits = _offenders(tmp_path, root, "共暴露 16 条路由：1 条 `OPTIONS` 路由。\n", "api-overview.md")
    assert "ident:OPTIONS" not in hits


def test_curl_content_type_header_is_not_a_route() -> None:
    # Go install (Nov 10): curl -X POST -H "Content-Type: application/json" ... -> POST /json
    line = (
        'curl -X POST -H "Content-Type: application/json" -d \'{"username": "demo", "password": "pass"}\' '
        "http://localhost:8080/v1/login"
    )
    found = extract_handbook_http_paths(line, api_page=False)
    assert ("POST", "/json") not in found
    assert ("POST", "/v1/login") in found


def test_curl_with_bare_path_still_extracted() -> None:
    assert ("GET", "/healthcheck") in extract_handbook_http_paths(
        "curl -X GET /healthcheck", api_page=False
    )
