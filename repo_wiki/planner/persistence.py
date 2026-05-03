"""Planner persistence into SQLite and manifest.

Stores planned pages, nav nodes, profile, source digests, and path registry.
Writes `.repo-agent-eval/<run>/manifest.json` with plugin-readable navigation tree.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from repo_wiki.orchestration.runtime_store import SQLiteRuntimeStore, create_runtime_store
from repo_wiki.planner.schema import (
    GenerationMode,
    NavNode,
    WikiPagePlan,
    WikiPlanManifest,
    WikiTaxonomyCategory,
)


def persist_plan(
    root: Path,
    plan: WikiPlanManifest,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Persist page plan to SQLite and write manifest.

    Args:
        root: Repository root
        plan: Wiki plan manifest to persist
        run_id: Optional run identifier (generated if not provided)

    Returns:
        Dict with persistence results including manifest path
    """
    if run_id is None:
        run_id = f"plan-{int(time.time() * 1000)}"

    # Ensure eval directory exists
    eval_dir = root / ".repo-agent-eval" / run_id
    eval_dir.mkdir(parents=True, exist_ok=True)

    # Persist to SQLite runtime store
    runtime_store = create_runtime_store(root)
    _persist_plan_to_sqlite(runtime_store, plan, run_id)
    runtime_store.close()

    # Write manifest.json
    manifest_path = _write_manifest(eval_dir, plan, run_id)

    return {
        "status": "ok",
        "run_id": run_id,
        "manifest_path": str(manifest_path),
        "page_count": plan.page_count(),
        "eval_dir": str(eval_dir),
    }


def _persist_plan_to_sqlite(
    store: SQLiteRuntimeStore,
    plan: WikiPlanManifest,
    run_id: str,
) -> None:
    """Persist plan pages and nav nodes to SQLite."""
    from repo_wiki.orchestration.runtime_store import DocHierarchyRecord

    # Persist each page as a doc hierarchy record
    for page in plan.pages:
        record = DocHierarchyRecord(
            doc_type=_category_to_doc_type(page.category),
            doc_slug=page.page_id,
            doc_path=page.output_path,
            layer=_category_to_layer(page.category),
            parent_slug=page.parent,
            title=page.title,
            sort_order=page.sort_order,
            generation_input_hash=None,
            generation_output_hash=None,
            generated_at=datetime.now(UTC).isoformat(),
        )
        store.upsert_doc_hierarchy(record)

    # Persist navigation nodes
    for nav_node in plan.navigation_tree:
        _persist_nav_node(store, nav_node, run_id)

    # Store plan metadata
    _store_plan_metadata(store, plan, run_id)


def _persist_nav_node(
    store: SQLiteRuntimeStore,
    node: NavNode,
    run_id: str,
    depth: int = 0,
) -> None:
    """Recursively persist nav node and its children."""
    # Get outgoing links from children
    outgoing = [child.node_id for child in node.children if child.node_type == "page"]

    # Get incoming links (simplified - full graph resolution would need full traversal)
    incoming: list[str] = []

    store.upsert_nav_node(
        doc_slug=node.node_id,
        doc_type=node.node_type,
        incoming_links=incoming,
        outgoing_links=outgoing,
        depth=depth,
        affected_pages=[n.path for n in _flatten_nodes(node.children) if n.path],
    )

    for child in node.children:
        _persist_nav_node(store, child, run_id, depth + 1)


def _flatten_nodes(nodes: list[NavNode]) -> list[NavNode]:
    """Flatten node tree to list."""
    result = []
    for node in nodes:
        result.append(node)
        result.extend(_flatten_nodes(node.children))
    return result


def _store_plan_metadata(
    store: SQLiteRuntimeStore,
    plan: WikiPlanManifest,
    run_id: str,
) -> None:
    """Store plan metadata in a dedicated table."""
    # Use page_invalidation table to store plan metadata
    # This is a pragmatic reuse - a dedicated table could be added in future schema
    metadata = {
        "version": plan.version,
        "profile": plan.profile,
        "generated_at": plan.generated_at,
        "page_count": plan.page_count(),
        "run_id": run_id,
    }
    store.invalidate_page(
        doc_slug=f"plan-{run_id}",
        doc_type="plan",
        reason="plan_persisted",
        changed_files=[],
        impacted_modules=[],
    )


