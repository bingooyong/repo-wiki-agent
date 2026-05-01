"""SQLite-driven page invalidation and incremental regeneration planner.

This module implements evidence-aware page invalidation and incremental
regeneration based on the runtime store's nav graph and document hierarchy.

Key concepts:
- Page granularity invalidation based on changed files and section registry updates
- Evidence-aware dependency rules: verify/compare evidence determines which pages need refresh
- Incremental regeneration preferred over full rebuild when scope is bounded
- Full rebuild available for unbounded changes or corrupted state
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from repo_wiki.generator.contracts import SECTION_DEFINITIONS, get_canonical_slug, is_known_section_slug
from repo_wiki.indexer.state_store import SQLiteStateStore
from repo_wiki.retrieval.service import IncrementalImpact, RetrievalService

if TYPE_CHECKING:
    from repo_wiki.orchestration.runtime_store import SQLiteRuntimeStore


@dataclass
class InvalidationResult:
    """Result of a page invalidation operation."""
    invalidated_pages: list[str]
    skipped_pages: list[str]
    regeneration_plan: list[str]
    reason: str
    changed_files: list[str]
    impacted_modules: list[str]
    is_full_rebuild: bool = False


@dataclass
class RegenerationTask:
    """A single regeneration task for a page."""
    doc_slug: str
    doc_type: str
    priority: int  # 1=high, 2=medium, 3=low
    reason: str
    dependencies: list[str]  # other doc_slugs that must be regenerated first


class PageInvalidationEngine:
    """SQLite-driven page invalidation and incremental regeneration planner.

    Uses the runtime store's nav graph to determine which pages are affected
    by changed files, section registry updates, or stale evidence.

    Invalidation reasons:
    - file_changed: Source files changed that affect this page
    - section_updated: Section content or structure changed
    - nav_broken: Navigation links broken or updated
    - evidence_stale: Verify/compare evidence indicates content may be outdated
    - section_registry_changed: New section or alias registered
    """

    def __init__(
        self,
        root: Path,
        state_store: SQLiteStateStore,
        runtime_store: "SQLiteRuntimeStore",
        retrieval_service: RetrievalService | None = None,
    ) -> None:
        self.root = root
        self.state_store = state_store
        self.runtime_store = runtime_store
        self.retrieval_service = retrieval_service

    def invalidate_from_changes(
        self,
        changed_files: list[str],
        deleted_files: list[str],
        renamed_files: dict[str, str],
        reason: str = "file_changed",
    ) -> InvalidationResult:
        """Invalidate pages based on changed files.

        Uses the nav graph to determine which pages depend on changed files.
        """
        if not changed_files and not deleted_files and not renamed_files:
            return InvalidationResult(
                invalidated_pages=[],
                skipped_pages=[],
                regeneration_plan=[],
                reason=reason,
                changed_files=[],
                impacted_modules=[],
            )

        # Map changed files to impacted modules
        impacted_modules = self._map_files_to_modules(changed_files + deleted_files + list(renamed_files.keys()))

        # Check for global regeneration triggers
        is_full_rebuild = self._needs_full_rebuild(changed_files, deleted_files, renamed_files)

        if is_full_rebuild:
            return self._create_full_rebuild_invalidation(reason, changed_files, impacted_modules)

        # Find all pages that depend on changed files via nav graph
        invalidated = set()
        skipped = set()

        for changed_file in changed_files + deleted_files + list(renamed_files.keys()):
            # Get doc_slugs that have this file in their affected_pages
            affected_pages = self._get_affected_pages_for_file(changed_file)
            invalidated.update(affected_pages)

        # Also invalidate pages for impacted modules
        for module in impacted_modules:
            module_pages = self._get_pages_for_module(module)
            invalidated.update(module_pages)

        # Get regeneration plan with proper ordering
        plan = self._compute_regeneration_plan(list(invalidated))

        # Save invalidation records
        for doc_slug in invalidated:
            doc_type = self._get_doc_type(doc_slug)
            self.runtime_store.invalidate_page(
                doc_slug=doc_slug,
                doc_type=doc_type,
                reason=reason,
                changed_files=changed_files,
                impacted_modules=impacted_modules,
            )

        return InvalidationResult(
            invalidated_pages=sorted(invalidated),
            skipped_pages=sorted(skipped),
            regeneration_plan=plan,
            reason=reason,
            changed_files=changed_files,
            impacted_modules=impacted_modules,
            is_full_rebuild=False,
        )

    def invalidate_from_section_change(
        self,
        section_slug: str,
        reason: str = "section_updated",
    ) -> InvalidationResult:
        """Invalidate pages when a section is updated."""
        # Get canonical slug
        canonical = get_canonical_slug(section_slug)
        if not canonical:
            canonical = section_slug

        # Find all docs that reference this section
        invalidated = set()

        # Section pages for this section
        invalidated.add(canonical)

        # Overview pages that link to this section
        nav_node = self.runtime_store.get_nav_node(canonical)
        if nav_node:
            # Pages that link TO this section (incoming)
            incoming = json.loads(nav_node.get("incoming_links_json", "[]"))
            invalidated.update(incoming)

        # Pages that this section links to (outgoing)
        if nav_node:
            outgoing = json.loads(nav_node.get("outgoing_links_json", "[]"))
            invalidated.update(outgoing)

        # Module pages that belong to this section
        section_docs = self.runtime_store.list_docs_by_type("section")
        for doc in section_docs:
            if doc.get("parent_slug") == canonical:
                invalidated.add(doc["doc_slug"])

        plan = self._compute_regeneration_plan(list(invalidated))

        # Save invalidation records
        for doc_slug in invalidated:
            doc_type = self._get_doc_type(doc_slug)
            self.runtime_store.invalidate_page(
                doc_slug=doc_slug,
                doc_type=doc_type,
                reason=reason,
                changed_files=[f"docs/sections/{canonical}/index.md"],
                impacted_modules=[],
            )

        return InvalidationResult(
            invalidated_pages=sorted(invalidated),
            skipped_pages=[],
            regeneration_plan=plan,
            reason=reason,
            changed_files=[f"docs/sections/{canonical}/index.md"],
            impacted_modules=[],
        )

    def invalidate_from_nav_broken(
        self,
        source_doc_slug: str,
        broken_target_slug: str,
        reason: str = "nav_broken",
    ) -> InvalidationResult:
        """Invalidate pages when navigation is broken."""
        invalidated = {source_doc_slug}

        # Also invalidate the target if it's missing
        target_path = self._resolve_doc_path(broken_target_slug)
        if not target_path.exists():
            invalidated.add(broken_target_slug)

        plan = self._compute_regeneration_plan(list(invalidated))

        for doc_slug in invalidated:
            doc_type = self._get_doc_type(doc_slug)
            self.runtime_store.invalidate_page(
                doc_slug=doc_slug,
                doc_type=doc_type,
                reason=reason,
                changed_files=[],
                impacted_modules=[],
            )

        return InvalidationResult(
            invalidated_pages=sorted(invalidated),
            skipped_pages=[],
            regeneration_plan=plan,
            reason=reason,
            changed_files=[],
            impacted_modules=[],
        )

    def invalidate_from_evidence_stale(
        self,
        target_path: str,
        reason: str = "evidence_stale",
    ) -> InvalidationResult:
        """Invalidate pages when verify/compare evidence indicates staleness."""
        # Get all docs for this target
        docs = self.runtime_store.list_docs_by_layer("overview")
        invalidated = {doc["doc_slug"] for doc in docs}

        # Also invalidate section pages
        section_docs = self.runtime_store.list_docs_by_type("section")
        invalidated.update(doc["doc_slug"] for doc in section_docs)

        plan = self._compute_regeneration_plan(list(invalidated))

        for doc_slug in invalidated:
            doc_type = self._get_doc_type(doc_slug)
            self.runtime_store.invalidate_page(
                doc_slug=doc_slug,
                doc_type=doc_type,
                reason=reason,
                changed_files=[],
                impacted_modules=[],
            )

        return InvalidationResult(
            invalidated_pages=sorted(invalidated),
            skipped_pages=[],
            regeneration_plan=plan,
            reason=reason,
            changed_files=[],
            impacted_modules=[],
        )

    def invalidate_from_section_registry_change(
        self,
        change_type: str,  # 'added', 'removed', 'alias_added'
        section_slug: str,
        reason: str = "section_registry_changed",
    ) -> InvalidationResult:
        """Invalidate pages when section registry is updated."""
        invalidated = set()

        if change_type == "added":
            # New section added - invalidate overview pages (they need to add link)
            overview_docs = self.runtime_store.list_docs_by_type("overview")
            invalidated.update(doc["doc_slug"] for doc in overview_docs)

            # Invalidate all section pages (nav graph may need update)
            section_docs = self.runtime_store.list_docs_by_type("section")
            invalidated.update(doc["doc_slug"] for doc in section_docs)

        elif change_type == "removed":
            # Section removed - invalidate all pages (major restructuring)
            all_docs = self.runtime_store.list_docs_by_layer("overview")
            invalidated.update(doc["doc_slug"] for doc in all_docs)
            section_docs = self.runtime_store.list_docs_by_type("section")
            invalidated.update(doc["doc_slug"] for doc in section_docs)
            module_docs = self.runtime_store.list_docs_by_type("module")
            invalidated.update(doc["doc_slug"] for doc in module_docs)

        elif change_type == "alias_added":
            # Alias added - invalidate section page and overview
            canonical = get_canonical_slug(section_slug)
            if canonical:
                invalidated.add(canonical)
            invalidated.add("00-overview")

        plan = self._compute_regeneration_plan(list(invalidated))

        for doc_slug in invalidated:
            doc_type = self._get_doc_type(doc_slug)
            self.runtime_store.invalidate_page(
                doc_slug=doc_slug,
                doc_type=doc_type,
                reason=reason,
                changed_files=[f"ai/source-of-truth/"],
                impacted_modules=[],
            )

        return InvalidationResult(
            invalidated_pages=sorted(invalidated),
            skipped_pages=[],
            regeneration_plan=plan,
            reason=reason,
            changed_files=["ai/source-of-truth/"],
            impacted_modules=[],
            is_full_rebuild=(change_type == "removed"),
        )

    def plan_regeneration(self, invalidation: InvalidationResult) -> list[RegenerationTask]:
        """Plan regeneration tasks with proper dependency ordering.

        Returns tasks sorted by priority (dependencies must be regenerated first).
        """
        tasks = []
        for doc_slug in invalidation.regeneration_plan:
            doc_type = self._get_doc_type(doc_slug)
            priority = self._get_regeneration_priority(doc_type, doc_slug)
            dependencies = self._get_regeneration_dependencies(doc_slug)

            tasks.append(RegenerationTask(
                doc_slug=doc_slug,
                doc_type=doc_type,
                priority=priority,
                reason=invalidation.reason,
                dependencies=dependencies,
            ))

        # Sort by priority (dependencies first, then priority order)
        tasks.sort(key=lambda t: (len(t.dependencies), t.priority, t.doc_slug))
        return tasks

    def execute_regeneration(
        self,
        tasks: list[RegenerationTask],
        generator_func=None,  # Function(doc_slug, doc_type) -> bool
    ) -> dict[str, bool]:
        """Execute regeneration tasks.

        Returns a dict of doc_slug -> success boolean.
        """
        results = {}
        completed = set()

        for task in tasks:
            # Check dependencies are complete
            deps_met = all(dep in completed for dep in task.dependencies)

            if not deps_met:
                # Wait for dependencies
                results[task.doc_slug] = False
                continue

            # Execute regeneration
            success = False
            if generator_func:
                success = generator_func(task.doc_slug, task.doc_type)
            else:
                # Placeholder - actual implementation would call generator
                success = True

            if success:
                completed.add(task.doc_slug)
                self.runtime_store.mark_page_regenerated(task.doc_slug, "completed")
            else:
                self.runtime_store.mark_page_regenerated(task.doc_slug, "failed")

            results[task.doc_slug] = success

        return results

    def _map_files_to_modules(self, files: list[str]) -> list[str]:
        """Map a list of files to module names."""
        if self.retrieval_service:
            modules = self.retrieval_service._map_files_to_modules(files, self.retrieval_service._load_module_index())
            return modules

        # Fallback: simple module extraction from path
        modules = set()
        for file_path in files:
            parts = Path(file_path).parts
            if parts:
                modules.add(parts[0])
        return sorted(modules)

    def _needs_full_rebuild(
        self,
        changed_files: list[str],
        deleted_files: list[str],
        renamed_files: dict[str, str],
    ) -> bool:
        """Check if changes require full rebuild."""
        global_triggers = {
            "pyproject.toml", "package.json", "go.mod",
            "Dockerfile", "Makefile", "repo-wiki.yaml", ".repo-wiki.yaml",
        }

        candidates = set(changed_files) | set(deleted_files) | set(renamed_files.keys()) | set(renamed_files.values())
        for path in candidates:
            if Path(path).name in global_triggers:
                return True
            if path.startswith("ai/source-of-truth/"):
                return True
            if path.startswith("docs/00-") or path.startswith("docs/01-"):
                return True  # Core overview docs changed

        # Check if more than 50% of files changed
        total_files = self.state_store._count("files")
        if total_files > 0 and len(candidates) > total_files * 0.5:
            return True

        return False

    def _create_full_rebuild_invalidation(
        self,
        reason: str,
        changed_files: list[str],
        impacted_modules: list[str],
    ) -> InvalidationResult:
        """Create invalidation for full rebuild scenario."""
        # Get all docs
        all_docs = []
        all_docs.extend(self.runtime_store.list_docs_by_layer("overview"))
        all_docs.extend(self.runtime_store.list_docs_by_type("section"))
        all_docs.extend(self.runtime_store.list_docs_by_type("module"))

        invalidated = [doc["doc_slug"] for doc in all_docs]
        plan = self._compute_regeneration_plan(invalidated)

        for doc_slug in invalidated:
            doc_type = self._get_doc_type(doc_slug)
            self.runtime_store.invalidate_page(
                doc_slug=doc_slug,
                doc_type=doc_type,
                reason=reason,
                changed_files=changed_files,
                impacted_modules=impacted_modules,
            )

        return InvalidationResult(
            invalidated_pages=invalidated,
            skipped_pages=[],
            regeneration_plan=plan,
            reason=reason,
            changed_files=changed_files,
            impacted_modules=impacted_modules,
            is_full_rebuild=True,
        )

    def _get_affected_pages_for_file(self, file_path: str) -> list[str]:
        """Get all doc_slugs that have this file in their affected_pages."""
        affected = []
        rows = self.state_store.conn.execute(
            """
            SELECT doc_slug FROM nav_graph
            WHERE affected_pages_json LIKE ?
            """,
            (f"%{file_path}%",),
        ).fetchall()
        for row in rows:
            affected.append(row["doc_slug"])
        return affected

    def _get_pages_for_module(self, module_name: str) -> list[str]:
        """Get all doc_slugs that belong to a module."""
        pages = []
        rows = self.state_store.conn.execute(
            """
            SELECT doc_slug FROM doc_hierarchy
            WHERE doc_slug LIKE ?
            """,
            (f"{module_name}%",),
        ).fetchall()
        for row in rows:
            pages.append(row["doc_slug"])
        return pages

    def _compute_regeneration_plan(self, doc_slugs: list[str]) -> list[str]:
        """Compute a topological ordering for regeneration.

        Pages with no dependencies come first, then pages that depend on them.
        """
        # Build dependency graph
        in_degree = {slug: 0 for slug in doc_slugs}
        dependents = {slug: [] for slug in doc_slugs}

        for doc_slug in doc_slugs:
            node = self.runtime_store.get_nav_node(doc_slug)
            if node:
                outgoing = json.loads(node.get("outgoing_links_json", "[]"))
                for target in outgoing:
                    if target in doc_slugs:
                        in_degree[target] += 1
                        dependents[doc_slug].append(target)

        # Kahn's algorithm for topological sort
        queue = [slug for slug in doc_slugs if in_degree[slug] == 0]
        result = []

        while queue:
            # Sort for deterministic ordering
            queue.sort()
            current = queue.pop(0)
            result.append(current)

            for dependent in dependents[current]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # Add any remaining (cycles would be here)
        result.extend([slug for slug in doc_slugs if slug not in result])

        return result

    def _get_doc_type(self, doc_slug: str) -> str:
        """Determine document type from slug."""
        if doc_slug.startswith("00-") or doc_slug.startswith("01-") or doc_slug.startswith("03-") or doc_slug.startswith("04-") or doc_slug.startswith("05-"):
            return "overview"
        if doc_slug in [s.canonical_slug for s in SECTION_DEFINITIONS]:
            return "section"
        return "module"

    def _get_regeneration_priority(self, doc_type: str, doc_slug: str) -> int:
        """Get regeneration priority (1=high, 2=medium, 3=low)."""
        if doc_type == "overview":
            # Core overview docs are high priority
            if doc_slug in ("00-overview", "01-architecture"):
                return 1
            return 2
        if doc_type == "section":
            return 2
        return 3

    def _get_regeneration_dependencies(self, doc_slug: str) -> list[str]:
        """Get list of doc_slugs that must be regenerated before this one."""
        node = self.runtime_store.get_nav_node(doc_slug)
        if not node:
            return []

        # Outgoing links mean this doc depends on those
        outgoing = json.loads(node.get("outgoing_links_json", "[]"))
        return [link for link in outgoing if link != doc_slug]

    def _resolve_doc_path(self, doc_slug: str) -> Path:
        """Resolve a doc_slug to its full path."""
        doc = self.runtime_store.get_doc_by_slug(doc_slug)
        if doc and doc.get("doc_path"):
            return self.root / doc["doc_path"]

        # Fallback: compute from slug
        if doc_slug.startswith("00-"):
            return self.root / "docs" / f"{doc_slug}.md"
        if doc_slug.startswith("01-"):
            return self.root / "docs" / f"{doc_slug}.md"
        if doc_slug.startswith("03-"):
            return self.root / "docs" / f"{doc_slug}.md"
        if doc_slug.startswith("04-"):
            return self.root / "docs" / f"{doc_slug}.md"
        if doc_slug.startswith("05-"):
            return self.root / "docs" / f"{doc_slug}.md"
        # Section pages
        return self.root / "docs" / "sections" / doc_slug / "index.md"


class IncrementalRegenerationPlanner:
    """Planner for incremental document regeneration based on SQLite state."""

    def __init__(
        self,
        root: Path,
        state_store: SQLiteStateStore,
        runtime_store,
    ) -> None:
        self.root = root
        self.state_store = state_store
        self.runtime_store = runtime_store
        self.invalidation_engine = PageInvalidationEngine(
            root=root,
            state_store=state_store,
            runtime_store=runtime_store,
        )

    def plan_from_incremental_impact(self, impact: IncrementalImpact) -> InvalidationResult:
        """Plan invalidation from an IncrementalImpact analysis.

        This is the main entry point for incremental regeneration planning.
        """
        if impact.global_doc_regeneration_triggers:
            return self.invalidation_engine.invalidate_from_changes(
                changed_files=impact.changed_files,
                deleted_files=impact.deleted_files,
                renamed_files=impact.renamed_files,
                reason="global_regeneration_trigger",
            )

        return self.invalidation_engine.invalidate_from_changes(
            changed_files=impact.changed_files,
            deleted_files=impact.deleted_files,
            renamed_files=impact.renamed_files,
            reason="file_changed",
        )

    def get_regeneration_summary(self, invalidation: InvalidationResult) -> dict[str, Any]:
        """Get a summary of the regeneration plan."""
        tasks = self.plan_regeneration(invalidation)

        by_priority = {1: [], 2: [], 3: []}
        for task in tasks:
            by_priority[task.priority].append(task.doc_slug)

        return {
            "total_pages": len(invalidation.invalidated_pages),
            "is_full_rebuild": invalidation.is_full_rebuild,
            "reason": invalidation.reason,
            "changed_files_count": len(invalidation.changed_files),
            "impacted_modules": invalidation.impacted_modules,
            "by_priority": {
                "high": by_priority[1],
                "medium": by_priority[2],
                "low": by_priority[3],
            },
            "execution_order": [t.doc_slug for t in tasks],
            "estimated_tasks": len(tasks),
        }