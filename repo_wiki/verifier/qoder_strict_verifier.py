"""Strict verifier for qoder-like profile."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from repo_wiki.evidence.citation_renderer import (
    is_placeholder_citation_ref,
    normalize_citation_ref,
)
from repo_wiki.verifier.service import CheckResult, GateType, SeverityThreshold, VerifierService


class QoderLikeSeverityThreshold(SeverityThreshold):
    """Strict severity thresholds for qoder-like profile."""

    STRICT_HARD_CODES = {
        "QODER_CONTENT_EMPTY",
        "QODER_CITATION_MISSING",
        "QODER_CITATION_RELEVANCE_MISMATCH",
        "QODER_TOC_MISSING",
        "QODER_FILE_REF_BROKEN",
        "QODER_PAGE_DUMP",
        "QODER_PROSE_TOO_LOW",
        "QODER_FILE_LINE_REF_LOW",
        "QODER_MERMAID_LOW",
        "QODER_API_AGGREGATION_LOW",
        "QODER_DATA_MODEL_AGGREGATION_LOW",
        "QODER_STALE_GIT_COMMIT",
        "QODER_DIRTY_WORKTREE",
        "QODER_ENDPOINT_PAGE_DUMP",
        "QODER_RAW_MODEL_PAGE_DUMP",
        "QODER_MANIFEST_NOT_READY",
        "QODER_MANIFEST_PATH_INVALID",
        "QODER_CONTENT_ROOT_MISSING",
        "QODER_META_ROOT_MISSING",
        "QODER_REPORT_MISMATCH",
        "QODER_API_MERMAID_MISSING",
        "QODER_ENDPOINT_LIFECYCLE_MERMAID_MISSING",
        "QODER_DATA_MODEL_ER_MERMAID_MISSING",
        "QODER_MANIFEST_MISSING",
        "QODER_QUALITY_ARTIFACT_MISSING",
        "QODER_QUALITY_ARTIFACT_INVALID",
        "QODER_PAGE_QUALITY_STATE_MISSING",
        "QODER_PAGE_QUALITY_STATE_DEGRADED",
        "QODER_UNRESOLVED_FACT_CONFLICT",
        "QODER_CRITICAL_FALSE_FACT",
        "QODER_CITATION_INVALID",
        "QODER_CITATION_FACT_COVERAGE_LOW",
        "QODER_REQUIRED_INVENTORY_MISSING",
        "QODER_OWNER_COVERAGE_MISSING",
        "QODER_CONFLICT_ARTIFACT_MISSING",
        "QODER_CONFLICT_ARTIFACT_INVALID",
        "SOURCE_DOC_MISMATCH",
        "STALE_DOC_REFERENCE",
        "UNSUPPORTED_DOC_CLAIM",
        "MISSING_SOURCE_CONFIRMATION",
    }

    STRICT_SOFT_TO_HARD = {
        "CONTENT_LIST_ONLY",
        "CONTENT_TOO_SHORT",
        "CONTENT_MISSING_SECTIONS",
        "AGG_API_NOT_GROUPED",
        "AGG_API_ENDPOINT_DUMP",
        "AGG_DM_NOT_GROUPED",
        "AGG_DM_MODEL_DUMP",
        "CITATION_MISSING",
        "CITATION_BROKEN_PATH",
    }

    def __init__(self, warn_on_soft: bool = False, fail_on_hard: bool = True) -> None:
        self.warn_on_soft = warn_on_soft
        self.fail_on_hard = fail_on_hard

    def get_gate_type(self, reason_code: str) -> GateType:
        if reason_code in self.STRICT_HARD_CODES:
            return GateType.HARD
        if reason_code in self.STRICT_SOFT_TO_HARD:
            return GateType.HARD
        return GateType.HARD

    def is_blocking(self, reason_code: str) -> bool:
        return self.get_gate_type(reason_code) == GateType.HARD


class QoderLikeVerifierService(VerifierService):
    """Strict verifier focused on qoder-like `content/**` outputs."""

    LOCAL_MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]\n]+\]\(([^)\n]+)\)")
    MIN_PROSE_DENSITY = 0.30
    MAX_LIST_RATIO = 0.6
    MIN_TOC_COVERAGE = 0.8
    MIN_FILE_LINE_COVERAGE = 0.7
    MIN_MERMAID_COVERAGE = 0.3
    MERMAID_CODE_BLOCK_PATTERN = re.compile(r"```mermaid\s*(.*?)```", re.IGNORECASE | re.DOTALL)

    def __init__(self, root: Path, retrieval_service=None, strict: bool = True) -> None:
        super().__init__(
            root,
            retrieval_service,
            severity_thresholds=QoderLikeSeverityThreshold(warn_on_soft=not strict),
        )
        self.strict = strict

    def verify(self, ci: bool = True) -> dict[str, Any]:
        checks: list[CheckResult] = [
            self._check_qoder_manifest_readiness_contract(),
            self._check_qoder_quality_artifacts(),
            self._check_qoder_unresolved_fact_conflicts(),
            self._check_qoder_critical_false_facts(),
            self._check_qoder_citation_targets(),
            self._check_qoder_claim_citation_coverage(),
            self._check_qoder_owner_inventory_coverage(),
            self._check_qoder_content_presence(),
            self._check_qoder_citation_presence(),
            self._check_qoder_citation_relevance(),
            self._check_qoder_toc_presence(),
            self._check_qoder_file_line_ref_coverage(),
            self._check_qoder_file_refs(),
            self._check_qoder_mermaid_coverage(),
            self._check_qoder_api_mermaid_presence(),
            self._check_qoder_endpoint_lifecycle_mermaid_presence(),
            self._check_qoder_data_model_er_mermaid_presence(),
            self._check_qoder_api_aggregation(),
            self._check_qoder_data_model_aggregation(),
            self._check_qoder_no_endpoint_pages(),
            self._check_qoder_no_raw_model_pages(),
            self._check_qoder_page_dumps(),
            self._check_qoder_prose_density(),
            self._check_qoder_stale_commit(),
            self._check_qoder_dirty_worktree(),
        ]

        hard_failures = [c for c in checks if c.is_hard_gate_failure()]
        soft_failures = [c for c in checks if c.is_soft_gate_failure()]
        warnings = [c for c in checks if c.status == "WARN"]
        passes = [c for c in checks if c.status == "PASS"]

        if hard_failures:
            grade = "FAIL"
        elif soft_failures:
            grade = "FAIL" if not self.strict else "WARN"
        elif warnings:
            grade = "WARN"
        else:
            grade = "PASS"

        reason_codes: list[str] = []
        hard_gate_failures: list[str] = []
        soft_gate_failures: list[str] = []
        for check in checks:
            if check.status in ("FAIL", "WARN") and check.reason_code:
                reason_codes.append(check.reason_code)
                if check.is_hard_gate_failure():
                    hard_gate_failures.append(check.reason_code)
                elif check.is_soft_gate_failure():
                    soft_gate_failures.append(check.reason_code)

        exit_code = 1 if hard_failures else 0
        return {
            "grade": grade,
            "profile": "qoder-like",
            "strict_mode": self.strict,
            "ci_mode": ci,
            "exit_code": exit_code,
            "checks": [check.to_dict() for check in checks],
            "summary": {
                "total": len(checks),
                "pass": len(passes),
                "warn": len(warnings),
                "fail": len(hard_failures) + len(soft_failures),
                "hard_gate_failures": len(hard_failures),
                "soft_gate_failures": len(soft_failures),
            },
            "reason_codes": reason_codes,
            "hard_gate_codes": hard_gate_failures,
            "soft_gate_codes": soft_gate_failures,
            "gate_summary": {
                "hard_gate_blocking": len(hard_failures) > 0,
                "soft_gate_warnings": len(soft_failures) > 0,
                "acceptance_blocked": len(hard_failures) > 0,
            },
        }

    def _check_qoder_content_presence(self) -> CheckResult:
        content_dir = self._find_content_dir()
        if not content_dir:
            return CheckResult(
                name="qoder-content-presence",
                status="FAIL",
                message="No qoder-like content directory found",
                details={},
                reason_code="QODER_CONTENT_EMPTY",
                gate_type=GateType.HARD,
            )
        md_files = list(content_dir.rglob("*.md"))
        if not md_files:
            return CheckResult(
                name="qoder-content-presence",
                status="FAIL",
                message="No markdown pages found",
                details={"content_dir": str(content_dir)},
                reason_code="QODER_CONTENT_EMPTY",
                gate_type=GateType.HARD,
            )
        return CheckResult(
            name="qoder-content-presence",
            status="PASS",
            message=f"Found {len(md_files)} markdown pages",
            details={"content_dir": str(content_dir), "pages": len(md_files)},
            gate_type=GateType.HARD,
        )

    def _extract_mermaid_blocks(self, content: str) -> list[str]:
        return [block.strip().lower() for block in self.MERMAID_CODE_BLOCK_PATTERN.findall(content)]

    def _has_mermaid_kind(self, content: str, diagram_keywords: tuple[str, ...]) -> bool:
        for block in self._extract_mermaid_blocks(content):
            if any(keyword in block for keyword in diagram_keywords):
                return True
        return False

    def _list_target_pages(self, content_dir: Path, roots: tuple[str, ...]) -> list[Path]:
        targets: list[Path] = []
        for root in roots:
            path = content_dir / root
            if path.exists():
                targets.extend(path.rglob("*.md"))
        return targets

    def _check_qoder_api_mermaid_presence(self) -> CheckResult:
        from repo_wiki.generator.io import read_text

        content_dir = self._find_content_dir()
        if not content_dir:
            return self._skip_check("api-mermaid-presence", "No content directory")
        if self._is_content_only_fixture_mode():
            return self._skip_check("api-mermaid-presence", "content-only fixture mode")

        api_pages = self._list_target_pages(content_dir, ("pages/api", "API参考"))
        if not api_pages:
            return self._skip_check("api-mermaid-presence", "No API directory")

        excluded_tokens = ("overview", "总览", "index", "目录", "聚合", "汇总")
        required_pages = [
            page
            for page in api_pages
            if not any(token in page.stem.lower() for token in excluded_tokens)
        ]
        if not required_pages:
            return self._skip_check("api-mermaid-presence", "No core service API pages")

        offenders: list[str] = []
        for page in required_pages:
            try:
                content = read_text(page)
            except Exception:
                continue
            if "```mermaid" not in content and ":::mermaid" not in content:
                offenders.append(page.relative_to(content_dir).as_posix())

        if offenders:
            return CheckResult(
                name="qoder-api-mermaid-presence",
                status="FAIL",
                message=f"{len(offenders)} core API pages missing Mermaid diagrams",
                details={"pages": offenders[:20]},
                reason_code="QODER_API_MERMAID_MISSING",
                gate_type=GateType.HARD,
            )
        return CheckResult(
            name="qoder-api-mermaid-presence",
            status="PASS",
            message="Core API pages include Mermaid diagrams",
            details={"checked_pages": len(required_pages)},
            gate_type=GateType.HARD,
        )

    def _check_qoder_endpoint_lifecycle_mermaid_presence(self) -> CheckResult:
        from repo_wiki.generator.io import read_text

        content_dir = self._find_content_dir()
        if not content_dir:
            return self._skip_check("endpoint-lifecycle-mermaid-presence", "No content directory")

        api_pages = self._list_target_pages(content_dir, ("pages/api", "API参考"))
        if not api_pages:
            return self._skip_check("endpoint-lifecycle-mermaid-presence", "No API directory")

        lifecycle_tokens = (
            "lifecycle",
            "life-cycle",
            "flow",
            "流程",
            "调用链",
            "request",
            "endpoint",
            "handler",
            "route",
        )
        lifecycle_pages = [
            page
            for page in api_pages
            if any(token in page.stem.lower() for token in lifecycle_tokens)
        ]
        if not lifecycle_pages:
            return self._skip_check(
                "endpoint-lifecycle-mermaid-presence", "No endpoint lifecycle pages"
            )

        offenders: list[str] = []
        for page in lifecycle_pages:
            try:
                content = read_text(page)
            except Exception:
                continue
            if not self._has_mermaid_kind(content, ("sequencediagram", "flowchart", "graph ")):
                offenders.append(page.relative_to(content_dir).as_posix())

        if offenders:
            return CheckResult(
                name="qoder-endpoint-lifecycle-mermaid-presence",
                status="FAIL",
                message=f"{len(offenders)} endpoint lifecycle pages missing sequence/flow Mermaid",
                details={"pages": offenders[:20]},
                reason_code="QODER_ENDPOINT_LIFECYCLE_MERMAID_MISSING",
                gate_type=GateType.HARD,
            )
        return CheckResult(
            name="qoder-endpoint-lifecycle-mermaid-presence",
            status="PASS",
            message="Endpoint lifecycle pages include sequence/flow Mermaid",
            details={"checked_pages": len(lifecycle_pages)},
            gate_type=GateType.HARD,
        )

    def _check_qoder_data_model_er_mermaid_presence(self) -> CheckResult:
        from repo_wiki.generator.io import read_text

        content_dir = self._find_content_dir()
        if not content_dir:
            return self._skip_check("data-model-er-mermaid-presence", "No content directory")

        model_pages = self._list_target_pages(content_dir, ("pages/data-models", "数据模型"))
        if not model_pages:
            return self._skip_check("data-model-er-mermaid-presence", "No data-model directory")

        relation_tokens = (
            "relationship",
            "relations",
            "关联",
            "关系",
            "foreign key",
            "join",
            "belongs to",
            "has many",
            "references",
        )
        relation_pages: list[Path] = []
        for page in model_pages:
            try:
                content = read_text(page).lower()
            except Exception:
                continue
            if any(token in content for token in relation_tokens):
                relation_pages.append(page)
        if not relation_pages:
            return self._skip_check(
                "data-model-er-mermaid-presence", "No relationship-evidence data-model pages"
            )

        offenders: list[str] = []
        for page in relation_pages:
            try:
                content = read_text(page)
            except Exception:
                continue
            if not self._has_mermaid_kind(content, ("erdiagram",)):
                offenders.append(page.relative_to(content_dir).as_posix())

        if offenders:
            return CheckResult(
                name="qoder-data-model-er-mermaid-presence",
                status="FAIL",
                message=f"{len(offenders)} data-model pages with relationships missing ER Mermaid",
                details={"pages": offenders[:20]},
                reason_code="QODER_DATA_MODEL_ER_MERMAID_MISSING",
                gate_type=GateType.HARD,
            )
        return CheckResult(
            name="qoder-data-model-er-mermaid-presence",
            status="PASS",
            message="Data-model relationship pages include ER Mermaid",
            details={"checked_pages": len(relation_pages)},
            gate_type=GateType.HARD,
        )

    def _check_qoder_citation_presence(self) -> CheckResult:
        from repo_wiki.generator.io import read_text

        content_dir = self._find_content_dir()
        if not content_dir:
            return self._skip_check("citation-presence", "No content directory")
        md_files = list(content_dir.rglob("*.md"))
        pages_without_citations: list[str] = []
        for f in md_files:
            try:
                content = read_text(f)
            except Exception:
                continue
            if len(content.strip()) < 100:
                continue
            if "<cite>" not in content and "[cite:" not in content:
                pages_without_citations.append(f.name)
        if pages_without_citations:
            return CheckResult(
                name="qoder-citation-presence",
                status="FAIL",
                message=f"{len(pages_without_citations)} pages missing citations",
                details={"pages": pages_without_citations[:10]},
                reason_code="QODER_CITATION_MISSING",
                gate_type=GateType.HARD,
            )
        return CheckResult(
            name="qoder-citation-presence",
            status="PASS",
            message="All pages have citations",
            details={},
            gate_type=GateType.HARD,
        )

    def _check_qoder_citation_relevance(self) -> CheckResult:
        """Check that citations in pages are relevant to the page's service/topic.

        This ensures that citations don't bind evidence to the wrong service:
        - A billing page should not cite authentication implementation files
        - An unrelated service page should not cite another service's implementation

        Same-app architectural layers (API, database/query, data-model/schema) are
        sibling evidence, not high-confidence wrong-service binds. FastAPI pages
        routinely cite ``app/db/queries``, ``app/models``, and schema tests.

        High-confidence mismatches are HARD failures in strict profile.
        Ambiguous cases that could be shared infrastructure are WARN only.
        """
        from repo_wiki.generator.io import read_text

        content_dir = self._find_content_dir()
        if not content_dir:
            return self._skip_check("citation-relevance", "No content directory")

        md_files = list(content_dir.rglob("*.md"))
        if not md_files:
            return self._skip_check("citation-relevance", "No markdown pages")

        # Pattern to extract citation paths and optional symbols
        cite_pattern = re.compile(
            r"<cite>\s*([^<>:]+):[0-9]+(?:-[0-9]+)?\s*(?:\([^)]+\))?\s*</cite>"
        )

        mismatches: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        # Known shared infrastructure paths that could appear in multiple services
        SHARED_INFRA_PATTERNS = [
            "shared/",
            "common/",
            "lib/",
            "utils/",
            "base/",
            "core/",
            "vendor/",
            "deps/",
            "external/",
            "third_party/",
        ]

        # Map page filename keywords to expected service/module patterns.
        # Domain services (auth, billing) are distinct product areas.
        # Layer labels (api, data-model, database) are the same app's
        # HTTP / persistence / schema files, not competing services.
        PAGE_SERVICE_MAP = {
            "auth": ["auth", "login", "session", "token", "oauth", "sso"],
            "billing": ["billing", "invoice", "payment", "subscription", "price"],
            "api": ["api", "endpoint", "route", "handler", "controller", "rest"],
            "data-model": ["model", "schema", "entity", "dto", "migration"],
            "database": ["db", "database", "repo", "query", "sql"],
        }
        SIBLING_LAYER_SERVICES = frozenset({"api", "data-model", "database"})

        for page in md_files:
            try:
                content = read_text(page)
            except Exception:
                continue

            page_name_lower = page.stem.lower()

            # Extract all citations from this page
            citations = cite_pattern.findall(content)
            if not citations:
                continue

            for cite_path in citations:
                # Skip external or absolute paths
                if cite_path.startswith(("http://", "https://", "/")):
                    continue

                cite_path_lower = cite_path.lower()

                # Check for shared infrastructure - these get a WARN not FAIL
                is_shared = any(
                    shared_pattern in cite_path_lower for shared_pattern in SHARED_INFRA_PATTERNS
                )

                # Determine expected service for this page
                page_service = None
                for service, keywords in PAGE_SERVICE_MAP.items():
                    if any(kw in page_name_lower for kw in keywords):
                        page_service = service
                        break

                if page_service is None:
                    # Cannot determine expected service, skip
                    continue

                # Check if citation path contains evidence of wrong service
                wrong_service_evidence = False
                other_services = [k for k in PAGE_SERVICE_MAP if k != page_service]

                for other_service in other_services:
                    if (
                        page_service in SIBLING_LAYER_SERVICES
                        and other_service in SIBLING_LAYER_SERVICES
                    ):
                        # API ↔ query/db ↔ domain model/schema is related
                        # evidence in FastAPI-style apps, not a HARD mismatch.
                        continue
                    other_keywords = PAGE_SERVICE_MAP[other_service]
                    # High confidence mismatch: page name suggests service A
                    # but citation path contains strong indicators of service B
                    if any(kw in cite_path_lower for kw in other_keywords):
                        # Make sure it's not shared infrastructure
                        if not is_shared:
                            wrong_service_evidence = True
                            break

                if wrong_service_evidence:
                    mismatches.append(
                        {
                            "page": page.name,
                            "citation": cite_path,
                            "expected_service": page_service,
                            "reason": "citation path indicates different service",
                        }
                    )
                elif is_shared:
                    warnings.append(
                        {
                            "page": page.name,
                            "citation": cite_path,
                            "reason": "shared infrastructure citation",
                        }
                    )

        if mismatches:
            return CheckResult(
                name="qoder-citation-relevance",
                status="FAIL",
                message=f"{len(mismatches)} citation relevance mismatches detected",
                details={
                    "mismatches": mismatches[:20],
                    "warning_count": len(warnings),
                },
                reason_code="QODER_CITATION_RELEVANCE_MISMATCH",
                gate_type=GateType.HARD,
            )

        if warnings:
            return CheckResult(
                name="qoder-citation-relevance",
                status="WARN",
                message=f"{len(warnings)} shared infrastructure citations (may be intentional)",
                details={"shared_citations": warnings[:20]},
                gate_type=GateType.HARD,
            )

        return CheckResult(
            name="qoder-citation-relevance",
            status="PASS",
            message="All citations appear relevant to their pages",
            details={},
            gate_type=GateType.HARD,
        )

    def _check_qoder_toc_presence(self) -> CheckResult:
        from repo_wiki.generator.io import read_text

        content_dir = self._find_content_dir()
        if not content_dir:
            return self._skip_check("toc-presence", "No content directory")
        md_files = list(content_dir.rglob("*.md"))
        if not md_files:
            return self._skip_check("toc-presence", "No markdown pages")

        pages_with_toc = 0
        for f in md_files:
            try:
                content = read_text(f)
            except Exception:
                continue
            if (
                re.search(r"^#{1,6}\s+(Table of Contents|目录|Contents|TOC)", content, re.MULTILINE)
                or "[TOC]" in content
            ):
                pages_with_toc += 1

        ratio = pages_with_toc / len(md_files)
        if ratio < self.MIN_TOC_COVERAGE:
            return CheckResult(
                name="qoder-toc-presence",
                status="FAIL",
                message=f"TOC coverage too low: {ratio:.2%}",
                details={"pages_with_toc": pages_with_toc, "total_pages": len(md_files)},
                reason_code="QODER_TOC_MISSING",
                gate_type=GateType.HARD,
            )
        return CheckResult(
            name="qoder-toc-presence",
            status="PASS",
            message=f"TOC coverage OK: {ratio:.2%}",
            details={"pages_with_toc": pages_with_toc, "total_pages": len(md_files)},
            gate_type=GateType.HARD,
        )

    def _check_qoder_file_line_ref_coverage(self) -> CheckResult:
        from repo_wiki.generator.io import read_text

        content_dir = self._find_content_dir()
        if not content_dir:
            return self._skip_check("file-line-ref-coverage", "No content directory")
        md_files = list(content_dir.rglob("*.md"))
        if not md_files:
            return self._skip_check("file-line-ref-coverage", "No markdown pages")

        pattern_cite = re.compile(r"<cite>[^<]*:[0-9]+(?:-[0-9]+)?[^<]*</cite>")
        pattern_link = re.compile(r"\[[^\]]+\]\((?:\./)?[^)]+#L?[0-9]+(?:-L?[0-9]+)?\)")
        covered = 0
        for page in md_files:
            try:
                text = read_text(page)
            except Exception:
                continue
            if pattern_cite.search(text) or pattern_link.search(text):
                covered += 1
        ratio = covered / len(md_files)
        if ratio < self.MIN_FILE_LINE_COVERAGE:
            return CheckResult(
                name="qoder-file-line-ref-coverage",
                status="FAIL",
                message=f"File/line ref coverage too low: {ratio:.2%}",
                details={"covered_pages": covered, "total_pages": len(md_files)},
                reason_code="QODER_FILE_LINE_REF_LOW",
                gate_type=GateType.HARD,
            )
        return CheckResult(
            name="qoder-file-line-ref-coverage",
            status="PASS",
            message=f"File/line ref coverage OK: {ratio:.2%}",
            details={"covered_pages": covered, "total_pages": len(md_files)},
            gate_type=GateType.HARD,
        )

    def _check_qoder_file_refs(self) -> CheckResult:
        from repo_wiki.generator.io import read_text

        content_dir = self._find_content_dir()
        if not content_dir:
            return self._skip_check("file-refs", "No content directory")
        md_files = list(content_dir.rglob("*.md"))
        broken_refs: list[str] = []
        for f in md_files:
            try:
                content = read_text(f)
            except Exception:
                continue
            links = self.LOCAL_MARKDOWN_LINK_PATTERN.findall(content)
            for path in links:
                path = path.strip()
                if path.startswith(("#", "http://", "https://", "mailto:")):
                    continue
                if not self._is_safe_local_markdown_target(path):
                    continue
                try:
                    ref_path = (f.parent / path).resolve()
                    exists = ref_path.exists()
                except OSError:
                    exists = False
                if not exists:
                    broken_refs.append(f"{f.name} -> {path}")
        if broken_refs:
            return CheckResult(
                name="qoder-file-refs",
                status="FAIL",
                message=f"{len(broken_refs)} broken file references",
                details={"broken": broken_refs[:10]},
                reason_code="QODER_FILE_REF_BROKEN",
                gate_type=GateType.HARD,
            )
        return CheckResult(
            name="qoder-file-refs",
            status="PASS",
            message="All file references are valid",
            details={},
            gate_type=GateType.HARD,
        )

    def _is_safe_local_markdown_target(self, target: str) -> bool:
        if not target or len(target) > 240:
            return False
        if any(ch in target for ch in ("\n", "\r", "\0")):
            return False
        if ":" in target and not target.startswith("."):
            return False
        return True

    def _check_qoder_mermaid_coverage(self) -> CheckResult:
        from repo_wiki.generator.io import read_text

        content_dir = self._find_content_dir()
        if not content_dir:
            return self._skip_check("mermaid-coverage", "No content directory")
        md_files = list(content_dir.rglob("*.md"))
        if not md_files:
            return self._skip_check("mermaid-coverage", "No markdown pages")
        with_mermaid = 0
        for page in md_files:
            try:
                content = read_text(page)
            except Exception:
                continue
            if "```mermaid" in content or ":::mermaid" in content:
                with_mermaid += 1
        ratio = with_mermaid / len(md_files)
        if ratio < self.MIN_MERMAID_COVERAGE:
            return CheckResult(
                name="qoder-mermaid-coverage",
                status="FAIL",
                message=f"Mermaid coverage too low: {ratio:.2%}",
                details={"pages_with_mermaid": with_mermaid, "total_pages": len(md_files)},
                reason_code="QODER_MERMAID_LOW",
                gate_type=GateType.HARD,
            )
        return CheckResult(
            name="qoder-mermaid-coverage",
            status="PASS",
            message=f"Mermaid coverage OK: {ratio:.2%}",
            details={"pages_with_mermaid": with_mermaid, "total_pages": len(md_files)},
            gate_type=GateType.HARD,
        )

    def _check_qoder_api_aggregation(self) -> CheckResult:
        from repo_wiki.verifier.qoder_parity_metrics import ParityMetricExtractor

        content_dir = self._find_content_dir()
        if not content_dir:
            return self._skip_check("api-aggregation", "No content directory")
        metric = ParityMetricExtractor(content_dir)._measure_api_aggregation()
        if metric.status.value == "fail":
            return CheckResult(
                name="qoder-api-aggregation",
                status="FAIL",
                message="API aggregation quality below threshold",
                details=metric.details,
                reason_code="QODER_API_AGGREGATION_LOW",
                gate_type=GateType.HARD,
            )
        return CheckResult(
            name="qoder-api-aggregation",
            status="PASS",
            message="API aggregation quality OK",
            details=metric.details,
            gate_type=GateType.HARD,
        )

    def _check_qoder_data_model_aggregation(self) -> CheckResult:
        from repo_wiki.verifier.qoder_parity_metrics import ParityMetricExtractor

        content_dir = self._find_content_dir()
        if not content_dir:
            return self._skip_check("data-model-aggregation", "No content directory")
        metric = ParityMetricExtractor(content_dir)._measure_data_model_aggregation()
        if metric.status.value == "fail":
            return CheckResult(
                name="qoder-data-model-aggregation",
                status="FAIL",
                message="Data model aggregation quality below threshold",
                details=metric.details,
                reason_code="QODER_DATA_MODEL_AGGREGATION_LOW",
                gate_type=GateType.HARD,
            )
        return CheckResult(
            name="qoder-data-model-aggregation",
            status="PASS",
            message="Data model aggregation quality OK",
            details=metric.details,
            gate_type=GateType.HARD,
        )

    def _check_qoder_no_endpoint_pages(self) -> CheckResult:
        content_dir = self._find_content_dir()
        if not content_dir:
            return self._skip_check("endpoint-pages", "No content directory")
        api_dirs = [
            path
            for path in (content_dir / "pages" / "api", content_dir / "API参考")
            if path.exists()
        ]
        if not api_dirs:
            return self._skip_check("endpoint-pages", "No API directory")
        method_pattern = re.compile(r"^(get|post|put|patch|delete|options|head)-", re.IGNORECASE)
        offenders: list[str] = []
        for api_dir in api_dirs:
            offenders.extend(
                page.relative_to(content_dir).as_posix()
                for page in api_dir.rglob("*.md")
                if method_pattern.match(page.stem)
            )
        if offenders:
            return CheckResult(
                name="qoder-no-endpoint-pages",
                status="FAIL",
                message=f"{len(offenders)} raw endpoint pages found in API navigation",
                details={"pages": offenders[:20]},
                reason_code="QODER_ENDPOINT_PAGE_DUMP",
                gate_type=GateType.HARD,
            )
        return CheckResult(
            name="qoder-no-endpoint-pages",
            status="PASS",
            message="No raw endpoint pages found",
            details={},
            gate_type=GateType.HARD,
        )

    def _check_qoder_no_raw_model_pages(self) -> CheckResult:
        content_dir = self._find_content_dir()
        if not content_dir:
            return self._skip_check("raw-model-pages", "No content directory")
        model_dirs = [
            path
            for path in (content_dir / "pages" / "data-models", content_dir / "数据模型")
            if path.exists()
        ]
        if not model_dirs:
            return self._skip_check("raw-model-pages", "No data-model directory")
        allowed_keywords = {
            "overview",
            "models",
            "model",
            "database",
            "migration",
            "architecture",
            "strategy",
            "core",
            "service",
        }
        offenders: list[str] = []
        for model_dir in model_dirs:
            for page in model_dir.rglob("*.md"):
                stem = page.stem.lower()
                if any(keyword in stem for keyword in allowed_keywords):
                    continue
                if re.search(r"(dto|entity|request|response|result|config|type)$", stem):
                    offenders.append(page.relative_to(content_dir).as_posix())
        if offenders:
            return CheckResult(
                name="qoder-no-raw-model-pages",
                status="FAIL",
                message=f"{len(offenders)} raw DTO/entity pages found in data model navigation",
                details={"pages": offenders[:20]},
                reason_code="QODER_RAW_MODEL_PAGE_DUMP",
                gate_type=GateType.HARD,
            )
        return CheckResult(
            name="qoder-no-raw-model-pages",
            status="PASS",
            message="No raw DTO/entity pages found",
            details={},
            gate_type=GateType.HARD,
        )

    def _check_qoder_page_dumps(self) -> CheckResult:
        from repo_wiki.generator.io import read_text

        content_dir = self._find_content_dir()
        if not content_dir:
            return self._skip_check("page-dumps", "No content directory")

        md_files = list(content_dir.rglob("*.md"))
        dump_pages: list[str] = []
        for f in md_files:
            try:
                content = read_text(f)
            except Exception:
                continue
            lines = content.split("\n")
            prose_lines = 0
            list_items = 0
            in_code_block = False
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped.startswith("```"):
                    in_code_block = not in_code_block
                    continue
                if in_code_block or stripped.startswith("#"):
                    continue
                if stripped.startswith("-") or stripped.startswith("*"):
                    list_items += 1
                else:
                    prose_lines += 1
            total = prose_lines + list_items
            if total > 0:
                list_ratio = list_items / total
                if list_ratio > self.MAX_LIST_RATIO and list_items > 10:
                    dump_pages.append(f.name)

        if dump_pages:
            return CheckResult(
                name="qoder-page-dumps",
                status="FAIL",
                message=f"{len(dump_pages)} dump pages detected",
                details={"pages": dump_pages[:10]},
                reason_code="QODER_PAGE_DUMP",
                gate_type=GateType.HARD,
            )
        return CheckResult(
            name="qoder-page-dumps",
            status="PASS",
            message="No dump pages detected",
            details={},
            gate_type=GateType.HARD,
        )

    def _check_qoder_prose_density(self) -> CheckResult:
        from repo_wiki.generator.io import read_text

        content_dir = self._find_content_dir()
        if not content_dir:
            return self._skip_check("prose-density", "No content directory")
        md_files = list(content_dir.rglob("*.md"))
        low_density_pages: list[str] = []
        for f in md_files:
            try:
                content = read_text(f)
            except Exception:
                continue
            prose = self._count_prose_chars(content)
            total = len(content)
            if total > 0 and (prose / total) < self.MIN_PROSE_DENSITY:
                low_density_pages.append(f.name)
        if low_density_pages:
            return CheckResult(
                name="qoder-prose-density",
                status="FAIL",
                message=f"{len(low_density_pages)} pages with low prose density",
                details={"pages": low_density_pages[:10]},
                reason_code="QODER_PROSE_TOO_LOW",
                gate_type=GateType.HARD,
            )
        return CheckResult(
            name="qoder-prose-density",
            status="PASS",
            message="All pages meet prose density minimum",
            details={},
            gate_type=GateType.HARD,
        )

    def _check_qoder_manifest_readiness_contract(self) -> CheckResult:
        """Deterministic readiness gate for qoder-like run manifests."""
        payload = self._load_manifest_payload(self.root)
        if payload is None:
            if self._is_release_candidate_root():
                return CheckResult(
                    name="qoder-manifest-readiness",
                    status="FAIL",
                    message="Release/run candidate is missing manifest.json",
                    details={"mode": "release-candidate"},
                    reason_code="QODER_MANIFEST_MISSING",
                    gate_type=GateType.HARD,
                )
            return CheckResult(
                name="qoder-manifest-readiness",
                status="PASS",
                message="Skipped: content-only fixture mode without manifest",
                details={"mode": "content-only"},
                reason_code="",
                gate_type=GateType.HARD,
            )

        run_id = payload.get("run_id")
        readiness = payload.get("readiness_state")
        reasons = payload.get("readiness_reasons", [])
        if not isinstance(readiness, str) or readiness not in {"READY", "NOT_READY", "REVIEW_ONLY"}:
            return CheckResult(
                name="qoder-manifest-readiness",
                status="FAIL",
                message="Manifest missing valid readiness_state",
                details={"readiness_state": readiness},
                reason_code="QODER_MANIFEST_NOT_READY",
                gate_type=GateType.HARD,
            )

        target_dirty = bool(payload.get("target_dirty", False))
        git_fresh = bool(payload.get("git_fresh", True))
        if target_dirty and readiness == "READY":
            return CheckResult(
                name="qoder-manifest-readiness",
                status="FAIL",
                message="target_dirty=true cannot be READY",
                details={"readiness_state": readiness, "readiness_reasons": reasons},
                reason_code="QODER_DIRTY_WORKTREE",
                gate_type=GateType.HARD,
            )
        if (not git_fresh) and readiness == "READY":
            return CheckResult(
                name="qoder-manifest-readiness",
                status="FAIL",
                message="stale git metadata cannot be READY",
                details={"readiness_state": readiness, "readiness_reasons": reasons},
                reason_code="QODER_STALE_GIT_COMMIT",
                gate_type=GateType.HARD,
            )

        repowiki_zh_root = payload.get("candidate_repowiki_zh_root")
        if not isinstance(repowiki_zh_root, str) or not repowiki_zh_root:
            return CheckResult(
                name="qoder-manifest-readiness",
                status="FAIL",
                message="Missing candidate_repowiki_zh_root",
                details={},
                reason_code="QODER_MANIFEST_PATH_INVALID",
                gate_type=GateType.HARD,
            )
        if not run_id:
            return CheckResult(
                name="qoder-manifest-readiness",
                status="FAIL",
                message="Manifest missing run_id; cannot validate candidate path contract",
                details={"run_id": run_id},
                reason_code="QODER_MANIFEST_PATH_INVALID",
                gate_type=GateType.HARD,
            )
        normalized = repowiki_zh_root.replace("\\", "/")
        expected_suffix = f"/.repo-agent-eval/runs/{run_id}/repowiki/zh"
        if expected_suffix not in normalized:
            return CheckResult(
                name="qoder-manifest-readiness",
                status="FAIL",
                message="candidate_repowiki_zh_root violates required runs/<run>/repowiki/zh contract",
                details={"candidate_repowiki_zh_root": repowiki_zh_root, "run_id": run_id},
                reason_code="QODER_MANIFEST_PATH_INVALID",
                gate_type=GateType.HARD,
            )

        content_root = payload.get("candidate_content_root")
        meta_root = payload.get("candidate_meta_root")
        if not isinstance(content_root, str) or not content_root:
            return CheckResult(
                name="qoder-manifest-readiness",
                status="FAIL",
                message="Missing candidate_content_root",
                details={},
                reason_code="QODER_CONTENT_ROOT_MISSING",
                gate_type=GateType.HARD,
            )
        if not isinstance(meta_root, str) or not meta_root:
            return CheckResult(
                name="qoder-manifest-readiness",
                status="FAIL",
                message="Missing candidate_meta_root",
                details={},
                reason_code="QODER_META_ROOT_MISSING",
                gate_type=GateType.HARD,
            )

        report_paths = payload.get("report_paths", {})
        if isinstance(report_paths, dict) and report_paths:
            files = payload.get("files", [])
            evidence = payload.get("evidence", [])
            indexed_paths = set()
            if isinstance(files, list):
                for item in files:
                    if isinstance(item, dict) and isinstance(item.get("path"), str):
                        indexed_paths.add(item["path"])
            if isinstance(evidence, list):
                for item in evidence:
                    if isinstance(item, dict) and isinstance(item.get("path"), str):
                        indexed_paths.add(item["path"])
            for _, p in report_paths.items():
                if isinstance(p, str) and p and p not in indexed_paths:
                    return CheckResult(
                        name="qoder-manifest-readiness",
                        status="FAIL",
                        message="Manifest report_paths mismatch files/evidence registry",
                        details={"missing_report_path": p},
                        reason_code="QODER_REPORT_MISMATCH",
                        gate_type=GateType.HARD,
                    )

        if readiness != "READY":
            return CheckResult(
                name="qoder-manifest-readiness",
                status="WARN",
                message=f"Manifest readiness is {readiness}",
                details={"readiness_state": readiness, "readiness_reasons": reasons},
                reason_code="QODER_MANIFEST_NOT_READY",
                gate_type=GateType.HARD,
            )
        return CheckResult(
            name="qoder-manifest-readiness",
            status="PASS",
            message="Manifest readiness contract satisfied",
            details={"readiness_state": readiness},
            gate_type=GateType.HARD,
        )

    def _check_qoder_quality_artifacts(self) -> CheckResult:
        """Require release candidates to carry structured quality/page state artifacts."""
        if not self._is_release_candidate_root():
            return self._skip_check("quality-artifacts", "content-only fixture mode")

        payload = self._load_manifest_payload(self.root)
        if payload is None:
            return self._skip_check("quality-artifacts", "manifest missing handled separately")

        meta_root = self._manifest_meta_root(payload)
        if meta_root is None:
            return CheckResult(
                name="qoder-quality-artifacts",
                status="FAIL",
                message="Release candidate missing candidate_meta_root",
                details={},
                reason_code="QODER_META_ROOT_MISSING",
                gate_type=GateType.HARD,
            )

        quality_path = meta_root / "quality-report.json"
        registry_path = meta_root / "page-registry.json"
        missing = [p.name for p in (quality_path, registry_path) if not p.exists()]
        if missing:
            return CheckResult(
                name="qoder-quality-artifacts",
                status="FAIL",
                message="Release candidate missing required quality artifacts",
                details={"missing": missing},
                reason_code="QODER_QUALITY_ARTIFACT_MISSING",
                gate_type=GateType.HARD,
            )

        quality, quality_error = self._read_required_json_object(quality_path)
        registry, registry_error = self._read_required_json_object(registry_path)
        schema_errors: list[str] = []
        if quality_error:
            schema_errors.append(f"quality-report.json: {quality_error}")
        if registry_error:
            schema_errors.append(f"page-registry.json: {registry_error}")
        if not schema_errors:
            from repo_wiki.orchestration.release_meta_schema import (
                validate_page_registry,
                validate_quality_report,
            )

            schema_errors.extend(validate_quality_report(quality))
            schema_errors.extend(validate_page_registry(registry))
        if schema_errors:
            return CheckResult(
                name="qoder-quality-artifacts",
                status="FAIL",
                message="Release candidate quality artifacts are invalid",
                details={"errors": schema_errors[:20]},
                reason_code="QODER_QUALITY_ARTIFACT_INVALID",
                gate_type=GateType.HARD,
            )

        content_dir = self._find_content_dir()
        pages = (
            []
            if content_dir is None
            else sorted(p.relative_to(content_dir).as_posix() for p in content_dir.rglob("*.md"))
        )
        expected_pages = set(pages)
        quality_states, quality_path_errors = self._collect_artifact_page_quality_states(
            quality, containers=("page_quality", "pages")
        )
        registry_states, registry_path_errors = self._collect_artifact_page_quality_states(
            registry, containers=("pages", "page_registry")
        )
        coverage_errors = quality_path_errors + registry_path_errors
        quality_paths = set(quality_states)
        registry_paths = set(registry_states)
        if quality_paths != expected_pages:
            coverage_errors.append(
                "quality-report.json page coverage mismatch: "
                f"missing={sorted(expected_pages - quality_paths)[:20]}, "
                f"extra={sorted(quality_paths - expected_pages)[:20]}"
            )
        if registry_paths != expected_pages:
            coverage_errors.append(
                "page-registry.json page coverage mismatch: "
                f"missing={sorted(expected_pages - registry_paths)[:20]}, "
                f"extra={sorted(registry_paths - expected_pages)[:20]}"
            )
        if quality_paths != registry_paths:
            coverage_errors.append(
                "quality-report.json and page-registry.json page sets do not match: "
                f"quality_only={sorted(quality_paths - registry_paths)[:20]}, "
                f"registry_only={sorted(registry_paths - quality_paths)[:20]}"
            )
        if coverage_errors:
            return CheckResult(
                name="qoder-quality-artifacts",
                status="FAIL",
                message="Release candidate quality artifacts do not exactly cover content pages",
                details={"errors": coverage_errors[:20], "content_pages": pages[:20]},
                reason_code="QODER_PAGE_QUALITY_STATE_MISSING",
                gate_type=GateType.HARD,
            )

        page_states = {**quality_states, **registry_states}
        bad_states = {
            page: state
            for page, state in page_states.items()
            if state.lower() not in {"ready", "pass", "passed", "ok"}
            or any(token in state.lower() for token in ("fallback", "degraded"))
        }
        if bad_states:
            return CheckResult(
                name="qoder-quality-artifacts",
                status="FAIL",
                message="Release candidate contains fallback/degraded page quality states",
                details={"states": dict(list(bad_states.items())[:20])},
                reason_code="QODER_PAGE_QUALITY_STATE_DEGRADED",
                gate_type=GateType.HARD,
            )

        return CheckResult(
            name="qoder-quality-artifacts",
            status="PASS",
            message="Release quality artifacts and per-page quality states are READY",
            details={"pages": len(pages)},
            gate_type=GateType.HARD,
        )

    def _check_qoder_unresolved_fact_conflicts(self) -> CheckResult:
        paths = self._candidate_artifact_paths(
            "source-docs-conflicts.json"
        ) + self._candidate_artifact_paths("fact-conflicts.json")
        seen: set[Path] = set()
        found_canonical_artifact = False
        unresolved: list[dict[str, Any]] = []
        for path in paths:
            if path in seen or not path.exists():
                continue
            seen.add(path)
            if path.name == "source-docs-conflicts.json":
                found_canonical_artifact = True
            payload, read_error = self._read_required_json_object(path)
            schema_errors = (
                [read_error] if read_error else self._validate_conflict_report_payload(payload)
            )
            if schema_errors:
                return CheckResult(
                    name="qoder-unresolved-fact-conflicts",
                    status="FAIL",
                    message="Conflict evidence artifact is unreadable or schema-invalid",
                    details={"path": str(path), "errors": schema_errors[:20]},
                    reason_code="QODER_CONFLICT_ARTIFACT_INVALID",
                    gate_type=GateType.HARD,
                )
            count = self._count_unresolved_conflicts(payload)
            if count:
                unresolved.append({"path": str(path), "unresolved_count": count})
        if unresolved:
            return CheckResult(
                name="qoder-unresolved-fact-conflicts",
                status="FAIL",
                message="Unresolved fact-conflict artifact blocks READY",
                details={"artifacts": unresolved},
                reason_code="QODER_UNRESOLVED_FACT_CONFLICT",
                gate_type=GateType.HARD,
            )
        if self._is_release_candidate_root() and not found_canonical_artifact:
            return CheckResult(
                name="qoder-unresolved-fact-conflicts",
                status="FAIL",
                message="Release candidate missing required canonical source-docs conflict artifact",
                details={"required": "source-docs-conflicts.json"},
                reason_code="QODER_CONFLICT_ARTIFACT_MISSING",
                gate_type=GateType.HARD,
            )
        return CheckResult(
            name="qoder-unresolved-fact-conflicts",
            status="PASS",
            message="No unresolved fact-conflict artifacts found",
            details={},
            gate_type=GateType.HARD,
        )

    def _count_unresolved_conflicts(self, payload: dict[str, Any]) -> int:
        summary = payload.get("summary", {}) if isinstance(payload, dict) else {}
        count = 0
        if isinstance(summary, dict):
            for key in (
                "deferred_count",
                "flagged_count",
                "unresolved_count",
                "critical_unresolved_count",
                "critical_conflict_count",
            ):
                count += int(summary.get(key, 0) or 0)
        for key in (
            "deferred_items",
            "flagged_items",
            "unresolved_items",
            "critical_items",
            "conflicts",
        ):
            value = payload.get(key) if isinstance(payload, dict) else None
            if not isinstance(value, list):
                continue
            for item in value:
                if not isinstance(item, dict):
                    count += 1
                    continue
                status = str(item.get("status") or item.get("state") or "").lower()
                severity = str(item.get("severity") or item.get("level") or "").lower()
                if (
                    key in {"deferred_items", "flagged_items", "unresolved_items"}
                    or status in {"unresolved", "deferred", "flagged", "open"}
                    or severity == "critical"
                ):
                    count += 1
        return count

    def _check_qoder_critical_false_facts(self) -> CheckResult:
        content_dir = self._find_content_dir()
        if not content_dir:
            return self._skip_check("critical-false-facts", "No content directory")
        inventories = self._load_structured_inventory_sets()
        if self._is_release_candidate_root():
            missing_required = [
                name
                for name in ("sources", "apis", "services", "models", "runtimes")
                if not inventories[name]
            ]
            if missing_required:
                return CheckResult(
                    name="qoder-critical-false-facts",
                    status="FAIL",
                    message="Release candidate missing required structured inventories",
                    details={"missing_required": missing_required},
                    reason_code="QODER_REQUIRED_INVENTORY_MISSING",
                    gate_type=GateType.HARD,
                )
        if not any(inventories.values()):
            if self._is_release_candidate_root():
                return CheckResult(
                    name="qoder-critical-false-facts",
                    status="FAIL",
                    message="Release candidate missing structured inventories for fact validation",
                    details={"required": ["sources", "apis", "services", "models", "runtimes"]},
                    reason_code="QODER_REQUIRED_INVENTORY_MISSING",
                    gate_type=GateType.HARD,
                )
            return self._skip_check("critical-false-facts", "No structured inventories")

        offenders: list[dict[str, str]] = []
        for page in content_dir.rglob("*.md"):
            text = page.read_text(encoding="utf-8", errors="ignore")
            rel = page.relative_to(content_dir).as_posix()
            if inventories["apis"]:
                for method, api_path in re.findall(
                    r"\b(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\s+(/[-A-Za-z0-9_./{}:]+)",
                    text,
                ):
                    if (method.upper(), api_path) not in inventories["apis"]:
                        offenders.append(
                            {
                                "page": rel,
                                "claim_type": "api",
                                "claim": f"{method.upper()} {api_path}",
                            }
                        )
            if inventories["services"]:
                for service in self._extract_structured_name_claims(text, "service"):
                    if service not in inventories["services"]:
                        offenders.append({"page": rel, "claim_type": "service", "claim": service})
            if inventories["models"]:
                for model in self._extract_structured_name_claims(text, "model"):
                    if model not in inventories["models"]:
                        offenders.append({"page": rel, "claim_type": "model", "claim": model})
            for endpoint, claimed_auth in self._extract_endpoint_auth_claims(text).items():
                expected_auth = inventories["endpoint_auth"].get(endpoint)
                if expected_auth is not None and expected_auth != claimed_auth:
                    offenders.append(
                        {
                            "page": rel,
                            "claim_type": "auth",
                            "claim": f"{endpoint[0]} {endpoint[1]} auth={claimed_auth}",
                        }
                    )
            for source, relation, target in re.findall(
                r"`([^`]+)`\s+(belongs to|has many|references|owns|uses)\s+`([^`]+)`",
                text,
                flags=re.IGNORECASE,
            ):
                normalized = (source, relation.lower(), target)
                if normalized not in inventories["relationships"]:
                    offenders.append(
                        {
                            "page": rel,
                            "claim_type": "relationship",
                            "claim": f"{source} {relation} {target}",
                        }
                    )
        if offenders:
            return CheckResult(
                name="qoder-critical-false-facts",
                status="FAIL",
                message="Content claims contradict structured inventories",
                details={"offenders": offenders[:30]},
                reason_code="QODER_CRITICAL_FALSE_FACT",
                gate_type=GateType.HARD,
            )
        return CheckResult(
            name="qoder-critical-false-facts",
            status="PASS",
            message="Structured inventory claims are consistent",
            details={"inventory_types": [k for k, v in inventories.items() if v]},
            gate_type=GateType.HARD,
        )

    def _check_qoder_citation_targets(self) -> CheckResult:
        content_dir = self._find_content_dir()
        if not content_dir:
            return self._skip_check("citation-targets", "No content directory")
        if not self._is_release_candidate_root():
            return self._skip_check("citation-targets", "content-only fixture mode")
        invalid: list[dict[str, Any]] = []
        for page in content_dir.rglob("*.md"):
            text = page.read_text(encoding="utf-8", errors="ignore")
            for cite in self._extract_citation_refs(text):
                problem = self._validate_citation_ref(cite)
                if problem:
                    invalid.append(
                        {
                            "page": page.relative_to(content_dir).as_posix(),
                            "citation": cite,
                            "problem": problem,
                        }
                    )
        if invalid:
            return CheckResult(
                name="qoder-citation-targets",
                status="FAIL",
                message=f"{len(invalid)} invalid repository citation targets",
                details={"invalid": invalid[:30], "invalid_count": len(invalid)},
                reason_code="QODER_CITATION_INVALID",
                gate_type=GateType.HARD,
            )
        return CheckResult(
            name="qoder-citation-targets",
            status="PASS",
            message="All repository citation targets exist within line bounds",
            details={"invalid_count": 0},
            gate_type=GateType.HARD,
        )

    def _check_qoder_claim_citation_coverage(self) -> CheckResult:
        """Hard gate release candidates on claim/fact-level repository citation coverage."""
        from repo_wiki.verifier.citation_fact_coverage import (
            build_claim_coverage,
            extract_citation_refs_with_lines,
            is_external_url,
        )

        content_dir = self._find_content_dir()
        if not content_dir:
            return self._skip_check("claim-citation-coverage", "No content directory")
        if not self._is_release_candidate_root():
            return self._skip_check("claim-citation-coverage", "content-only fixture mode")

        total = 0
        covered = 0
        uncovered: list[dict[str, object]] = []
        for page in content_dir.rglob("*.md"):
            text = page.read_text(encoding="utf-8", errors="ignore")
            rel = page.relative_to(content_dir).as_posix()
            valid_repo_lines = {
                ref.line
                for ref in extract_citation_refs_with_lines(text)
                if not is_external_url(ref.raw) and self._validate_citation_ref(ref.raw) is None
            }
            page_coverage = build_claim_coverage(
                text, page=rel, valid_repo_citation_lines=valid_repo_lines
            )
            page_total = page_coverage["total"]
            page_covered = page_coverage["covered"]
            page_uncovered = page_coverage["uncovered"]
            if isinstance(page_total, int):
                total += page_total
            if isinstance(page_covered, int):
                covered += page_covered
            if isinstance(page_uncovered, list):
                uncovered.extend(page_uncovered)

        ratio = 1.0 if total == 0 else covered / total
        if ratio < 0.95:
            return CheckResult(
                name="qoder-claim-citation-coverage",
                status="FAIL",
                message=f"Claim-level repository citation coverage below 95%: {ratio:.2%}",
                details={
                    "covered_claims": covered,
                    "total_claims": total,
                    "coverage_ratio": ratio,
                    "uncovered": uncovered[:30],
                },
                reason_code="QODER_CITATION_FACT_COVERAGE_LOW",
                gate_type=GateType.HARD,
            )
        return CheckResult(
            name="qoder-claim-citation-coverage",
            status="PASS",
            message=f"Claim-level repository citation coverage OK: {ratio:.2%}",
            details={"covered_claims": covered, "total_claims": total, "coverage_ratio": ratio},
            gate_type=GateType.HARD,
        )

    def _check_qoder_owner_inventory_coverage(self) -> CheckResult:
        """Require every important inventory item to map to an owner page or UNIDENTIFIED warning."""
        from repo_wiki.verifier.ownership_coverage import (
            collect_owner_inventory_items,
            item_owner_coverage,
        )

        if not self._is_release_candidate_root():
            return self._skip_check("owner-inventory-coverage", "content-only fixture mode")
        content_dir = self._find_content_dir()
        payload = self._load_manifest_payload(self.root)
        meta_root = self._manifest_meta_root(payload) if payload else None
        if not content_dir or not meta_root or not meta_root.exists():
            return CheckResult(
                name="qoder-owner-inventory-coverage",
                status="FAIL",
                message="Release candidate missing content/meta roots for owner coverage",
                details={},
                reason_code="QODER_REQUIRED_INVENTORY_MISSING",
                gate_type=GateType.HARD,
            )
        items = collect_owner_inventory_items(meta_root)
        if not items:
            return CheckResult(
                name="qoder-owner-inventory-coverage",
                status="FAIL",
                message="Release candidate missing inventories required for owner coverage",
                details={"meta_root": str(meta_root)},
                reason_code="QODER_REQUIRED_INVENTORY_MISSING",
                gate_type=GateType.HARD,
            )

        pages = [
            page.read_text(encoding="utf-8", errors="ignore") for page in content_dir.rglob("*.md")
        ]
        warnings = self._load_structured_unidentified_warnings(meta_root)
        missing: list[dict[str, str]] = []
        for item in items:
            covered, reason = item_owner_coverage(item, pages, warnings)
            if not covered:
                missing.append(
                    {
                        "kind": item.kind,
                        "identifier": item.identifier,
                        "source": item.source,
                        "reason": reason,
                    }
                )
        if missing:
            return CheckResult(
                name="qoder-owner-inventory-coverage",
                status="FAIL",
                message="Inventory items missing owner page mapping or UNIDENTIFIED warning",
                details={"missing": missing[:30], "missing_count": len(missing)},
                reason_code="QODER_OWNER_COVERAGE_MISSING",
                gate_type=GateType.HARD,
            )
        return CheckResult(
            name="qoder-owner-inventory-coverage",
            status="PASS",
            message="Inventory owner coverage complete",
            details={"items": len(items)},
            gate_type=GateType.HARD,
        )

    def _is_content_only_fixture_mode(self) -> bool:
        return (self.root / "fixture_metadata.json").exists() and not (
            self.root / "manifest.json"
        ).exists()

    def _is_release_candidate_root(self) -> bool:
        if self._load_manifest_payload(self.root) is not None:
            return not (self.root / "fixture_metadata.json").exists()
        normalized = self.root.as_posix()
        if "/.repo-agent-eval/runs/" in normalized or normalized.endswith("/.repo-agent-eval"):
            return True
        if (
            (self.root / "repowiki" / "zh").exists()
            or self.root.name == "zh"
            and self.root.parent.name == "repowiki"
        ):
            return True
        return False

    def _layout_meta_root(self) -> Path | None:
        for candidate in (
            self.root / "repowiki" / "zh" / "meta",
            self.root / "meta",
        ):
            if candidate.is_dir():
                return candidate
        return None

    def _manifest_meta_root(self, payload: dict[str, Any]) -> Path | None:
        layout = self._layout_meta_root()
        if layout is not None and (
            (layout / "quality-report.json").exists() or (layout / "page-registry.json").exists()
        ):
            return layout

        raw = payload.get("candidate_meta_root")
        if isinstance(raw, str) and raw:
            declared = Path(raw)
            if not declared.is_absolute():
                declared = self.root / declared
            if declared.exists() or layout is None:
                return declared

        if layout is not None:
            return layout

        repowiki = payload.get("candidate_repowiki_zh_root")
        if isinstance(repowiki, str) and repowiki:
            return Path(repowiki) / "meta"
        return None

    def _read_required_json_object(self, path: Path) -> tuple[dict[str, Any], str | None]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return {}, f"failed to read/parse JSON: {exc.__class__.__name__}"
        if not isinstance(payload, dict):
            return {}, f"JSON root must be an object, got {type(payload).__name__}"
        return payload, None

    def _collect_artifact_page_quality_states(
        self, payload: dict[str, Any], *, containers: tuple[str, ...]
    ) -> tuple[dict[str, str], list[str]]:
        states: dict[str, str] = {}
        errors: list[str] = []
        for container_key in containers:
            items = payload.get(container_key)
            if items is None:
                continue
            if not isinstance(items, list):
                errors.append(f"{container_key} must be a list")
                continue
            for index, item in enumerate(items):
                if not isinstance(item, dict):
                    errors.append(f"{container_key}[{index}] must be an object")
                    continue
                rel = (
                    item.get("relative_path") or item.get("path") or item.get("page_relative_path")
                )
                state = item.get("quality_state") or item.get("state") or item.get("status")
                if not isinstance(rel, str) or not rel.strip():
                    errors.append(f"{container_key}[{index}] missing relative_path")
                    continue
                rel = self._strip_content_prefix(rel.strip())
                if rel in states:
                    errors.append(f"duplicate page entry: {rel}")
                if not isinstance(state, str) or not state.strip():
                    errors.append(f"{container_key}[{index}] missing quality_state")
                    continue
                states[rel] = state.strip()
        return states, errors

    def _validate_conflict_report_payload(self, payload: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if payload.get("schema_version") != "source-docs-conflict-resolver-v1":
            errors.append(
                "source-docs-conflicts schema_version must be 'source-docs-conflict-resolver-v1'"
            )
        summary = payload.get("summary")
        if not isinstance(summary, dict):
            errors.append("summary must be an object")
        else:
            for key in ("resolved_count", "deferred_count", "flagged_count", "total_items"):
                if not isinstance(summary.get(key), int):
                    errors.append(f"summary.{key} must be an integer")
        for key in ("resolved_items", "deferred_items", "flagged_items"):
            items = payload.get(key)
            if not isinstance(items, list):
                errors.append(f"{key} must be a list")
                continue
            for index, item in enumerate(items):
                if not isinstance(item, dict):
                    errors.append(f"{key}[{index}] must be an object")
        return errors

    def _read_json_object(self, path: Path) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _collect_page_quality_states(self, *payloads: dict[str, Any]) -> dict[str, str]:
        states: dict[str, str] = {}
        for payload in payloads:
            for container_key in ("pages", "page_quality", "page_registry"):
                items = payload.get(container_key)
                if not isinstance(items, list):
                    continue
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    rel = (
                        item.get("relative_path")
                        or item.get("path")
                        or item.get("page_relative_path")
                    )
                    state = item.get("quality_state") or item.get("state") or item.get("status")
                    if isinstance(rel, str) and isinstance(state, str):
                        states[self._strip_content_prefix(rel)] = state
        return states

    def _strip_content_prefix(self, value: str) -> str:
        return value.removeprefix("content/")

    def _candidate_artifact_paths(self, name: str) -> list[Path]:
        paths = [self.root / name, self.root / "reports" / name, self.root / "meta" / name]
        payload = self._load_manifest_payload(self.root)
        if payload:
            meta = self._manifest_meta_root(payload)
            if meta:
                paths.append(meta / name)
            for key in ("report_paths", "artifact_paths"):
                values = payload.get(key)
                if isinstance(values, dict):
                    for raw in values.values():
                        if isinstance(raw, str) and Path(raw).name == name:
                            paths.append(self.root / raw)
        return paths

    def _load_structured_inventory_sets(self) -> dict[str, Any]:
        meta = None
        payload = self._load_manifest_payload(self.root)
        if payload:
            meta = self._manifest_meta_root(payload)
        search_roots = [
            p for p in (meta, self.root / "meta", self.root) if p is not None and p.exists()
        ]
        sources: set[str] = set()
        apis: set[tuple[str, str]] = set()
        endpoint_auth: dict[tuple[str, str], str] = {}
        services: set[str] = set()
        models: set[str] = set()
        runtimes: set[str] = set()
        relationships: set[tuple[str, str, str]] = set()
        for root in search_roots:
            for path in root.glob("*.json"):
                data = self._read_json_object(path)
                if (
                    path.name == "source-inventory.json"
                    or data.get("schema_version") == "repo_agent.source_inventory/1.0"
                ):
                    sources.add(path.name)
                endpoints = data.get("endpoints", [])
                if not isinstance(endpoints, list):
                    endpoints = data.get("api_surfaces", [])
                for item in endpoints if isinstance(endpoints, list) else []:
                    if (
                        isinstance(item, dict)
                        and isinstance(item.get("method"), str)
                        and isinstance(item.get("path") or item.get("endpoint"), str)
                    ):
                        endpoint_path = str(item.get("path") or item.get("endpoint"))
                        api_key = (item["method"].upper(), endpoint_path)
                        apis.add(api_key)
                        auth = self._endpoint_auth_value(item)
                        if auth is not None:
                            endpoint_auth[api_key] = auth
                services_payload = data.get("services", [])
                for item in services_payload if isinstance(services_payload, list) else []:
                    if isinstance(item, dict):
                        for key in ("service_id", "service", "name", "display_name"):
                            value = item.get(key)
                            if isinstance(value, str):
                                services.add(value)
                models_payload = data.get("models", [])
                if not isinstance(models_payload, list):
                    models_payload = data.get("data_models", [])
                for item in models_payload if isinstance(models_payload, list) else []:
                    if isinstance(item, dict):
                        for key in ("model_id", "name", "display_name"):
                            value = item.get(key)
                            if isinstance(value, str):
                                models.add(value)
                for key in ("runtime_entrypoints", "entrypoints", "commands"):
                    runtime_payload = data.get(key, [])
                    for item in runtime_payload if isinstance(runtime_payload, list) else []:
                        if isinstance(item, str) and item.strip():
                            runtimes.add(item.strip())
                        if isinstance(item, dict):
                            for field in ("entrypoint", "command", "name", "id", "path"):
                                value = item.get(field)
                                if isinstance(value, str) and value.strip():
                                    runtimes.add(value.strip())
                relationships_payload = data.get("relationships", [])
                for item in (
                    relationships_payload if isinstance(relationships_payload, list) else []
                ):
                    if isinstance(item, dict):
                        source = item.get("source") or item.get("from")
                        target = item.get("target") or item.get("to")
                        relation = item.get("relation") or item.get("type")
                        if (
                            isinstance(source, str)
                            and isinstance(target, str)
                            and isinstance(relation, str)
                        ):
                            relationships.add((source, relation.lower(), target))
        return {
            "sources": sources,
            "apis": apis,
            "endpoint_auth": endpoint_auth,
            "services": services,
            "models": models,
            "runtimes": runtimes,
            "relationships": relationships,
        }

    def _endpoint_auth_value(self, item: dict[str, Any]) -> str | None:
        if isinstance(item.get("auth_required"), bool):
            return "required" if item["auth_required"] else "none"
        auth_type = item.get("auth_type") or item.get("auth") or item.get("authentication")
        if isinstance(auth_type, str) and auth_type.strip():
            normalized = auth_type.strip().lower()
            if normalized in {"none", "no", "public", "unauthenticated"}:
                return "none"
            if normalized in {"unknown", "n/a"}:
                return None
            return "required"
        return None

    def _extract_endpoint_auth_claims(self, text: str) -> dict[tuple[str, str], str]:
        claims: dict[tuple[str, str], str] = {}
        endpoint = r"\b(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\s+(/[-A-Za-z0-9_./{}:]+)"
        for method, path, value in re.findall(
            endpoint
            + r"[^.\n]{0,120}?\b(requires authentication|requires auth|requires bearer|requires oauth|requires api-key|is public|is unauthenticated|requires no auth|requires no authentication)",
            text,
            flags=re.IGNORECASE,
        ):
            normalized = value.lower()
            claims[(method.upper(), path)] = (
                "none"
                if "public" in normalized
                or "unauthenticated" in normalized
                or "no auth" in normalized
                else "required"
            )
        return claims

    def _extract_structured_name_claims(self, text: str, kind: str) -> set[str]:
        """Extract deterministic service/model identifiers from ordinary prose."""
        if kind == "service":
            patterns = (
                r"\b[Ss]ervice\s+`([^`]+)`",
                r"\b`([^`]+)`\s+service\b",
                r"\b[Ss]ervice\s+([a-z][a-z0-9_-]{2,})\b",
                r"\b([a-z][a-z0-9_-]{2,})\s+service\b",
            )
            generic = {"service", "services", "core", "public"}
        else:
            patterns = (
                r"\b(?:Model|Entity)\s+`([^`]+)`",
                r"\b`([^`]+)`\s+(?:model|entity)\b",
                r"\b(?:Model|Entity)\s+([A-Za-z][A-Za-z0-9_-]{2,})\b",
                r"\b([A-Za-z][A-Za-z0-9_-]{2,})\s+(?:model|entity)\b",
            )
            generic = {"model", "models", "entity", "entities", "data"}
        claims: set[str] = set()
        for pattern in patterns:
            for value in re.findall(pattern, text):
                claim = value.strip("`.,;:()[]{} ")
                if claim and claim.lower() not in generic:
                    claims.add(claim)
        return claims

    def _load_structured_unidentified_warnings(self, meta_root: Path) -> set[Any]:
        warnings: set[Any] = set()
        for path in meta_root.glob("*.json"):
            payload = self._read_json_object(path)
            for key in ("warnings", "quality_warnings", "unidentified", "owner_warnings"):
                values = payload.get(key)
                if not isinstance(values, list):
                    continue
                for item in values:
                    if isinstance(item, str) and "UNIDENTIFIED" in item:
                        warnings.add(item)
                    if not isinstance(item, dict):
                        continue
                    code = str(item.get("code") or item.get("type") or "").upper()
                    state = str(item.get("state") or item.get("status") or "").upper()
                    if "UNIDENTIFIED" not in code and "UNIDENTIFIED" not in state:
                        continue
                    kind = item.get("kind") or item.get("inventory_kind")
                    identifier = item.get("identifier") or item.get("id") or item.get("name")
                    if isinstance(identifier, str):
                        warnings.add(identifier)
                    if isinstance(kind, str) and isinstance(identifier, str):
                        warnings.add((kind, identifier))
        return warnings

    def _extract_citation_refs(self, text: str) -> list[str]:
        refs: list[str] = []
        for raw in re.findall(r"<cite>\s*([^<]+?)\s*</cite>", text):
            if is_placeholder_citation_ref(raw):
                continue
            refs.append(raw.strip())
        for raw in re.findall(r"\[cite:\s*([^\]]+?)\]", text):
            if is_placeholder_citation_ref(raw):
                continue
            refs.append(raw.strip())
        return refs

    def _validate_citation_ref(self, citation: str) -> str | None:
        from repo_wiki.verifier.citation_fact_coverage import (
            is_external_url,
            is_source_looking_url,
        )

        raw = normalize_citation_ref(citation, self._source_root_for_citations())
        if is_source_looking_url(raw):
            return "source-looking external URL cannot validate repository lines"
        if is_external_url(raw):
            return None
        if raw.startswith("source:"):
            raw = raw[len("source:") :]
        match = re.fullmatch(r"(.+?):(\d+)(?:-(\d+))?(?:\s*\([^)]+\))?", raw)
        if not match:
            return "missing line reference"
        path_text, start_text, end_text = match.groups()
        if not self._is_safe_repo_relative_path(path_text):
            return "unsafe path"
        source_path = self._source_root_for_citations() / path_text
        if not source_path.exists() or not source_path.is_file():
            return "file does not exist"
        start = int(start_text)
        end = int(end_text or start_text)
        if start < 1 or end < start:
            return "invalid line range"
        try:
            line_count = sum(1 for _ in source_path.open("r", encoding="utf-8", errors="ignore"))
        except OSError:
            return "file unreadable"
        if end > line_count:
            return "line range exceeds file bounds"
        return None

    def _is_safe_repo_relative_path(self, value: str) -> bool:
        path = Path(value)
        if path.is_absolute():
            return False
        if any(part == ".." for part in path.parts):
            return False
        if any(ch in value for ch in ("\n", "\r", "\0")):
            return False
        return bool(value.strip())

    def _check_qoder_stale_commit(self) -> CheckResult:
        current = self._git_commit(self.root)
        wiki = self._manifest_commit(self.root)
        if not current or not wiki:
            return self._skip_check("stale-commit", "Missing git commit metadata")
        if not (current.startswith(wiki) or wiki.startswith(current)):
            return CheckResult(
                name="qoder-stale-commit",
                status="FAIL",
                message="Wiki commit is stale compared with current repo commit",
                details={"current_commit": current, "wiki_commit": wiki},
                reason_code="QODER_STALE_GIT_COMMIT",
                gate_type=GateType.HARD,
            )
        return CheckResult(
            name="qoder-stale-commit",
            status="PASS",
            message="Wiki commit matches current repo commit",
            details={"current_commit": current, "wiki_commit": wiki},
            gate_type=GateType.HARD,
        )

    def _check_qoder_dirty_worktree(self) -> CheckResult:
        """Check if the worktree has uncommitted changes (dirty state).

        In strict mode, a dirty worktree during generation is flagged as
        QODER_DIRTY_WORKTREE since it indicates non-repeatable state.
        """
        if self._git_dirty(self.root):
            return CheckResult(
                name="qoder-dirty-worktree",
                status="FAIL",
                message="Target repository has uncommitted changes",
                details={},
                reason_code="QODER_DIRTY_WORKTREE",
                gate_type=GateType.HARD,
            )
        return CheckResult(
            name="qoder-dirty-worktree",
            status="PASS",
            message="Target repository worktree is clean",
            details={},
            gate_type=GateType.HARD,
        )

    def _git_dirty(self, path: Path) -> bool:
        """Return True if the repository has uncommitted changes or untracked files."""
        root = self._find_git_root(path)
        if root is None:
            return False
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(root),
                capture_output=True,
                text=True,
                check=True,
            )
            return bool(result.stdout.strip())
        except Exception:
            return False

    def _find_content_dir(self) -> Path | None:
        if self.root.exists() and self.root.is_dir() and self.root.name == "content":
            return self.root
        candidates = [
            self.root / "content",
            self.root / "repowiki" / "zh" / "content",
            self.root / ".repo-agent-eval" / "content",
            self.root / ".qoder" / "repowiki" / "zh" / "content",
        ]
        for c in candidates:
            if c.exists():
                return c
        for f in self.root.rglob("*.md"):
            return f.parent
        return None

    def _count_prose_chars(self, content: str) -> int:
        lines = content.split("\n")
        prose_lines = []
        in_code_block = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue
            if (
                stripped.startswith("#")
                or stripped.startswith("-")
                or stripped.startswith("*")
                or stripped.startswith("|")
            ):
                continue
            prose_lines.append(stripped)
        return len(" ".join(prose_lines))

    def _skip_check(self, name: str, reason: str) -> CheckResult:
        return CheckResult(
            name=name,
            status="PASS",
            message=f"Skipped: {reason}",
            details={},
            reason_code="",
            gate_type=GateType.HARD,
        )

    def _git_commit(self, path: Path) -> str | None:
        root = self._find_git_root(path)
        if root is None:
            return None
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(root),
                capture_output=True,
                text=True,
                check=True,
            )
        except Exception:
            return None
        value = result.stdout.strip()
        return value or None

    def _find_git_root(self, path: Path) -> Path | None:
        start = path if path.is_dir() else path.parent
        for candidate in [start, *start.parents]:
            if (candidate / ".git").exists():
                return candidate
        return None

    def _manifest_commit(self, root: Path) -> str | None:
        candidates = [
            root / "manifest.json",
            root.parent / "manifest.json",
            root / "meta.json",
            root / "metadata.json",
        ]
        for path in candidates:
            if not path.exists() or not path.is_file():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            for key in (
                "wiki_git_commit",
                "target_git_commit",
                "commit_hash",
                "git_commit",
                "commit",
            ):
                value = payload.get(key)
                if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{7,40}", value):
                    return value
        return None

    def _source_root_for_citations(self) -> Path:
        payload = self._load_manifest_payload(self.root)
        if payload and isinstance(payload.get("target_repo"), str):
            target = Path(payload["target_repo"])
            if target.exists() and target.is_dir():
                return target
        return self.root

    def _load_manifest_payload(self, root: Path) -> dict[str, Any] | None:
        candidates = [root / "manifest.json", root / "meta.json", root / "metadata.json"]
        start = root if root.is_dir() else root.parent
        for ancestor in [start, *start.parents[:5]]:
            candidates.append(ancestor / "manifest.json")
        for path in candidates:
            if not path.exists() or not path.is_file():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(payload, dict):
                return payload
        return None


def create_qoder_like_verifier(root: Path, strict: bool = True) -> QoderLikeVerifierService:
    return QoderLikeVerifierService(root, strict=strict)


def verify_qoder_like(root: Path, ci: bool = True, strict: bool = True) -> dict[str, Any]:
    verifier = create_qoder_like_verifier(root, strict)
    return verifier.verify(ci=ci)