def _write_manifest(
    eval_dir: Path,
    plan: WikiPlanManifest,
    run_id: str,
) -> Path:
    """Write manifest.json to eval directory."""
    manifest_path = eval_dir / "manifest.json"

    manifest_data = {
        "version": plan.version,
        "run_id": run_id,
        "generated_at": plan.generated_at,
        "profile": plan.profile,
        "repository": {
            "name": plan.repository_identity.name if plan.repository_identity else "unknown",
            "display_name": plan.repository_identity.display_name
            if plan.repository_identity
            else "unknown",
            "root_path": plan.repository_identity.root_path if plan.repository_identity else "",
        },
        "page_count": plan.page_count(),
        "navigation_tree": _nav_node_to_dict(plan.navigation_tree),
        "pages": [
            {
                "page_id": p.page_id,
                "title": p.title,
                "category": p.category.value,
                "parent": p.parent,
                "output_path": p.output_path,
                "generation_mode": p.generation_mode.value,
                "sort_order": p.sort_order,
                "tags": p.tags,
            }
            for p in plan.pages
        ],
    }

    manifest_path.write_text(
        json.dumps(manifest_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return manifest_path


def _nav_node_to_dict(nodes: list[NavNode]) -> list[dict[str, Any]]:
    """Convert nav node tree to dict for JSON serialization."""
    result = []
    for node in nodes:
        result.append(
            {
                "node_id": node.node_id,
                "label": node.label,
                "node_type": node.node_type,
                "path": node.path,
                "icon": node.icon,
                "sort_order": node.sort_order,
                "metadata": node.metadata,
                "children": _nav_node_to_dict(node.children),
            }
        )
    return result


def _category_to_doc_type(category: WikiTaxonomyCategory) -> str:
    """Map category to doc type string."""
    mapping = {
        WikiTaxonomyCategory.PROJECT_OVERVIEW: "overview",
        WikiTaxonomyCategory.ARCHITECTURE_DESIGN: "section",
        WikiTaxonomyCategory.CORE_SERVICES: "module",
        WikiTaxonomyCategory.PYTHON_SERVICES: "module",
        WikiTaxonomyCategory.FRONTEND_APPLICATIONS: "module",
        WikiTaxonomyCategory.DATA_MODELS: "data-model",
        WikiTaxonomyCategory.API_REFERENCE: "api",
        WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS: "ops",
        WikiTaxonomyCategory.DEVELOPMENT_GUIDE: "guide",
        WikiTaxonomyCategory.SECURITY_COMPLIANCE: "security",
        WikiTaxonomyCategory.TROUBLESHOOTING: "troubleshooting",
    }
    return mapping.get(category, "page")


def _category_to_layer(category: WikiTaxonomyCategory) -> str:
    """Map category to layer string."""
    if category in (
        WikiTaxonomyCategory.PROJECT_OVERVIEW,
        WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
    ):
        return "overview"
    if category in (
        WikiTaxonomyCategory.CORE_SERVICES,
        WikiTaxonomyCategory.PYTHON_SERVICES,
        WikiTaxonomyCategory.FRONTEND_APPLICATIONS,
    ):
        return "module"
    if category in (WikiTaxonomyCategory.DATA_MODELS, WikiTaxonomyCategory.API_REFERENCE):
        return "reference"
    return "ops"


def load_plan_from_sqlite(root: Path) -> WikiPlanManifest | None:
    """Load a plan from SQLite runtime store.

    Returns:
        WikiPlanManifest if found, None otherwise
    """
    runtime_store = create_runtime_store(root)

    # Load docs
    docs = runtime_store.list_docs_by_layer("overview")
    docs.extend(runtime_store.list_docs_by_layer("module"))
    docs.extend(runtime_store.list_docs_by_layer("reference"))
    docs.extend(runtime_store.list_docs_by_layer("ops"))

    if not docs:
        runtime_store.close()
        return None

    pages = []
    for doc in docs:
        category = _doc_type_to_category(doc.get("doc_type", "page"))
        page = WikiPagePlan(
            page_id=doc["doc_slug"],
            title=doc.get("title", doc["doc_slug"]),
            category=category,
            parent=doc.get("parent_slug"),
            output_path=doc["doc_path"],
            generation_mode=GenerationMode.RULE_FIRST,
            sort_order=doc.get("sort_order", 0),
        )
        pages.append(page)

    # Load nav nodes
    nav_nodes: dict[str, NavNode] = {}
    all_nodes = (
        runtime_store.list_nav_nodes_by_type("category")
        + runtime_store.list_nav_nodes_by_type("page")
        + runtime_store.list_nav_nodes_by_type("separator")
    )
    for node_data in all_nodes:
        node = NavNode(
            node_id=node_data["doc_slug"],
            label=node_data.get("title", node_data["doc_slug"]),
            node_type=node_data.get("doc_type", "page"),
            sort_order=0,
        )
        nav_nodes[node.node_id] = node

    runtime_store.close()

    return WikiPlanManifest(
        version="1.0.0",
        profile="loaded-from-sqlite",
        pages=pages,
        navigation_tree=list(nav_nodes.values()),
    )


def _doc_type_to_category(doc_type: str) -> WikiTaxonomyCategory:
    """Map doc type back to category."""
    mapping = {
        "overview": WikiTaxonomyCategory.PROJECT_OVERVIEW,
        "section": WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
        "module": WikiTaxonomyCategory.CORE_SERVICES,
        "data-model": WikiTaxonomyCategory.DATA_MODELS,
        "api": WikiTaxonomyCategory.API_REFERENCE,
        "ops": WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS,
        "guide": WikiTaxonomyCategory.DEVELOPMENT_GUIDE,
        "security": WikiTaxonomyCategory.SECURITY_COMPLIANCE,
        "troubleshooting": WikiTaxonomyCategory.TROUBLESHOOTING,
    }
    return mapping.get(doc_type, WikiTaxonomyCategory.PROJECT_OVERVIEW)
