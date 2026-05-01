"""SQLite runtime store extending state_store for Phase 12 dual-database architecture.

This module defines the responsibilities of:
- Primary state DB (state.sqlite3): operational state, file/chunk/symbol indexes, FTS
- Generation/evidence DB (generation_cache.sqlite3): document hierarchy, nav graph, readiness evidence

Dual-database boundary rules:
1. state.sqlite3: files, chunks, symbols, FTS, verify_runs (summary only)
2. generation_cache.sqlite3: doc hierarchy, section registry, nav graph, evidence bundles, generation cache

Migration path:
- Schema version 2 introduces document hierarchy tables
- Schema version 3 introduces nav_graph and evidence tables
- Each migration is deterministic and idempotent
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Sequence


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _now_epoch() -> float:
    return time.time()


SCHEMA_VERSION = 4

# Migration 2: Document hierarchy and section registry
MIGRATION_2 = """
-- Document hierarchy table: stores the structure of generated docs
CREATE TABLE IF NOT EXISTS doc_hierarchy (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_type TEXT NOT NULL,          -- 'overview', 'section', 'module', 'phase'
    doc_slug TEXT NOT NULL,         -- e.g., '00-overview', 'architecture', 'repo_wiki'
    doc_path TEXT NOT NULL,         -- relative path: 'docs/00-overview.md', 'docs/sections/architecture/index.md'
    title TEXT,
    layer TEXT NOT NULL,            -- 'overview', 'section', 'module', 'phase'
    parent_slug TEXT,                -- parent section slug (for sections)
    sort_order INTEGER DEFAULT 0,
    generation_input_hash TEXT,
    generation_output_hash TEXT,
    generated_at TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(doc_type, doc_slug)
);

CREATE INDEX IF NOT EXISTS idx_doc_hierarchy_type ON doc_hierarchy(doc_type);
CREATE INDEX IF NOT EXISTS idx_doc_hierarchy_slug ON doc_hierarchy(doc_slug);
CREATE INDEX IF NOT EXISTS idx_doc_hierarchy_path ON doc_hierarchy(doc_path);
CREATE INDEX IF NOT EXISTS idx_doc_hierarchy_layer ON doc_hierarchy(layer);

-- Section registry table: canonical sections and their aliases
CREATE TABLE IF NOT EXISTS section_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT,
    required_for_phase TEXT,         -- which phase requires this section
    sort_order INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_section_registry_slug ON section_registry(canonical_slug);
CREATE INDEX IF NOT EXISTS idx_section_registry_active ON section_registry(is_active);

-- Section alias table: maps aliases to canonical sections
CREATE TABLE IF NOT EXISTS section_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alias_slug TEXT NOT NULL UNIQUE,
    canonical_slug TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (canonical_slug) REFERENCES section_registry(canonical_slug)
);

CREATE INDEX IF NOT EXISTS idx_section_aliases_alias ON section_aliases(alias_slug);
CREATE INDEX IF NOT EXISTS idx_section_aliases_canonical ON section_aliases(canonical_slug);

-- Cross-link table: navigation links between documents
CREATE TABLE IF NOT EXISTS doc_cross_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_doc_type TEXT NOT NULL,
    source_doc_slug TEXT NOT NULL,
    target_doc_type TEXT NOT NULL,
    target_doc_slug TEXT NOT NULL,
    link_type TEXT NOT NULL,         -- 'navigation', 'reference', 'cross_section'
    link_path TEXT NOT NULL,         -- relative path used in markdown
    is_valid INTEGER DEFAULT 1,
    validated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_cross_links_source ON doc_cross_links(source_doc_type, source_doc_slug);
CREATE INDEX IF NOT EXISTS idx_cross_links_target ON doc_cross_links(target_doc_type, target_doc_slug);
"""

# Migration 3: Nav graph and readiness evidence tables
MIGRATION_3 = """
-- Nav graph: page-level navigation structure for incremental invalidation
CREATE TABLE IF NOT EXISTS nav_graph (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_slug TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    incoming_links_json TEXT NOT NULL,    -- JSON array of doc_slugs linking TO this doc
    outgoing_links_json TEXT NOT NULL,    -- JSON array of doc_slugs this doc links TO
    depth INTEGER DEFAULT 0,              -- 0=overview, 1=section, 2=module
    affected_pages_json TEXT NOT NULL,    -- JSON array of page slugs that depend on this doc
    last_validated_at TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(doc_slug)
);

CREATE INDEX IF NOT EXISTS idx_nav_graph_slug ON nav_graph(doc_slug);
CREATE INDEX IF NOT EXISTS idx_nav_graph_type ON nav_graph(doc_type);

-- Verify runs persistence table (extended from state_store basic tracking)
CREATE TABLE IF NOT EXISTS verify_run_details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL UNIQUE,         -- unique run identifier (timestamp-based)
    target_path TEXT NOT NULL,
    grade TEXT NOT NULL,                  -- 'PASS', 'WARN', 'FAIL'
    exit_code INTEGER NOT NULL,
    hard_gate_failures INTEGER DEFAULT 0,
    soft_gate_failures INTEGER DEFAULT 0,
    warning_count INTEGER DEFAULT 0,
    pass_count INTEGER DEFAULT 0,
    total_checks INTEGER DEFAULT 0,
    score REAL DEFAULT 0.0,
    hard_gate_codes_json TEXT NOT NULL,  -- JSON array of hard gate reason codes
    soft_gate_codes_json TEXT NOT NULL,  -- JSON array of soft gate reason codes
    checks_summary_json TEXT NOT NULL,    -- JSON summary of all checks
    full_result_json TEXT NOT NULL,       -- complete verify result for audit
    created_at TEXT NOT NULL,
    duration_ms INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_verify_runs_target ON verify_run_details(target_path);
