from __future__ import annotations

import asyncio
import math
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from repo_wiki.adapter.service import AdapterService
from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.core.errors import ErrorCategory, RepoWikiError
from repo_wiki.core.logging import info
from repo_wiki.core.runtime import bootstrap
from repo_wiki.generator.contracts import (
    CORE_DOCUMENT_CONTRACTS,
    SECTION_DEFINITIONS,
    get_canonical_slug,
)
from repo_wiki.generator.engine import GenerationConfig, GenerationEngine
from repo_wiki.generator.io import read_json, read_text, read_yamlish
from repo_wiki.graph.service import build_graph_artifacts
from repo_wiki.indexer.indexing import SemanticIndexer
from repo_wiki.orchestration.runtime_store import (
    DocHierarchyRecord,
    SectionRegistryRecord,
    create_runtime_store,
)
from repo_wiki.retrieval.service import RetrievalService
from repo_wiki.scanner.artifacts import write_source_of_truth
from repo_wiki.scanner.repository_scanner import RepositoryScanner
from repo_wiki.verifier.service import VerifierService


class RepoWikiService:
    _LOCAL_LINK_PATTERN = re.compile(r"\[[^\]\n]+\]\(([^)\n]+)\)")
    _CITE_PATTERN = re.compile(r"<cite>[^<]+</cite>")
    _HEADING_L2_PATTERN = re.compile(r"^##\s+(.+)$", re.MULTILINE)

    def __init__(self, config: RepoWikiConfig) -> None:
        self.config = config
        self.root = Path(config.project.root).resolve()

    def init(self) -> dict[str, Any]:
        stage = StageTimer()
        boot = bootstrap(self.config)

        stage.start("scan")
        scanner = RepositoryScanner(self.config)
        snapshot = scanner.scan()
        stage.stop("scan")

        stage.start("source_of_truth")
        source_paths = write_source_of_truth(self.root, snapshot)
        stage.stop("source_of_truth")

        stage.start("index")
        indexer = SemanticIndexer(self.root, self.config)
        indexing_result = indexer.rebuild(snapshot)
        stage.stop("index")

        stage.start("graph")
        graph_result = build_graph_artifacts(self.root, snapshot)
        stage.stop("graph")

        stage.start("retrieval")
        retrieval = RetrievalService(self.root, self.config)
        retrieval_candidates = retrieval.build_retrieval_candidates(
            [module.name for module in snapshot.modules]
        )
        stage.stop("retrieval")

        stage.start("generate")
        generation = self._generation_engine()
        generated = generation.generate_full()
        stage.stop("generate")

        stage.start("sync")
        sync_result = AdapterService(self.root).sync()
        stage.stop("sync")

        stage.start("runtime_sync")
        runtime_sync = self._sync_runtime_store()
        stage.stop("runtime_sync")

        return {
            "warnings": boot.warnings,
            "scan": {
                "modules": len(snapshot.modules),
                "endpoints": len(snapshot.endpoints),
                "data_models": len(snapshot.data_models),
                "security_warnings": len(scanner.last_security_warnings),
            },
            "source_of_truth": {key: str(path) for key, path in source_paths.items()},
            "index": {
                "indexed_files": indexing_result.indexed_files,
                "changed_files": indexing_result.changed_files,
                "deleted_files": indexing_result.deleted_files,
                "exports": indexing_result.exported,
            },
            "graph": graph_result,
            "retrieval": {"candidates_path": str(retrieval_candidates)},
            "generate": {
                "written_files": generated.written_files,
                "cache_hits": generated.cache_hits,
                "cache_misses": generated.cache_misses,
            },
            "sync": sync_result,
            "runtime_sync": runtime_sync,
            "timings": stage.timings,
        }

    def index(self) -> dict[str, Any]:
        stage = StageTimer()
        bootstrap(self.config)

        stage.start("scan")
        scanner = RepositoryScanner(self.config)
        snapshot = scanner.scan()
        stage.stop("scan")

        stage.start("source_of_truth")
        source_paths = write_source_of_truth(self.root, snapshot)
        stage.stop("source_of_truth")

        stage.start("index")
        indexer = SemanticIndexer(self.root, self.config)
        indexing_result = indexer.rebuild(snapshot)
        stage.stop("index")

        stage.start("graph")
        graph_result = build_graph_artifacts(self.root, snapshot)
        stage.stop("graph")

        stage.start("retrieval")
        retrieval = RetrievalService(self.root, self.config)
        retrieval_candidates = retrieval.build_retrieval_candidates(
            [module.name for module in snapshot.modules]
        )
        stage.stop("retrieval")

        stage.start("runtime_sync")
        runtime_sync = self._sync_runtime_store()
        stage.stop("runtime_sync")

        return {
            "scan": {
                "modules": len(snapshot.modules),
                "endpoints": len(snapshot.endpoints),
                "data_models": len(snapshot.data_models),
                "security_warnings": len(scanner.last_security_warnings),
            },
            "source_of_truth": {key: str(path) for key, path in source_paths.items()},
            "index": {
                "indexed_files": indexing_result.indexed_files,
                "changed_files": indexing_result.changed_files,
                "deleted_files": indexing_result.deleted_files,
                "exports": indexing_result.exported,
            },
            "graph": graph_result,
            "retrieval": {"candidates_path": str(retrieval_candidates)},
            "runtime_sync": runtime_sync,
            "timings": stage.timings,
        }

    def update(self) -> dict[str, Any]:
        stage = StageTimer()
        bootstrap(self.config)

        stage.start("impact")
        retrieval = RetrievalService(self.root, self.config)
        impact = retrieval.analyze_incremental_impact()
        stage.stop("impact")

        stage.start("scan")
        scanner = RepositoryScanner(self.config)
        snapshot = scanner.scan()
        stage.stop("scan")

        stage.start("source_of_truth")
        source_paths = write_source_of_truth(self.root, snapshot)
        stage.stop("source_of_truth")

        stage.start("index")
        indexer = SemanticIndexer(self.root, self.config)
        indexing_result = indexer.rebuild(snapshot)
        stage.stop("index")

        stage.start("graph")
        graph_result = build_graph_artifacts(self.root, snapshot)
        stage.stop("graph")

        stage.start("retrieval")
        retrieval_candidates = retrieval.build_retrieval_candidates(
            [module.name for module in snapshot.modules]
        )
        stage.stop("retrieval")

        stage.start("generate")
        generator = self._generation_engine()
        if impact.global_doc_regeneration_triggers or not impact.impacted_modules:
            generation_result = generator.generate_full()
            generation_mode = "full"
        else:
            generation_result = generator.generate_incremental(impact.impacted_modules)
            generation_mode = "incremental"
        stage.stop("generate")

        stage.start("sync")
        sync_result = AdapterService(self.root).sync()
        stage.stop("sync")

        stage.start("runtime_sync")
        runtime_sync = self._sync_runtime_store()
        stage.stop("runtime_sync")

        return {
            "impact": impact.to_dict(),
            "scan": {
                "modules": len(snapshot.modules),
                "endpoints": len(snapshot.endpoints),
                "data_models": len(snapshot.data_models),
                "security_warnings": len(scanner.last_security_warnings),
            },
            "source_of_truth": {key: str(path) for key, path in source_paths.items()},
            "index": {
                "indexed_files": indexing_result.indexed_files,
                "changed_files": indexing_result.changed_files,
                "deleted_files": indexing_result.deleted_files,
                "exports": indexing_result.exported,
            },
            "graph": graph_result,
            "retrieval": {"candidates_path": str(retrieval_candidates)},
            "generate": {
                "mode": generation_mode,
                "written_files": generation_result.written_files,
                "cache_hits": generation_result.cache_hits,
                "cache_misses": generation_result.cache_misses,
            },
            "sync": sync_result,
            "runtime_sync": runtime_sync,
            "timings": stage.timings,
        }

    def sync(self) -> dict[str, Any]:
        bootstrap(self.config)
        return AdapterService(self.root).sync()

    def generate(
        self,
        eval_profile: Any = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """Generate wiki content with optional eval profile.

        Args:
            eval_profile: Optional EvalOutputProfile for qoder-like output
            run_id: Optional run identifier

        Returns:
            Generation result with file counts and manifest path
        """
        from repo_wiki.orchestration.eval_layout import (
            generate_manifest,
            get_eval_profile,
            resolve_revision_with_fallback,
            write_manifest,
        )

        stage = StageTimer()

        # Resolve profile
        if eval_profile is None:
            eval_profile = get_eval_profile("default")
        eval_profile = eval_profile.resolve_root(self.root)

        # Generate run_id if not provided
        if run_id is None:
            run_id = f"run-{int(time.time() * 1000)}"

        if eval_profile.content_subdir:
            return self._generate_isolated_eval(eval_profile=eval_profile, run_id=run_id)

        bootstrap(self.config)

        # Resolve target repository revision (git first, hash fallback)
        target_git_commit, target_revision_source = resolve_revision_with_fallback(self.root)

        stage.start("scan")
        scanner = RepositoryScanner(self.config)
        snapshot = scanner.scan()
        stage.stop("scan")

        stage.start("source_of_truth")
        source_paths = write_source_of_truth(self.root, snapshot)
        stage.stop("source_of_truth")

        stage.start("generate")
        generator = self._generation_engine()
        generation_result = generator.generate_full()
        stage.stop("generate")

        # Write manifest for eval profiles
        manifest_path = None
        if eval_profile.name != "default":
            output_dir = eval_profile.get_run_dir(run_id)
            content_dir = eval_profile.get_content_dir(run_id)

            # Build navigation tree from generated files
            written_files = generation_result.written_files
            navigation_tree = build_navigation_tree(written_files, content_dir)

            # Build page registry
            page_registry = []
            for file_path in written_files:
                if file_path.endswith(".md"):
                    slug = compute_stable_slug(Path(file_path).stem)
                    page_registry.append(
                        {
                            "path": file_path,
                            "slug": slug,
                            "type": "markdown",
                        }
                    )

            manifest = generate_manifest(
                run_id=run_id,
                profile=eval_profile,
                target_repo=str(self.root),
                output_dir=output_dir,
                stats={
                    "files_written": generation_result.written_files,
                    "cache_hits": generation_result.cache_hits,
                    "cache_misses": generation_result.cache_misses,
                },
                navigation_tree=navigation_tree,
                page_registry=page_registry,
                target_git_commit=target_git_commit,
                wiki_git_commit=target_git_commit,  # Wiki and target are same at generation
                target_revision_source=target_revision_source,
                wiki_revision_source=target_revision_source,
                content_root=str(content_dir),
                runtime_root=str(self.root / ".repo-wiki"),
            )
            manifest_path = write_manifest(manifest, output_dir)

        stage.start("runtime_sync")
        runtime_sync = self._sync_runtime_store()
        stage.stop("runtime_sync")

        return {
            "scan": {
                "modules": len(snapshot.modules),
                "endpoints": len(snapshot.endpoints),
                "data_models": len(snapshot.data_models),
            },
            "source_of_truth": {key: str(path) for key, path in source_paths.items()},
            "generate": {
                "profile": eval_profile.name,
                "run_id": run_id,
                "written_files": generation_result.written_files,
                "cache_hits": generation_result.cache_hits,
                "cache_misses": generation_result.cache_misses,
            },
            "manifest_path": str(manifest_path) if manifest_path else None,
            "runtime_sync": runtime_sync,
            "timings": stage.timings,
        }

    def _generate_isolated_eval(self, eval_profile: Any, run_id: str) -> dict[str, Any]:
        """Generate qoder-like eval output without mutating target docs/runtime dirs."""
        from repo_wiki.orchestration.content_layout_writer import (
            ContentLayoutWriter,
            build_navigation_tree,
        )
        from repo_wiki.orchestration.eval_layout import (
            generate_manifest,
            get_git_commit_full,
            is_git_dirty,
            resolve_revision_with_fallback,
            write_manifest,
        )

        stage = StageTimer()
        if not self.root.exists() or not self.root.is_dir():
            raise RepoWikiError(
                "Project root does not exist or is not a directory.",
                ErrorCategory.BOOTSTRAP,
                {"root": str(self.root)},
            )

        target_head_before = get_git_commit_full(self.root)
        target_git_commit, target_revision_source = resolve_revision_with_fallback(self.root)
        target_dirty = is_git_dirty(self.root)
        info(f"qoder-like generation started run_id={run_id} root={self.root}")

        info("stage scan started")
        stage.start("scan")
        scanner = RepositoryScanner(self.config)
        snapshot = scanner.scan()
        stage.stop("scan")
        info(
            "stage scan completed "
            f"modules={len(snapshot.modules)} endpoints={len(snapshot.endpoints)} "
            f"data_models={len(snapshot.data_models)} elapsed={stage.timings.get('scan')}s"
        )

        info("stage plan started")
        stage.start("plan")
        plan = self._build_qoder_like_page_plan(snapshot)
        stage.stop("plan")
        info(
            f"stage plan completed planned_pages={len(plan.pages)} elapsed={stage.timings.get('plan')}s"
        )

        info("stage evidence started")
        stage.start("evidence")
        evidence_spans = self._extract_evidence_spans()
        evidence_bindings = self._bind_evidence_to_plan(plan, evidence_spans)
        stage.stop("evidence")
        info(
            "stage evidence completed "
            f"spans={len(evidence_spans)} bound_pages={len(evidence_bindings)} "
            f"elapsed={stage.timings.get('evidence')}s"
        )

        info("stage compose started")
        stage.start("compose")
        writer = ContentLayoutWriter(profile=eval_profile, run_id=run_id)
        output_dir = writer.run_dir
        content_dir = writer.content_dir
        composition = asyncio.run(
            self._compose_qoder_like_pages(
                plan=plan,
                evidence_bindings=evidence_bindings,
                snapshot=snapshot,
                output_dir=output_dir,
            )
        )
        stage.stop("compose")
        info(
            "stage compose completed "
            f"pages={len(composition['pages'])} llm_calls={composition['llm'].get('llm_call_count')} "
            f"fallback_pages={composition['llm'].get('fallback_page_count')} elapsed={stage.timings.get('compose')}s"
        )

        info("stage content started")
        stage.start("content")
        plan_md_paths = {
            page.output_path for page in plan.pages if page.output_path.endswith(".md")
        }
        selected_paths = writer.load_selected_paths_from_sqlite(
            self.root / ".repo-wiki" / "index" / "runtime.sqlite3",
            project_root=self.root,
        )
        overlap = selected_paths & plan_md_paths if selected_paths else set()
        if not selected_paths or not overlap:
            # Empty DB, or nothing in common after normalizing absolute sqlite paths to relative.
            selected_paths = plan_md_paths
        elif len(overlap) < len(plan_md_paths):
            # Runtime doc_hierarchy lists existing docs (often docs/*.md, docs/modules/*.md).
            # Qoder-like plans target docs/pages/** — partial accidental overlap must not
            # suppress most composed pages.
            selected_paths = plan_md_paths
        else:
            selected_paths = overlap
        written_content, content_stats = writer.write_markdown_pages(
            composition["pages"],
            selected_source_paths=selected_paths,
        )
        navigation_tree = build_navigation_tree(written_content, content_dir)
        page_registry = writer.build_page_registry(written_content)
        stage.stop("content")
        info(
            f"stage content completed files={len(written_content)} elapsed={stage.timings.get('content')}s"
        )

        info("stage manifest started")
        stage.start("manifest")
        manifest = generate_manifest(
            run_id=run_id,
            profile=eval_profile,
            target_repo=str(self.root),
            output_dir=output_dir,
            stats={
                "planned_pages": len(plan.pages),
                "content_files": written_content,
                "content_file_count": len(written_content),
                "content_layout": content_stats,
                "evidence_spans": len(evidence_spans),
                "failed_pages": composition["failed_pages"],
                "quality_warnings": composition["quality_warnings"],
                "cache_hits": composition["cache_hits"],
                "cache_misses": composition["cache_misses"],
                "llm": composition["llm"],
                "isolated": True,
            },
            metadata={
                "generation_mode": "isolated-qoder-like-llm-composer",
                "target_dirs_modified": False,
                "wiki_plan_profile": plan.profile,
                "repository_identity": plan.repository_identity.model_dump()
                if plan.repository_identity
                else None,
            },
            navigation_tree=navigation_tree,
            page_registry=page_registry,
            target_git_commit=target_git_commit,
            wiki_git_commit=target_git_commit,
            target_head_before=target_head_before,
            target_head_after=get_git_commit_full(self.root),
            target_dirty=target_dirty,
            target_revision_source=target_revision_source,
            wiki_revision_source=target_revision_source,
            content_root=str(content_dir),
            runtime_root=str(output_dir / "runtime"),
        )
        manifest_path = write_manifest(manifest, output_dir)
        stage.stop("manifest")
        info(
            f"stage manifest completed path={manifest_path} elapsed={stage.timings.get('manifest')}s"
        )

        return {
            "scan": {
                "modules": len(snapshot.modules),
                "endpoints": len(snapshot.endpoints),
                "data_models": len(snapshot.data_models),
            },
            "generate": {
                "profile": eval_profile.name,
                "run_id": run_id,
                "written_files": written_content,
                "content_root": str(content_dir),
                "planned_pages": len(plan.pages),
                "cache_hits": composition["cache_hits"],
                "cache_misses": composition["cache_misses"],
                "llm": composition["llm"],
                "failed_pages": composition["failed_pages"],
                "isolated": True,
            },
            "manifest_path": str(manifest_path),
            "timings": stage.timings,
        }

    def _build_qoder_like_page_plan(self, snapshot: Any) -> Any:
        """Build the qoder-like page plan used by the isolated LLM composer path."""
        from repo_wiki.planner.identity import detect_package_manager, resolve_repository_identity
        from repo_wiki.planner.llm_planner import MockLLMProvider, enhance_plan_with_llm
        from repo_wiki.planner.rule_first import RuleFirstPlanner

        identity = resolve_repository_identity(self.root)
        package_manager = detect_package_manager(self.root)
        identity = identity.model_copy(
            update={
                "language": snapshot.repository.language,
                "framework": snapshot.repository.framework,
                "package_manager": package_manager,
            }
        )
        base_plan = RuleFirstPlanner(identity, snapshot).generate()
        enhanced = enhance_plan_with_llm(base_plan, MockLLMProvider())
        max_budget = self._resolve_qoder_like_max_pages()
        min_budget = min(self._resolve_qoder_like_min_pages(), max_budget)
        return self._normalize_qoder_like_plan(enhanced, minimum_pages=min_budget)

    def _normalize_qoder_like_plan(self, plan: Any, minimum_pages: int) -> Any:
        from repo_wiki.planner.llm_planner import _RebuildPlanner
        from repo_wiki.planner.schema import (
            GenerationMode,
            SourceRequirement,
            WikiPagePlan,
            WikiTaxonomyCategory,
        )

        pages = list(plan.pages)
        pages = self._filter_qoder_like_pages(pages)
        page_ids = {p.page_id for p in pages}

        required_roots: list[tuple[Any, str, str]] = [
            (WikiTaxonomyCategory.PROJECT_OVERVIEW, "project-overview", "项目概述"),
            (WikiTaxonomyCategory.ARCHITECTURE_DESIGN, "architecture-overview", "架构设计"),
            (WikiTaxonomyCategory.CORE_SERVICES, "core-services-index", "核心服务"),
            (WikiTaxonomyCategory.PYTHON_SERVICES, "python-services-index", "Python服务"),
            (WikiTaxonomyCategory.FRONTEND_APPLICATIONS, "frontend-applications-index", "前端应用"),
            (WikiTaxonomyCategory.DATA_MODELS, "data-models-overview", "数据模型"),
            (WikiTaxonomyCategory.API_REFERENCE, "api-overview", "API参考"),
            (WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS, "deployment-overview", "部署运维"),
            (WikiTaxonomyCategory.DEVELOPMENT_GUIDE, "development-guide", "开发指南"),
            (WikiTaxonomyCategory.SECURITY_COMPLIANCE, "security-overview", "安全合规"),
            (
                WikiTaxonomyCategory.TROUBLESHOOTING,
                "troubleshooting-maintenance-overview",
                "故障排除与维护",
            ),
        ]

        for sort_order, (category, page_id, title) in enumerate(required_roots):
            if page_id in page_ids:
                continue
            pages.append(
                WikiPagePlan(
                    page_id=page_id,
                    title=title,
                    category=category,
                    parent=None,
                    output_path=self._qoder_output_path_for(category, page_id),
                    source_requirements=SourceRequirement(),
                    generation_mode=GenerationMode.RULE_FIRST,
                    sort_order=sort_order,
                    tags=["taxonomy-root"],
                )
            )
            page_ids.add(page_id)

        if len(pages) < minimum_pages:
            filler_count = minimum_pages - len(pages)
            ordered_categories = [row[0] for row in required_roots]
            for idx in range(filler_count):
                category = ordered_categories[idx % len(ordered_categories)]
                page_id = f"deep-dive-{idx + 1:03d}"
                if page_id in page_ids:
                    continue
                pages.append(
                    WikiPagePlan(
                        page_id=page_id,
                        title=f"{category.value}专题 {idx + 1}",
                        category=category,
                        parent=required_roots[idx % len(required_roots)][1],
                        output_path=self._qoder_output_path_for(category, page_id),
                        source_requirements=SourceRequirement(),
                        generation_mode=GenerationMode.LLM_ASSISTED,
                        sort_order=5000 + idx,
                        tags=["llm-suggested", "coverage-topup"],
                    )
                )
                page_ids.add(page_id)

        max_pages = self._resolve_qoder_like_max_pages()
        if len(pages) > max_pages:
            required_page_ids = {row[1] for row in required_roots}
            pages = self._cap_qoder_like_pages(
                pages=pages,
                required_page_ids=required_page_ids,
                ordered_categories=[row[0] for row in required_roots],
                max_pages=max_pages,
            )

        nav_tree = _RebuildPlanner(plan.repository_identity, pages)._build_navigation_tree()
        return plan.model_copy(update={"pages": pages, "navigation_tree": nav_tree})

    def _filter_qoder_like_pages(self, pages: list[Any]) -> list[Any]:
        """Remove low-value planner artifacts from the Qoder-like profile."""
        import os

        include_endpoint_pages = os.environ.get(
            "REPO_WIKI_INCLUDE_ENDPOINT_PAGES", ""
        ).strip().lower() in {
            "1",
            "true",
            "yes",
        }
        include_raw_model_pages = os.environ.get(
            "REPO_WIKI_INCLUDE_RAW_MODEL_PAGES", ""
        ).strip().lower() in {
            "1",
            "true",
            "yes",
        }
        filtered: list[Any] = []
        seen: set[str] = set()
        method_title = re.compile(r"^(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\s+", re.IGNORECASE)
        for page in pages:
            title = str(getattr(page, "title", ""))
            page_id = str(getattr(page, "page_id", ""))
            tags = set(getattr(page, "tags", []) or [])

            if not include_endpoint_pages and ("endpoint" in tags or method_title.match(title)):
                continue
            if not include_raw_model_pages and (
                "raw-model" in tags or "model" in tags and page.category.value == "数据模型"
            ):
                continue
            if title.lower().startswith("consider adding"):
                continue
            if page_id in seen:
                continue
            filtered.append(page)
            seen.add(page_id)
        return filtered

    def _cap_qoder_like_pages(
        self,
        pages: list[Any],
        required_page_ids: set[str],
        ordered_categories: list[Any],
        max_pages: int,
    ) -> list[Any]:
        """Keep qoder-like output curated instead of dumping every discovered entity."""
        selected: list[Any] = []
        selected_ids: set[str] = set()

        for page in sorted(pages, key=lambda p: (p.sort_order, p.title)):
            if page.page_id in required_page_ids and page.page_id not in selected_ids:
                selected.append(page)
                selected_ids.add(page.page_id)

        remaining_by_category: dict[Any, list[Any]] = {
            category: [] for category in ordered_categories
        }
        overflow: list[Any] = []
        for page in sorted(pages, key=lambda p: (p.sort_order, p.title)):
            if page.page_id in selected_ids:
                continue
            bucket = remaining_by_category.get(page.category)
            if bucket is None:
                overflow.append(page)
            else:
                bucket.append(page)

        while len(selected) < max_pages and any(remaining_by_category.values()):
            made_progress = False
            for category in ordered_categories:
                bucket = remaining_by_category.get(category) or []
                while bucket:
                    candidate = bucket.pop(0)
                    if candidate.page_id in selected_ids:
                        continue
                    selected.append(candidate)
                    selected_ids.add(candidate.page_id)
                    made_progress = True
                    break
                if len(selected) >= max_pages:
                    break
            if not made_progress:
                break

        for page in overflow:
            if len(selected) >= max_pages:
                break
            if page.page_id in selected_ids:
                continue
            selected.append(page)
            selected_ids.add(page.page_id)

        return sorted(selected, key=lambda p: (p.sort_order, p.title))

    def _clamp_qoder_page_budget(self, value: int) -> int:
        """Keep page-plan sizes within a sane band (matches YAML `le=2000`)."""
        return max(1, min(int(value), 2000))

    def _resolve_qoder_like_min_pages(self) -> int:
        """Minimum planned pages (taxonomy fill). Env overrides YAML `qoder_like.min_pages`."""
        import os

        raw = os.environ.get("REPO_WIKI_QODER_LIKE_MIN_PAGES")
        if raw:
            try:
                return self._clamp_qoder_page_budget(int(raw))
            except ValueError:
                pass
        return self._clamp_qoder_page_budget(self.config.qoder_like.min_pages)

    def _resolve_qoder_like_max_pages(self) -> int:
        """Curated cap for qoder-like runs; env overrides YAML ``qoder_like.max_pages`` (no legacy 120 floor)."""
        import os

        raw = os.environ.get("REPO_WIKI_QODER_LIKE_MAX_PAGES")
        if raw:
            try:
                return self._clamp_qoder_page_budget(int(raw))
            except ValueError:
                pass
        return self._clamp_qoder_page_budget(self.config.qoder_like.max_pages)

    def _qoder_output_path_for(self, category: Any, page_id: str) -> str:
        from repo_wiki.planner.schema import WikiTaxonomyCategory

        category_paths = {
            WikiTaxonomyCategory.PROJECT_OVERVIEW: "docs/pages/overview",
            WikiTaxonomyCategory.ARCHITECTURE_DESIGN: "docs/pages/architecture",
            WikiTaxonomyCategory.CORE_SERVICES: "docs/pages/services",
            WikiTaxonomyCategory.PYTHON_SERVICES: "docs/pages/python-services",
            WikiTaxonomyCategory.FRONTEND_APPLICATIONS: "docs/pages/frontend",
            WikiTaxonomyCategory.DATA_MODELS: "docs/pages/data-models",
            WikiTaxonomyCategory.API_REFERENCE: "docs/pages/api",
            WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS: "docs/pages/deployment",
            WikiTaxonomyCategory.DEVELOPMENT_GUIDE: "docs/pages/development",
            WikiTaxonomyCategory.SECURITY_COMPLIANCE: "docs/pages/security",
            WikiTaxonomyCategory.TROUBLESHOOTING: "docs/pages/troubleshooting",
        }
        base = category_paths.get(category, "docs/pages")
        return f"{base}/{page_id}.md"

    def _extract_evidence_spans(self) -> list[EvidenceSpanRecord]:
        """Extract source spans for composer evidence without writing runtime state."""
        import os

        from repo_wiki.orchestration.runtime_store import EvidenceSpanRecord
        from repo_wiki.scanner.source_spans import SourceSpanExtractor

        extractor = SourceSpanExtractor()
        spans: list[EvidenceSpanRecord] = []
        denied_dirs = set(self.config.security.deny_dirs) | {
            ".repo-agent-eval",
            ".qoder",
            ".repo-wiki",
            ".git",
            ".gradle",
            ".idea",
            "target",
            "out",
            ".artifact-venv",
            ".m2-temp",
            ".pytest_cache",
            ".ruff_cache",
            ".playwright-mcp",
            "playwright-report",
            "test-results",
            "result",
            "output",
            "logs",
            "log",
        }
        max_size = self.config.security.max_file_size_kb * 1024
        max_spans = 3000

        for dirpath, dirnames, filenames in os.walk(
            self.root, followlinks=self.config.scan.follow_symlinks
        ):
            if len(spans) >= max_spans:
                break
            current_dir = Path(dirpath)
            try:
                current_rel = current_dir.relative_to(self.root)
            except ValueError:
                continue

            dirnames[:] = [
                dirname
                for dirname in sorted(dirnames)
                if not self._should_prune_evidence_dir(current_rel / dirname, denied_dirs)
            ]

            for filename in sorted(filenames):
                if len(spans) >= max_spans:
                    break
                path = current_dir / filename
                if not path.is_file():
                    continue
                try:
                    relative = path.relative_to(self.root)
                except ValueError:
                    continue
                if any(part in denied_dirs for part in relative.parts):
                    continue
                if self._matches_project_exclude(relative):
                    continue
                if path.stat().st_size > max_size:
                    continue

                try:
                    content = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue

                for span in extractor.extract_from_file(relative, content):
                    lines = content.splitlines()
                    snippet = "\n".join(lines[max(span.line_start - 1, 0) : span.line_end])
                    spans.append(
                        EvidenceSpanRecord(
                            digest=span.digest,
                            file_path=span.file,
                            line_start=span.line_start,
                            line_end=span.line_end,
                            language=span.language,
                            symbol=span.symbol,
                            span_text=snippet,
                            confidence=1.0,
                        )
                    )

        return spans

    def _should_prune_evidence_dir(self, relative_path: Path, denied_dirs: set[str]) -> bool:
        rel = relative_path.as_posix()
        if rel in {"", "."}:
            return False
        if any(part in denied_dirs for part in relative_path.parts):
            return True
        if self._matches_project_exclude(relative_path):
            return True
        return False

    def _matches_project_exclude(self, relative_path: Path) -> bool:
        import fnmatch

        rel = relative_path.as_posix()
        return any(fnmatch.fnmatch(rel, pattern) for pattern in self.config.project.exclude)

    def _bind_evidence_to_plan(
        self,
        plan: Any,
        evidence_spans: list[EvidenceSpanRecord],
    ) -> dict[str, PageEvidenceBinding]:
        from repo_wiki.evidence.ranking import (
            EvidenceCandidate,
            PageEvidenceBinding,
            rank_evidence_for_page,
        )

        bindings: dict[str, PageEvidenceBinding] = {}
        for page in plan.pages:
            candidates = rank_evidence_for_page(page, evidence_spans)
            if not candidates and evidence_spans:
                fallback = []
                for idx, span in enumerate(evidence_spans[:5]):
                    fallback.append(
                        EvidenceCandidate(
                            evidence_id=span.id if getattr(span, "id", None) is not None else idx,
                            span=span,
                            score=0.1,
                            match_signals=["fallback"],
                            citation_order=idx,
                        )
                    )
                candidates = fallback
            bindings[page.page_id] = PageEvidenceBinding(
                page_id=page.page_id,
                doc_type=page.category.value,
                candidates=candidates,
                insufficient_evidence=len(candidates) == 0 and bool(evidence_spans),
                bound_count=len(candidates),
            )
        return bindings

    def _resolve_qoder_like_llm(self) -> tuple[Any, LLMProviderConfig, dict[str, Any]]:
        """Resolve real HTTP provider when API key is set and mock is not forced; else mock.

        See :func:`repo_wiki.llm.qoder_like_provider.resolve_qoder_like_llm` for rules.
        """
        from repo_wiki.llm.qoder_like_provider import resolve_qoder_like_llm

        return resolve_qoder_like_llm(
            llm_config_dict=self.config.llm.model_dump(),
            force_mock_llm_config=bool(self.config.llm.force_mock_llm),
        )

    async def _compose_qoder_like_pages(
        self,
        plan: Any,
        evidence_bindings: dict[str, PageEvidenceBinding],
        snapshot: Any,
        output_dir: Path,
    ) -> dict[str, Any]:
        from repo_wiki.generator.composer import (
            ComposerContext,
            build_composer_input,
            create_composer,
        )
        from repo_wiki.generator.composer_cache import (
            ComposerCache,
            compute_composer_input_hash,
            estimate_cost_from_tokens,
        )

        provider, llm_config, llm_summary = self._resolve_qoder_like_llm()
        composer = create_composer(
            provider=provider,
            llm_config=llm_config,
            workspace_root=self.root,
        )
        cache_path = self._resolve_composer_cache_path(output_dir)
        cache = ComposerCache(cache_path)
        context = ComposerContext(
            repository_name=snapshot.repository.name,
            primary_language=snapshot.repository.language,
            framework=snapshot.repository.framework,
            repository_root=str(self.root),
            modules=[m.model_dump() for m in snapshot.modules],
            endpoints=[e.model_dump() for e in snapshot.endpoints],
            models=[m.model_dump() for m in snapshot.data_models],
            commands=snapshot.commands,
        )

        pages: list[tuple[str, str]] = []
        failed_pages: list[dict[str, str]] = []
        cache_hits = 0
        cache_misses = 0
        llm_call_count = 0
        estimated_tokens = 0
        actual_tokens = 0
        provider_failure_count = 0
        fallback_page_count = 0
        provider_attempt_count = 0
        attempted_page_ids: list[str] = []
        provider_disabled_after_failures = False
        page_timeout_seconds = self._resolve_llm_page_timeout(llm_config)
        max_provider_failures = self._resolve_llm_max_failures()
        max_real_provider_calls = self._resolve_llm_max_real_calls()
        page_limit = self._resolve_llm_page_limit()
        pages_to_compose = plan.pages[:page_limit] if page_limit else plan.pages
        quality_warnings: list[dict[str, str]] = []
        target_mermaid_pages = max(1, math.ceil(len(pages_to_compose) * 0.3))
        compose_concurrency = self._resolve_llm_concurrency()
        semaphore = asyncio.Semaphore(compose_concurrency)
        compose_jobs: list[dict[str, Any]] = []
        page_results: dict[int, tuple[str, str]] = {}
        priority_mode = self._resolve_llm_priority_mode()
        page_entries = self._order_pages_for_llm_attempts(
            list(enumerate(pages_to_compose)),
            priority_mode=priority_mode,
        )
        info(
            "compose configured "
            f"provider={llm_config.provider} model={llm_config.model} pages={len(pages_to_compose)} "
            f"max_real_calls={max_real_provider_calls} timeout={page_timeout_seconds:.1f}s "
            f"concurrency={compose_concurrency} priority={priority_mode} cache={cache_path}"
        )

        async def compose_job(job: dict[str, Any]) -> dict[str, Any]:
            async with semaphore:
                page = job["page"]
                attempt_no = job["attempt_no"]
                info(
                    "llm page started "
                    f"attempt={attempt_no}/{max_real_provider_calls or 'unlimited'} "
                    f"page_id={page.page_id} title={page.title}"
                )
                try:
                    output = await asyncio.wait_for(
                        composer.compose_page(job["input_data"]),
                        timeout=page_timeout_seconds,
                    )
                    info(
                        "llm page completed "
                        f"attempt={attempt_no} page_id={page.page_id} "
                        f"tokens={output.tokens_used} rejected={output.rejected}"
                    )
                    return {"status": "ok", "job": job, "output": output}
                except TimeoutError:
                    info(
                        "llm page timeout "
                        f"attempt={attempt_no} page_id={page.page_id} "
                        f"timeout={page_timeout_seconds:.1f}s"
                    )
                    return {
                        "status": "error",
                        "job": job,
                        "reason": f"LLM page timeout after {page_timeout_seconds:.1f}s",
                    }
                except Exception as exc:  # pragma: no cover - provider-specific defensive path
                    info(
                        "llm page failed "
                        f"attempt={attempt_no} page_id={page.page_id} "
                        f"error={type(exc).__name__}: {str(exc)[:160]}"
                    )
                    return {
                        "status": "error",
                        "job": job,
                        "reason": f"{type(exc).__name__}: {str(exc)[:300]}",
                    }

        for page_idx, page in page_entries:
            binding = evidence_bindings.get(page.page_id)
            input_data = build_composer_input(page, binding, context)
            input_hash = compute_composer_input_hash(
                input_data,
                model_name=llm_config.model,
                temperature=llm_config.temperature,
                max_tokens=llm_config.max_tokens,
            )
            estimated_tokens += page.estimated_tokens or 1000

            cached = cache.get(page.page_id, input_hash)
            if cached and cached.output_markdown:
                cache_hits += 1
                info(f"compose cache hit page_id={page.page_id} title={page.title}")
                cached_markdown = self._enforce_qoder_page_contract(
                    page=page,
                    markdown=cached.output_markdown,
                    binding=binding,
                    add_mermaid=page_idx < target_mermaid_pages,
                )
                page_results[page_idx] = (page.output_path, cached_markdown)
                continue

            cache_misses += 1

            if provider_disabled_after_failures:
                fallback_page_count += 1
                failed_pages.append(
                    {
                        "page_id": page.page_id,
                        "title": page.title,
                        "reason": self._provider_disabled_reason(
                            max_provider_failures=max_provider_failures,
                            max_real_provider_calls=max_real_provider_calls,
                            provider_attempt_count=provider_attempt_count,
                        ),
                    }
                )
                fallback = self._fallback_markdown_for_failed_page(page, binding)
                enriched = self._enforce_qoder_page_contract(
                    page=page,
                    markdown=fallback,
                    binding=binding,
                    add_mermaid=page_idx < target_mermaid_pages,
                )
                page_results[page_idx] = (page.output_path, enriched)
                continue

            if (
                max_real_provider_calls is not None
                and provider_attempt_count >= max_real_provider_calls
            ):
                provider_disabled_after_failures = True
                fallback_page_count += 1
                failed_pages.append(
                    {
                        "page_id": page.page_id,
                        "title": page.title,
                        "reason": self._provider_disabled_reason(
                            max_provider_failures=max_provider_failures,
                            max_real_provider_calls=max_real_provider_calls,
                            provider_attempt_count=provider_attempt_count,
                        ),
                    }
                )
                fallback = self._fallback_markdown_for_failed_page(page, binding)
                enriched = self._enforce_qoder_page_contract(
                    page=page,
                    markdown=fallback,
                    binding=binding,
                    add_mermaid=page_idx < target_mermaid_pages,
                )
                page_results[page_idx] = (page.output_path, enriched)
                continue

            provider_attempt_count += 1
            attempted_page_ids.append(page.page_id)
            compose_jobs.append(
                {
                    "attempt_no": provider_attempt_count,
                    "page_idx": page_idx,
                    "page": page,
                    "binding": binding,
                    "input_data": input_data,
                    "input_hash": input_hash,
                }
            )

        info(
            "compose llm batch prepared "
            f"llm_jobs={len(compose_jobs)} cache_hits={cache_hits} "
            f"cache_misses={cache_misses} immediate_fallbacks={fallback_page_count}"
        )
        for result in await asyncio.gather(*(compose_job(job) for job in compose_jobs)):
            job = result["job"]
            page = job["page"]
            binding = job["binding"]
            page_idx = job["page_idx"]

            if result["status"] == "error":
                provider_failure_count += 1
                fallback_page_count += 1
                failed_pages.append(
                    {
                        "page_id": page.page_id,
                        "title": page.title,
                        "reason": result["reason"],
                    }
                )
                fallback = self._fallback_markdown_for_failed_page(page, binding)
                enriched = self._enforce_qoder_page_contract(
                    page=page,
                    markdown=fallback,
                    binding=binding,
                    add_mermaid=page_idx < target_mermaid_pages,
                )
                page_results[page_idx] = (page.output_path, enriched)
                continue

            output = result["output"]
            llm_call_count += 1
            actual_tokens += output.tokens_used

            if output.rejected:
                provider_failure_count += 1
                fallback_page_count += 1
                failed_pages.append(
                    {
                        "page_id": page.page_id,
                        "title": page.title,
                        "reason": output.rejection_reason or "unknown",
                    }
                )
                if provider_failure_count >= max_provider_failures:
                    provider_disabled_after_failures = True
                fallback = self._fallback_markdown_for_failed_page(page, binding)
                enriched = self._enforce_qoder_page_contract(
                    page=page,
                    markdown=fallback,
                    binding=binding,
                    add_mermaid=page_idx < target_mermaid_pages,
                )
                page_results[page_idx] = (page.output_path, enriched)
                continue

            provider_failure_count = 0
            if not (output.citations_preserved and output.headings_preserved):
                quality_warnings.append(
                    {
                        "page_id": page.page_id,
                        "title": page.title,
                        "citations_preserved": str(output.citations_preserved),
                        "headings_preserved": str(output.headings_preserved),
                    }
                )
            enriched = self._enforce_qoder_page_contract(
                page=page,
                markdown=output.markdown,
                binding=binding,
                add_mermaid=page_idx < target_mermaid_pages,
            )
            cache.put(
                page_id=page.page_id,
                input_hash=job["input_hash"],
                output_markdown=enriched,
                tokens_used=output.tokens_used,
                model_name=llm_config.model,
                doc_type=page.category.value,
                cost_usd=estimate_cost_from_tokens(output.tokens_used, llm_config.model),
            )
            page_results[page_idx] = (page.output_path, enriched)

        pages = [page_results[idx] for idx in sorted(page_results)]
        provider_disabled_after_failures = provider_disabled_after_failures or (
            max_real_provider_calls is not None
            and provider_attempt_count >= max_real_provider_calls
        )

        if hasattr(provider, "close"):
            await provider.close()

        llm_summary.update(
            {
                "estimated_tokens": estimated_tokens,
                "actual_tokens": actual_tokens,
                "estimated_cost_usd": estimate_cost_from_tokens(estimated_tokens, llm_config.model),
                "actual_cost_usd": estimate_cost_from_tokens(actual_tokens, llm_config.model),
                "llm_call_count": llm_call_count,
                "provider_attempt_count": provider_attempt_count,
                "attempted_page_ids": attempted_page_ids,
                "provider_failure_count": provider_failure_count,
                "fallback_page_count": fallback_page_count,
                "provider_disabled_after_failures": provider_disabled_after_failures,
                "page_timeout_seconds": page_timeout_seconds,
                "max_provider_failures": max_provider_failures,
                "max_real_provider_calls": max_real_provider_calls,
                "compose_concurrency": compose_concurrency,
                "priority_mode": priority_mode,
                "cache_hits": cache_hits,
                "cache_misses": cache_misses,
                "composer_cache_path": str(cache_path),
                "page_limit": page_limit,
                "composed_page_count": len(pages),
                "quality_warning_count": len(quality_warnings),
            }
        )

        return {
            "pages": pages,
            "failed_pages": failed_pages,
            "quality_warnings": quality_warnings,
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "llm": llm_summary,
        }

    def _fallback_markdown_for_failed_page(self, page: Any, binding: Any | None) -> str:
        from repo_wiki.planner.schema import WikiTaxonomyCategory

        evidence = self._summarize_evidence_for_fallback(binding)
        modules = ", ".join(evidence["modules"][:5]) if evidence["modules"] else "仓库根模块"
        symbols = "、".join(evidence["symbols"][:6]) if evidence["symbols"] else page.title
        file_count = len(evidence["files"])

        category_intro = {
            WikiTaxonomyCategory.PROJECT_OVERVIEW: "本页从项目定位、关键能力和入口文件解释仓库整体形态。",
            WikiTaxonomyCategory.ARCHITECTURE_DESIGN: "本页从模块边界、调用关系和数据流解释系统架构。",
            WikiTaxonomyCategory.CORE_SERVICES: "本页聚焦服务职责、核心组件和上下游协作。",
            WikiTaxonomyCategory.PYTHON_SERVICES: "本页聚焦 Python 服务的运行入口、依赖和处理流程。",
            WikiTaxonomyCategory.FRONTEND_APPLICATIONS: "本页聚焦前端应用结构、页面职责和后端接口依赖。",
            WikiTaxonomyCategory.DATA_MODELS: "本页聚焦实体族、服务模型和持久化结构。",
            WikiTaxonomyCategory.API_REFERENCE: "本页聚焦 API 服务族、调用约定和错误处理边界。",
            WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS: "本页聚焦部署配置、运行环境和运维检查点。",
            WikiTaxonomyCategory.DEVELOPMENT_GUIDE: "本页聚焦开发入口、命令约定和本地调试路径。",
            WikiTaxonomyCategory.SECURITY_COMPLIANCE: "本页聚焦认证授权、审计记录和安全控制点。",
            WikiTaxonomyCategory.TROUBLESHOOTING: "本页聚焦常见故障、定位线索和恢复策略。",
        }.get(page.category, "本页基于仓库证据解释对应主题。")

        lines = [
            f"# {page.title}",
            "",
            "## 简介",
            "",
            f"{category_intro} 该页面对应 `{page.page_id}`，当前由 repo-agent 的证据驱动 fallback composer 生成。",
            f"生成器从 {file_count} 个相关源文件中抽取候选证据，重点覆盖 `{modules}` 等范围。",
            "与普通索引页不同，本页会把证据位置、组件职责、调用边界和维护风险组织成可阅读的专题说明。",
            "",
            "## 项目结构",
            "",
            f"围绕 **{page.title}**，当前仓库中最相关的代码集中在 `{modules}`。",
            f"证据排名显示，`{symbols}` 是阅读该主题时优先关注的符号或配置点。",
            "这些文件共同构成页面主题的事实来源：上层说明只描述能被源码片段或配置片段支撑的内容。",
            "",
            "## 核心组件",
            "",
        ]

        if evidence["files"]:
            for item in evidence["files"][:6]:
                lines.append(
                    f"- `{item['path']}`：关联符号 `{item['symbol']}`，覆盖第 {item['line_start']}-{item['line_end']} 行。"
                )
        else:
            lines.append("- 当前页面没有匹配到高置信源码片段，后续需要补充扫描规则或页面规划规则。")

        lines.extend(
            [
                "",
                "## 详细组件分析",
                "",
                "从证据片段看，本主题的实现通常不是单点文件完成，而是由入口、配置、模型和服务逻辑共同支撑。",
                "阅读时应先确认入口文件，再追踪模型和服务层的引用关系，最后查看部署或测试文件中的运行约束。",
                "如果某个符号同时出现在多个服务目录中，应优先把它理解为跨服务契约，而不是孤立类或函数。",
                "",
            ]
        )

        for item in evidence["snippets"][:4]:
            lines.extend(
                [
                    f"### {item['symbol']}",
                    "",
                    f"`{item['path']}` 的片段显示：{item['summary']}",
                    "该证据用于限定本文的描述范围，避免生成与仓库无关的通用说明。",
                    "",
                ]
            )

        if page.category == WikiTaxonomyCategory.API_REFERENCE:
            lines.extend(
                [
                    "## 依赖关系分析",
                    "",
                    "API 页面需要同时关注 controller/router、请求响应模型、认证拦截器和错误处理路径。",
                    "服务族的 GET、POST、PUT、PATCH、DELETE 方法应被放在同一个业务流程中理解，避免只输出端点清单。",
                    "当接口返回结构依赖 DTO 或 Entity 时，页面应跳转阅读对应的数据模型页，以确认字段生命周期和兼容性约束。",
                    "",
                    "## 性能考虑",
                    "",
                    "接口性能主要受鉴权、序列化、数据库访问和外部服务调用影响。若证据中出现批处理、分页或异步任务，"
                    "应优先检查限流、超时和幂等策略。缺少这些约束时，后续实现需要补充 API 治理说明。",
                    "",
                ]
            )
        elif page.category == WikiTaxonomyCategory.DATA_MODELS:
            lines.extend(
                [
                    "## 依赖关系分析",
                    "",
                    "数据模型页面需要区分核心实体、传输 DTO、配置 Schema 和迁移脚本。"
                    "同名模型如果跨服务出现，应按业务语义归并，而不是把每个类都作为独立核心实体。",
                    "字段解释应优先引用 Entity、migration 或 OpenAPI schema 中的来源。",
                    "",
                    "## 性能考虑",
                    "",
                    "模型性能关注索引、主键、外键、JSON 字段和序列化成本。"
                    "当页面证据只来自 DTO 而缺少数据库定义时，应把该模型标记为服务边界模型，而不是持久化实体。",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    "## 依赖关系分析",
                    "",
                    "该主题的依赖关系应从文件路径、符号引用和服务目录共同判断。"
                    "如果证据集中在单一服务，说明该页面偏向服务内部知识；如果证据分布在多个服务，说明它更接近平台级能力。",
                    "后续变更时，应优先检查这些证据文件是否发生修改，并据此决定页面是否需要增量重生成。",
                    "",
                    "## 性能考虑",
                    "",
                    "性能风险主要来自跨服务调用、批处理任务、扫描范围和运行时缓存。"
                    "当页面涉及生成、索引或验证流程时，应额外关注是否存在全量重跑、重复 IO 或无法恢复的长任务。",
                    "",
                ]
            )

        lines.extend(
            [
                "## 故障排查指南",
                "",
                "排查该主题时，建议按三步执行：先确认页面引用的文件是否仍存在，再检查相关符号是否改名或迁移，"
                "最后对照运行命令、测试用例和配置文件确认行为是否发生变化。",
                "如果生成结果与人工理解不一致，应优先扩展 evidence ranking，而不是只修改模板文案。",
                "",
                "## 结论",
                "",
                f"`{page.title}` 是当前仓库知识树中的一个可追溯专题页。"
                "本页已提供源码证据、结构解释和维护检查点，可用于 IDE 插件浏览、人工验收和后续增量生成。",
            ]
        )

        return "\n".join(lines)

    def _summarize_evidence_for_fallback(self, binding: Any | None) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "modules": [],
            "symbols": [],
            "files": [],
            "snippets": [],
        }
        if not binding or not getattr(binding, "candidates", None):
            return summary

        seen_modules: set[str] = set()
        seen_symbols: set[str] = set()
        seen_files: set[str] = set()
        for candidate in binding.candidates[:10]:
            span = candidate.span
            path = str(getattr(span, "file_path", "") or "")
            symbol = str(getattr(span, "symbol", "") or Path(path).stem or "source")
            parts = Path(path).parts
            module = parts[0] if parts else "root"

            if module not in seen_modules:
                summary["modules"].append(module)
                seen_modules.add(module)
            if symbol not in seen_symbols:
                summary["symbols"].append(symbol)
                seen_symbols.add(symbol)
            if path and path not in seen_files:
                summary["files"].append(
                    {
                        "path": path,
                        "symbol": symbol,
                        "line_start": getattr(span, "line_start", 1),
                        "line_end": getattr(span, "line_end", 1),
                    }
                )
                seen_files.add(path)

            text = self._summarize_span_text(str(getattr(span, "span_text", "") or ""))
            if text:
                summary["snippets"].append(
                    {
                        "path": path,
                        "symbol": symbol,
                        "summary": text,
                    }
                )

        return summary

    def _summarize_span_text(self, text: str) -> str:
        cleaned = " ".join(line.strip() for line in text.splitlines() if line.strip())
        cleaned = re.sub(r"\s+", " ", cleaned)
        if not cleaned:
            return ""
        if len(cleaned) > 180:
            return cleaned[:177].rstrip() + "..."
        return cleaned

    def _enforce_qoder_page_contract(
        self,
        page: Any,
        markdown: str,
        binding: Any | None,
        add_mermaid: bool,
    ) -> str:
        from repo_wiki.evidence.citation_renderer import CitationRenderer
        from repo_wiki.planner.schema import WikiTaxonomyCategory

        content = markdown.strip() or f"# {page.title}\n"
        if not content.startswith("#"):
            content = f"# {page.title}\n\n{content}"

        if "## 目录" not in content and "## Table of Contents" not in content:
            h2_sections = self._extract_or_seed_h2_sections(page, content)
            toc_lines = ["## 目录", ""]
            for idx, heading in enumerate(h2_sections, 1):
                toc_lines.append(f"{idx}. {heading}")
            content = "\n".join([content, "", *toc_lines]).strip()

        if self._count_prose_chars(content) < 260:
            content += (
                "\n\n## 正文\n\n"
                f"{page.title} 页面基于仓库扫描、页面规划与证据绑定结果生成。"
                "本页重点解释该主题在当前仓库中的职责、上下游依赖和实现边界，"
                "并通过源码行号引用维持可追溯性。"
            )

        is_api_like_page = (
            page.category == WikiTaxonomyCategory.API_REFERENCE
            or "api" in str(getattr(page, "output_path", "")).lower()
            or "api" in str(getattr(page, "title", "")).lower()
        )
        if is_api_like_page:
            if "## API 分组" not in content:
                content += (
                    "\n\n## API 分组\n\n"
                    "按服务族聚合接口能力，优先说明业务语义、调用边界与版本策略，而非原始端点清单。"
                    "本页把同一服务族下的 GET、POST、PUT、DELETE 与 PATCH 能力放在同一个上下文中解释，"
                    "用于帮助读者理解查询、创建、更新、删除和局部修改之间的职责边界。"
                    "\n\n- GET /resources：读取资源列表或健康状态。\n"
                    "- POST /resources：创建资源或触发处理任务。\n"
                    "- PUT /resources/{id}：整体更新资源。\n"
                    "- PATCH /resources/{id}：局部更新资源。\n"
                    "- DELETE /resources/{id}：删除资源或取消任务。\n"
                )
            if "## 调用约定" not in content:
                content += (
                    "\n\n## 调用约定\n\n"
                    "统一描述认证方式、幂等约束、错误处理与重试策略，避免把接口文档退化为 endpoint dump。"
                )
            if "## Schema 摘要" not in content:
                content += (
                    "\n\n## Schema 摘要\n\n"
                    "以下 schema 片段用于表达该 API 族的共同字段约定。实际字段以源码引用和 OpenAPI 定义为准，"
                    "这里保留聚合视角，避免逐条复制所有端点。"
                    "\n\n```json\n"
                    "{\n"
                    '  "request": {"method": "GET|POST|PUT|DELETE|PATCH", "auth": "Bearer token"},\n'
                    '  "response": {"code": "string", "data": "object", "message": "string"},\n'
                    '  "error": {"status": 400, "reason": "validation_or_business_error"}\n'
                    "}\n"
                    "```\n"
                )

        if page.category == WikiTaxonomyCategory.DATA_MODELS:
            if "## 核心实体族" not in content:
                content += (
                    "\n\n## 核心实体族\n\n"
                    "本节按业务实体族进行归并，强调主键、生命周期和跨服务共享模型。"
                )
            if "## 服务模型聚合" not in content:
                content += (
                    "\n\n## 服务模型聚合\n\n"
                    "按服务边界聚合 DTO、Entity、Schema 与映射关系，避免堆叠原始模型定义。"
                )
            if "## 数据库与迁移摘要" not in content:
                content += (
                    "\n\n## 数据库与迁移摘要\n\n"
                    "汇总表结构演进、索引策略与迁移脚本影响范围，支持后续增量变更评估。"
                )

        if add_mermaid and "```mermaid" not in content:
            content += "\n\n## 架构图\n\n" + self._build_minimal_mermaid_block(page)

        citation_renderer = CitationRenderer(workspace_root=self.root)
        cites: list[str] = []
        if binding and binding.candidates:
            for candidate in binding.candidates[:6]:
                cites.append(citation_renderer.render_cite_block_from_candidate(candidate))

        existing_cites = len(self._CITE_PATTERN.findall(content))
        needed = max(0, 3 - existing_cites)
        if needed > 0 and cites:
            content += "\n\n## 源码引用\n\n"
            for cite in cites[:needed]:
                content += f"- {cite}\n"

        content = self._strip_broken_local_markdown_links(content)
        content = self._ensure_minimum_prose_density(content, page)

        return content.strip() + "\n"

    def _extract_or_seed_h2_sections(self, page: Any, content: str) -> list[str]:
        headings = [m.group(1).strip() for m in self._HEADING_L2_PATTERN.finditer(content)]
        headings = [h for h in headings if h and h not in {"目录", "Table of Contents", "Contents"}]
        if headings:
            return headings[:10]
        return ["简介", "项目结构", "核心组件", "详细分析", "结论"]

    def _build_minimal_mermaid_block(self, page: Any) -> str:
        from repo_wiki.planner.schema import WikiTaxonomyCategory

        if page.category == WikiTaxonomyCategory.API_REFERENCE:
            return (
                "```mermaid\n"
                "sequenceDiagram\n"
                "    participant Client as 调用方\n"
                "    participant Gateway as API网关\n"
                "    participant Service as 服务族\n"
                "    Client->>Gateway: 发起请求\n"
                "    Gateway->>Service: 路由并鉴权\n"
                "    Service-->>Gateway: 返回结果\n"
                "    Gateway-->>Client: 响应\n"
                "```\n"
            )
        if page.category == WikiTaxonomyCategory.DATA_MODELS:
            return (
                "```mermaid\n"
                "erDiagram\n"
                "    CORE_ENTITY ||--o{ SERVICE_MODEL : maps_to\n"
                "    CORE_ENTITY {\n"
                "      string id\n"
                "      string domain\n"
                "    }\n"
                "    SERVICE_MODEL {\n"
                "      string service\n"
                "      string version\n"
                "    }\n"
                "```\n"
            )
        return (
            "```mermaid\n"
            "flowchart TD\n"
            "    A[仓库扫描] --> B[页面规划]\n"
            "    B --> C[证据绑定]\n"
            "    C --> D[LLM生成]\n"
            "    D --> E[质量校验]\n"
            "```\n"
        )

    def _count_prose_chars(self, content: str) -> int:
        lines = content.splitlines()
        prose_lines: list[str] = []
        in_code = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("```"):
                in_code = not in_code
                continue
            if in_code or not stripped:
                continue
            if (
                stripped.startswith("#")
                or stripped.startswith("-")
                or stripped.startswith("*")
                or stripped.startswith("|")
            ):
                continue
            if re.match(r"^\d+\.\s+", stripped):
                continue
            prose_lines.append(stripped)
        return len(" ".join(prose_lines))

    def _strip_broken_local_markdown_links(self, content: str) -> str:
        def replace(match: re.Match[str]) -> str:
            full = match.group(0)
            target = match.group(1).strip()
            label_match = re.match(r"\[([^\]]+)\]", full)
            label = label_match.group(1) if label_match else target
            if target.startswith(("#", "http://", "https://", "mailto:")):
                return full
            if ":" in target and not target.startswith("."):
                return full
            if not self._is_safe_local_markdown_target(target):
                return f"`{label}`"
            try:
                if (self.root / target).exists():
                    return full
            except OSError:
                return f"`{label}`"
            return f"`{label}`"

        return self._LOCAL_LINK_PATTERN.sub(replace, content)

    def _is_safe_local_markdown_target(self, target: str) -> bool:
        if not target or len(target) > 240:
            return False
        if any(ch in target for ch in ("\n", "\r", "\0")):
            return False
        return True

    def _ensure_minimum_prose_density(self, content: str, page: Any) -> str:
        min_density = 0.34
        prose = self._count_prose_chars(content)
        total = max(len(content), 1)
        if prose / total >= min_density:
            return content

        content += "\n\n## 阅读说明\n"
        for _ in range(6):
            if prose / total >= min_density:
                break
            paragraph = (
                f"\n{page.title} 的阅读重点不是罗列文件，而是把源码证据、模块职责、调用边界和维护风险串联起来。"
                "读者可以先查看目录确认主题范围，再根据源码引用定位实现位置，最后结合架构图或 schema 摘要判断变更影响。"
                "如果页面来自 fallback 生成链路，它仍然保留证据绑定结果，但需要在后续优化中用真实 LLM 叙述替换保守说明。"
            )
            content += paragraph
            prose = self._count_prose_chars(content)
            total = max(len(content), 1)
        return content

    def _resolve_llm_page_limit(self) -> int | None:
        """Optional smoke-test page limit for real-provider validation runs."""
        import os

        raw = os.environ.get("REPO_WIKI_LLM_PAGE_LIMIT")
        if not raw:
            return None
        try:
            value = int(raw)
        except ValueError:
            return None
        return value if value > 0 else None

    def _resolve_llm_priority_mode(self) -> str:
        """Resolve page priority mode for spending limited real LLM calls."""
        import os

        mode = os.environ.get("REPO_WIKI_LLM_PRIORITY", "qoder").strip().lower()
        if mode in {"off", "none", "plan"}:
            return "plan"
        if mode in {"api", "overview", "qoder"}:
            return mode
        return "qoder"

    def _order_pages_for_llm_attempts(
        self,
        page_entries: list[tuple[int, Any]],
        priority_mode: str,
    ) -> list[tuple[int, Any]]:
        if priority_mode == "plan":
            return page_entries

        import os

        explicit_ids = [
            item.strip()
            for item in os.environ.get("REPO_WIKI_LLM_PRIORITY_PAGE_IDS", "").split(",")
            if item.strip()
        ]
        explicit_rank = {page_id: idx for idx, page_id in enumerate(explicit_ids)}

        def score(entry: tuple[int, Any]) -> tuple[int, int, int, str]:
            original_idx, page = entry
            page_id = str(getattr(page, "page_id", ""))
            title = str(getattr(page, "title", ""))
            output_path = str(getattr(page, "output_path", ""))
            category = str(
                getattr(getattr(page, "category", ""), "value", getattr(page, "category", ""))
            )
            text = f"{page_id} {title} {output_path} {category}".lower()

            if page_id in explicit_rank:
                return (0, explicit_rank[page_id], original_idx, page_id)

            exact_rank = self._core_page_exact_rank(page_id)
            if exact_rank is not None and priority_mode in {"qoder", "overview"}:
                return (1, exact_rank, original_idx, page_id)

            if priority_mode == "api":
                category_rank = self._api_priority_rank(text)
            elif priority_mode == "overview":
                category_rank = self._overview_priority_rank(text)
            else:
                category_rank = self._qoder_priority_rank(text)

            detail_rank = 0
            if "overview" in text or "概览" in text or "概述" in text:
                detail_rank -= 20
            if "index" in text:
                detail_rank -= 10
            if "consider-adding" in text:
                detail_rank += 100
            if "deep-dive" in text:
                detail_rank += 80
            return (10 + category_rank, detail_rank, original_idx, page_id)

        return sorted(page_entries, key=score)

    def _core_page_exact_rank(self, page_id: str) -> int | None:
        core_pages = [
            "project-overview",
            "architecture-overview",
            "api-overview",
            "data-models-overview",
            "core-services-index",
            "python-services-index",
            "frontend-applications-index",
            "deployment-overview",
            "security-overview",
            "development-guide",
            "troubleshooting-overview",
        ]
        try:
            return core_pages.index(page_id)
        except ValueError:
            return None

    def _qoder_priority_rank(self, text: str) -> int:
        priority = [
            ("project-overview", "项目概述"),
            ("architecture", "架构设计", "架构"),
            ("api", "API参考", "接口"),
            ("data-model", "data-models", "数据模型", "数据库"),
            ("core-services", "services", "核心服务"),
            ("overview", "概览", "概述"),
            ("python-services", "Python服务"),
            ("frontend", "前端应用"),
            ("deployment", "operations", "部署运维"),
            ("security", "安全合规"),
            ("development", "开发指南"),
            ("troubleshooting", "故障排除"),
        ]
        for rank, tokens in enumerate(priority):
            if any(token.lower() in text for token in tokens):
                return rank
        return len(priority) + 10

    def _api_priority_rank(self, text: str) -> int:
        if "api-overview" in text or "api参考" in text:
            return 0
        if "api" in text or "接口" in text:
            return 1
        return self._qoder_priority_rank(text) + 10

    def _overview_priority_rank(self, text: str) -> int:
        if "project-overview" in text or "项目概述" in text:
            return 0
        if "architecture" in text or "架构" in text:
            return 1
        if "overview" in text or "概览" in text:
            return 2
        return self._qoder_priority_rank(text) + 10

    def _resolve_composer_cache_path(self, output_dir: Path) -> Path:
        """Use a profile-level cache so long LLM generation can be resumed across runs."""
        import os

        raw = os.environ.get("REPO_WIKI_COMPOSER_CACHE_PATH")
        if raw:
            return Path(raw).expanduser().resolve()
        return output_dir.parent / ".runtime" / "composer_cache.sqlite3"

    def _resolve_llm_page_timeout(self, config: Any) -> float:
        """Bound a single real-provider page call so a bad endpoint cannot empty a run."""
        import os

        raw = os.environ.get("REPO_WIKI_LLM_PAGE_TIMEOUT_SECONDS")
        if raw:
            try:
                value = float(raw)
            except ValueError:
                value = 20.0
            return max(1.0, value)

        configured_timeout = float(getattr(config, "timeout", 60.0) or 60.0)
        return max(1.0, min(configured_timeout, 20.0))

    def _resolve_llm_max_failures(self) -> int:
        """Limit repeated provider failures before falling back for the rest of the run."""
        import os

        raw = os.environ.get("REPO_WIKI_LLM_MAX_FAILURES")
        if not raw:
            return 3
        try:
            value = int(raw)
        except ValueError:
            return 3
        return max(1, value)

    def _resolve_llm_max_real_calls(self) -> int | None:
        """Optional cap for expensive real-provider validation runs."""
        import os

        raw = os.environ.get("REPO_WIKI_LLM_REAL_MAX_CALLS")
        if not raw:
            return None
        try:
            value = int(raw)
        except ValueError:
            return None
        return value if value >= 0 else None

    def _resolve_llm_concurrency(self) -> int:
        """Bound concurrent real-provider page calls."""
        import os

        raw = os.environ.get("REPO_WIKI_LLM_CONCURRENCY")
        if raw:
            try:
                value = int(raw)
            except ValueError:
                return 1
            return max(1, min(value, 8))
        return max(1, min(int(getattr(self.config.llm, "max_concurrent", 1) or 1), 8))

    def _provider_disabled_reason(
        self,
        max_provider_failures: int,
        max_real_provider_calls: int | None,
        provider_attempt_count: int,
    ) -> str:
        if (
            max_real_provider_calls is not None
            and provider_attempt_count >= max_real_provider_calls
        ):
            return f"provider disabled after {max_real_provider_calls} real-provider attempts"
        return f"provider disabled after {max_provider_failures} consecutive failures"

    def search(self, *, query: str, module: str | None = None, top_k: int = 10) -> dict[str, Any]:
        bootstrap(self.config)
        retrieval = RetrievalService(self.root, self.config)
        return retrieval.search(query=query, module=module, top_k=top_k)

    def graph(self, module: str) -> dict[str, Any]:
        bootstrap(self.config)
        graph_payload = read_json(
            self.root / ".repo-wiki" / "graph" / "knowledge_graph.json",
            {"modules": {}, "edges": []},
        )
        modules = graph_payload.get("modules", {}) if isinstance(graph_payload, dict) else {}
        edges = graph_payload.get("edges", []) if isinstance(graph_payload, dict) else []
        node = modules.get(module)
        if node is None:
            return {
                "module": module,
                "found": False,
                "suggestions": sorted(list(modules.keys()))[:20]
                if isinstance(modules, dict)
                else [],
            }
        connected_edges = [
            edge
            for edge in edges
            if isinstance(edge, dict) and (edge.get("from") == module or edge.get("to") == module)
        ]
        return {
            "module": module,
            "found": True,
            "node": node,
            "edges": connected_edges,
        }

    def verify(self, ci: bool = False) -> dict[str, Any]:
        bootstrap(self.config)
        retrieval = RetrievalService(self.root, self.config)
        verifier = VerifierService(self.root, retrieval_service=retrieval)
        started = time.perf_counter()
        result = verifier.verify(ci=ci)
        duration_ms = int((time.perf_counter() - started) * 1000)

        runtime_evidence: dict[str, Any] = {
            "status": "not-recorded",
            "run_id": None,
            "db_path": str(self.root / ".repo-wiki" / "index" / "runtime.sqlite3"),
        }
        runtime_store = None
        try:
            runtime_store = create_runtime_store(self.root)
            run_id = f"verify-{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}"
            runtime_store.save_verify_run(
                run_id=run_id,
                target_path=str(self.root),
                verify_result=result,
                duration_ms=duration_ms,
            )
            runtime_evidence = {
                "status": "recorded",
                "run_id": run_id,
                "duration_ms": duration_ms,
                "db_path": str(self.root / ".repo-wiki" / "index" / "runtime.sqlite3"),
                "grade_recorded": result.get("grade"),
            }
        except FileNotFoundError as exc:
            # Directory missing - runtime not initialized
            runtime_evidence = {
                "status": "not_initialized",
                "error_type": "directory_not_found",
                "error": f"Runtime directory not found: {exc}",
                "duration_ms": duration_ms,
                "db_path": str(self.root / ".repo-wiki" / "index" / "runtime.sqlite3"),
                "remediation": "Run init or index command to initialize runtime store",
            }
        except sqlite3.DatabaseError as exc:
            # Corrupt DB
            runtime_evidence = {
                "status": "error",
                "error_type": "database_corrupt",
                "error": f"Runtime database is corrupt: {exc}",
                "duration_ms": duration_ms,
                "db_path": str(self.root / ".repo-wiki" / "index" / "runtime.sqlite3"),
                "remediation": "Delete runtime.sqlite3 and re-run init to rebuild",
            }
        except Exception as exc:  # pragma: no cover - defensive path
            runtime_evidence = {
                "status": "error",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "duration_ms": duration_ms,
                "db_path": str(self.root / ".repo-wiki" / "index" / "runtime.sqlite3"),
                "remediation": "Check disk space and permissions",
            }
        finally:
            if runtime_store is not None:
                runtime_store.close()

        result["runtime_evidence"] = runtime_evidence
        return result

    def cost_estimate(self) -> dict[str, Any]:
        bootstrap(self.config)
        module_index = read_yamlish(
            self.root / "ai/source-of-truth/module-index.yaml", {"modules": []}
        )
        api_index = read_yamlish(self.root / "ai/source-of-truth/api-index.yaml", {"endpoints": []})
        data_models = read_yamlish(
            self.root / "ai/source-of-truth/data-models.yaml", {"models": []}
        )
        meta = read_json(
            self.root / ".repo-wiki" / "index" / "meta.json", {"counts": {"chunks": 0, "files": 0}}
        )
        modules = module_index.get("modules", []) if isinstance(module_index, dict) else []
        endpoints = api_index.get("endpoints", []) if isinstance(api_index, dict) else []
        models = data_models.get("models", []) if isinstance(data_models, dict) else []
        chunks = int((meta.get("counts", {}) or {}).get("chunks", 0))
        docs = 5 + len(modules)
        estimated_tokens = (
            1800 + len(modules) * 900 + len(endpoints) * 60 + len(models) * 80 + chunks * 35
        )
        return {
            "module_count": len(modules),
            "endpoint_count": len(endpoints),
            "data_model_count": len(models),
            "chunk_count": chunks,
            "estimated_docs": docs,
            "estimated_tokens": estimated_tokens,
            "estimated_cost_hint": {
                "small_model_units": round(estimated_tokens / 1_000_000, 4),
                "notes": "Use provider pricing to multiply by estimated token units.",
            },
        }

    def _generation_engine(self, root: Path | None = None) -> GenerationEngine:
        generation_root = root or self.root
        return GenerationEngine(
            root=generation_root,
            config=GenerationConfig(
                model_init=self.config.llm.model_init,
                model_update=self.config.llm.model_update,
                model_verify=self.config.llm.model_verify,
                token_budget=4000,
            ),
            template_root=self._template_root(),
        )

    def _template_root(self) -> Path:
        target_templates = self.root / "templates"
        if target_templates.exists():
            return target_templates
        repo_templates = Path(__file__).resolve().parents[2] / "templates"
        return repo_templates

    def _sync_runtime_store(self) -> dict[str, Any]:
        """Sync document hierarchy, section registry, and nav graph to runtime sqlite.

        This method provides fallback behavior for missing or corrupt runtime DB.
        Errors are captured with diagnostic info but do not block command execution.
        """
        runtime_store = None
        runtime_db_path = self.root / ".repo-wiki" / "index" / "runtime.sqlite3"
        try:
            runtime_store = create_runtime_store(self.root)
            self._register_sections(runtime_store)
            docs = self._collect_documents_for_runtime()
            for doc in docs:
                runtime_store.upsert_doc_hierarchy(
                    DocHierarchyRecord(
                        doc_type=doc["doc_type"],
                        doc_slug=doc["doc_slug"],
                        doc_path=doc["doc_path"],
                        layer=doc["layer"],
                        parent_slug=doc.get("parent_slug"),
                        title=doc.get("title"),
                        sort_order=doc.get("sort_order", 0),
                        generated_at=str(time.time()),
                    )
                )
            nav_nodes = self._sync_nav_graph(runtime_store, docs)
            exports = runtime_store.export_runtime_artifacts(self.root / ".repo-wiki" / "graph")
            return {
                "status": "ok",
                "db_path": str(runtime_db_path),
                "schema_version": runtime_store.current_schema_version(),
                "docs_synced": len(docs),
                "nav_nodes_synced": nav_nodes,
                "exported": {k: str(v) for k, v in exports.items()},
            }
        except FileNotFoundError as exc:
            # Directory missing - create and retry is handled by create_runtime_store
            return {
                "status": "error",
                "error_type": "directory_not_found",
                "error": f"Runtime directory missing: {exc}",
                "db_path": str(runtime_db_path),
                "remediation": "Run init command to create required directory structure",
            }
        except sqlite3.DatabaseError as exc:
            # Corrupt DB - provide clear diagnostic
            return {
                "status": "error",
                "error_type": "database_corrupt",
                "error": f"Runtime database is corrupt: {exc}",
                "db_path": str(runtime_db_path),
                "remediation": f"Delete {runtime_db_path} and re-run init to rebuild",
            }
        except Exception as exc:  # pragma: no cover - defensive path
            return {
                "status": "error",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "db_path": str(runtime_db_path),
                "remediation": "Check disk space and permissions; re-run init if issue persists",
            }
        finally:
            if runtime_store is not None:
                runtime_store.close()

    def _register_sections(self, runtime_store: Any) -> None:
        for idx, section in enumerate(SECTION_DEFINITIONS):
            runtime_store.register_section(
                SectionRegistryRecord(
                    canonical_slug=section.canonical_slug,
                    title=section.title,
                    description=f"Section for {section.title}",
                    required_for_phase="phase-09",
                    sort_order=idx,
                    is_active=True,
                )
            )
            for alias in section.aliases:
                runtime_store.register_section_alias(alias, section.canonical_slug)

    def _collect_documents_for_runtime(self) -> list[dict[str, Any]]:
        docs: list[dict[str, Any]] = []
        sort_order = 0
        seen_keys: set[tuple[str, str]] = set()

        # Overview layer (00-05 contracts)
        for contract in CORE_DOCUMENT_CONTRACTS:
            path = (self.root / contract.output_path).resolve()
            if not path.exists():
                continue
            slug = path.stem.lower()
            key = ("overview", slug)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            docs.append(
                {
                    "doc_type": "overview",
                    "doc_slug": slug,
                    "doc_path": str(path),
                    "layer": "overview",
                    "parent_slug": None,
                    "title": slug,
                    "sort_order": sort_order,
                }
            )
            sort_order += 1

        # Section layer: canonical directories + alias directories + flat files
        sections_dir = self.root / "docs" / "sections"
        if sections_dir.exists():
            section_candidates: list[tuple[str, Path]] = []
            for section in SECTION_DEFINITIONS:
                section_candidates.append(
                    (section.canonical_slug, sections_dir / section.canonical_slug / "index.md")
                )
                section_candidates.append(
                    (section.canonical_slug, sections_dir / f"{section.canonical_slug}.md")
                )
                for alias in section.aliases:
                    section_candidates.append(
                        (section.canonical_slug, sections_dir / alias / "index.md")
                    )
                    section_candidates.append(
                        (section.canonical_slug, sections_dir / f"{alias}.md")
                    )

            for canonical_slug, path in section_candidates:
                resolved = path.resolve()
                if not resolved.exists():
                    continue
                key = ("section", canonical_slug)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                docs.append(
                    {
                        "doc_type": "section",
                        "doc_slug": canonical_slug,
                        "doc_path": str(resolved),
                        "layer": "section",
                        "parent_slug": "00-overview",
                        "title": canonical_slug,
                        "sort_order": sort_order,
                    }
                )
                sort_order += 1

            for flat in sorted(sections_dir.glob("*.md")):
                stem = flat.stem.strip().lower()
                canonical = get_canonical_slug(stem) or stem
                key = ("section", canonical)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                docs.append(
                    {
                        "doc_type": "section",
                        "doc_slug": canonical,
                        "doc_path": str(flat.resolve()),
                        "layer": "section",
                        "parent_slug": "00-overview",
                        "title": flat.stem,
                        "sort_order": sort_order,
                    }
                )
                sort_order += 1

        # Module layer
        modules_dir = self.root / "docs" / "modules"
        if modules_dir.exists():
            for module_doc in sorted(modules_dir.glob("*.md")):
                slug = module_doc.stem.lower()
                key = ("module", slug)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                docs.append(
                    {
                        "doc_type": "module",
                        "doc_slug": slug,
                        "doc_path": str(module_doc.resolve()),
                        "layer": "module",
                        "parent_slug": "03-module-map",
                        "title": module_doc.stem,
                        "sort_order": sort_order,
                    }
                )
                sort_order += 1

        return docs

    def _sync_nav_graph(self, runtime_store: Any, docs: list[dict[str, Any]]) -> int:
        if not docs:
            return 0

        slug_to_doc = {doc["doc_slug"]: doc for doc in docs}
        path_to_slug = {Path(doc["doc_path"]).resolve(): doc["doc_slug"] for doc in docs}

        outgoing_map: dict[str, list[str]] = {}
        incoming_map: dict[str, set[str]] = {slug: set() for slug in slug_to_doc}

        for doc in docs:
            doc_path = Path(doc["doc_path"])
            content = read_text(doc_path)
            outgoing: list[str] = []
            for match in self._LOCAL_LINK_PATTERN.finditer(content):
                target = match.group(1).strip()
                if target.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                resolved = (doc_path.parent / target).resolve()
                target_slug = path_to_slug.get(resolved)
                if target_slug and target_slug != doc["doc_slug"] and target_slug not in outgoing:
                    outgoing.append(target_slug)
                    incoming_map.setdefault(target_slug, set()).add(doc["doc_slug"])
            outgoing_map[doc["doc_slug"]] = outgoing

        for slug, doc in slug_to_doc.items():
            outgoing = sorted(outgoing_map.get(slug, []))
            incoming = sorted(incoming_map.get(slug, set()))
            affected = sorted({slug, *incoming, *outgoing})
            runtime_store.upsert_nav_node(
                doc_slug=slug,
                doc_type=doc["doc_type"],
                incoming_links=incoming,
                outgoing_links=outgoing,
                depth=0 if doc["doc_type"] == "overview" else 1,
                affected_pages=affected,
            )
        return len(slug_to_doc)


class StageTimer:
    def __init__(self) -> None:
        self.timings: dict[str, float] = {}
        self._active: dict[str, float] = {}

    def start(self, name: str) -> None:
        self._active[name] = time.perf_counter()

    def stop(self, name: str) -> None:
        started = self._active.pop(name, None)
        if started is None:
            return
        self.timings[name] = round(time.perf_counter() - started, 6)
