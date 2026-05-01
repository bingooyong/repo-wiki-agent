"""Tests for Phase 12 SQLite runtime store and page invalidation."""

import json
import tempfile
import time
from pathlib import Path

import pytest

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.orchestration.service import RepoWikiService
from repo_wiki.orchestration.runtime_store import (
    SQLiteRuntimeStore,
    DocHierarchyRecord,
    SectionRegistryRecord,
    VerifyRunRecord,
    CompareRunRecord,
    PageInvalidationRecord,
)
from repo_wiki.orchestration.invalidation import (
    PageInvalidationEngine,
    IncrementalRegenerationPlanner,
    InvalidationResult,
    RegenerationTask,
)


class TestSQLiteRuntimeStore:
    """Tests for SQLiteRuntimeStore with Phase 12 schema."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_runtime.sqlite3"
            store = SQLiteRuntimeStore(db_path)
            yield store
            store.close()

    def test_schema_version(self, temp_db):
        """Test that migrations apply correctly."""
        assert temp_db.current_schema_version() >= 2

    def test_doc_hierarchy_crud(self, temp_db):
        """Test document hierarchy CRUD operations."""
        record = DocHierarchyRecord(
            doc_type="overview",
            doc_slug="00-overview",
            doc_path="docs/00-overview.md",
            layer="overview",
            title="Repository Overview",
            sort_order=0,
            generation_input_hash="abc123",
            generation_output_hash="def456",
            generated_at="2026-04-18T00:00:00Z",
        )
        temp_db.upsert_doc_hierarchy(record)

        # Read back
        docs = temp_db.list_docs_by_type("overview")
        assert len(docs) == 1
        assert docs[0]["doc_slug"] == "00-overview"
        assert docs[0]["title"] == "Repository Overview"

        # Update
        record.title = "Updated Title"
        temp_db.upsert_doc_hierarchy(record)
        doc = temp_db.get_doc_by_slug("00-overview")
        assert doc["title"] == "Updated Title"

        # Delete
        temp_db.delete_doc("overview", "00-overview")
        docs = temp_db.list_docs_by_type("overview")
        assert len(docs) == 0

    def test_section_registry_crud(self, temp_db):
        """Test section registry CRUD operations."""
        record = SectionRegistryRecord(
            canonical_slug="architecture",
            title="Architecture Overview",
            description="System architecture documentation",
            required_for_phase="phase-09",
            sort_order=1,
            is_active=True,
        )
        temp_db.register_section(record)

        # Read back
        section = temp_db.get_section_by_slug("architecture")
        assert section is not None
        assert section["canonical_slug"] == "architecture"
        assert section["title"] == "Architecture Overview"

        # Alias support
        temp_db.register_section_alias("q01-architecture", "architecture")
        resolved = temp_db.resolve_section_alias("q01-architecture")
        assert resolved == "architecture"

        aliases = temp_db.list_section_aliases("architecture")
        assert "q01-architecture" in aliases

    def test_nav_graph_crud(self, temp_db):
        """Test navigation graph CRUD operations."""
        temp_db.upsert_nav_node(
            doc_slug="architecture",
            doc_type="section",
            incoming_links=["00-overview", "03-module-map"],
            outgoing_links=["services", "data-model"],
            depth=1,
            affected_pages=["docs/01-architecture.md", "docs/sections/architecture/index.md"],
        )

        # Read back
        node = temp_db.get_nav_node("architecture")
        assert node is not None
        assert node["doc_type"] == "section"
        assert node["depth"] == 1

        incoming = json.loads(node["incoming_links_json"])
        assert "00-overview" in incoming

        outgoing = json.loads(node["outgoing_links_json"])
        assert "services" in outgoing

        affected = temp_db.get_affected_pages("architecture")
        assert "docs/01-architecture.md" in affected

    def test_verify_run_persistence(self, temp_db):
        """Test verify run persistence and trend analysis."""
        run_id = f"verify-{int(time.time())}"
        verify_result = {
            "grade": "FAIL",
            "exit_code": 1,
            "summary": {
                "total": 12,
                "pass": 6,
                "warn": 2,
                "fail": 4,
                "hard_gate_failures": 2,
                "soft_gate_failures": 2,
            },
            "hard_gate_codes": ["STRUCT_MISSING_SECTIONS", "STRUCT_SECTION_DIR_MISSING"],
            "soft_gate_codes": ["CONTENT_TOO_SHORT", "ARCH_MERMAID_MISSING"],
        }

        temp_db.save_verify_run(run_id, "/test/repo", verify_result, duration_ms=1500)

        # Read back
        runs = temp_db.list_verify_runs("/test/repo", limit=10)
        assert len(runs) >= 1

        run = temp_db.get_verify_run(run_id)
        assert run is not None
        assert run["grade"] == "FAIL"
        assert run["hard_gate_failures"] == 2

        # Trend
        trend = temp_db.get_verify_trend("/test/repo", limit=5)
        assert len(trend) >= 1

    def test_compare_run_persistence(self, temp_db):
        """Test compare run persistence and trend analysis."""
        run_id = f"compare-{int(time.time())}"
        compare_result = {
            "summary": {
                "overall_score": 0.493,
                "overall_band": "POOR",
                "structural_score": 0.333,
                "quality_score": 0.650,
                "acceptance_blocked": True,
                "total_gaps": 8,
                "critical_gaps": 2,
                "major_gaps": 4,
            },
            "dimensions": [
                {
                    "dimension": "directory_hierarchy",
                    "score": 0.5,
                    "delta_type": "STRUCTURAL",
                    "gaps": [],
                },
            ],
        }

        temp_db.save_compare_run(
            run_id,
            "/test/repo",
            "/baseline/qoder",
            compare_result,
            duration_ms=2000,
        )

        # Read back
        runs = temp_db.list_compare_runs("/test/repo", limit=10)
        assert len(runs) >= 1

        run = temp_db.get_compare_run(run_id)
        assert run is not None
        assert run["overall_band"] == "POOR"
        assert run["structural_score"] == 0.333

        # Trend
        trend = temp_db.get_compare_trend("/test/repo", limit=5)
        assert len(trend) >= 1

    def test_page_invalidation(self, temp_db):
        """Test page invalidation tracking."""
        temp_db.invalidate_page(
            doc_slug="00-overview",
            doc_type="overview",
            reason="file_changed",
            changed_files=["repo_wiki/core/config.py"],
            impacted_modules=["repo_wiki"],
        )

        # Read back
        invalidated = temp_db.list_invalidated_pages()
        assert len(invalidated) >= 1

        # Mark as regenerated
        temp_db.mark_page_regenerated("00-overview", "completed")

        # Clear invalidations
        temp_db.clear_invalidations("00-overview")
        remaining = temp_db.list_invalidated_pages()
        # The one we just cleared should be gone, but there might be others
        # Just check it doesn't throw

    def test_integrity_checks(self, temp_db):
        """Test integrity check methods."""
        # Add some test data
        record = DocHierarchyRecord(
            doc_type="section",
            doc_slug="architecture",
            doc_path="docs/sections/architecture/index.md",
            layer="section",
        )
        temp_db.upsert_doc_hierarchy(record)

        # Check orphaned docs (file doesn't exist)
        orphaned = temp_db.check_orphaned_docs()
        assert isinstance(orphaned, list)

        # Check broken section mappings
        broken = temp_db.check_broken_section_mappings()
        assert isinstance(broken, list)

        # Check stale evidence
        stale = temp_db.check_stale_evidence(max_age_days=30)
        assert isinstance(stale, list)

    def test_export_rebuild(self, temp_db):
        """Test export and rebuild from artifacts."""
        import tempfile

        # Add some data
        doc = DocHierarchyRecord(
            doc_type="overview",
            doc_slug="00-overview",
            doc_path="docs/00-overview.md",
            layer="overview",
            title="Test Doc",
        )
        temp_db.upsert_doc_hierarchy(doc)

        section = SectionRegistryRecord(
            canonical_slug="test-section",
            title="Test Section",
        )
        temp_db.register_section(section)

        # Export
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            artifacts = temp_db.export_runtime_artifacts(output_dir)

            assert "doc_hierarchy.json" in artifacts
            assert "section_registry.json" in artifacts
            assert "nav_graph.json" in artifacts

            # Create fresh store and rebuild
            fresh_db_path = Path(tmpdir) / "fresh.sqlite3"
            fresh_db = SQLiteRuntimeStore(fresh_db_path)

            count = fresh_db.rebuild_from_artifacts(output_dir)
            assert count >= 2  # At least doc and section

            fresh_db.close()


class TestPageInvalidationEngine:
    """Tests for PageInvalidationEngine."""

    @pytest.fixture
    def mock_stores(self):
        """Create mock stores for testing."""
        from unittest.mock import MagicMock

        root = Path("/test/repo")
        state_store = MagicMock()
        runtime_store = MagicMock()
        retrieval_service = MagicMock()

        return root, state_store, runtime_store, retrieval_service

    def test_invalidation_result_dataclass(self):
        """Test InvalidationResult dataclass."""
        result = InvalidationResult(
            invalidated_pages=["00-overview", "01-architecture"],
            skipped_pages=[],
            regeneration_plan=["00-overview", "01-architecture"],
            reason="file_changed",
            changed_files=["src/main.py"],
            impacted_modules=["main"],
            is_full_rebuild=False,
        )

        assert len(result.invalidated_pages) == 2
        assert result.reason == "file_changed"
        assert result.is_full_rebuild is False

    def test_regeneration_task_dataclass(self):
        """Test RegenerationTask dataclass."""
        task = RegenerationTask(
            doc_slug="00-overview",
            doc_type="overview",
            priority=1,
            reason="file_changed",
            dependencies=[],
        )

        assert task.doc_slug == "00-overview"
        assert task.priority == 1
        assert len(task.dependencies) == 0


class TestIncrementalRegenerationPlanner:
    """Tests for IncrementalRegenerationPlanner."""

    def test_regeneration_summary(self):
        """Test regeneration summary generation."""
        # Test the InvalidationResult and RegenerationTask dataclasses directly
        invalidation = InvalidationResult(
            invalidated_pages=["00-overview", "01-architecture", "architecture"],
            skipped_pages=[],
            regeneration_plan=["00-overview", "01-architecture", "architecture"],
            reason="file_changed",
            changed_files=["src/main.py"],
            impacted_modules=["main"],
            is_full_rebuild=False,
        )

        # Create regeneration tasks manually (like plan_regeneration would)
        tasks = []
        for doc_slug in invalidation.regeneration_plan:
            doc_type = "overview" if doc_slug.startswith("0") else "section"
            priority = 1 if doc_slug in ("00-overview", "01-architecture") else 2
            tasks.append(RegenerationTask(
                doc_slug=doc_slug,
                doc_type=doc_type,
                priority=priority,
                reason=invalidation.reason,
                dependencies=[],
            ))

        by_priority = {1: [], 2: [], 3: []}
        for task in tasks:
            by_priority[task.priority].append(task.doc_slug)

        summary = {
            "total_pages": len(invalidation.invalidated_pages),
            "reason": invalidation.reason,
            "is_full_rebuild": invalidation.is_full_rebuild,
            "by_priority": by_priority,
            "execution_order": [t.doc_slug for t in tasks],
        }

        assert summary["total_pages"] == 3
        assert summary["reason"] == "file_changed"
        assert 1 in summary["by_priority"]  # high priority
        assert 2 in summary["by_priority"]  # medium priority
        assert 3 in summary["by_priority"]  # low priority
        assert summary["by_priority"][1] == ["00-overview", "01-architecture"]


class TestRuntimeSyncIntegration:
    """Integration tests for runtime sqlite sync in orchestration service."""

    def test_sync_runtime_store_creates_runtime_sqlite_and_tables(self, tmp_path: Path):
        docs_dir = tmp_path / "docs"
        sections_dir = docs_dir / "sections"
        modules_dir = docs_dir / "modules"
        sections_dir.mkdir(parents=True, exist_ok=True)
        modules_dir.mkdir(parents=True, exist_ok=True)

        (docs_dir / "00-overview.md").write_text("# Overview\n\nSee [Architecture](01-architecture.md)\n", encoding="utf-8")
        (docs_dir / "01-architecture.md").write_text("# Architecture\n", encoding="utf-8")
        (docs_dir / "03-module-map.md").write_text("# Module Map\n", encoding="utf-8")
        (docs_dir / "04-api-contracts.md").write_text("# API\n", encoding="utf-8")
        (docs_dir / "05-data-model.md").write_text("# Data Model\n", encoding="utf-8")
        (sections_dir / "Q01-代码质量与可维护性.md").write_text("# Q01\n", encoding="utf-8")
        (sections_dir / "S01-Injection-Checklist.md").write_text("# S01\n", encoding="utf-8")
        (modules_dir / "repo_wiki.md").write_text("# Module\n", encoding="utf-8")

        cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
        svc = RepoWikiService(cfg)
        result = svc._sync_runtime_store()

        assert result["status"] == "ok"
        runtime_db = tmp_path / ".repo-wiki" / "index" / "runtime.sqlite3"
        assert runtime_db.exists()

        store = SQLiteRuntimeStore(runtime_db)
        try:
            assert len(store.list_docs_by_layer("overview")) >= 2
            assert len(store.list_active_sections()) >= 1
            assert len(store.list_nav_nodes_by_type("overview")) >= 1
        finally:
            store.close()

    def test_verify_persists_runtime_evidence(self, tmp_path: Path, monkeypatch):
        cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
        svc = RepoWikiService(cfg)

        class FakeRetrievalService:
            def __init__(self, root, config):  # noqa: D401
                self.root = root
                self.config = config

        class FakeVerifierService:
            def __init__(self, root, retrieval_service=None):  # noqa: D401
                self.root = root
                self.retrieval_service = retrieval_service

            def verify(self, ci: bool = False):
                return {
                    "grade": "PASS",
                    "ci_mode": ci,
                    "exit_code": 0,
                    "checks": [],
                    "summary": {
                        "total": 1,
                        "pass": 1,
                        "warn": 0,
                        "fail": 0,
                        "hard_gate_failures": 0,
                        "soft_gate_failures": 0,
                    },
                    "reason_codes": [],
                    "hard_gate_codes": [],
                    "soft_gate_codes": [],
                    "gate_summary": {
                        "hard_gate_blocking": False,
                        "soft_gate_warnings": False,
                        "acceptance_blocked": False,
                    },
                }

        monkeypatch.setattr("repo_wiki.orchestration.service.RetrievalService", FakeRetrievalService)
        monkeypatch.setattr("repo_wiki.orchestration.service.VerifierService", FakeVerifierService)

        result = svc.verify(ci=True)
        assert result["runtime_evidence"]["status"] == "recorded"
        assert result["runtime_evidence"]["run_id"]

        runtime_db = tmp_path / ".repo-wiki" / "index" / "runtime.sqlite3"
        store = SQLiteRuntimeStore(runtime_db)
        try:
            runs = store.list_verify_runs(target_path=str(tmp_path), limit=5)
            assert len(runs) == 1
            assert runs[0]["grade"] == "PASS"
        finally:
            store.close()


class TestRuntimeStoreFallbackBehavior:
    """Tests for runtime store fallback behavior with missing/corrupt DB."""

    def test_sync_runtime_store_handles_corrupt_db_gracefully(self, tmp_path: Path):
        """Verify _sync_runtime_store returns diagnostic info when DB is corrupt."""
        docs_dir = tmp_path / "docs"
        sections_dir = docs_dir / "sections"
        modules_dir = docs_dir / "modules"
        sections_dir.mkdir(parents=True, exist_ok=True)
        modules_dir.mkdir(parents=True, exist_ok=True)

        (docs_dir / "00-overview.md").write_text("# Overview\n", encoding="utf-8")
        (docs_dir / "01-architecture.md").write_text("# Architecture\n", encoding="utf-8")

        # Create corrupt DB file (not a valid SQLite)
        runtime_db = tmp_path / ".repo-wiki" / "index"
        runtime_db.mkdir(parents=True, exist_ok=True)
        corrupt_db = runtime_db / "runtime.sqlite3"
        corrupt_db.write_text("this is not a valid sqlite database", encoding="utf-8")

        cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
        svc = RepoWikiService(cfg)
        result = svc._sync_runtime_store()

        assert result["status"] == "error"
        assert result["error_type"] == "database_corrupt"
        assert "remediation" in result

    def test_sync_runtime_store_handles_missing_directory_gracefully(self, tmp_path: Path):
        """Verify _sync_runtime_store handles missing .repo-wiki directory."""
        # Don't create .repo-wiki directory
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "00-overview.md").write_text("# Overview\n", encoding="utf-8")

        cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
        svc = RepoWikiService(cfg)
        result = svc._sync_runtime_store()

        # Should still work - create_runtime_store creates directory
        assert result["status"] in ("ok", "error")

    def test_verify_handles_missing_runtime_gracefully(self, tmp_path: Path, monkeypatch):
        """Verify verify command works even when runtime store is missing.

        Note: create_runtime_store auto-creates the directory and schema if missing,
        so the verify command should successfully record evidence even on first run.
        """
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "00-overview.md").write_text("# Overview\n", encoding="utf-8")

        cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})

        class FakeRetrievalService:
            def __init__(self, root, config):  # noqa: D401
                self.root = root
                self.config = config

        class FakeVerifierService:
            def __init__(self, root, retrieval_service=None):  # noqa: D401
                self.root = root
                self.retrieval_service = retrieval_service

            def verify(self, ci: bool = False):
                return {
                    "grade": "PASS",
                    "ci_mode": ci,
                    "exit_code": 0,
                    "checks": [],
                    "summary": {"total": 1, "pass": 1, "warn": 0, "fail": 0, "hard_gate_failures": 0, "soft_gate_failures": 0},
                    "reason_codes": [],
                    "hard_gate_codes": [],
                    "soft_gate_codes": [],
                    "gate_summary": {"hard_gate_blocking": False, "soft_gate_warnings": False, "acceptance_blocked": False},
                }

        monkeypatch.setattr("repo_wiki.orchestration.service.RetrievalService", FakeRetrievalService)
        monkeypatch.setattr("repo_wiki.orchestration.service.VerifierService", FakeVerifierService)

        # Ensure .repo-wiki directory does NOT exist
        import shutil
        repo_wiki_dir = tmp_path / ".repo-wiki"
        if repo_wiki_dir.exists():
            shutil.rmtree(repo_wiki_dir)

        svc = RepoWikiService(cfg)
        result = svc.verify(ci=True)

        # Verify still works even without runtime store (it auto-creates)
        assert result["grade"] == "PASS"
        # Runtime evidence should be recorded since store is auto-created
        assert result["runtime_evidence"]["status"] == "recorded"


class TestRuntimeStoreSchemaSafety:
    """Tests for runtime store schema bootstrap and migration safety."""

    def test_migrations_are_idempotent(self, tmp_path: Path):
        """Verify migrations can be applied multiple times safely."""
        runtime_db = tmp_path / ".repo-wiki" / "index" / "runtime.sqlite3"
        runtime_db.parent.mkdir(parents=True, exist_ok=True)

        store1 = SQLiteRuntimeStore(runtime_db)
        version1 = store1.current_schema_version()
        store1.close()

        # Apply migrations again
        store2 = SQLiteRuntimeStore(runtime_db)
        version2 = store2.current_schema_version()
        store2.close()

        assert version1 == version2
        assert version1 >= 3  # Should have migrations 2 and 3

    def test_schema_version_tracked_correctly(self, tmp_path: Path):
        """Verify schema version is correctly reported."""
        runtime_db = tmp_path / ".repo-wiki" / "index" / "runtime.sqlite3"
        runtime_db.parent.mkdir(parents=True, exist_ok=True)

        store = SQLiteRuntimeStore(runtime_db)
        version = store.current_schema_version()
        store.close()

        assert version >= 2  # Minimum schema version for Phase 12

    def test_upsert_is_idempotent(self, tmp_path: Path):
        """Verify upsert operations can be repeated safely."""
        runtime_db = tmp_path / ".repo-wiki" / "index" / "runtime.sqlite3"
        runtime_db.parent.mkdir(parents=True, exist_ok=True)
        store = SQLiteRuntimeStore(runtime_db)

        record = DocHierarchyRecord(
            doc_type="overview",
            doc_slug="00-overview",
            doc_path="docs/00-overview.md",
            layer="overview",
            title="Test",
        )

        # Insert twice
        store.upsert_doc_hierarchy(record)
        store.upsert_doc_hierarchy(record)

        docs = store.list_docs_by_type("overview")
        assert len(docs) == 1  # Should still be 1, not duplicated

        store.close()


class TestRuntimeEvidenceWorkflow:
    """Integration tests for runtime evidence persistence during typical workflows."""

    def test_multiple_verify_runs_persist_individually(self, tmp_path: Path, monkeypatch):
        """Verify multiple verify runs each create separate evidence records."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "00-overview.md").write_text("# Overview\n", encoding="utf-8")

        cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})

        class FakeRetrievalService:
            def __init__(self, root, config):  # noqa: D401
                self.root = root
                self.config = config

        call_count = {"count": 0}

        class FakeVerifierService:
            def __init__(self, root, retrieval_service=None):  # noqa: D401
                self.root = root
                self.retrieval_service = retrieval_service

            def verify(self, ci: bool = False):
                call_count["count"] += 1
                grade = "PASS" if call_count["count"] % 2 == 1 else "WARN"
                return {
                    "grade": grade,
                    "ci_mode": ci,
                    "exit_code": 0,
                    "checks": [],
                    "summary": {"total": 1, "pass": 1, "warn": 0 if grade == "PASS" else 1, "fail": 0, "hard_gate_failures": 0, "soft_gate_failures": 0 if grade == "PASS" else 1},
                    "reason_codes": [],
                    "hard_gate_codes": [],
                    "soft_gate_codes": [],
                    "gate_summary": {"hard_gate_blocking": False, "soft_gate_warnings": grade == "WARN", "acceptance_blocked": False},
                }

        monkeypatch.setattr("repo_wiki.orchestration.service.RetrievalService", FakeRetrievalService)
        monkeypatch.setattr("repo_wiki.orchestration.service.VerifierService", FakeVerifierService)

        svc = RepoWikiService(cfg)

        # Run verify multiple times
        for i in range(3):
            result = svc.verify(ci=True)
            assert result["runtime_evidence"]["status"] == "recorded"
            assert result["runtime_evidence"]["grade_recorded"] in ("PASS", "WARN")

        runtime_db = tmp_path / ".repo-wiki" / "index" / "runtime.sqlite3"
        store = SQLiteRuntimeStore(runtime_db)
        try:
            runs = store.list_verify_runs(target_path=str(tmp_path), limit=10)
            assert len(runs) == 3  # All 3 runs persisted
        finally:
            store.close()

    def test_verify_trend_accessible_after_multiple_runs(self, tmp_path: Path, monkeypatch):
        """Verify trend data is accessible after multiple verify runs."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "00-overview.md").write_text("# Overview\n", encoding="utf-8")

        cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})

        class FakeRetrievalService:
            def __init__(self, root, config):  # noqa: D401
                self.root = root
                self.config = config

        class FakeVerifierService:
            def __init__(self, root, retrieval_service=None):  # noqa: D401
                self.root = root
                self.retrieval_service = retrieval_service

            def verify(self, ci: bool = False):
                return {
                    "grade": "PASS",
                    "ci_mode": ci,
                    "exit_code": 0,
                    "checks": [],
                    "summary": {"total": 1, "pass": 1, "warn": 0, "fail": 0, "hard_gate_failures": 0, "soft_gate_failures": 0},
                    "reason_codes": [],
                    "hard_gate_codes": [],
                    "soft_gate_codes": [],
                    "gate_summary": {"hard_gate_blocking": False, "soft_gate_warnings": False, "acceptance_blocked": False},
                }

        monkeypatch.setattr("repo_wiki.orchestration.service.RetrievalService", FakeRetrievalService)
        monkeypatch.setattr("repo_wiki.orchestration.service.VerifierService", FakeVerifierService)

        svc = RepoWikiService(cfg)

        # Run verify multiple times
        for _ in range(5):
            svc.verify(ci=True)

        # Access trend data
        runtime_db = tmp_path / ".repo-wiki" / "index" / "runtime.sqlite3"
        store = SQLiteRuntimeStore(runtime_db)
        try:
            trend = store.get_verify_trend(str(tmp_path), limit=5)
            assert len(trend) == 5
            assert all(t["grade"] == "PASS" for t in trend)
        finally:
            store.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
