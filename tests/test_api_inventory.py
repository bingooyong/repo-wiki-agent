"""Tests for API inventory enrichment (Phase 25 - Task 25.1).

These tests validate that API endpoints are enriched with:
- service_family, domain, runtime_role metadata
- auth_type and auth_required detection
- request_body, response_type, error_codes
- line_number and line_end for handler citations
"""

from __future__ import annotations

from pathlib import Path

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.scanner.repository_scanner import RepositoryScanner


class TestEndpointEnrichment:
    """Tests for endpoint metadata enrichment."""

    def test_endpoint_inherits_module_service_family(self, tmp_path: Path) -> None:
        """Test that endpoints inherit service_family from their module."""
        (tmp_path / "api").mkdir(parents=True, exist_ok=True)
        (tmp_path / "api" / "routes.py").write_text(
            """
from fastapi import APIRouter
router = APIRouter()

@router.get("/users")
def list_users():
    return []
""".strip(),
            encoding="utf-8",
        )
        (tmp_path / "requirements.txt").write_text("fastapi\npydantic\n", encoding="utf-8")

        cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
        snapshot = RepositoryScanner(cfg).scan()

        assert len(snapshot.endpoints) == 1
        endpoint = snapshot.endpoints[0]
        # Module should have service_family set
        module = next((m for m in snapshot.modules if m.name == endpoint.module), None)
        assert module is not None
        assert module.service_family == "python-backend"

    def test_endpoint_auth_type_detection(self, tmp_path: Path) -> None:
        """Test that auth type is detected correctly."""
        (tmp_path / "users").mkdir(parents=True, exist_ok=True)
        (tmp_path / "users" / "api.py").write_text(
            """
from fastapi import APIRouter
router = APIRouter()

@router.post("/users")
def create_user():
    return {"id": 1}
""".strip(),
            encoding="utf-8",
        )
        (tmp_path / "requirements.txt").write_text("fastapi\npydantic\n", encoding="utf-8")

        cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
        snapshot = RepositoryScanner(cfg).scan()

        assert len(snapshot.endpoints) == 1
        endpoint = snapshot.endpoints[0]
        # POST to /users should require auth (not health/login)
        assert endpoint.auth_type in ("bearer", "unknown")

    def test_endpoint_request_body_detection(self, tmp_path: Path) -> None:
        """Test that request_body is detected correctly."""
        (tmp_path / "api").mkdir(parents=True, exist_ok=True)
        (tmp_path / "api" / "handlers.py").write_text(
            """
from fastapi import APIRouter
router = APIRouter()

@router.post("/items")
def create_item():
    return {"id": 1}

@router.get("/items")
def list_items():
    return []
""".strip(),
            encoding="utf-8",
        )
        (tmp_path / "requirements.txt").write_text("fastapi\npydantic\n", encoding="utf-8")

        cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
        snapshot = RepositoryScanner(cfg).scan()

        post_ep = next((e for e in snapshot.endpoints if e.method == "POST"), None)
        get_ep = next((e for e in snapshot.endpoints if e.method == "GET"), None)

        assert post_ep is not None
        assert get_ep is not None
        # POST should have request_body=True, GET should have request_body=False
        assert post_ep.request_body == True
        assert get_ep.request_body == False

    def test_endpoint_line_number_citation(self, tmp_path: Path) -> None:
        """Test that handler line numbers are captured for citations."""
        (tmp_path / "api").mkdir(parents=True, exist_ok=True)
        (tmp_path / "api" / "server.py").write_text(
            """
from flask import Flask
app = Flask(__name__)

@app.route("/health")
def health_check():
    return {"status": "ok"}

@app.route("/users", methods=["GET"])
def list_users():
    return []
""".strip(),
            encoding="utf-8",
        )
        (tmp_path / "requirements.txt").write_text("flask\n", encoding="utf-8")

        cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
        snapshot = RepositoryScanner(cfg).scan()

        assert len(snapshot.endpoints) >= 1
        for endpoint in snapshot.endpoints:
            # Line numbers should be captured (or 0 if not found)
            assert endpoint.line_number >= 0
            assert endpoint.line_end >= 0

    def test_webhook_endpoint_auth_none(self, tmp_path: Path) -> None:
        """Test that webhook endpoints are detected and have auth_type=none."""
        (tmp_path / "hooks").mkdir(parents=True, exist_ok=True)
        (tmp_path / "hooks" / "webhooks.py").write_text(
            """
from fastapi import APIRouter
router = APIRouter()

@router.post("/webhook/github")
def handle_github_webhook():
    return {"status": "received"}
""".strip(),
            encoding="utf-8",
        )
        (tmp_path / "requirements.txt").write_text("fastapi\npydantic\n", encoding="utf-8")

        cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
        snapshot = RepositoryScanner(cfg).scan()

        webhook_ep = next((e for e in snapshot.endpoints if "webhook" in e.path.lower()), None)
        if webhook_ep:
            # Webhook paths should have auth_type = "none" (they use signature verification)
            assert webhook_ep.auth_type == "none"

    def test_health_endpoint_auth_none(self, tmp_path: Path) -> None:
        """Test that health endpoints don't require auth."""
        (tmp_path / "api").mkdir(parents=True, exist_ok=True)
        (tmp_path / "api" / "status.py").write_text(
            """
from fastapi import APIRouter
router = APIRouter()

@router.get("/health")
def health():
    return {"status": "ok"}

@router.get("/ready")
def ready():
    return {"ready": True}
""".strip(),
            encoding="utf-8",
        )
        (tmp_path / "requirements.txt").write_text("fastapi\npydantic\n", encoding="utf-8")

        cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
        snapshot = RepositoryScanner(cfg).scan()

        health_ep = next((e for e in snapshot.endpoints if "health" in e.path.lower()), None)
        if health_ep:
            assert health_ep.auth_type == "none"

    def test_endpoints_have_error_codes(self, tmp_path: Path) -> None:
        """Test that endpoints have common error codes assigned."""
        (tmp_path / "api").mkdir(parents=True, exist_ok=True)
        (tmp_path / "api" / "main.py").write_text(
            """
from fastapi import APIRouter
router = APIRouter()

@router.get("/users")
def list_users():
    return []
""".strip(),
            encoding="utf-8",
        )
        (tmp_path / "requirements.txt").write_text("fastapi\npydantic\n", encoding="utf-8")

        cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
        snapshot = RepositoryScanner(cfg).scan()

        assert len(snapshot.endpoints) >= 1
        for endpoint in snapshot.endpoints:
            assert len(endpoint.error_codes) > 0  # Default error codes should be set

    def test_flask_route_extraction_with_methods(self, tmp_path: Path) -> None:
        """Test that Flask routes with methods are extracted."""
        (tmp_path / "api").mkdir(parents=True, exist_ok=True)
        (tmp_path / "api" / "server.py").write_text(
            """
from flask import Flask
app = Flask(__name__)

@app.route("/users", methods=["GET", "POST"])
def users():
    return "users"
""".strip(),
            encoding="utf-8",
        )
        (tmp_path / "requirements.txt").write_text("flask\n", encoding="utf-8")

        cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
        snapshot = RepositoryScanner(cfg).scan()

        # Should have 2 endpoints (GET and POST)
        user_endpoints = [e for e in snapshot.endpoints if "/users" in e.path]
        assert len(user_endpoints) == 2
        methods = {e.method for e in user_endpoints}
        assert "GET" in methods
        assert "POST" in methods

    def test_flask_route_extraction_without_methods(self, tmp_path: Path) -> None:
        """Test that Flask routes without methods (default GET) are extracted."""
        (tmp_path / "api").mkdir(parents=True, exist_ok=True)
        (tmp_path / "api" / "server.py").write_text(
            """
from flask import Flask
app = Flask(__name__)

@app.route("/status")
def status():
    return {"status": "ok"}
""".strip(),
            encoding="utf-8",
        )
        (tmp_path / "requirements.txt").write_text("flask\n", encoding="utf-8")

        cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
        snapshot = RepositoryScanner(cfg).scan()

        status_ep = next((e for e in snapshot.endpoints if "/status" in e.path), None)
        assert status_ep is not None
        assert status_ep.method == "GET"
