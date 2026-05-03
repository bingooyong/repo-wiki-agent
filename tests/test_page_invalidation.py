"""Tests for page invalidation with git diff and hash fallback."""

import tempfile
from pathlib import Path

import pytest

from repo_wiki.orchestration.generation_invalidation import (
    GenerationAwareInvalidator,
    GitDiffResult,
    HashBasedChangeDetector,
    HashChangeResult,
    get_file_hash,
    get_directory_hashes,
    get_git_diff,
    create_generation_invalidator,
)
from repo_wiki.orchestration.generation_state import (
    GenerationStateMachine,
    PageState,
)


class TestGitDiffResult:
    """Tests for GitDiffResult dataclass."""

    def test_create_git_diff_result(self):
        """Test creating a GitDiffResult."""
        result = GitDiffResult(
            changed_files=["a.py", "b.py"],
            deleted_files=["c.py"],
            renamed_files={"old.py": "new.py"},
            commit_range=("HEAD~1", "HEAD"),
        )
        assert len(result.changed_files) == 2
        assert len(result.deleted_files) == 1
        assert len(result.renamed_files) == 1


class TestHashChangeResult:
    """Tests for HashChangeResult dataclass."""

    def test_create_hash_change_result(self):
        """Test creating a HashChangeResult."""
        result = HashChangeResult(
            changed_files=["a.py"],
            deleted_files=["b.py"],
            new_files=["c.py"],
            is_clean=False,
        )
        assert len(result.changed_files) == 1
        assert result.is_clean is False


