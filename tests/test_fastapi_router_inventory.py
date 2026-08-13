"""FastAPI APIRouter prefixes and decorator isolation for product HTTP inventory."""

from __future__ import annotations

from pathlib import Path

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.scanner.repository_scanner import RepositoryScanner


def _scan(root: Path):
    cfg = RepoWikiConfig.model_validate({"project": {"root": str(root)}})
    return RepositoryScanner(cfg).scan()


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
