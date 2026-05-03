"""Page composer incremental cache for avoiding repeated LLM calls.

Computes input hashes from:
- Page plan (WikiPagePlan)
- Evidence binding (PageEvidenceBinding) and source digests
- Prompt contract
- Skeleton
- Model config

Phase 24 - Task 24.6: Page composer incremental cache

Key features:
- Computes deterministic input hash from composer inputs
- Avoids repeated LLM calls for unchanged pages
- Persists token/cost and output hashes per page
- Integrates with SQLiteRuntimeStore for cache storage
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from repo_wiki.evidence.ranking import PageEvidenceBinding
from repo_wiki.generator.composer import (
    ArticleSkeleton,
    ComposerContext,
    ComposerInput,
)
from repo_wiki.planner.schema import WikiPagePlan


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _now_epoch() -> float:
    return time.time()


# =============================================================================
# COMPOSER CACHE RECORD
# =============================================================================


@dataclass
class ComposerCacheRecord:
    """A cache record for page composition."""

    page_id: str
    doc_type: str
    input_hash: str
    output_hash: str | None = None
    model_name: str = "mock-gpt"
    tokens_used: int = 0
    cost_usd: float = 0.0
    cached_at: str | None = None
    output_markdown: str | None = None


@dataclass
class ComposerCacheStats:
    """Statistics for composer cache."""

    total_entries: int
    cache_hits: int
    cache_misses: int
    total_tokens_saved: int
    total_cost_saved_usd: float


# =============================================================================
# INPUT HASH COMPUTATION
# =============================================================================


def compute_page_plan_hash(page: WikiPagePlan) -> str:
    """Compute deterministic hash from WikiPagePlan.

    Includes: page_id, title, category, parent, output_path,
    source_requirements, generation_mode, sort_order, tags.
    """
    parts = [
        page.page_id,
        page.title,
        page.category.value,
        page.parent or "",
        page.output_path,
        page.generation_mode.value,
        str(page.sort_order),
    ]

    # Source requirements
    sr = page.source_requirements
    if sr:
        parts.extend(
            [
                ",".join(sorted(sr.modules)),
                ",".join(sorted(sr.endpoints)),
                ",".join(sorted(sr.data_models)),
                ",".join(sorted(sr.commands)),
                ",".join(sorted(sr.files)),
            ]
        )

    # Tags
    parts.append(",".join(sorted(page.tags)))

    content = "|".join(parts)
    return hashlib.sha256(content.encode()).hexdigest()[:24]


def compute_evidence_hash(binding: PageEvidenceBinding | None) -> str:
    """Compute deterministic hash from evidence binding.

    Includes: evidence candidate digests, citation order.
    """
    if binding is None:
        return hashlib.sha256(b"no-evidence").hexdigest()[:24]

    parts = [binding.page_id, binding.doc_type]

    for candidate in sorted(binding.candidates, key=lambda c: c.citation_order):
        span = candidate.span
        # Use digest as the primary identifier for deduplication
        digest = (
            getattr(span, "digest", None)
            or hashlib.sha256(
                f"{span.file_path}:{span.line_start}-{span.line_end}".encode()
            ).hexdigest()[:24]
        )
        parts.append(f"{digest}:{candidate.citation_order}")

    content = "|".join(parts)
    return hashlib.sha256(content.encode()).hexdigest()[:24]


def compute_skeleton_hash(skeleton: ArticleSkeleton) -> str:
    """Compute deterministic hash from article skeleton."""
    # Serialize skeleton toc_entries and headings for deterministic output
    toc_data = []
    if skeleton.toc_entries:
        for entry in skeleton.toc_entries:
            toc_data.append({"text": entry})

    # Also include headings for completeness
    headings_data = []
    if skeleton.headings:
        for h in skeleton.headings:
            headings_data.append(
                {
                    "key": h.key,
                    "level": h.level,
                    "required": h.required,
                }
            )

    data = {
        "page_type": skeleton.page_type,
        "title": skeleton.title,
        "toc": toc_data,
        "headings": headings_data,
    }

    content = json.dumps(data, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()[:24]


def compute_context_hash(context: ComposerContext) -> str:
    """Compute deterministic hash from composer context.

    Includes: repository_name, primary_language, framework,
    modules, endpoints, models, commands.
    """
    parts = [
        context.repository_name,
        context.primary_language,
        context.framework,
        context.repository_root,
    ]

    # Sort modules by name for deterministic ordering
    modules = sorted(context.modules, key=lambda m: m.get("name", ""))
    parts.append(json.dumps(modules, sort_keys=True))

    endpoints = sorted(context.endpoints, key=lambda e: e.get("path", ""))
    parts.append(json.dumps(endpoints, sort_keys=True))

    models = sorted(context.models, key=lambda m: m.get("name", ""))
    parts.append(json.dumps(models, sort_keys=True))

    commands = json.dumps(dict(sorted(context.commands.items())), sort_keys=True)
    parts.append(commands)

    content = "|".join(parts)
    return hashlib.sha256(content.encode()).hexdigest()[:24]


def compute_composer_input_hash(
    input_data: ComposerInput,
    model_name: str = "mock-gpt",
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    """Compute overall input hash for ComposerInput.

    Combines hashes of:
    - Page plan
    - Evidence binding
    - Skeleton
    - Context
    - Model name (as config identifier)
    - Temperature
    - Max tokens

    This hash uniquely identifies the composition input and can be used
    to determine if a page needs regeneration.
    """
    page_hash = compute_page_plan_hash(input_data.page_plan)
    evidence_hash = compute_evidence_hash(input_data.evidence_binding)
    skeleton_hash = compute_skeleton_hash(input_data.skeleton)
    context_hash = compute_context_hash(input_data.context)

    # Combine all hashes
    combined = "|".join(
        [
            page_hash,
            evidence_hash,
            skeleton_hash,
            context_hash,
            model_name,
            str(temperature),
            str(max_tokens),
        ]
    )

    return hashlib.sha256(combined.encode()).hexdigest()[:32]


def compute_output_hash(markdown: str) -> str:
    """Compute hash from composed markdown output."""
    return hashlib.sha256(markdown.encode()).hexdigest()[:24]


def estimate_tokens_from_markdown(markdown: str) -> int:
    """Estimate token count from markdown content.

    Uses a rough approximation: 1 token ≈ 4 characters.
    """
    return len(markdown) // 4


def estimate_cost_from_tokens(
    tokens: int,
    model_name: str = "mock-gpt",
) -> float:
    """Estimate cost in USD from token count.

    Uses approximate pricing:
    - mock-gpt: $0.00 (free for testing)
    - gpt-4o: $0.005 per 1K input tokens, $0.015 per 1K output tokens
    - gpt-4o-mini: $0.00015 per 1K input, $0.0006 per 1K output
    """
    pricing = {
        "mock-gpt": 0.0,
        "gpt-4o": 0.005 / 1000,  # Input only (output ~3x)
        "gpt-4o-mini": 0.00015 / 1000,
    }

    rate = pricing.get(model_name, 0.001 / 1000)
    return tokens * rate


# =============================================================================
# COMPOSER CACHE
# =============================================================================


class ComposerCache:
    """Incremental cache for page composition.

    Avoids repeated LLM calls by caching results based on input hashes.
    Stores token/cost and output hashes per page.

    Usage:
        cache = ComposerCache(sqlite_path)

        # Check if page is cached
        record = cache.get(page_id, input_hash)
        if record and record.output_markdown:
            return record.output_markdown, record.tokens_used

        # Compose page (call LLM)...

        # Store result
        cache.put(
            page_id=page_id,
            input_hash=input_hash,
            output_markdown=markdown,
            tokens_used=tokens,
            model_name="gpt-4o",
        )
    """

    def __init__(self, sqlite_path: str | Path) -> None:
        self.sqlite_path = Path(sqlite_path)
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._stats = {"hits": 0, "misses": 0}

    def _init_db(self) -> None:
        """Initialize cache database schema."""
        conn = sqlite3.connect(str(self.sqlite_path))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS composer_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    page_id TEXT NOT NULL,
                    doc_type TEXT NOT NULL,
                    input_hash TEXT NOT NULL,
                    output_hash TEXT,
                    model_name TEXT NOT NULL DEFAULT 'mock-gpt',
                    tokens_used INTEGER DEFAULT 0,
                    cost_usd REAL DEFAULT 0.0,
                    output_markdown TEXT,
                    cached_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(page_id, input_hash)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_composer_cache_page
                ON composer_cache(page_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_composer_cache_input_hash
                ON composer_cache(input_hash)
            """)
            conn.commit()
        finally:
            conn.close()

    def get(
        self,
        page_id: str,
        input_hash: str | None = None,
    ) -> ComposerCacheRecord | None:
        """Get cached composition for a page.

        If input_hash is provided, retrieves the specific cached result.
        If input_hash is None, retrieves the most recent cache entry for the page.

        Args:
            page_id: The page identifier
            input_hash: Optional input hash to match

        Returns:
            ComposerCacheRecord if found, None otherwise
        """
        conn = sqlite3.connect(str(self.sqlite_path))
        conn.row_factory = sqlite3.Row
        try:
            if input_hash:
                row = conn.execute(
                    """
                    SELECT * FROM composer_cache
                    WHERE page_id = ? AND input_hash = ?
                    ORDER BY cached_at DESC
                    LIMIT 1
                    """,
                    (page_id, input_hash),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT * FROM composer_cache
                    WHERE page_id = ?
                    ORDER BY cached_at DESC
                    LIMIT 1
                    """,
                    (page_id,),
                ).fetchone()

            if row is None:
                self._stats["misses"] += 1
                return None

            self._stats["hits"] += 1
            return ComposerCacheRecord(
                page_id=row["page_id"],
                doc_type=row["doc_type"],
                input_hash=row["input_hash"],
                output_hash=row["output_hash"],
                model_name=row["model_name"],
                tokens_used=row["tokens_used"],
                cost_usd=row["cost_usd"],
                cached_at=row["cached_at"],
                output_markdown=row["output_markdown"],
            )
        finally:
            conn.close()

    def put(
        self,
        page_id: str,
        input_hash: str,
        output_markdown: str,
        tokens_used: int,
        model_name: str = "mock-gpt",
        doc_type: str | None = None,
        cost_usd: float | None = None,
    ) -> None:
        """Store composition result in cache.

        Args:
            page_id: The page identifier
            input_hash: Hash of the input that produced this output
            output_markdown: The composed markdown output
            tokens_used: Number of tokens consumed
            model_name: LLM model used
            doc_type: Document type (e.g., 'overview', 'section')
            cost_usd: Cost in USD (computed if not provided)
        """
        if cost_usd is None:
            cost_usd = estimate_cost_from_tokens(tokens_used, model_name)

        output_hash = compute_output_hash(output_markdown)
        now = _now_iso()

        conn = sqlite3.connect(str(self.sqlite_path))
        try:
            conn.execute(
                """
                INSERT INTO composer_cache(
                    page_id, doc_type, input_hash, output_hash,
                    model_name, tokens_used, cost_usd, output_markdown,
                    cached_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(page_id, input_hash) DO UPDATE SET
                    output_hash=excluded.output_hash,
                    model_name=excluded.model_name,
                    tokens_used=excluded.tokens_used,
                    cost_usd=excluded.cost_usd,
                    output_markdown=excluded.output_markdown,
                    updated_at=excluded.updated_at
                """,
                (
                    page_id,
                    doc_type or "page",
                    input_hash,
                    output_hash,
                    model_name,
                    tokens_used,
                    cost_usd,
                    output_markdown,
                    now,
                    now,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def invalidate(self, page_id: str) -> int:
        """Invalidate all cache entries for a page.

        Args:
            page_id: The page to invalidate

        Returns:
            Number of entries invalidated
        """
        conn = sqlite3.connect(str(self.sqlite_path))
        try:
            cursor = conn.execute(
                "DELETE FROM composer_cache WHERE page_id = ?",
                (page_id,),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def invalidate_by_hash(self, page_id: str, input_hash: str) -> int:
        """Invalidate specific cache entry by page_id and input_hash.

        Args:
            page_id: The page identifier
            input_hash: The input hash to invalidate

        Returns:
            Number of entries invalidated (0 or 1)
        """
        conn = sqlite3.connect(str(self.sqlite_path))
        try:
            cursor = conn.execute(
                "DELETE FROM composer_cache WHERE page_id = ? AND input_hash = ?",
                (page_id, input_hash),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def clear(self) -> None:
        """Clear all cache entries."""
        conn = sqlite3.connect(str(self.sqlite_path))
        try:
            conn.execute("DELETE FROM composer_cache")
            conn.commit()
            self._stats = {"hits": 0, "misses": 0}
        finally:
            conn.close()

    def stats(self) -> ComposerCacheStats:
        """Get cache statistics.

        Returns:
            ComposerCacheStats with hit/miss counts and savings
        """
        conn = sqlite3.connect(str(self.sqlite_path))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT COUNT(*) as total, SUM(tokens_used) as tokens, SUM(cost_usd) as cost FROM composer_cache"
            ).fetchone()

            total = row["total"] if row else 0
            total_tokens = row["tokens"] if row and row["tokens"] else 0
            total_cost = row["cost"] if row and row["cost"] else 0.0

            return ComposerCacheStats(
                total_entries=total,
                cache_hits=self._stats["hits"],
                cache_misses=self._stats["misses"],
                total_tokens_saved=total_tokens,
                total_cost_saved_usd=total_cost,
            )
        finally:
            conn.close()

    def list_entries(
        self,
        page_id: str | None = None,
        limit: int = 100,
    ) -> list[ComposerCacheRecord]:
        """List cache entries, optionally filtered by page_id.

        Args:
            page_id: Optional page_id filter
            limit: Maximum number of entries to return

        Returns:
            List of ComposerCacheRecord
        """
        conn = sqlite3.connect(str(self.sqlite_path))
        conn.row_factory = sqlite3.Row
        try:
            if page_id:
                rows = conn.execute(
                    """
                    SELECT * FROM composer_cache
                    WHERE page_id = ?
                    ORDER BY cached_at DESC
                    LIMIT ?
                    """,
                    (page_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM composer_cache
                    ORDER BY cached_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

            return [
                ComposerCacheRecord(
                    page_id=row["page_id"],
                    doc_type=row["doc_type"],
                    input_hash=row["input_hash"],
                    output_hash=row["output_hash"],
                    model_name=row["model_name"],
                    tokens_used=row["tokens_used"],
                    cost_usd=row["cost_usd"],
                    cached_at=row["cached_at"],
                    output_markdown=row["output_markdown"],
                )
                for row in rows
            ]
        finally:
            conn.close()

    def get_for_page(
        self,
        page_id: str,
        input_hash: str,
    ) -> tuple[str | None, int]:
        """Get cached output and tokens for a page with input hash.

        Convenience method that returns just the output and token count.

        Args:
            page_id: The page identifier
            input_hash: Hash of the composition input

        Returns:
            Tuple of (output_markdown, tokens_used) or (None, 0) if not cached
        """
        record = self.get(page_id, input_hash)
        if record and record.output_markdown:
            return record.output_markdown, record.tokens_used
        return None, 0


# =============================================================================
# COMPOSER CACHE INTEGRATION
# =============================================================================


def create_composer_cache(
    root: Path,
    filename: str = "composer_cache.sqlite3",
) -> ComposerCache:
    """Create a composer cache at the standard location within a repo.

    Standard location: .repo-wiki/index/cache/composer_cache.sqlite3

    Args:
        root: Repository root path
        filename: Cache filename

    Returns:
        ComposerCache instance
    """
    cache_path = root / ".repo-wiki" / "index" / "cache" / filename
    return ComposerCache(cache_path)


class CachedComposerMixin:
    """Mixin for LLMPageComposer that adds caching capability.

    Use with LLMPageComposer to enable incremental cache.
    """

    def __init__(
        self,
        cache: ComposerCache | None = None,
        cache_enabled: bool = True,
        **kwargs: Any,
    ) -> None:
        """Initialize cached composer.

        Args:
            cache: ComposerCache instance
            cache_enabled: Whether caching is enabled
            **kwargs: Additional arguments for LLMPageComposer
        """
        self._cache = cache
        self._cache_enabled = cache_enabled

    def _get_cache(self) -> ComposerCache | None:
        """Get the cache instance."""
        return self._cache if self._cache_enabled else None

    def _compute_input_hash(self, input_data: ComposerInput) -> str:
        """Compute input hash for caching."""
        return compute_composer_input_hash(input_data)

    def _check_cache(
        self,
        page_id: str,
        input_hash: str,
    ) -> tuple[str | None, int]:
        """Check cache for existing composition.

        Returns (markdown, tokens) if cached, (None, 0) otherwise.
        """
        cache = self._get_cache()
        if cache is None:
            return None, 0

        return cache.get_for_page(page_id, input_hash)

    def _store_cache(
        self,
        page_id: str,
        input_hash: str,
        markdown: str,
        tokens: int,
        model_name: str = "mock-gpt",
        doc_type: str | None = None,
    ) -> None:
        """Store composition result in cache."""
        cache = self._get_cache()
        if cache is None:
            return

        cache.put(
            page_id=page_id,
            input_hash=input_hash,
            output_markdown=markdown,
            tokens_used=tokens,
            model_name=model_name,
            doc_type=doc_type,
        )


# =============================================================================
# UTILITIES
# =============================================================================


def format_cache_stats(stats: ComposerCacheStats) -> str:
    """Format cache statistics as a human-readable string.

    Args:
        stats: ComposerCacheStats to format

    Returns:
        Formatted string
    """
    hit_rate = 0.0
    total_requests = stats.cache_hits + stats.cache_misses
    if total_requests > 0:
        hit_rate = stats.cache_hits / total_requests * 100

    return f"""Composer Cache Statistics:
  Total entries: {stats.total_entries}
  Cache hits: {stats.cache_hits}
  Cache misses: {stats.cache_misses}
  Hit rate: {hit_rate:.1f}%
  Tokens saved: {stats.total_tokens_saved}
  Cost saved: ${stats.total_cost_saved_usd:.6f}"""


def compare_input_hashes(
    cached_hash: str,
    current_hash: str,
) -> bool:
    """Compare two input hashes to determine if composition is needed.

    Args:
        cached_hash: Previously computed input hash
        current_hash: Current input hash

    Returns:
        True if hashes match (page unchanged, use cache),
        False if different (needs regeneration)
    """
    return cached_hash == current_hash
