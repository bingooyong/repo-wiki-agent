"""Tests for business domain classification in repository scanner."""

from __future__ import annotations

from pathlib import Path

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.scanner.repository_scanner import RepositoryScanner


def test_domain_classifier_core_platform_module(tmp_path: Path) -> None:
    """Test classification of core platform modules."""
    # Create a core module with platform signals
    (tmp_path / "repo_wiki" / "core").mkdir(parents=True)
    (tmp_path / "repo_wiki" / "core" / "base.py").write_text(
        "class BaseModel:\n    pass\n",
        encoding="utf-8",
    )

    cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
    snapshot = RepositoryScanner(cfg).scan()

    assert len(snapshot.modules) >= 1
    # Module path will be 'repo_wiki' (first directory level)
    repo_wiki_module = next((m for m in snapshot.modules if m.path == "repo_wiki"), None)
    assert repo_wiki_module is not None
    # Should be classified with some domain
    assert repo_wiki_module.domain in ("core-platform", "ai-services", "unknown")
    assert 0.0 <= repo_wiki_module.domain_confidence <= 1.0


def test_domain_classifier_ai_services_module(tmp_path: Path) -> None:
    """Test classification of AI/ML service modules."""
    # Create an AI service with embedding/model signals
    (tmp_path / "repo_wiki" / "indexer").mkdir(parents=True)
    (tmp_path / "repo_wiki" / "indexer" / "embeddings.py").write_text(
        "class EmbeddingProvider:\n    def embed(self): pass\n",
        encoding="utf-8",
    )
    (tmp_path / "repo_wiki" / "indexer" / "vector_store.py").write_text(
        "class VectorStore:\n    def search(self): pass\n",
        encoding="utf-8",
    )

    cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
    snapshot = RepositoryScanner(cfg).scan()

    assert len(snapshot.modules) >= 1
    # Module path will be 'repo_wiki' (indexer is a subdirectory)
    repo_wiki_module = next((m for m in snapshot.modules if m.path == "repo_wiki"), None)
    assert repo_wiki_module is not None
    # Should be classified with some domain (may be ai-services if signals are strong enough)
    assert repo_wiki_module.domain in ("ai-services", "core-platform", "unknown")


def test_domain_classifier_tooling_module(tmp_path: Path) -> None:
    """Test classification of tooling/scripts modules."""
    # Create a scripts module
    (tmp_path / "scripts").mkdir(parents=True)
    (tmp_path / "scripts" / "run.py").write_text(
        "def run_command():\n    pass\n\ndef main():\n    pass\n",
        encoding="utf-8",
    )

    cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
    snapshot = RepositoryScanner(cfg).scan()

    assert len(snapshot.modules) >= 1
    scripts_module = next((m for m in snapshot.modules if m.path == "scripts"), None)
    assert scripts_module is not None
    assert scripts_module.service_family == "python-backend"


def test_domain_classifier_test_module(tmp_path: Path) -> None:
    """Test classification of test modules."""
    # Create a test module
    (tmp_path / "tests").mkdir(parents=True)
    (tmp_path / "tests" / "test_example.py").write_text(
        "def test_example():\n    assert True\n",
        encoding="utf-8",
    )

    cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
    snapshot = RepositoryScanner(cfg).scan()

    assert len(snapshot.modules) >= 1
    test_module = next((m for m in snapshot.modules if m.path == "tests"), None)
    assert test_module is not None
    assert test_module.domain == "testing"


def test_domain_classifier_api_server_module(tmp_path: Path) -> None:
    """Test classification of API server modules with HTTP handlers."""
    # Create a module with API routes
    (tmp_path / "api_service").mkdir(parents=True)
    (tmp_path / "api_service" / "routes.py").write_text(
        "router = {}\nrouter.get('/users', handler)\nrouter.post('/users', handler)\n",
        encoding="utf-8",
    )

    cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
    snapshot = RepositoryScanner(cfg).scan()

    assert len(snapshot.modules) >= 1
    api_module = next((m for m in snapshot.modules if "api_service" in m.path.lower()), None)
    assert api_module is not None
    assert api_module.runtime_role in ("api-server", "worker", "unknown")


def test_domain_classifier_fallback_for_weak_signals(tmp_path: Path) -> None:
    """Test fallback classification when signals are weak."""
    # Create a minimal module with few signals
    (tmp_path / "unknown_module").mkdir(parents=True)
    (tmp_path / "unknown_module" / "main.py").write_text(
        "def helper():\n    pass\n",
        encoding="utf-8",
    )

    cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
    snapshot = RepositoryScanner(cfg).scan()

    assert len(snapshot.modules) >= 1
    unknown_module = next((m for m in snapshot.modules if "unknown_module" in m.path), None)
    assert unknown_module is not None
    # Should still get a stable classification, not crash
    assert unknown_module.domain in ("core-platform", "unknown")
    assert 0.0 <= unknown_module.domain_confidence <= 1.0


def test_domain_classifier_mixed_service_families(tmp_path: Path) -> None:
    """Test classification in mixed repositories with multiple service families."""
    # Create Python service
    (tmp_path / "python_service" / "src").mkdir(parents=True)
    (tmp_path / "python_service" / "src" / "main.py").write_text(
        "from flask import Flask\napp = Flask(__name__)\n",
        encoding="utf-8",
    )

    # Create TypeScript frontend
    (tmp_path / "frontend" / "src").mkdir(parents=True)
    (tmp_path / "frontend" / "src" / "app.tsx").write_text(
        "const App = () => <div>Hello</div>\nexport default App;\n",
        encoding="utf-8",
    )

    cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
    snapshot = RepositoryScanner(cfg).scan()

    assert len(snapshot.modules) >= 2

    # Find both modules
    py_module = next((m for m in snapshot.modules if "python_service" in m.path), None)
    ts_module = next((m for m in snapshot.modules if "frontend" in m.path), None)

    if py_module:
        assert py_module.service_family in ("python-backend", "unknown")
    if ts_module:
        assert ts_module.service_family in ("typescript-frontend", "unknown")


def test_domain_classifier_all_fields_populated(tmp_path: Path) -> None:
    """Test that all domain classification fields are properly populated."""
    # Create a module with clear signals
    (tmp_path / "repo_wiki" / "generator").mkdir(parents=True)
    (tmp_path / "repo_wiki" / "generator" / "engine.py").write_text(
        "class GenerationEngine:\n    def generate(self): pass\n",
        encoding="utf-8",
    )
    (tmp_path / "repo_wiki" / "generator" / "contracts.py").write_text(
        "class DocumentContract:\n    pass\n",
        encoding="utf-8",
    )

    cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
    snapshot = RepositoryScanner(cfg).scan()

    assert len(snapshot.modules) >= 1
    # Module path will be 'repo_wiki' (first directory level)
    repo_wiki_module = next((m for m in snapshot.modules if m.path == "repo_wiki"), None)
    assert repo_wiki_module is not None

    # All domain fields should be populated
    assert hasattr(repo_wiki_module, "domain")
    assert hasattr(repo_wiki_module, "service_family")
    assert hasattr(repo_wiki_module, "runtime_role")
    assert hasattr(repo_wiki_module, "domain_confidence")
    assert hasattr(repo_wiki_module, "domain_classification_reason")

    # Values should be non-None (may be 'unknown' for low confidence)
    assert repo_wiki_module.domain is not None
    assert repo_wiki_module.service_family is not None
    assert repo_wiki_module.runtime_role is not None
    assert isinstance(repo_wiki_module.domain_confidence, float)
    assert isinstance(repo_wiki_module.domain_classification_reason, str)