CREATE INDEX IF NOT EXISTS idx_verify_runs_grade ON verify_run_details(grade);
CREATE INDEX IF NOT EXISTS idx_verify_runs_created ON verify_run_details(created_at);

-- Compare runs persistence table
CREATE TABLE IF NOT EXISTS compare_run_details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL UNIQUE,
    target_path TEXT NOT NULL,
    baseline_path TEXT NOT NULL,
    overall_score REAL DEFAULT 0.0,
    overall_band TEXT NOT NULL,           -- 'EXCELLENT', 'GOOD', 'ACCEPTABLE', 'POOR'
    structural_score REAL DEFAULT 0.0,
    quality_score REAL DEFAULT 0.0,
    acceptance_blocked INTEGER DEFAULT 0,
    total_gaps INTEGER DEFAULT 0,
    critical_gaps INTEGER DEFAULT 0,
    major_gaps INTEGER DEFAULT 0,
    delta_type_json TEXT NOT NULL,        -- JSON object with dimension -> delta_type mapping
    scores_json TEXT NOT NULL,            -- JSON object with dimension -> score mapping
    gaps_json TEXT NOT NULL,              -- JSON array of gap items
    full_result_json TEXT NOT NULL,       -- complete compare result for audit
    created_at TEXT NOT NULL,
    duration_ms INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_compare_runs_target ON compare_run_details(target_path);
CREATE INDEX IF NOT EXISTS idx_compare_runs_band ON compare_run_details(overall_band);
CREATE INDEX IF NOT EXISTS idx_compare_runs_created ON compare_run_details(created_at);

-- Page invalidation cache: tracks which pages need regeneration
CREATE TABLE IF NOT EXISTS page_invalidation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_slug TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    invalidation_reason TEXT NOT NULL,   -- 'file_changed', 'section_updated', 'nav_broken', 'evidence_stale'
    changed_files_json TEXT NOT NULL,    -- JSON array of file paths that changed
    impacted_modules_json TEXT NOT NULL, -- JSON array of module names affected
    is_invalidated INTEGER DEFAULT 1,
    invalidated_at TEXT NOT NULL,
    regenerated_at TEXT,
    regeneration_status TEXT           -- 'pending', 'in_progress', 'completed', 'failed'
);

CREATE INDEX IF NOT EXISTS idx_invalidation_slug ON page_invalidation(doc_slug);
CREATE INDEX IF NOT EXISTS idx_invalidation_reason ON page_invalidation(invalidation_reason);
CREATE INDEX IF NOT EXISTS idx_invalidation_at ON page_invalidation(invalidated_at);
"""

# Migration 4: Evidence spans with file/line citations
MIGRATION_4 = """
-- Evidence span: source spans with file path, line range, language, symbol, digest
CREATE TABLE IF NOT EXISTS evidence_span (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    digest TEXT NOT NULL,                -- SHA256 of span text for deduplication
    file_path TEXT NOT NULL,             -- absolute or relative file path
    line_start INTEGER NOT NULL,
    line_end INTEGER NOT NULL,
    language TEXT NOT NULL,              -- 'python', 'typescript', 'java', 'sql', 'yaml', 'markdown'
    symbol TEXT,                          -- symbol name (function, class, variable)
    span_text TEXT NOT NULL,             -- the actual source text
    confidence REAL DEFAULT 1.0,        -- extraction confidence 0.0-1.0
    created_at TEXT NOT NULL,
    UNIQUE(digest)
);

CREATE INDEX IF NOT EXISTS idx_evidence_span_file ON evidence_span(file_path);
CREATE INDEX IF NOT EXISTS idx_evidence_span_language ON evidence_span(language);
CREATE INDEX IF NOT EXISTS idx_evidence_span_symbol ON evidence_span(symbol);
CREATE INDEX IF NOT EXISTS idx_evidence_span_digest ON evidence_span(digest);

-- Page source map: links evidence spans to wiki page slugs
CREATE TABLE IF NOT EXISTS page_source_map (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_slug TEXT NOT NULL,              -- wiki page slug (e.g., '00-overview', 'architecture')
    doc_type TEXT NOT NULL,              -- 'overview', 'section', 'module', 'phase'
    evidence_id INTEGER NOT NULL,        -- FK to evidence_span.id
    citation_order INTEGER DEFAULT 0,    -- order of citation on the page
    context_hint TEXT,                    -- optional context (e.g., 'parameter of foo()')
    created_at TEXT NOT NULL,
    FOREIGN KEY (evidence_id) REFERENCES evidence_span(id)
);

CREATE INDEX IF NOT EXISTS idx_page_source_doc ON page_source_map(doc_slug, doc_type);
CREATE INDEX IF NOT EXISTS idx_page_source_evidence ON page_source_map(evidence_id);

