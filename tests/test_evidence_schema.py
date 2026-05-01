"""Tests for Phase 23 Evidence SQLite schema.

Tests evidence_span, page_source_map, and symbol_reference tables
for storing source spans with file/line citations.
"""

import json
import tempfile
from pathlib import Path

import pytest

from repo_wiki.orchestration.runtime_store import (
    SQLiteRuntimeStore,
    EvidenceSpanRecord,
    PageSourceMapRecord,
    SymbolReferenceRecord,
)


class TestEvidenceSQLiteSchema:
    """Tests for Phase 23 evidence schema."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_evidence.sqlite3"
            store = SQLiteRuntimeStore(db_path)
            yield store
            store.close()

    def test_schema_version_includes_migration_4(self, temp_db):
        """Test that migration 4 is applied."""
        assert temp_db.current_schema_version() >= 4

    # =====================================================================
    # Evidence Span Tests
    # =====================================================================

    def test_evidence_span_crud(self, temp_db):
        """Test evidence span CRUD operations."""
        record = EvidenceSpanRecord(
            digest="abc123def456",
            file_path="repo_wiki/core/runtime.py",
            line_start=10,
            line_end=20,
            language="python",
            symbol="BootstrapResult",
            span_text="class BootstrapResult:",
            confidence=1.0,
        )
        evidence_id = temp_db.upsert_evidence_span(record)

        # Read back
        spans = temp_db.list_evidence_spans()
        assert len(spans) == 1
        assert spans[0]["file_path"] == "repo_wiki/core/runtime.py"
        assert spans[0]["line_start"] == 10
        assert spans[0]["line_end"] == 20
        assert spans[0]["language"] == "python"
        assert spans[0]["symbol"] == "BootstrapResult"

        # Get by id
        span = temp_db.get_evidence_span(evidence_id)
        assert span is not None
        assert span["digest"] == "abc123def456"

        # Get by digest
        span = temp_db.get_evidence_span_by_digest("abc123def456")
        assert span is not None
        assert span["symbol"] == "BootstrapResult"

    def test_evidence_span_upsert_idempotent(self, temp_db):
        """Test that upserting same digest updates, not duplicates."""
        record = EvidenceSpanRecord(
            digest="dupdigest123",
            file_path="src/main.py",
            line_start=1,
            line_end=10,
            language="python",
            span_text="def main(): pass",
        )

        # Insert twice
        temp_db.upsert_evidence_span(record)
        record.symbol = "UpdatedSymbol"
        temp_db.upsert_evidence_span(record)

        spans = temp_db.list_evidence_spans()
        assert len(spans) == 1  # Should still be 1, not duplicated
        assert spans[0]["symbol"] == "UpdatedSymbol"

    def test_evidence_span_filter_by_language(self, temp_db):
        """Test filtering evidence spans by language."""
        records = [
            EvidenceSpanRecord(
                digest=f"digest{i}",
                file_path=f"src/file{i}.py",
                line_start=i * 10,
                line_end=i * 10 + 5,
                language="python",
                span_text=f"# python code {i}",
            )
            for i in range(3)
        ]
        records.append(
            EvidenceSpanRecord(
                digest="tsdigest",
                file_path="src/app.ts",
                line_start=1,
                line_end=5,
                language="typescript",
                span_text="// typescript code",
            )
        )
        for r in records:
            temp_db.upsert_evidence_span(r)

        python_spans = temp_db.list_evidence_spans(language="python")
        assert len(python_spans) == 3

        ts_spans = temp_db.list_evidence_spans(language="typescript")
        assert len(ts_spans) == 1

    def test_evidence_span_filter_by_file_path(self, temp_db):
        """Test filtering evidence spans by file path."""
        record1 = EvidenceSpanRecord(
            digest="fp1digest",
            file_path="repo_wiki/core/config.py",
            line_start=1,
            line_end=5,
            language="python",
            span_text="class Config:",
        )
        record2 = EvidenceSpanRecord(
            digest="fp2digest",
            file_path="repo_wiki/core/runtime.py",
            line_start=1,
            line_end=5,
            language="python",
            span_text="class Runtime:",
        )
        temp_db.upsert_evidence_span(record1)
        temp_db.upsert_evidence_span(record2)

        spans = temp_db.list_evidence_spans(file_path="repo_wiki/core/config.py")
        assert len(spans) == 1
        assert spans[0]["span_text"] == "class Config:"

    def test_count_evidence_spans(self, temp_db):
        """Test counting evidence spans."""
        for i in range(5):
            record = EvidenceSpanRecord(
                digest=f"count{i}",
                file_path=f"src/file{i}.py",
                line_start=1,
                line_end=5,
                language="python",
                span_text=f"code {i}",
            )
            temp_db.upsert_evidence_span(record)

        assert temp_db.count_evidence_spans() == 5

    # =====================================================================
    # Page Source Map Tests
    # =====================================================================

    def test_map_evidence_to_page(self, temp_db):
        """Test mapping evidence spans to wiki pages."""
        # First create an evidence span
        evidence = EvidenceSpanRecord(
            digest="pagemapdigest",
            file_path="repo_wiki/scanner/artifacts.py",
            line_start=15,
            line_end=25,
            language="python",
            symbol="write_source_of_truth",
            span_text="def write_source_of_truth(root, snapshot):",
        )
        evidence_id = temp_db.upsert_evidence_span(evidence)

        # Map to page
        temp_db.map_evidence_to_page(
            doc_slug="00-overview",
            doc_type="overview",
            evidence_id=evidence_id,
            citation_order=0,
            context_hint="source of truth writer",
        )

        # Read back page sources
        sources = temp_db.list_page_sources("00-overview", "overview")
        assert len(sources) == 1
        assert sources[0]["evidence_id"] == evidence_id
        assert sources[0]["citation_order"] == 0
        assert sources[0]["context_hint"] == "source of truth writer"

    def test_list_pages_for_evidence(self, temp_db):
        """Test listing all pages that reference an evidence span."""
        evidence = EvidenceSpanRecord(
            digest="multipagedigest",
            file_path="repo_wiki/core/contracts.py",
            line_start=1,
            line_end=10,
            language="python",
            span_text="class DataModel:",
        )
        evidence_id = temp_db.upsert_evidence_span(evidence)

        # Map to multiple pages
        temp_db.map_evidence_to_page("00-overview", "overview", evidence_id, 0)
        temp_db.map_evidence_to_page("01-architecture", "section", evidence_id, 1)

        pages = temp_db.list_pages_for_evidence(evidence_id)
        assert len(pages) == 2
        doc_slugs = [p["doc_slug"] for p in pages]
        assert "00-overview" in doc_slugs
        assert "01-architecture" in doc_slugs

    def test_unmap_evidence_from_page(self, temp_db):
        """Test removing evidence-to-page mapping."""
        evidence = EvidenceSpanRecord(
            digest="unmapdigest",
            file_path="src/main.py",
            line_start=1,
            line_end=5,
            language="python",
            span_text="def main():",
        )
        evidence_id = temp_db.upsert_evidence_span(evidence)

        temp_db.map_evidence_to_page("test-page", "section", evidence_id)
        sources = temp_db.list_page_sources("test-page", "section")
        assert len(sources) == 1

        temp_db.unmap_evidence_from_page("test-page", "section", evidence_id)
        sources = temp_db.list_page_sources("test-page", "section")
        assert len(sources) == 0

    def test_clear_page_sources(self, temp_db):
        """Test clearing all evidence mappings for a page."""
        evidence_ids = []
        for i in range(3):
            evidence = EvidenceSpanRecord(
                digest=f"cleardigest{i}",
                file_path=f"src/file{i}.py",
                line_start=1,
                line_end=5,
                language="python",
                span_text=f"code {i}",
            )
            evidence_id = temp_db.upsert_evidence_span(evidence)
            evidence_ids.append(evidence_id)

        for eid in evidence_ids:
            temp_db.map_evidence_to_page("target-page", "section", eid)

        sources = temp_db.list_page_sources("target-page", "section")
        assert len(sources) == 3

        temp_db.clear_page_sources("target-page", "section")
        sources = temp_db.list_page_sources("target-page", "section")
        assert len(sources) == 0

    # =====================================================================
    # Symbol Reference Tests
    # =====================================================================

    def test_symbol_reference_crud(self, temp_db):
        """Test symbol reference CRUD operations."""
        record = SymbolReferenceRecord(
            source_file_path="repo_wiki/core/runtime.py",
            source_line_start=25,
            source_line_end=25,
            source_symbol="RuntimeError",
            target_symbol="BootstrapResult",
            target_file_path="repo_wiki/core/runtime.py",
            target_line_start=10,
            target_line_end=20,
            ref_type="type_ref",
            confidence=1.0,
        )
        ref_id = temp_db.upsert_symbol_reference(record)

        # Read back
        refs = temp_db.list_symbol_references()
        assert len(refs) == 1
        assert refs[0]["target_symbol"] == "BootstrapResult"
        assert refs[0]["ref_type"] == "type_ref"

    def test_symbol_reference_filter_by_target(self, temp_db):
        """Test filtering symbol references by target symbol."""
        records = [
            SymbolReferenceRecord(
                source_file_path=f"src/file{i}.py",
                source_line_start=i * 10,
                source_line_end=i * 10,
                target_symbol="TargetSymbol",
                ref_type="call",
                source_symbol=f"caller{i}",
            )
            for i in range(3)
        ]
        records.append(
            SymbolReferenceRecord(
                source_file_path="src/other.py",
                source_line_start=1,
                source_line_end=1,
                target_symbol="OtherSymbol",
                ref_type="import",
            )
        )
        for r in records:
            temp_db.upsert_symbol_reference(r)

        refs = temp_db.list_symbol_references(target_symbol="TargetSymbol")
        assert len(refs) == 3

    def test_symbol_reference_filter_by_type(self, temp_db):
        """Test filtering symbol references by reference type."""
        call_ref = SymbolReferenceRecord(
            source_file_path="src/main.py",
            source_line_start=10,
            source_line_end=10,
            target_symbol="process",
            ref_type="call",
        )
        import_ref = SymbolReferenceRecord(
            source_file_path="src/main.py",
            source_line_start=5,
            source_line_end=5,
            target_symbol="os",
            ref_type="import",
        )
        temp_db.upsert_symbol_reference(call_ref)
        temp_db.upsert_symbol_reference(import_ref)

        call_refs = temp_db.list_symbol_references(ref_type="call")
        assert len(call_refs) == 1
        assert call_refs[0]["target_symbol"] == "process"

        import_refs = temp_db.list_symbol_references(ref_type="import")
        assert len(import_refs) == 1
        assert import_refs[0]["target_symbol"] == "os"

    def test_get_symbol_targets_at_line(self, temp_db):
        """Test getting symbol targets at a specific source location."""
        # Create overlapping references
        temp_db.upsert_symbol_reference(
            SymbolReferenceRecord(
                source_file_path="src/utils.py",
                source_line_start=5,
                source_line_end=15,
                target_symbol="Helper",
                ref_type="inheritance",
            )
        )
        temp_db.upsert_symbol_reference(
            SymbolReferenceRecord(
                source_file_path="src/utils.py",
                source_line_start=20,
                source_line_end=25,
                target_symbol="Validator",
                ref_type="call",
            )
        )

        # Query for a line within the first reference
        targets = temp_db.get_symbol_targets("src/utils.py", 10)
        assert len(targets) == 1
        assert targets[0]["target_symbol"] == "Helper"

        # Query for a line within the second reference
        targets = temp_db.get_symbol_targets("src/utils.py", 22)
        assert len(targets) == 1
        assert targets[0]["target_symbol"] == "Validator"

        # Query for a line with no references
        targets = temp_db.get_symbol_targets("src/utils.py", 30)
        assert len(targets) == 0

    def test_count_symbol_references(self, temp_db):
        """Test counting symbol references."""
        for i in range(4):
            temp_db.upsert_symbol_reference(
                SymbolReferenceRecord(
                    source_file_path=f"src/file{i}.py",
                    source_line_start=i,
                    source_line_end=i,
                    target_symbol=f"target{i}",
                    ref_type="call",
                )
            )

        assert temp_db.count_symbol_references() == 4

    # =====================================================================
    # Cross-Table Integrity Tests
    # =====================================================================

    def test_evidence_with_page_sources_and_symbol_refs(self, temp_db):
        """Test full workflow: evidence spans, page mapping, symbol references."""
        # Create evidence spans
        evidence1 = EvidenceSpanRecord(
            digest="fulldigest1",
            file_path="repo_wiki/core/config.py",
            line_start=10,
            line_end=20,
            language="python",
            symbol="IndexConfig",
            span_text="class IndexConfig:",
        )
        evidence2 = EvidenceSpanRecord(
            digest="fulldigest2",
            file_path="repo_wiki/core/runtime.py",
            line_start=10,
            line_end=20,
            language="python",
            symbol="BootstrapResult",
            span_text="class BootstrapResult:",
        )
        eid1 = temp_db.upsert_evidence_span(evidence1)
        eid2 = temp_db.upsert_evidence_span(evidence2)

        # Map to pages
        temp_db.map_evidence_to_page("00-overview", "overview", eid1, 0)
        temp_db.map_evidence_to_page("05-data-model", "section", eid1, 1)
        temp_db.map_evidence_to_page("05-data-model", "section", eid2, 0)

        # Create symbol references
        temp_db.upsert_symbol_reference(
            SymbolReferenceRecord(
                source_file_path="repo_wiki/core/runtime.py",
                source_line_start=15,
                source_line_end=15,
                source_symbol="RuntimeError",
                target_symbol="BootstrapResult",
                ref_type="type_ref",
            )
        )

        # Verify counts
        assert temp_db.count_evidence_spans() == 2
        assert temp_db.count_symbol_references() == 1

        # Verify page sources
        overview_sources = temp_db.list_page_sources("00-overview", "overview")
        assert len(overview_sources) == 1

        datamodel_sources = temp_db.list_page_sources("05-data-model", "section")
        assert len(datamodel_sources) == 2

        # Verify pages for evidence
        pages_for_e1 = temp_db.list_pages_for_evidence(eid1)
        assert len(pages_for_e1) == 2

    # =====================================================================
    # Migration Safety Tests
    # =====================================================================

    def test_migration_4_idempotent(self, tmp_path: Path):
        """Test that migration 4 can be applied multiple times safely."""
        db_path = tmp_path / "idempotent.sqlite3"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        store1 = SQLiteRuntimeStore(db_path)
        version1 = store1.current_schema_version()
        store1.close()

        # Apply migrations again
        store2 = SQLiteRuntimeStore(db_path)
        version2 = store2.current_schema_version()
        store2.close()

        assert version1 == version2
        assert version1 >= 4

    def test_upsert_idempotent_forEvidenceSpans(self, tmp_path: Path):
        """Test upsert operations are idempotent for evidence spans."""
        db_path = tmp_path / "upsert_evidence.sqlite3"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        store = SQLiteRuntimeStore(db_path)

        record = EvidenceSpanRecord(
            digest="upsertidempotent",
            file_path="src/main.py",
            line_start=1,
            line_end=10,
            language="python",
            span_text="def main(): pass",
        )

        # Insert same digest twice
        store.upsert_evidence_span(record)
        store.upsert_evidence_span(record)

        spans = store.list_evidence_spans()
        assert len(spans) == 1

        store.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