class TestGetFileHash:
    """Tests for get_file_hash function."""

    def test_get_hash_nonexistent(self, tmp_path):
        """Test hash of nonexistent file."""
        hash_val = get_file_hash(tmp_path / "nonexistent.txt")
        assert hash_val is None

    def test_get_hash_file(self, tmp_path):
        """Test hash of existing file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        hash_val = get_file_hash(test_file)
        assert hash_val is not None
        assert len(hash_val) == 64  # SHA256 hex length

    def test_same_content_same_hash(self, tmp_path):
        """Test same content produces same hash."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"

        file1.write_text("hello world")
        file2.write_text("hello world")

        assert get_file_hash(file1) == get_file_hash(file2)

    def test_different_content_different_hash(self, tmp_path):
        """Test different content produces different hash."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"

        file1.write_text("hello")
        file2.write_text("world")

        assert get_file_hash(file1) != get_file_hash(file2)


class TestGetDirectoryHashes:
    """Tests for get_directory_hashes function."""

    def test_empty_directory(self, tmp_path):
        """Test hashing empty directory."""
        hashes = get_directory_hashes(tmp_path, tmp_path)
        assert len(hashes) == 0

    def test_directory_with_files(self, tmp_path):
        """Test hashing directory with files."""
        (tmp_path / "a.txt").write_text("content a")
        (tmp_path / "b.txt").write_text("content b")

        hashes = get_directory_hashes(tmp_path, tmp_path)
        assert len(hashes) == 2
        assert "a.txt" in hashes
        assert "b.txt" in hashes

    def test_pattern_filter(self, tmp_path):
        """Test pattern filtering."""
        (tmp_path / "a.py").write_text("python")
        (tmp_path / "b.txt").write_text("text")

        hashes = get_directory_hashes(tmp_path, tmp_path, patterns=["*.py"])
        assert len(hashes) == 1
        assert "a.py" in hashes


class TestHashBasedChangeDetector:
    """Tests for HashBasedChangeDetector."""

    def test_detect_no_baseline(self, tmp_path):
        """Test detection with no baseline."""
        (tmp_path / "new.py").write_text("content")
        detector = HashBasedChangeDetector(tmp_path)
        result = detector.detect_changes()

        assert len(result.new_files) == 1
        assert result.is_clean is False

    def test_detect_no_changes(self, tmp_path):
        """Test detection with no changes."""
        content = "same content"
        file1 = tmp_path / "file.py"
        file1.write_text(content)

        # Compute baseline
        baseline = get_directory_hashes(tmp_path, tmp_path)

        # No changes
        detector = HashBasedChangeDetector(tmp_path, baseline)
        result = detector.detect_changes()

        assert len(result.changed_files) == 0
        assert len(result.deleted_files) == 0
        assert result.is_clean is True

    def test_detect_file_changed(self, tmp_path):
        """Test detecting file changes."""
        file1 = tmp_path / "file.py"
        file1.write_text("original")

        # Compute baseline
        baseline = get_directory_hashes(tmp_path, tmp_path)

        # Modify file
        file1.write_text("modified")

        detector = HashBasedChangeDetector(tmp_path, baseline)
        result = detector.detect_changes()

        assert len(result.changed_files) == 1
        assert "file.py" in result.changed_files

    def test_detect_file_deleted(self, tmp_path):
        """Test detecting file deletion."""
        file1 = tmp_path / "file.py"
        file1.write_text("content")

        # Compute baseline
        baseline = get_directory_hashes(tmp_path, tmp_path)

        # Delete file
        file1.unlink()

        detector = HashBasedChangeDetector(tmp_path, baseline)
        result = detector.detect_changes()

        assert len(result.deleted_files) == 1
        assert "file.py" in result.deleted_files


class TestGenerationAwareInvalidator:
    """Tests for GenerationAwareInvalidator."""

    @pytest.fixture
    def invalidator_setup(self, tmp_path):
        """Set up invalidator with dependencies."""
        db_path = tmp_path / "state.sqlite3"
        state_machine = GenerationStateMachine(db_path)
        invalidator = GenerationAwareInvalidator(state_machine, tmp_path)

        return invalidator, state_machine

    def test_create_invalidator(self, invalidator_setup):
        """Test creating invalidator."""
        invalidator, _ = invalidator_setup
        assert isinstance(invalidator, GenerationAwareInvalidator)

    def test_map_file_to_pages_docs(self, invalidator_setup):
        """Test mapping docs file to pages."""
        invalidator, _ = invalidator_setup

        pages = invalidator._map_file_to_pages("docs/00-overview.md")
        assert "00-overview" in pages

        pages = invalidator._map_file_to_pages("docs/01-architecture.md")
        assert "01-architecture" in pages

    def test_map_file_to_pages_modules(self, invalidator_setup):
        """Test mapping module file to pages."""
        invalidator, _ = invalidator_setup

        pages = invalidator._map_file_to_pages("modules/my-service/index.md")
        assert "my-service" in pages

    def test_get_page_impact_summary(self, invalidator_setup):
        """Test getting page impact summary."""
        invalidator, state_machine = invalidator_setup

        # Create a run with pages
        run = state_machine.create_run(profile="test", total_pages=3)
        state_machine.add_page(run.run_id, "00-overview", "overview", "docs/00-overview.md")
        state_machine.add_page(run.run_id, "01-architecture", "overview", "docs/01-architecture.md")
        state_machine.add_page(run.run_id, "02-services", "module", "docs/02-services.md")

        # Start and complete one page
        state_machine.start_page(run.run_id, "00-overview")
        state_machine.complete_page(run.run_id, "00-overview")

        summary = invalidator.get_page_impact_summary(run.run_id)

        assert summary["total_pages"] == 3
        assert summary["completed_count"] == 1
        assert summary["pending_count"] == 2
        assert summary["by_state"]["completed"] == 1
        assert summary["by_state"]["pending"] == 2

    def test_invalidate_nonexistent_run(self, invalidator_setup):
        """Test invalidating nonexistent run."""
        invalidator, _ = invalidator_setup

        invalidated, skipped = invalidator.invalidate_from_git_diff("nonexistent-run")
        assert len(invalidated) == 0
        assert len(skipped) == 0

    def test_one_service_change_only_invalidates_related_page(self, invalidator_setup):
        """Changing one service should only invalidate related pages."""
        invalidator, state_machine = invalidator_setup
        run = state_machine.create_run(profile="test", total_pages=3)
        state_machine.add_page(run.run_id, "service-a", "module", "docs/modules/service-a.md")
        state_machine.add_page(run.run_id, "service-b", "module", "docs/modules/service-b.md")
        state_machine.add_page(run.run_id, "00-overview", "overview", "docs/00-overview.md")
        state_machine.complete_page(run.run_id, "service-a")
        state_machine.complete_page(run.run_id, "service-b")
        state_machine.complete_page(run.run_id, "00-overview")

        invalidated, skipped = invalidator.invalidate_from_hash_comparison(
            run_id=run.run_id,
            baseline_hashes={"services/service-a/app.py": "aaa", "services/service-b/app.py": "bbb"},
            current_hashes={"services/service-a/app.py": "changed", "services/service-b/app.py": "bbb"},
        )

        assert "service-a" in invalidated
        assert "service-b" not in invalidated
        assert "00-overview" not in invalidated
        page_a = state_machine.get_page_state(run.run_id, "service-a")
        page_b = state_machine.get_page_state(run.run_id, "service-b")
        assert page_a is not None and page_a.state == PageState.PENDING
        assert page_b is not None and page_b.state == PageState.COMPLETED

    def test_git_clean_falls_back_to_hash(self, invalidator_setup, monkeypatch):
        """When git reports clean, invalidator should use hash fallback if provided."""
        invalidator, state_machine = invalidator_setup
        run = state_machine.create_run(profile="test", total_pages=1)
        state_machine.add_page(run.run_id, "service-a", "module", "docs/modules/service-a.md")
        state_machine.complete_page(run.run_id, "service-a")

        monkeypatch.setattr(
            "repo_wiki.orchestration.generation_invalidation.get_git_diff",
            lambda root, ref=None, file_filter=None: GitDiffResult(
                changed_files=[],
                deleted_files=[],
                renamed_files={},
                commit_range=None,
                is_clean=True,
            ),
        )

        invalidated, _, strategy = invalidator.invalidate_with_git_or_hash_fallback(
            run_id=run.run_id,
            baseline_hashes={"services/service-a/app.py": "aaa"},
            current_hashes={"services/service-a/app.py": "bbb"},
        )
        assert strategy == "hash-fallback"
        assert invalidated == ["service-a"]

    def test_map_changed_file_to_page_via_evidence_span(self, invalidator_setup):
        """Changed file should map to page via runtime evidence tables."""
        invalidator, state_machine = invalidator_setup
        run = state_machine.create_run(profile="test", total_pages=1)
        state_machine.add_page(run.run_id, "service-a", "module", "docs/modules/service-a.md")
        state_machine.complete_page(run.run_id, "service-a")

        runtime_db = invalidator.root / ".repo-wiki" / "index" / "runtime.sqlite3"
        runtime_db.parent.mkdir(parents=True, exist_ok=True)
        import sqlite3
        with sqlite3.connect(runtime_db) as conn:
            conn.execute(
                "CREATE TABLE evidence_span (id INTEGER PRIMARY KEY, file_path TEXT)"
            )
            conn.execute(
                "CREATE TABLE page_source_map (evidence_id INTEGER, doc_slug TEXT)"
            )
            conn.execute(
                "INSERT INTO evidence_span(id, file_path) VALUES (1, ?)",
                ("services/service-a/app.py",),
            )
            conn.execute(
                "INSERT INTO page_source_map(evidence_id, doc_slug) VALUES (1, ?)",
                ("service-a",),
            )
            conn.commit()

        invalidated, _ = invalidator.invalidate_from_hash_comparison(
            run_id=run.run_id,
            baseline_hashes={"services/service-a/app.py": "aaa"},
            current_hashes={"services/service-a/app.py": "changed"},
        )
        assert "service-a" in invalidated


class TestCreateGenerationInvalidator:
    """Tests for create_generation_invalidator factory."""

    def test_create_invalidator_factory(self, tmp_path):
        """Test create_generation_invalidator factory."""
        db_path = tmp_path / "state.sqlite3"
        state_machine = GenerationStateMachine(db_path)

        invalidator = create_generation_invalidator(state_machine, tmp_path)
        assert isinstance(invalidator, GenerationAwareInvalidator)
