"""FastAPI APIRouter prefixes and decorator isolation for product HTTP inventory."""

from __future__ import annotations

from pathlib import Path

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.scanner.multi_runtime_scanner_v3 import scan_repository_source_inventory_v3
from repo_wiki.scanner.repository_scanner import RepositoryScanner


def _scan(root: Path):
    cfg = RepoWikiConfig.model_validate({"project": {"root": str(root)}})
    return RepositoryScanner(cfg).scan()


def _endpoint_pairs(snapshot) -> set[tuple[str, str]]:
    return {(endpoint.method, endpoint.path) for endpoint in snapshot.endpoints}


def _v3_endpoint_pairs(root: Path) -> set[tuple[str, str]]:
    inventory = scan_repository_source_inventory_v3(root, incremental=False)
    return {
        (str(item["method"]).upper(), str(item["path"]))
        for item in inventory["api_surfaces"]
        if item.get("method") and item.get("path")
    }


def _write_realworld_fastapi_tree(root: Path) -> None:
    """Multi-file FastAPI tree matching nsidnev RealWorld mount/settings shape."""
    settings_dir = root / "app" / "core" / "settings"
    routes = root / "app" / "api" / "routes"
    settings_dir.mkdir(parents=True)
    routes.mkdir(parents=True)
    (root / "app" / "__init__.py").write_text("", encoding="utf-8")
    (root / "app" / "core" / "__init__.py").write_text("", encoding="utf-8")
    (root / "app" / "api" / "__init__.py").write_text("", encoding="utf-8")
    (routes / "__init__.py").write_text("", encoding="utf-8")
    (settings_dir / "__init__.py").write_text("", encoding="utf-8")
    (settings_dir / "app.py").write_text(
        """
class AppSettings:
    api_prefix: str = "/api"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (root / "app" / "core" / "config.py").write_text(
        """
from app.core.settings.app import AppSettings


def get_app_settings():
    return AppSettings()
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (routes / "authentication.py").write_text(
        """
from fastapi import APIRouter

router = APIRouter()


@router.post("/login")
async def login():
    return {"token": "x"}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (routes / "articles.py").write_text(
        """
from fastapi import APIRouter

router = APIRouter()


@router.get("")
def list_articles():
    return []


@router.get("/feed")
def get_feed():
    return []


@router.get("/{slug}")
def get_article():
    return {}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (routes / "api.py").write_text(
        """
from fastapi import APIRouter

from app.api.routes import articles, authentication

router = APIRouter()
router.include_router(authentication.router, prefix="/users")
router.include_router(articles.router, prefix="/articles")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (root / "app" / "main.py").write_text(
        """
from fastapi import FastAPI

from app.api.routes.api import router as api_router
from app.core.config import get_app_settings


def get_application():
    settings = get_app_settings()
    application = FastAPI()
    application.include_router(api_router, prefix=settings.api_prefix)
    return application


app = get_application()
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (root / "requirements.txt").write_text("fastapi\n", encoding="utf-8")


def test_include_router_prefix_is_joined_into_product_path(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text(
        """
from fastapi import APIRouter, FastAPI

router = APIRouter()


@router.post("/login")
async def login():
    return {"ok": True}


api = APIRouter()
api.include_router(router, prefix="/users")

app = FastAPI()
app.include_router(api)
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "requirements.txt").write_text("fastapi\n", encoding="utf-8")

    snapshot = _scan(tmp_path)
    pairs = {(endpoint.method, endpoint.path) for endpoint in snapshot.endpoints}

    assert ("POST", "/users/login") in pairs
    assert ("POST", "/login") not in pairs


def test_app_include_router_prefix_is_joined(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text(
        """
from fastapi import APIRouter, FastAPI

router = APIRouter()


@router.post("/login")
async def login():
    return {"ok": True}


api = APIRouter()
api.include_router(router, prefix="/users")

app = FastAPI()
app.include_router(api, prefix="/api")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "requirements.txt").write_text("fastapi\n", encoding="utf-8")

    snapshot = _scan(tmp_path)
    pairs = {(endpoint.method, endpoint.path) for endpoint in snapshot.endpoints}

    assert ("POST", "/api/users/login") in pairs
    assert ("POST", "/login") not in pairs
    assert ("POST", "/users/login") not in pairs


def test_cross_file_include_router_prefix_is_joined(tmp_path: Path) -> None:
    routes = tmp_path / "app" / "api" / "routes"
    routes.mkdir(parents=True)
    (routes / "authentication.py").write_text(
        """
from fastapi import APIRouter

router = APIRouter()


@router.post("/login")
async def login():
    return {"token": "x"}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (routes / "api.py").write_text(
        """
from fastapi import APIRouter

from app.api.routes import authentication

router = APIRouter()
router.include_router(authentication.router, prefix="/users")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "app" / "main.py").write_text(
        """
from fastapi import FastAPI

from app.api.routes.api import router as api_router

app = FastAPI()
app.include_router(api_router)
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "requirements.txt").write_text("fastapi\n", encoding="utf-8")

    snapshot = _scan(tmp_path)
    pairs = {(endpoint.method, endpoint.path) for endpoint in snapshot.endpoints}

    assert ("POST", "/users/login") in pairs
    assert ("POST", "/login") not in pairs


def test_decorator_method_and_path_stay_on_their_handler(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "articles.py").write_text(
        """
from fastapi import APIRouter, FastAPI

router = APIRouter()


@router.get("")
def list_articles():
    return []


@router.get("/{slug}")
def get_article():
    return {}


@router.delete("/{slug}")
def delete_article():
    return None


app = FastAPI()
app.include_router(router, prefix="/articles")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "requirements.txt").write_text("fastapi\n", encoding="utf-8")

    snapshot = _scan(tmp_path)
    by_handler = {}
    for endpoint in snapshot.endpoints:
        by_handler.setdefault(endpoint.handler, []).append(endpoint)

    list_eps = by_handler["list_articles"]
    assert list_eps
    assert all(endpoint.method == "GET" for endpoint in list_eps)
    assert all(endpoint.method != "DELETE" for endpoint in list_eps)
    assert all(
        endpoint.path in {"", "/", "/articles"} or endpoint.path.endswith("/articles")
        for endpoint in list_eps
    )
    assert not any("/{slug}" in endpoint.path for endpoint in list_eps)

    get_eps = by_handler["get_article"]
    assert get_eps
    assert all(endpoint.method == "GET" for endpoint in get_eps)
    assert any(endpoint.path.endswith("/{slug}") for endpoint in get_eps)

    delete_eps = by_handler["delete_article"]
    assert delete_eps
    assert all(endpoint.method == "DELETE" for endpoint in delete_eps)
    assert any(endpoint.path.endswith("/{slug}") for endpoint in delete_eps)


def test_imported_router_alias_literal_prefix_is_joined(tmp_path: Path) -> None:
    """`from auth import router as auth_router` must still join prefix=/users."""
    (tmp_path / "auth.py").write_text(
        """
from fastapi import APIRouter

router = APIRouter()


@router.post("/login")
def login():
    return {"token": "x"}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "api.py").write_text(
        """
from fastapi import APIRouter

from auth import router as auth_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/users")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "main.py").write_text(
        """
from fastapi import FastAPI

from api import api_router

app = FastAPI()
app.include_router(api_router)
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "requirements.txt").write_text("fastapi\n", encoding="utf-8")

    snapshot = _scan(tmp_path)
    pairs = {(endpoint.method, endpoint.path) for endpoint in snapshot.endpoints}

    assert ("POST", "/users/login") in pairs
    assert ("POST", "/login") not in pairs


def test_factory_get_application_still_joins_literal_prefixes(tmp_path: Path) -> None:
    """FastAPI() inside get_application() must not drop include_router prefixes."""
    (tmp_path / "auth.py").write_text(
        """
from fastapi import APIRouter

router = APIRouter()


@router.post("/login")
def login():
    return {"token": "x"}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "api.py").write_text(
        """
from fastapi import APIRouter

from auth import router as auth_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/users")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "main.py").write_text(
        """
from fastapi import FastAPI

from api import api_router


def get_application():
    application = FastAPI()
    application.include_router(api_router, prefix="/api")
    return application


app = get_application()
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "requirements.txt").write_text("fastapi\n", encoding="utf-8")

    snapshot = _scan(tmp_path)
    pairs = {(endpoint.method, endpoint.path) for endpoint in snapshot.endpoints}

    assert ("POST", "/api/users/login") in pairs or ("POST", "/users/login") in pairs
    assert ("POST", "/login") not in pairs


def test_non_literal_settings_api_prefix_keeps_literal_router_prefixes(
    tmp_path: Path,
) -> None:
    """settings.api_prefix may resolve to /api; literal /users must still join."""
    (tmp_path / "settings.py").write_text(
        """
class S:
    api_prefix: str = "/api"


settings = S()
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "auth.py").write_text(
        """
from fastapi import APIRouter

router = APIRouter()


@router.post("/login")
def login():
    return {"token": "x"}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "api.py").write_text(
        """
from fastapi import APIRouter

from auth import router as auth_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/users")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "main.py").write_text(
        """
from fastapi import FastAPI

from api import api_router
from settings import settings


def get_application():
    application = FastAPI()
    application.include_router(api_router, prefix=settings.api_prefix)
    return application


app = get_application()
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "requirements.txt").write_text("fastapi\n", encoding="utf-8")

    snapshot = _scan(tmp_path)
    pairs = {(endpoint.method, endpoint.path) for endpoint in snapshot.endpoints}
    login_paths = {path for method, path in pairs if method == "POST" and path.endswith("/login")}

    assert ("POST", "/login") not in pairs
    assert any(path.endswith("/users/login") for path in login_paths)
    assert ("POST", "/api/users/login") in pairs


def test_nested_articles_prefix_joins_empty_and_slug_paths(tmp_path: Path) -> None:
    """Nested prefix=/articles + get('') / get('/{slug}') keep handlers unswapped."""
    (tmp_path / "articles.py").write_text(
        """
from fastapi import APIRouter

router = APIRouter()


@router.get("")
def list_articles():
    return []


@router.get("/{slug}")
def get_article():
    return {}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "api.py").write_text(
        """
from fastapi import APIRouter

from articles import router as articles_router

api_router = APIRouter()
api_router.include_router(articles_router, prefix="/articles")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "main.py").write_text(
        """
from fastapi import FastAPI

from api import api_router


def get_application():
    application = FastAPI()
    application.include_router(api_router)
    return application


app = get_application()
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "requirements.txt").write_text("fastapi\n", encoding="utf-8")

    snapshot = _scan(tmp_path)
    by_handler = {}
    for endpoint in snapshot.endpoints:
        by_handler.setdefault(endpoint.handler, []).append(endpoint)

    list_eps = by_handler["list_articles"]
    assert any(endpoint.method == "GET" and endpoint.path == "/articles" for endpoint in list_eps)
    assert not any("/{slug}" in endpoint.path for endpoint in list_eps)

    get_eps = by_handler["get_article"]
    assert any(
        endpoint.method == "GET" and endpoint.path == "/articles/{slug}" for endpoint in get_eps
    )
    assert not any(endpoint.path == "/articles" for endpoint in get_eps)


def test_factory_get_app_settings_resolves_api_prefix(tmp_path: Path) -> None:
    """No-arg get_app_settings() returning AppSettings() must join api_prefix=/api."""
    _write_realworld_fastapi_tree(tmp_path)
    pairs = _endpoint_pairs(_scan(tmp_path))

    assert ("POST", "/api/users/login") in pairs
    assert ("GET", "/api/articles") in pairs
    assert ("GET", "/api/articles/feed") in pairs
    assert ("GET", "/api/articles/{slug}") in pairs
    assert ("POST", "/login") not in pairs
    assert ("POST", "/users/login") not in pairs


def test_v3_inventory_joins_cross_file_and_settings_factory_prefix(tmp_path: Path) -> None:
    """v3 must scan the full Python set once so include_router prefixes survive."""
    _write_realworld_fastapi_tree(tmp_path)
    pairs = _v3_endpoint_pairs(tmp_path)

    assert ("POST", "/api/users/login") in pairs
    assert ("GET", "/api/articles") in pairs
    assert ("GET", "/api/articles/feed") in pairs
    assert ("GET", "/api/articles/{slug}") in pairs
    assert ("POST", "/login") not in pairs
    assert ("POST", "/users/login") not in pairs


def test_v3_and_repository_scanner_agree_on_mounted_fastapi_paths(tmp_path: Path) -> None:
    _write_realworld_fastapi_tree(tmp_path)
    scanner_pairs = _endpoint_pairs(_scan(tmp_path))
    v3_pairs = _v3_endpoint_pairs(tmp_path)
    mounted = {
        ("POST", "/api/users/login"),
        ("GET", "/api/articles"),
        ("GET", "/api/articles/feed"),
        ("GET", "/api/articles/{slug}"),
    }

    assert mounted <= scanner_pairs
    assert mounted <= v3_pairs
    assert scanner_pairs & mounted == v3_pairs & mounted