-- Symbol reference: cross-references between symbols and their usages
CREATE TABLE IF NOT EXISTS symbol_reference (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file_path TEXT NOT NULL,
    source_line_start INTEGER NOT NULL,
    source_line_end INTEGER NOT NULL,
    source_symbol TEXT,                  -- symbol at the reference location
    target_symbol TEXT NOT NULL,        -- symbol being referenced
    target_file_path TEXT,               -- file where target symbol is defined
    target_line_start INTEGER,           -- line where target symbol is defined
    target_line_end INTEGER,             -- line range of target symbol definition
    ref_type TEXT NOT NULL,              -- 'call', 'import', 'inheritance', 'type_ref', 'variable_ref'
    confidence REAL DEFAULT 1.0,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_symbol_ref_source ON symbol_reference(source_file_path);
CREATE INDEX IF NOT EXISTS idx_symbol_ref_target ON symbol_reference(target_symbol);
CREATE INDEX IF NOT EXISTS idx_symbol_ref_type ON symbol_reference(ref_type);
"""

MIGRATIONS = {
    2: MIGRATION_2,
    3: MIGRATION_3,
    4: MIGRATION_4,
}


@dataclass
class DocHierarchyRecord:
    """A document hierarchy record."""
    doc_type: str
    doc_slug: str
    doc_path: str
    layer: str
    parent_slug: str | None = None
    title: str | None = None
    sort_order: int = 0
    generation_input_hash: str | None = None
    generation_output_hash: str | None = None
    generated_at: str | None = None
    updated_at: str | None = None


@dataclass
class SectionRegistryRecord:
    """A section registry record."""
    canonical_slug: str
    title: str
    description: str | None = None
    required_for_phase: str | None = None
    sort_order: int = 0
    is_active: bool = True


@dataclass
class VerifyRunRecord:
    """A verify run record for trend analysis."""
    run_id: str
    target_path: str
    grade: str
    exit_code: int
    hard_gate_failures: int
    soft_gate_failures: int
    score: float
    hard_gate_codes: list[str]
    soft_gate_codes: list[str]
    created_at: str
    duration_ms: int = 0


@dataclass
class CompareRunRecord:
    """A compare run record for trend analysis."""
    run_id: str
    target_path: str
    baseline_path: str
    overall_score: float
    overall_band: str
    structural_score: float
    quality_score: float
    acceptance_blocked: bool
    total_gaps: int
    critical_gaps: int
    created_at: str
    duration_ms: int = 0


@dataclass
class PageInvalidationRecord:
    """A page invalidation record."""
    doc_slug: str
    doc_type: str
    invalidation_reason: str
    changed_files: list[str]
    impacted_modules: list[str]
    invalidated_at: str
    is_invalidated: bool = True
    regenerated_at: str | None = None
    regeneration_status: str | None = None


@dataclass
class EvidenceSpanRecord:
    """An evidence span record with file/line citation."""
    digest: str
    file_path: str
    line_start: int
    line_end: int
    language: str
    span_text: str
    symbol: str | None = None
    confidence: float = 1.0
    created_at: str | None = None


@dataclass
class PageSourceMapRecord:
    """A page source map record linking evidence to wiki pages."""
    doc_slug: str
    doc_type: str
    evidence_id: int
    citation_order: int = 0
    context_hint: str | None = None
    created_at: str | None = None


@dataclass
class SymbolReferenceRecord:
    """A symbol reference record for cross-referencing symbols."""
    source_file_path: str
    source_line_start: int
    source_line_end: int
    target_symbol: str
    ref_type: str
    source_symbol: str | None = None
    target_file_path: str | None = None
    target_line_start: int | None = None
    target_line_end: int | None = None
    confidence: float = 1.0
    created_at: str | None = None


class SQLiteRuntimeStore:
    """SQLite runtime store for Phase 12 dual-database architecture.

    This store extends the state store with document hierarchy, section registry,
    nav graph, and readiness evidence tables. It maintains the dual-database boundary:

    - state.sqlite3: operational state (files, chunks, symbols, FTS)
    - This store (runtime.sqlite3 or same state.db): document hierarchy and evidence

    The boundary is enforced by keeping file/chunk/symbol operations in SQLiteStateStore
    while this store handles doc-level metadata and evidence persistence.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._configure_pragmas()
        self._apply_migrations()

    def _configure_pragmas(self) -> None:
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self.conn.execute("PRAGMA foreign_keys=ON;")

    def _apply_migrations(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            );
            """
        )
        applied = {
            int(row["version"])
            for row in self.conn.execute("SELECT version FROM schema_migrations")
        }
        for version in sorted(MIGRATIONS):
            if version in applied:
                continue
            with self.conn:
                self.conn.executescript(MIGRATIONS[version])
                self.conn.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES(?, ?)",
                    (version, _now_iso()),
                )
        self.conn.commit()

    def current_schema_version(self) -> int:
        row = self.conn.execute(
            "SELECT MAX(version) as v FROM schema_migrations"
        ).fetchone()
        return int(row["v"]) if row and row["v"] else 0

    def close(self) -> None:
        self.conn.close()

    # =========================================================================
    # Document Hierarchy Operations
    # =========================================================================

    def upsert_doc_hierarchy(self, record: DocHierarchyRecord) -> None:
        """Insert or update a document hierarchy record."""
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO doc_hierarchy(
                    doc_type, doc_slug, doc_path, title, layer, parent_slug,
                    sort_order, generation_input_hash, generation_output_hash,
                    generated_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(doc_type, doc_slug) DO UPDATE SET
                    doc_path=excluded.doc_path,
                    title=excluded.title,
                    layer=excluded.layer,
                    parent_slug=excluded.parent_slug,
                    sort_order=excluded.sort_order,
                    generation_input_hash=excluded.generation_input_hash,
                    generation_output_hash=excluded.generation_output_hash,
                    generated_at=excluded.generated_at,
                    updated_at=excluded.updated_at
                """,
                (
                    record.doc_type,
                    record.doc_slug,
                    record.doc_path,
                    record.title,
                    record.layer,
                    record.parent_slug,
                    record.sort_order,
                    record.generation_input_hash,
                    record.generation_output_hash,
                    record.generated_at,
                    _now_iso(),
                ),
            )

    def list_docs_by_type(self, doc_type: str) -> List[dict]:
        """List all documents of a given type."""
        rows = self.conn.execute(
            """
            SELECT * FROM doc_hierarchy
            WHERE doc_type = ?
            ORDER BY sort_order, doc_slug
            """,
            (doc_type,),
        ).fetchall()
        return [dict(row) for row in rows]

    def list_docs_by_layer(self, layer: str) -> List[dict]:
        """List all documents in a given layer."""
        rows = self.conn.execute(
            """
            SELECT * FROM doc_hierarchy
            WHERE layer = ?
            ORDER BY sort_order, doc_slug
            """,
            (layer,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_doc_by_slug(self, doc_slug: str) -> dict | None:
        """Get a document by its slug."""
        row = self.conn.execute(
            "SELECT * FROM doc_hierarchy WHERE doc_slug = ?",
            (doc_slug,),
        ).fetchone()
        return dict(row) if row else None

    def get_doc_by_path(self, doc_path: str) -> dict | None:
        """Get a document by its path."""
        row = self.conn.execute(
            "SELECT * FROM doc_hierarchy WHERE doc_path = ?",
            (doc_path,),
        ).fetchone()
        return dict(row) if row else None

    def delete_doc(self, doc_type: str, doc_slug: str) -> None:
        """Delete a document hierarchy record."""
        with self.conn:
            self.conn.execute(
                "DELETE FROM doc_hierarchy WHERE doc_type = ? AND doc_slug = ?",
                (doc_type, doc_slug),
            )

    # =========================================================================
    # Section Registry Operations
    # =========================================================================

    def register_section(self, record: SectionRegistryRecord) -> None:
        """Register a section in the section registry."""
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO section_registry(
                    canonical_slug, title, description, required_for_phase,
                    sort_order, is_active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(canonical_slug) DO UPDATE SET
                    title=excluded.title,
                    description=excluded.description,
                    required_for_phase=excluded.required_for_phase,
                    sort_order=excluded.sort_order,
                    is_active=excluded.is_active,
                    updated_at=excluded.updated_at
                """,
                (
                    record.canonical_slug,
                    record.title,
                    record.description,
                    record.required_for_phase,
                    record.sort_order,
                    1 if record.is_active else 0,
                    _now_iso(),
                    _now_iso(),
                ),
            )

    def register_section_alias(self, alias_slug: str, canonical_slug: str) -> None:
        """Register an alias for a section."""
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO section_aliases(alias_slug, canonical_slug, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(alias_slug) DO UPDATE SET
                    canonical_slug=excluded.canonical_slug
                """,
                (alias_slug, canonical_slug, _now_iso()),
            )

    def resolve_section_alias(self, alias_slug: str) -> str | None:
        """Resolve an alias to its canonical slug."""
        row = self.conn.execute(
            "SELECT canonical_slug FROM section_aliases WHERE alias_slug = ?",
            (alias_slug,),
        ).fetchone()
        return row["canonical_slug"] if row else None

    def list_active_sections(self) -> List[dict]:
        """List all active sections."""
        rows = self.conn.execute(
            """
            SELECT * FROM section_registry
            WHERE is_active = 1
            ORDER BY sort_order, canonical_slug
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def get_section_by_slug(self, slug: str) -> dict | None:
        """Get a section by slug (canonical or alias)."""
        # First check canonical
        row = self.conn.execute(
            "SELECT * FROM section_registry WHERE canonical_slug = ?",
            (slug,),
        ).fetchone()
        if row:
            return dict(row)
        # Then check alias
        canonical = self.resolve_section_alias(slug)
        if canonical:
            row = self.conn.execute(
                "SELECT * FROM section_registry WHERE canonical_slug = ?",
                (canonical,),
            ).fetchone()
            if row:
                return dict(row)
        return None

    def list_section_aliases(self, canonical_slug: str) -> List[str]:
        """List all aliases for a canonical slug."""
        rows = self.conn.execute(
            "SELECT alias_slug FROM section_aliases WHERE canonical_slug = ?",
            (canonical_slug,),
        ).fetchall()
        return [row["alias_slug"] for row in rows]

    # =========================================================================
    # Nav Graph Operations
    # =========================================================================

    def upsert_nav_node(
        self,
        doc_slug: str,
        doc_type: str,
        incoming_links: list[str],
        outgoing_links: list[str],
        depth: int,
        affected_pages: list[str],
    ) -> None:
        """Insert or update a navigation graph node."""
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO nav_graph(
                    doc_slug, doc_type, incoming_links_json, outgoing_links_json,
                    depth, affected_pages_json, last_validated_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(doc_slug) DO UPDATE SET
                    doc_type=excluded.doc_type,
                    incoming_links_json=excluded.incoming_links_json,
                    outgoing_links_json=excluded.outgoing_links_json,
                    depth=excluded.depth,
                    affected_pages_json=excluded.affected_pages_json,
                    last_validated_at=excluded.last_validated_at,
                    updated_at=excluded.updated_at
                """,
                (
                    doc_slug,
                    doc_type,
                    json.dumps(incoming_links),
                    json.dumps(outgoing_links),
                    depth,
                    json.dumps(affected_pages),
                    _now_iso(),
                    _now_iso(),
                ),
            )

    def get_nav_node(self, doc_slug: str) -> dict | None:
        """Get a navigation node by doc_slug."""
        row = self.conn.execute(
            "SELECT * FROM nav_graph WHERE doc_slug = ?",
            (doc_slug,),
        ).fetchone()
        return dict(row) if row else None

    def list_nav_nodes_by_type(self, doc_type: str) -> List[dict]:
        """List all navigation nodes of a given type."""
        rows = self.conn.execute(
            "SELECT * FROM nav_graph WHERE doc_type = ? ORDER BY depth, doc_slug",
            (doc_type,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_affected_pages(self, doc_slug: str) -> list[str]:
        """Get all pages affected by changes to a given document."""
        row = self.conn.execute(
            "SELECT affected_pages_json FROM nav_graph WHERE doc_slug = ?",
            (doc_slug,),
        ).fetchone()
        if row:
            return json.loads(row["affected_pages_json"])
        return []

    # =========================================================================
    # Cross-Link Operations
    # =========================================================================

    def add_cross_link(
        self,
        source_doc_type: str,
        source_doc_slug: str,
        target_doc_type: str,
        target_doc_slug: str,
        link_type: str,
        link_path: str,
    ) -> None:
        """Add a cross-link between documents."""
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO doc_cross_links(
                    source_doc_type, source_doc_slug, target_doc_type,
                    target_doc_slug, link_type, link_path, is_valid, validated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (source_doc_type, source_doc_slug, target_doc_type, target_doc_slug, link_type, link_path, _now_iso()),
            )

    def validate_cross_links(self, doc_slug: str) -> list[dict]:
        """Validate all cross-links for a document and return broken ones."""
        # This would be implemented to check if target docs exist
        # For now, return empty list (no broken links)
        return []

    # =========================================================================
    # Verify Run Persistence
    # =========================================================================

    def save_verify_run(
        self,
        run_id: str,
        target_path: str,
        verify_result: dict[str, Any],
        duration_ms: int = 0,
    ) -> None:
        """Save a verify run result for trend analysis."""
        summary = verify_result.get("summary", {})
        hard_codes = verify_result.get("hard_gate_codes", [])
        soft_codes = verify_result.get("soft_gate_codes", [])

        # Calculate score from summary
        total = summary.get("total", 0)
        pass_count = summary.get("pass", 0)
        score = pass_count / total if total > 0 else 0.0

        with self.conn:
            self.conn.execute(
                """
                INSERT INTO verify_run_details(
                    run_id, target_path, grade, exit_code,
                    hard_gate_failures, soft_gate_failures,
                    warning_count, pass_count, total_checks,
                    score, hard_gate_codes_json, soft_gate_codes_json,
                    checks_summary_json, full_result_json,
                    created_at, duration_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    target_path,
                    verify_result.get("grade", "FAIL"),
                    verify_result.get("exit_code", 1),
                    summary.get("hard_gate_failures", 0),
                    summary.get("soft_gate_failures", 0),
                    summary.get("warn", 0),
                    pass_count,
                    total,
                    score,
                    json.dumps(hard_codes),
                    json.dumps(soft_codes),
                    json.dumps(summary),
                    json.dumps(verify_result),
                    _now_iso(),
                    duration_ms,
                ),
            )

    def list_verify_runs(
        self,
        target_path: str | None = None,
        limit: int = 100,
    ) -> List[dict]:
        """List verify runs, optionally filtered by target path."""
        if target_path:
            rows = self.conn.execute(
                """
                SELECT * FROM verify_run_details
                WHERE target_path = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (target_path, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """
                SELECT * FROM verify_run_details
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_verify_run(self, run_id: str) -> dict | None:
        """Get a specific verify run by run_id."""
        row = self.conn.execute(
            "SELECT * FROM verify_run_details WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_verify_trend(
        self,
        target_path: str,
        limit: int = 30,
    ) -> list[dict]:
        """Get verify run trend for a target path."""
        rows = self.conn.execute(
            """
            SELECT
                created_at,
                grade,
                score,
                hard_gate_failures,
                soft_gate_failures,
                hard_gate_codes_json,
                soft_gate_codes_json
            FROM verify_run_details
            WHERE target_path = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (target_path, limit),
        ).fetchall()
        return [
            {
                "created_at": row["created_at"],
                "grade": row["grade"],
                "score": row["score"],
                "hard_gate_failures": row["hard_gate_failures"],
                "soft_gate_failures": row["soft_gate_failures"],
                "hard_gate_codes": json.loads(row["hard_gate_codes_json"]),
                "soft_gate_codes": json.loads(row["soft_gate_codes_json"]),
            }
            for row in rows
        ]

    # =========================================================================
    # Compare Run Persistence
    # =========================================================================

    def save_compare_run(
        self,
        run_id: str,
        target_path: str,
        baseline_path: str,
        compare_result: dict[str, Any],
        duration_ms: int = 0,
    ) -> None:
        """Save a compare run result for trend analysis."""
        summary = compare_result.get("summary", {})

        with self.conn:
            self.conn.execute(
                """
                INSERT INTO compare_run_details(
                    run_id, target_path, baseline_path,
                    overall_score, overall_band,
                    structural_score, quality_score,
                    acceptance_blocked, total_gaps,
                    critical_gaps, major_gaps,
                    delta_type_json, scores_json, gaps_json,
                    full_result_json, created_at, duration_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    target_path,
                    baseline_path,
                    summary.get("overall_score", 0.0),
                    summary.get("overall_band", "POOR"),
                    summary.get("structural_score", 0.0),
                    summary.get("quality_score", 0.0),
                    1 if summary.get("acceptance_blocked") else 0,
                    summary.get("total_gaps", 0),
                    summary.get("critical_gaps", 0),
                    summary.get("major_gaps", 0),
                    json.dumps({d["dimension"]: d.get("delta_type", "QUALITY") for d in compare_result.get("dimensions", [])}),
                    json.dumps({d["dimension"]: d.get("score", 0.0) for d in compare_result.get("dimensions", [])}),
                    json.dumps([g.to_dict() if hasattr(g, "to_dict") else g for g in sum((d.get("gaps", []) for d in compare_result.get("dimensions", [])), [])]),
                    json.dumps(compare_result),
                    _now_iso(),
                    duration_ms,
                ),
            )

    def list_compare_runs(
        self,
        target_path: str | None = None,
        limit: int = 100,
    ) -> List[dict]:
        """List compare runs, optionally filtered by target path."""
        if target_path:
            rows = self.conn.execute(
                """
                SELECT * FROM compare_run_details
                WHERE target_path = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (target_path, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """
                SELECT * FROM compare_run_details
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_compare_run(self, run_id: str) -> dict | None:
        """Get a specific compare run by run_id."""
        row = self.conn.execute(
            "SELECT * FROM compare_run_details WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_compare_trend(
        self,
        target_path: str,
        limit: int = 30,
    ) -> list[dict]:
        """Get compare run trend for a target path."""
        rows = self.conn.execute(
            """
            SELECT
                created_at,
                overall_score,
                overall_band,
                structural_score,
                quality_score,
                acceptance_blocked,
                total_gaps,
                critical_gaps,
                major_gaps
            FROM compare_run_details
            WHERE target_path = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (target_path, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    # =========================================================================
    # Page Invalidation Operations
    # =========================================================================

    def invalidate_page(
        self,
        doc_slug: str,
        doc_type: str,
        reason: str,
        changed_files: list[str],
        impacted_modules: list[str],
    ) -> None:
        """Mark a page as invalid for regeneration."""
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO page_invalidation(
                    doc_slug, doc_type, invalidation_reason,
                    changed_files_json, impacted_modules_json,
                    is_invalidated, invalidated_at
                ) VALUES (?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    doc_slug,
                    doc_type,
                    reason,
                    json.dumps(changed_files),
                    json.dumps(impacted_modules),
                    _now_iso(),
                ),
            )

    def mark_page_regenerated(
        self,
        doc_slug: str,
        status: str = "completed",
    ) -> None:
        """Mark a page as regenerated."""
        with self.conn:
            self.conn.execute(
                """
                UPDATE page_invalidation
                SET regenerated_at = ?, regeneration_status = ?
                WHERE doc_slug = ? AND is_invalidated = 1
                """,
                (_now_iso(), status, doc_slug),
            )

    def list_invalidated_pages(
        self,
        reason: str | None = None,
    ) -> List[dict]:
        """List all invalidated pages."""
        if reason:
            rows = self.conn.execute(
                """
                SELECT * FROM page_invalidation
                WHERE is_invalidated = 1 AND invalidation_reason = ?
                ORDER BY invalidated_at DESC
                """,
                (reason,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """
                SELECT * FROM page_invalidation
                WHERE is_invalidated = 1
                ORDER BY invalidated_at DESC
                """,
            ).fetchall()
        return [
            {
                **dict(row),
                "changed_files": json.loads(row["changed_files_json"]),
                "impacted_modules": json.loads(row["impacted_modules_json"]),
            }
            for row in rows
        ]

    def clear_invalidations(self, doc_slug: str | None = None) -> None:
        """Clear invalidation records."""
        with self.conn:
            if doc_slug:
                self.conn.execute(
                    "DELETE FROM page_invalidation WHERE doc_slug = ?",
                    (doc_slug,),
                )
            else:
                self.conn.execute("DELETE FROM page_invalidation")

    # =========================================================================
    # Evidence Span Operations
    # =========================================================================

    def upsert_evidence_span(self, record: EvidenceSpanRecord) -> int:
        """Insert or update an evidence span record.

        Returns the evidence span id.
        """
        with self.conn:
            cursor = self.conn.execute(
                """
                INSERT INTO evidence_span(
                    digest, file_path, line_start, line_end, language,
                    symbol, span_text, confidence, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(digest) DO UPDATE SET
                    file_path=excluded.file_path,
                    line_start=excluded.line_start,
                    line_end=excluded.line_end,
                    language=excluded.language,
                    symbol=excluded.symbol,
                    span_text=excluded.span_text,
                    confidence=excluded.confidence
                """,
                (
                    record.digest,
                    record.file_path,
                    record.line_start,
                    record.line_end,
                    record.language,
                    record.symbol,
                    record.span_text,
                    record.confidence,
                    record.created_at or _now_iso(),
                ),
            )
            return cursor.lastrowid or self.conn.execute(
                "SELECT id FROM evidence_span WHERE digest = ?",
                (record.digest,),
            ).fetchone()["id"]

    def get_evidence_span(self, evidence_id: int) -> dict | None:
        """Get an evidence span by id."""
        row = self.conn.execute(
            "SELECT * FROM evidence_span WHERE id = ?",
            (evidence_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_evidence_span_by_digest(self, digest: str) -> dict | None:
        """Get an evidence span by digest."""
        row = self.conn.execute(
            "SELECT * FROM evidence_span WHERE digest = ?",
            (digest,),
        ).fetchone()
        return dict(row) if row else None

    def list_evidence_spans(
        self,
        file_path: str | None = None,
        language: str | None = None,
        symbol: str | None = None,
        limit: int = 100,
    ) -> List[dict]:
        """List evidence spans with optional filters."""
        where = ["1=1"]
        params: list[Any] = []
        if file_path:
            where.append("file_path = ?")
            params.append(file_path)
        if language:
            where.append("language = ?")
            params.append(language)
        if symbol:
            where.append("symbol = ?")
            params.append(symbol)
        params.append(limit)
        rows = self.conn.execute(
            f"""
            SELECT * FROM evidence_span
            WHERE {' AND '.join(where)}
            ORDER BY file_path, line_start
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def count_evidence_spans(self) -> int:
        """Count total evidence spans."""
        row = self.conn.execute("SELECT COUNT(*) AS c FROM evidence_span").fetchone()
        return int(row["c"])

    # =========================================================================
    # Page Source Map Operations
    # =========================================================================

    def map_evidence_to_page(
        self,
        doc_slug: str,
        doc_type: str,
        evidence_id: int,
        citation_order: int = 0,
        context_hint: str | None = None,
    ) -> None:
        """Map an evidence span to a wiki page."""
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO page_source_map(
                    doc_slug, doc_type, evidence_id, citation_order, context_hint, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (doc_slug, doc_type, evidence_id, citation_order, context_hint, _now_iso()),
            )

    def list_page_sources(self, doc_slug: str, doc_type: str) -> List[dict]:
        """List all evidence sources for a wiki page."""
        rows = self.conn.execute(
            """
            SELECT psm.*, es.file_path, es.line_start, es.line_end,
                   es.language, es.symbol, es.span_text, es.digest
            FROM page_source_map psm
            JOIN evidence_span es ON psm.evidence_id = es.id
            WHERE psm.doc_slug = ? AND psm.doc_type = ?
            ORDER BY psm.citation_order, es.file_path, es.line_start
            """,
            (doc_slug, doc_type),
        ).fetchall()
        return [dict(row) for row in rows]

    def list_pages_for_evidence(self, evidence_id: int) -> List[dict]:
        """List all pages that reference an evidence span."""
        rows = self.conn.execute(
            """
            SELECT psm.doc_slug, psm.doc_type, psm.citation_order, psm.context_hint
            FROM page_source_map psm
            WHERE psm.evidence_id = ?
            ORDER BY psm.doc_slug
            """,
            (evidence_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def unmap_evidence_from_page(self, doc_slug: str, doc_type: str, evidence_id: int) -> None:
        """Remove evidence-to-page mapping."""
        with self.conn:
            self.conn.execute(
                """
                DELETE FROM page_source_map
                WHERE doc_slug = ? AND doc_type = ? AND evidence_id = ?
                """,
                (doc_slug, doc_type, evidence_id),
            )

    def clear_page_sources(self, doc_slug: str, doc_type: str) -> None:
        """Clear all evidence mappings for a wiki page."""
        with self.conn:
            self.conn.execute(
                "DELETE FROM page_source_map WHERE doc_slug = ? AND doc_type = ?",
                (doc_slug, doc_type),
            )

    # =========================================================================
    # Symbol Reference Operations
    # =========================================================================

    def upsert_symbol_reference(self, record: SymbolReferenceRecord) -> int:
        """Insert or update a symbol reference record.

        Returns the symbol reference id.
        """
        with self.conn:
            cursor = self.conn.execute(
                """
                INSERT INTO symbol_reference(
                    source_file_path, source_line_start, source_line_end,
                    source_symbol, target_symbol, target_file_path,
                    target_line_start, target_line_end, ref_type,
                    confidence, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.source_file_path,
                    record.source_line_start,
                    record.source_line_end,
                    record.source_symbol,
                    record.target_symbol,
                    record.target_file_path,
                    record.target_line_start,
                    record.target_line_end,
                    record.ref_type,
                    record.confidence,
                    record.created_at or _now_iso(),
                ),
            )
            return cursor.lastrowid

    def list_symbol_references(
        self,
        target_symbol: str | None = None,
        ref_type: str | None = None,
        source_file_path: str | None = None,
        limit: int = 100,
    ) -> List[dict]:
        """List symbol references with optional filters."""
        where = ["1=1"]
        params: list[Any] = []
        if target_symbol:
            where.append("target_symbol = ?")
            params.append(target_symbol)
        if ref_type:
            where.append("ref_type = ?")
            params.append(ref_type)
        if source_file_path:
            where.append("source_file_path = ?")
            params.append(source_file_path)
        params.append(limit)
        rows = self.conn.execute(
            f"""
            SELECT * FROM symbol_reference
            WHERE {' AND '.join(where)}
            ORDER BY source_file_path, source_line_start
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def get_symbol_targets(self, source_file_path: str, source_line: int) -> List[dict]:
        """Get all target symbols referenced from a given source location."""
        rows = self.conn.execute(
            """
            SELECT * FROM symbol_reference
            WHERE source_file_path = ?
              AND source_line_start <= ?
              AND source_line_end >= ?
            ORDER BY source_line_start
            """,
            (source_file_path, source_line, source_line),
        ).fetchall()
        return [dict(row) for row in rows]

    def count_symbol_references(self) -> int:
        """Count total symbol references."""
        row = self.conn.execute("SELECT COUNT(*) AS c FROM symbol_reference").fetchone()
        return int(row["c"])

    # =========================================================================
    # Integrity Checks
    # =========================================================================

    def check_orphaned_docs(self) -> list[dict]:
        """Find documents that reference non-existent targets."""
        # Check for section pages that don't exist on disk
        orphaned = []
        rows = self.conn.execute(
            """
            SELECT doc_slug, doc_path, doc_type
            FROM doc_hierarchy
            WHERE doc_type = 'section'
            """
        ).fetchall()
        for row in rows:
            doc_path = Path(row["doc_path"])
            if not doc_path.exists():
                orphaned.append({
                    "doc_slug": row["doc_slug"],
                    "doc_path": row["doc_path"],
                    "issue": "section_page_missing",
                })
        return orphaned

    def check_broken_section_mappings(self) -> list[dict]:
        """Find section aliases that don't resolve to active sections."""
        broken = []
        rows = self.conn.execute(
            """
            SELECT sa.alias_slug, sa.canonical_slug, sr.canonical_slug as resolved
            FROM section_aliases sa
            LEFT JOIN section_registry sr ON sa.canonical_slug = sr.canonical_slug AND sr.is_active = 1
            WHERE sr.canonical_slug IS NULL
            """
        ).fetchall()
        for row in rows:
            broken.append({
                "alias_slug": row["alias_slug"],
                "canonical_slug": row["canonical_slug"],
                "issue": "alias_not_resolved",
            })
        return broken

    def check_stale_evidence(self, max_age_days: int = 30) -> list[dict]:
        """Find verify/compare runs older than max_age_days."""
        stale = []
        cutoff = datetime.fromtimestamp(time.time() - max_age_days * 86400, tz=UTC).isoformat()

        verify_rows = self.conn.execute(
            """
            SELECT run_id, target_path, created_at
            FROM verify_run_details
            WHERE created_at < ?
            """,
            (cutoff,),
        ).fetchall()
        for row in verify_rows:
            stale.append({
                "run_id": row["run_id"],
                "target_path": row["target_path"],
                "type": "verify_run",
                "created_at": row["created_at"],
                "issue": "evidence_stale",
            })

        compare_rows = self.conn.execute(
            """
            SELECT run_id, target_path, created_at
            FROM compare_run_details
            WHERE created_at < ?
            """,
            (cutoff,),
        ).fetchall()
        for row in compare_rows:
            stale.append({
                "run_id": row["run_id"],
                "target_path": row["target_path"],
                "type": "compare_run",
                "created_at": row["created_at"],
                "issue": "evidence_stale",
            })

        return stale

    # =========================================================================
    # Export and Rebuild
    # =========================================================================

    def export_runtime_artifacts(self, output_dir: str | Path) -> dict[str, Path]:
        """Export runtime metadata as JSON artifacts."""
        target = Path(output_dir)
        target.mkdir(parents=True, exist_ok=True)

        # Export doc hierarchy
        docs = self.conn.execute(
            "SELECT * FROM doc_hierarchy ORDER BY doc_type, sort_order"
        ).fetchall()
        docs_path = target / "doc_hierarchy.json"
        docs_path.write_text(
            json.dumps([dict(row) for row in docs], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Export section registry
        sections = self.conn.execute(
            "SELECT * FROM section_registry WHERE is_active = 1 ORDER BY sort_order"
        ).fetchall()
        sections_path = target / "section_registry.json"
        sections_path.write_text(
            json.dumps([dict(row) for row in sections], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Export nav graph
        nav_nodes = self.conn.execute(
            "SELECT * FROM nav_graph ORDER BY doc_type, depth"
        ).fetchall()
        nav_path = target / "nav_graph.json"
        nav_path.write_text(
            json.dumps([dict(row) for row in nav_nodes], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return {
            "doc_hierarchy.json": docs_path,
            "section_registry.json": sections_path,
            "nav_graph.json": nav_path,
        }

    def rebuild_from_artifacts(self, artifacts_dir: Path) -> int:
        """Rebuild runtime store from exported artifacts.

        Returns the number of records imported.
        """
        count = 0

        # Rebuild doc hierarchy
        docs_path = artifacts_dir / "doc_hierarchy.json"
        if docs_path.exists():
            docs_data = json.loads(docs_path.read_text(encoding="utf-8"))
            for doc in docs_data:
                record = DocHierarchyRecord(
                    doc_type=doc["doc_type"],
                    doc_slug=doc["doc_slug"],
                    doc_path=doc["doc_path"],
                    layer=doc["layer"],
                    parent_slug=doc.get("parent_slug"),
                    title=doc.get("title"),
                    sort_order=doc.get("sort_order", 0),
                    generation_input_hash=doc.get("generation_input_hash"),
                    generation_output_hash=doc.get("generation_output_hash"),
                    generated_at=doc.get("generated_at"),
                    updated_at=doc.get("updated_at"),
                )
                self.upsert_doc_hierarchy(record)
                count += 1

        # Rebuild section registry
        sections_path = artifacts_dir / "section_registry.json"
        if sections_path.exists():
            sections_data = json.loads(sections_path.read_text(encoding="utf-8"))
            for section in sections_data:
                record = SectionRegistryRecord(
                    canonical_slug=section["canonical_slug"],
                    title=section["title"],
                    description=section.get("description"),
                    required_for_phase=section.get("required_for_phase"),
                    sort_order=section.get("sort_order", 0),
                    is_active=section.get("is_active", True),
                )
                self.register_section(record)
                count += 1

        # Rebuild nav graph
        nav_path = artifacts_dir / "nav_graph.json"
        if nav_path.exists():
            nav_data = json.loads(nav_path.read_text(encoding="utf-8"))
            for node in nav_data:
                self.upsert_nav_node(
                    doc_slug=node["doc_slug"],
                    doc_type=node["doc_type"],
                    incoming_links=json.loads(node["incoming_links_json"]),
                    outgoing_links=json.loads(node["outgoing_links_json"]),
                    depth=node.get("depth", 0),
                    affected_pages=json.loads(node["affected_pages_json"]),
                )
                count += 1

        return count


# =============================================================================
# Runtime Store Factory
# =============================================================================

def create_runtime_store(root: Path) -> SQLiteRuntimeStore:
    """Create a runtime store at the standard location within a repo.

    Standard location: .repo-wiki/index/runtime.sqlite3
    """
    runtime_path = root / ".repo-wiki" / "index" / "runtime.sqlite3"
    return SQLiteRuntimeStore(runtime_path)