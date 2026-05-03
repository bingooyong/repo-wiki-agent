from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from repo_wiki.generator.contracts import (
    SECTION_DEFINITIONS,
)
from repo_wiki.generator.io import list_repo_files, read_text, read_yamlish
from repo_wiki.retrieval.service import RetrievalService


class GateType(Enum):
    """Classification of gate severity for acceptance decisions.

    HARD gate violations are non-recoverable structural failures that MUST be
    fixed before acceptance. SOFT gate violations are quality issues that can
    be addressed later but indicate the output needs improvement.
    """

    HARD = "HARD"  # Structural failures - must fix before acceptance
    SOFT = "SOFT"  # Quality issues - should fix but not blocking


class SeverityThreshold:
    """Configurable severity thresholds for acceptance decisions.

    These thresholds determine which gate types trigger acceptance failure.
    Teams can customize these based on their quality standards.
    """

    def __init__(
        self,
        hard_gate_codes: set[str] | None = None,
        soft_gate_codes: set[str] | None = None,
        warn_on_soft: bool = True,
        fail_on_hard: bool = True,
    ) -> None:
        # Default HARD gate codes: structural failures
        self.hard_gate_codes = hard_gate_codes or {
            "STRUCT_SECTION_DIR_MISSING",
            "STRUCT_MISSING_SECTIONS",
            "STRUCT_NAVIGATION_BROKEN",
            "STRUCT_NAV_BAD_DEPTH",
            "STRUCT_NAV_TARGET_MISSING",
            "CONTENT_EMPTY",
            "CITATION_SOURCE_EMPTY",  # Empty source blocks are hard gate
        }
        # Default SOFT gate codes: quality issues
        self.soft_gate_codes = soft_gate_codes or {
            "CONTENT_LIST_ONLY",
            "CONTENT_TOO_SHORT",
            "CONTENT_MISSING_SECTIONS",
            "AGG_API_NOT_GROUPED",
            "AGG_API_ENDPOINT_DUMP",
            "AGG_DM_NOT_GROUPED",
            "AGG_DM_MODEL_DUMP",
            "ARCH_MERMAID_MISSING",
            "ARCH_MERMAID_INSUFFICIENT",
            "ARCH_LAYER_EXPLANATION_MISSING",
            "CITATION_MISSING",  # Missing citations are soft gate
            "CITATION_BROKEN_PATH",  # Broken paths are soft gate
            "CITATION_BAD_LINES",  # Bad line ranges are soft gate
        }
        self.warn_on_soft = warn_on_soft
        self.fail_on_hard = fail_on_hard

    def get_gate_type(self, reason_code: str) -> GateType:
        """Determine gate type for a given reason code."""
        if reason_code in self.hard_gate_codes:
            return GateType.HARD
        if reason_code in self.soft_gate_codes:
            return GateType.SOFT
        # Unknown codes default to HARD for safety
        return GateType.HARD

    def is_blocking(self, reason_code: str) -> bool:
        """Check if a reason code should block acceptance."""
        gate = self.get_gate_type(reason_code)
        if gate == GateType.HARD:
            return self.fail_on_hard
        return False  # Soft gates never block by default

    @classmethod
    def from_yaml(cls, config: dict[str, Any]) -> SeverityThreshold:
        """Create SeverityThreshold from YAML configuration.

        Args:
            config: Dictionary with optional keys:
                - hard_gate_codes: list of codes that are HARD failures
                - soft_gate_codes: list of codes that are SOFT failures
                - warn_on_soft: whether to warn on soft failures (default True)
                - fail_on_hard: whether to fail on hard failures (default True)

        Example YAML:
            verify:
              hard_gate_codes:
                - STRUCT_MISSING_SECTIONS
                - STRUCT_NAVIGATION_BROKEN
              soft_gate_codes:
                - CONTENT_LIST_ONLY
                - CONTENT_TOO_SHORT
              warn_on_soft: true
              fail_on_hard: true
        """
        hard_codes = set(config.get("hard_gate_codes", []))
        soft_codes = set(config.get("soft_gate_codes", []))
        warn_on_soft = config.get("warn_on_soft", True)
        fail_on_hard = config.get("fail_on_hard", True)
        return cls(
            hard_gate_codes=hard_codes if hard_codes else None,
            soft_gate_codes=soft_codes if soft_codes else None,
            warn_on_soft=warn_on_soft,
            fail_on_hard=fail_on_hard,
        )

    def to_dict(self) -> dict[str, Any]:
        """Export threshold configuration as dictionary."""
        return {
            "hard_gate_codes": sorted(list(self.hard_gate_codes)),
            "soft_gate_codes": sorted(list(self.soft_gate_codes)),
            "warn_on_soft": self.warn_on_soft,
            "fail_on_hard": self.fail_on_hard,
        }


# Global default thresholds (can be overridden per instance)
DEFAULT_THRESHOLDS = SeverityThreshold()


# Reason codes for CI output - precise categorization of WARN/FAIL outcomes
class ReasonCode:
    # Content quality codes (1xxx)
    CONTENT_EMPTY = "CONTENT_EMPTY"  # 1001: Document is empty
    CONTENT_LIST_ONLY = "CONTENT_LIST_ONLY"  # 1002: Document is primarily list/table, no prose
    CONTENT_TOO_SHORT = "CONTENT_TOO_SHORT"  # 1003: Document below minimum prose length
    CONTENT_MISSING_SECTIONS = "CONTENT_MISSING_SECTIONS"  # 1004: Missing required sections

    # Structure quality codes (2xxx)
    STRUCT_MISSING_SECTIONS = (
        "STRUCT_MISSING_SECTIONS"  # 2001: docs/sections/ missing required sections
    )
    STRUCT_SECTION_DIR_MISSING = (
        "STRUCT_SECTION_DIR_MISSING"  # 2002: Section directory does not exist
    )
    STRUCT_NAVIGATION_BROKEN = "STRUCT_NAVIGATION_BROKEN"  # 2003: Navigation links are broken
    STRUCT_NAV_BAD_DEPTH = "STRUCT_NAV_BAD_DEPTH"  # 2004: Incorrect relative path depth
    STRUCT_NAV_TARGET_MISSING = "STRUCT_NAV_TARGET_MISSING"  # 2005: Linked file does not exist

    # Aggregation quality codes (3xxx)
    AGG_API_NOT_GROUPED = "AGG_API_NOT_GROUPED"  # 3001: API doc is raw endpoint dump
    AGG_API_ENDPOINT_DUMP = "AGG_API_ENDPOINT_DUMP"  # 3002: Too many raw endpoints
    AGG_DM_NOT_GROUPED = "AGG_DM_NOT_GROUPED"  # 3003: Data model is not aggregated
    AGG_DM_MODEL_DUMP = "AGG_DM_MODEL_DUMP"  # 3004: Too many raw models

    # Architecture quality codes (4xxx)
    ARCH_MERMAID_MISSING = "ARCH_MERMAID_MISSING"  # 4001: Architecture missing Mermaid diagrams
    ARCH_MERMAID_INSUFFICIENT = "ARCH_MERMAID_INSUFFICIENT"  # 4002: Not enough Mermaid blocks
    ARCH_LAYER_EXPLANATION_MISSING = (
        "ARCH_LAYER_EXPLANATION_MISSING"  # 4003: Missing three-layer explanation
    )

    # Citation quality codes (5xxx)
    CITATION_MISSING = "CITATION_MISSING"  # 5001: Page has no citations at all
    CITATION_BROKEN_PATH = "CITATION_BROKEN_PATH"  # 5002: Citation file path does not exist
    CITATION_BAD_LINES = "CITATION_BAD_LINES"  # 5003: Citation line range is invalid
    CITATION_SOURCE_EMPTY = "CITATION_SOURCE_EMPTY"  # 5004: Source block is empty


@dataclass
class CheckResult:
    name: str
    status: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    reason_code: str = ""
    gate_type: GateType = GateType.SOFT  # Default to SOFT for backward compatibility

    def to_dict(self) -> dict[str, Any]:
        result = {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "details": self.details,
        }
        if self.reason_code:
            result["reason_code"] = self.reason_code
        if self.gate_type:
            result["gate_type"] = self.gate_type.value
        return result

    def is_hard_gate_failure(self) -> bool:
        """Check if this is a HARD gate failure."""
        return self.status == "FAIL" and self.gate_type == GateType.HARD

    def is_soft_gate_failure(self) -> bool:
        """Check if this is a SOFT gate failure."""
        return self.status == "FAIL" and self.gate_type == GateType.SOFT


class VerifierService:
    def __init__(
        self,
        root: Path,
        retrieval_service: RetrievalService | None = None,
        severity_thresholds: SeverityThreshold | None = None,
    ) -> None:
        self.root = root
        self.retrieval_service = retrieval_service
        self.severity_thresholds = severity_thresholds or DEFAULT_THRESHOLDS

    def verify(self, ci: bool = False) -> dict[str, Any]:
        checks: list[CheckResult] = []

        # Existing MVP checks
        checks.append(self._check_required_files())
        checks.append(self._check_module_doc_coverage())
        checks.append(self._check_api_module_cross_refs())
        checks.append(self._check_data_model_refs())
        checks.append(self._check_stale_docs())
        checks.append(self._check_adapter_paths())

        # Phase 08: Content quality checks
        checks.append(self._check_overview_prose_quality())
        checks.append(self._check_architecture_prose_quality())
        checks.append(self._check_sections_exist())
        checks.append(self._check_api_aggregated())
        checks.append(self._check_data_model_aggregated())
        checks.append(self._check_navigation_links())

        # Phase 23: Citation quality checks
        checks.append(self._check_citation_coverage())
        checks.append(self._check_citation_validity())
        checks.append(self._check_citation_source_empty())

        hard_failures = [c for c in checks if c.is_hard_gate_failure()]
        soft_failures = [c for c in checks if c.is_soft_gate_failure()]
        warnings = [c for c in checks if c.status == "WARN"]
        passes = [c for c in checks if c.status == "PASS"]

        # Gate-aware grade determination
        # FAIL if any HARD gate failures exist, regardless of soft gate passes
        if hard_failures:
            grade = "FAIL"
        elif soft_failures:
            # When warn_on_soft=False, soft gates become blocking failures
            grade = "WARN" if self.severity_thresholds.warn_on_soft else "FAIL"
        elif warnings:
            grade = "WARN"
        else:
            grade = "PASS"

        # Build reason codes for CI mode
        reason_codes = []
        hard_gate_failures = []
        soft_gate_failures = []
        if ci:
            for check in checks:
                if check.status in ("FAIL", "WARN") and check.reason_code:
                    reason_codes.append(check.reason_code)
                    if check.is_hard_gate_failure():
                        hard_gate_failures.append(check.reason_code)
                    elif check.is_soft_gate_failure():
                        soft_gate_failures.append(check.reason_code)

        # Exit code for CI: 0 = pass, 1 = hard gate failure, 2 = soft gate failure (if configured to fail)
        exit_code = 0
        if hard_failures:
            exit_code = 1
        elif soft_failures and not self.severity_thresholds.warn_on_soft:
            exit_code = 2

        return {
            "grade": grade,
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
            "reason_codes": reason_codes if ci else [],
            "hard_gate_codes": hard_gate_failures if ci else [],
            "soft_gate_codes": soft_gate_failures if ci else [],
            "gate_summary": {
                "hard_gate_blocking": len(hard_failures) > 0,
                "soft_gate_warnings": len(soft_failures) > 0,
                "acceptance_blocked": len(hard_failures) > 0,
            },
        }

    def _check_required_files(self) -> CheckResult:
        required = [
            "ai/source-of-truth/repo-map.yaml",
            "ai/source-of-truth/module-index.yaml",
            "ai/source-of-truth/api-index.yaml",
            "ai/source-of-truth/data-models.yaml",
            "ai/source-of-truth/task-catalog.yaml",
            "ai/source-of-truth/prompt-fragments/overview.txt",
            "ai/source-of-truth/prompt-fragments/architecture.txt",
            "docs/00-overview.md",
            "docs/01-architecture.md",
            "docs/03-module-map.md",
            "docs/04-api-contracts.md",
            "docs/05-data-model.md",
            ".claude/CLAUDE.md",
            ".claude/settings.json",
            "AGENTS.md",
            ".opencode/opencode.json",
            ".codex/config.toml",
            ".codex/hooks.json",
        ]
        missing = [path for path in required if not (self.root / path).exists()]
        if missing:
            return CheckResult(
                name="required-files",
                status="FAIL",
                message="Missing required MVP artifacts.",
                details={"missing": sorted(missing)},
                reason_code="STRUCT_NAV_TARGET_MISSING",  # Hard gate: missing files
                gate_type=GateType.HARD,
            )
        return CheckResult(
            name="required-files",
            status="PASS",
            message="All required files are present.",
            details={},
            gate_type=GateType.HARD,
        )

    def _check_module_doc_coverage(self) -> CheckResult:
        module_index = read_yamlish(
            self.root / "ai/source-of-truth/module-index.yaml", {"modules": []}
        )
        modules = module_index.get("modules", []) if isinstance(module_index, dict) else []
        missing_docs: list[str] = []
        for module in modules:
            if not isinstance(module, dict):
                continue
            doc_path = str(module.get("doc_path", "")).strip()
            module_name = str(module.get("name", "unknown"))
            if not doc_path or not (self.root / doc_path).exists():
                missing_docs.append(module_name)
        if missing_docs:
            return CheckResult(
                name="module-doc-coverage",
                status="FAIL",
                message="Some modules do not have corresponding docs.",
                details={"missing_modules": sorted(missing_docs)},
                reason_code="STRUCT_NAV_TARGET_MISSING",  # Hard gate: missing files
                gate_type=GateType.HARD,
            )
        return CheckResult(
            name="module-doc-coverage",
            status="PASS",
            message="All modules have documentation files.",
            details={},
            gate_type=GateType.HARD,
        )

    def _check_api_module_cross_refs(self) -> CheckResult:
        module_index = read_yamlish(
            self.root / "ai/source-of-truth/module-index.yaml", {"modules": []}
        )
        api_index = read_yamlish(self.root / "ai/source-of-truth/api-index.yaml", {"endpoints": []})
        modules = {
            str(item.get("name", ""))
            for item in (module_index.get("modules", []) if isinstance(module_index, dict) else [])
            if isinstance(item, dict)
        }
        dangling = []
        for endpoint in api_index.get("endpoints", []) if isinstance(api_index, dict) else []:
            if not isinstance(endpoint, dict):
                continue
            module_name = str(endpoint.get("module", ""))
            if module_name and module_name not in modules:
                dangling.append(
                    {
                        "method": endpoint.get("method", ""),
                        "path": endpoint.get("path", ""),
                        "module": module_name,
                    }
                )
        if dangling:
            return CheckResult(
                name="api-module-cross-refs",
                status="FAIL",
                message="API index contains endpoints linked to unknown modules.",
                details={"dangling_endpoints": dangling},
                reason_code="STRUCT_NAV_TARGET_MISSING",  # Hard gate: broken references
                gate_type=GateType.HARD,
            )
        return CheckResult(
            name="api-module-cross-refs",
            status="PASS",
            message="API index cross-references are valid.",
            details={},
            gate_type=GateType.HARD,
        )

    def _check_data_model_refs(self) -> CheckResult:
        module_index = read_yamlish(
            self.root / "ai/source-of-truth/module-index.yaml", {"modules": []}
        )
        data_models = read_yamlish(
            self.root / "ai/source-of-truth/data-models.yaml", {"models": []}
        )
        modules = {
            str(item.get("name", ""))
            for item in (module_index.get("modules", []) if isinstance(module_index, dict) else [])
            if isinstance(item, dict)
        }
        dangling = []
        for model in data_models.get("models", []) if isinstance(data_models, dict) else []:
            if not isinstance(model, dict):
                continue
            module_name = str(model.get("module", ""))
            if module_name and module_name not in modules:
                dangling.append({"name": model.get("name", ""), "module": module_name})
        if dangling:
            return CheckResult(
                name="data-model-refs",
                status="FAIL",
                message="data-models.yaml contains dangling module references.",
                details={"dangling_models": dangling},
                reason_code="STRUCT_NAV_TARGET_MISSING",  # Hard gate: broken references
                gate_type=GateType.HARD,
            )
        return CheckResult(
            name="data-model-refs",
            status="PASS",
            message="Data model references are valid.",
            details={},
            gate_type=GateType.HARD,
        )

    def _check_stale_docs(self) -> CheckResult:
        docs = [
            self.root / "docs/00-overview.md",
            self.root / "docs/01-architecture.md",
            self.root / "docs/03-module-map.md",
            self.root / "docs/04-api-contracts.md",
            self.root / "docs/05-data-model.md",
        ]
        existing_docs = [path for path in docs if path.exists()]
        if not existing_docs:
            return CheckResult(
                name="stale-docs",
                status="WARN",
                message="Core docs are missing, stale check skipped.",
                details={},
                reason_code="CONTENT_EMPTY",
                gate_type=GateType.SOFT,
            )
        latest_doc_mtime = max(path.stat().st_mtime for path in existing_docs)
        latest_code_mtime = 0.0
        for path in list_repo_files(self.root):
            rel = path.relative_to(self.root).as_posix()
            if (
                rel.startswith("docs/")
                or rel.startswith("ai/source-of-truth/")
                or rel.startswith(".repo-wiki/")
            ):
                continue
            if path.suffix.lower() not in {".py", ".go", ".ts", ".tsx", ".js", ".jsx"}:
                continue
            latest_code_mtime = max(latest_code_mtime, path.stat().st_mtime)

        changed_modules: list[str] = []
        if self.retrieval_service is not None:
            try:
                incremental = self.retrieval_service.analyze_incremental_impact()
                changed_modules = incremental.changed_modules
            except Exception:
                changed_modules = []

        if latest_code_mtime > latest_doc_mtime or changed_modules:
            return CheckResult(
                name="stale-docs",
                status="WARN",
                message="Potential stale docs detected after code changes.",
                details={"changed_modules": changed_modules},
                reason_code="STALE_DOCS_DETECTED",
                gate_type=GateType.SOFT,
            )
        return CheckResult(
            name="stale-docs",
            status="PASS",
            message="No stale docs detected.",
            details={},
            gate_type=GateType.SOFT,
        )

    def _check_adapter_paths(self) -> CheckResult:
        missing: list[str] = []

        settings_path = self.root / ".claude/settings.json"
        if settings_path.exists():
            try:
                parsed = json.loads(settings_path.read_text(encoding="utf-8"))
                for path in parsed.get("knowledge_base", []):
                    if isinstance(path, str) and not (self.root / path).exists():
                        missing.append(path)
            except json.JSONDecodeError:
                missing.append(".claude/settings.json(parse-error)")

        opencode_path = self.root / ".opencode/opencode.json"
        if opencode_path.exists():
            try:
                parsed = json.loads(opencode_path.read_text(encoding="utf-8"))
                for path in parsed.get("knowledge_paths", []):
                    if isinstance(path, str) and not (self.root / path).exists():
                        missing.append(path)
            except json.JSONDecodeError:
                missing.append(".opencode/opencode.json(parse-error)")

        codex_config_path = self.root / ".codex/config.toml"
        if codex_config_path.exists():
            raw = read_text(codex_config_path)
            in_knowledge = False
            for line in raw.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped.startswith("[") and stripped.endswith("]"):
                    in_knowledge = stripped == "[knowledge]"
                    continue
                if not in_knowledge:
                    continue
                if not stripped.startswith("path_"):
                    continue
                if "=" not in stripped:
                    continue
                _, value = stripped.split("=", 1)
                value = value.strip().strip('"').strip("'")
                if value and not (self.root / value).exists():
                    missing.append(value)

        if missing:
            return CheckResult(
                name="adapter-paths",
                status="FAIL",
                message="Adapter references contain unresolved paths.",
                details={"missing_paths": sorted(set(missing))},
                reason_code="STRUCT_NAV_TARGET_MISSING",  # Hard gate: broken paths
                gate_type=GateType.HARD,
            )
        return CheckResult(
            name="adapter-paths",
            status="PASS",
            message="Adapter references are path-valid.",
            details={},
            gate_type=GateType.HARD,
        )

    # =============================================================================
    # Phase 08: Content Quality Checks
    # =============================================================================

    # Minimum prose requirements for overview document
    OVERVIEW_MIN_PROSE_CHARS = 200
    OVERVIEW_MIN_SECTIONS = 5
    OVERVIEW_MAX_LIST_RATIO = 0.7

    def _check_overview_prose_quality(self) -> CheckResult:
        """Check that docs/00-overview.md meets minimum prose quality standards.

        Requirements:
        - Minimum 200 characters of prose content (not lists/tables)
        - Minimum 5 sections (## headers)
        - Not primarily list/table content (>70% ratio)
        """
        overview_path = self.root / "docs/00-overview.md"
        if not overview_path.exists():
            return CheckResult(
                name="overview-prose-quality",
                status="FAIL",
                message="docs/00-overview.md does not exist",
                reason_code=ReasonCode.CONTENT_EMPTY,
                gate_type=GateType.HARD,  # Missing file is hard gate
            )

        content = read_text(overview_path)
        if not content or len(content.strip()) == 0:
            return CheckResult(
                name="overview-prose-quality",
                status="FAIL",
                message="docs/00-overview.md is empty",
                reason_code=ReasonCode.CONTENT_EMPTY,
                gate_type=GateType.HARD,  # Empty content is hard gate
            )

        lines = content.split("\n")
        prose_lines = []
        in_code_block = False

        for line in lines:
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue

            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                continue
            if stripped.startswith("-"):
                continue
            if stripped.startswith("|"):
                continue
            if stripped.startswith("!"):
                continue

            prose_lines.append(stripped)

        prose_text = " ".join(prose_lines)

        # Check minimum prose length
        if len(prose_text) < self.OVERVIEW_MIN_PROSE_CHARS:
            return CheckResult(
                name="overview-prose-quality",
                status="FAIL",
                message=f"Overview has only {len(prose_text)} chars of prose, need at least {self.OVERVIEW_MIN_PROSE_CHARS}",
                details={
                    "prose_chars": len(prose_text),
                    "min_required": self.OVERVIEW_MIN_PROSE_CHARS,
                },
                reason_code=ReasonCode.CONTENT_TOO_SHORT,
                gate_type=GateType.SOFT,  # Quality issue - soft gate
            )

        # Count sections
        section_count = sum(1 for line in lines if line.strip().startswith("## "))
        if section_count < self.OVERVIEW_MIN_SECTIONS:
            return CheckResult(
                name="overview-prose-quality",
                status="FAIL",
                message=f"Overview has only {section_count} sections, need at least {self.OVERVIEW_MIN_SECTIONS}",
                details={
                    "section_count": section_count,
                    "min_required": self.OVERVIEW_MIN_SECTIONS,
                },
                reason_code=ReasonCode.CONTENT_MISSING_SECTIONS,
                gate_type=GateType.SOFT,  # Quality issue - soft gate
            )

        # Check list/table ratio
        list_items = sum(1 for l in lines if l.strip().startswith("-"))
        table_rows = sum(1 for l in lines if l.strip().startswith("|"))
        total_content_lines = list_items + table_rows + len(prose_lines)
        if total_content_lines > 0:
            list_ratio = (list_items + table_rows) / total_content_lines
            if list_ratio > self.OVERVIEW_MAX_LIST_RATIO:
                return CheckResult(
                    name="overview-prose-quality",
                    status="FAIL",
                    message=f"Overview is {list_ratio*100:.0f}% list/table content, must be less than 70%",
                    details={
                        "list_ratio": round(list_ratio, 2),
                        "max_allowed": self.OVERVIEW_MAX_LIST_RATIO,
                    },
                    reason_code=ReasonCode.CONTENT_LIST_ONLY,
                    gate_type=GateType.SOFT,  # Quality issue - soft gate
                )

        return CheckResult(
            name="overview-prose-quality",
            status="PASS",
            message="Overview passes prose quality checks",
            details={"prose_chars": len(prose_text), "section_count": section_count},
            gate_type=GateType.SOFT,
        )

    ARCHITECTURE_MIN_MERMAID_BLOCKS = 2

    def _check_architecture_prose_quality(self) -> CheckResult:
        """Check that docs/01-architecture.md meets quality standards.

        Requirements:
        - Must contain at least 2 Mermaid diagram blocks
        - Must explain the three-layer architecture (.repo-wiki, ai/source-of-truth, docs)
        """
        arch_path = self.root / "docs/01-architecture.md"
        if not arch_path.exists():
            return CheckResult(
                name="architecture-prose-quality",
                status="FAIL",
                message="docs/01-architecture.md does not exist",
                reason_code=ReasonCode.CONTENT_EMPTY,
                gate_type=GateType.HARD,  # Missing file is hard gate
            )

        content = read_text(arch_path)
        if not content or len(content.strip()) == 0:
            return CheckResult(
                name="architecture-prose-quality",
                status="FAIL",
                message="docs/01-architecture.md is empty",
                reason_code=ReasonCode.CONTENT_EMPTY,
                gate_type=GateType.HARD,  # Empty content is hard gate
            )

        # Check for mermaid blocks
        mermaid_blocks = content.count("```mermaid")
        if mermaid_blocks == 0:
            return CheckResult(
                name="architecture-prose-quality",
                status="FAIL",
                message="Architecture must contain at least one Mermaid diagram",
                details={"mermaid_blocks": 0, "min_required": self.ARCHITECTURE_MIN_MERMAID_BLOCKS},
                reason_code=ReasonCode.ARCH_MERMAID_MISSING,
                gate_type=GateType.SOFT,  # Quality issue - soft gate
            )

        if mermaid_blocks < self.ARCHITECTURE_MIN_MERMAID_BLOCKS:
            return CheckResult(
                name="architecture-prose-quality",
                status="FAIL",
                message=f"Architecture has only {mermaid_blocks} Mermaid block(s), should have at least 2 for three-layer explanation",
                details={
                    "mermaid_blocks": mermaid_blocks,
                    "min_required": self.ARCHITECTURE_MIN_MERMAID_BLOCKS,
                },
                reason_code=ReasonCode.ARCH_MERMAID_INSUFFICIENT,
                gate_type=GateType.SOFT,  # Quality issue - soft gate
            )

        # Check for three-layer explanation
        has_repo_wiki = ".repo-wiki" in content
        has_source_of_truth = "source-of-truth" in content
        has_docs = "docs/" in content

        missing_refs = []
        if not has_repo_wiki:
            missing_refs.append(".repo-wiki")
        if not has_source_of_truth:
            missing_refs.append("ai/source-of-truth")
        if not has_docs:
            missing_refs.append("docs/")

        if missing_refs:
            return CheckResult(
                name="architecture-prose-quality",
                status="FAIL",
                message=f"Architecture missing explanation of: {', '.join(missing_refs)}",
                details={"missing_references": missing_refs},
                reason_code=ReasonCode.ARCH_LAYER_EXPLANATION_MISSING,
                gate_type=GateType.SOFT,  # Quality issue - soft gate
            )

        return CheckResult(
            name="architecture-prose-quality",
            status="PASS",
            message="Architecture passes quality checks",
            details={"mermaid_blocks": mermaid_blocks},
            gate_type=GateType.SOFT,
        )

    REQUIRED_SECTIONS = [
        "project",
        "architecture",
        "services",
        "data-model",
        "api",
        "operations",
        "development",
        "security",
        "troubleshooting",
    ]
    LEGACY_SECTION_PATTERN = re.compile(r"^[qs]\d{2}[-_].+\.md$", re.IGNORECASE)
    LEGACY_SECTION_MIN_TOTAL = 8
    LEGACY_SECTION_MIN_Q = 4
    LEGACY_SECTION_MIN_S = 4

    def _legacy_section_profile(self, sections_dir: Path) -> dict[str, Any]:
        """Inspect legacy Qxx/Sxx flat section files for compatibility mode."""
        flat_files = [p.name for p in sections_dir.glob("*.md") if p.is_file()]
        q_files = sorted(
            [
                name
                for name in flat_files
                if name.lower().startswith("q") and self.LEGACY_SECTION_PATTERN.match(name)
            ]
        )
        s_files = sorted(
            [
                name
                for name in flat_files
                if name.lower().startswith("s") and self.LEGACY_SECTION_PATTERN.match(name)
            ]
        )
        total = len(q_files) + len(s_files)
        qualified = (
            total >= self.LEGACY_SECTION_MIN_TOTAL
            and len(q_files) >= self.LEGACY_SECTION_MIN_Q
            and len(s_files) >= self.LEGACY_SECTION_MIN_S
        )
        return {
            "qualified": qualified,
            "q_files": q_files,
            "s_files": s_files,
            "total": total,
            "thresholds": {
                "min_total": self.LEGACY_SECTION_MIN_TOTAL,
                "min_q": self.LEGACY_SECTION_MIN_Q,
                "min_s": self.LEGACY_SECTION_MIN_S,
            },
        }

    def _check_sections_exist(self) -> CheckResult:
        """Check that docs/sections/** exists and contains required section pages.

        Uses SECTION_DEFINITIONS from contracts.py to support canonical slugs
        and repository-specific aliases (e.g., Q01/S01 format from AI_API_Atlas).

        Required sections: project, architecture, services, data-model, api, operations, development, security

        Returns alias resolution evidence in details for diagnostics and readiness reports:
        - alias_resolutions: per-section resolution status (canonical, alias, legacy, missing)
        - legacy_file_mapping: maps legacy Qxx/Sxx files to their discovery status
        """
        sections_dir = self.root / "docs/sections"
        if not sections_dir.exists():
            return CheckResult(
                name="sections-exist",
                status="FAIL",
                message="docs/sections/ directory does not exist",
                details={"path": str(sections_dir)},
                reason_code=ReasonCode.STRUCT_SECTION_DIR_MISSING,
                gate_type=GateType.HARD,  # Missing directory is hard gate
            )

        # Get canonical required slugs
        canonical_required = [
            s.canonical_slug
            for s in SECTION_DEFINITIONS
            if s.canonical_slug in self.REQUIRED_SECTIONS
        ]

        missing_sections: list[str] = []
        found_sections = []
        alias_resolutions: dict[str, str] = {}  # canonical_slug -> resolution_type
        alias_details: dict[str, str] = {}  # canonical_slug -> resolution_detail

        for section_slug in canonical_required:
            section_index = sections_dir / section_slug / "index.md"
            canonical_flat = sections_dir / f"{section_slug}.md"
            if section_index.exists() or canonical_flat.exists():
                found_sections.append(section_slug)
                alias_resolutions[section_slug] = "canonical"
                alias_details[section_slug] = (
                    f"Found at {section_slug}/index.md or {section_slug}.md"
                )
            else:
                # Check if alias exists instead
                section_def = next(
                    (s for s in SECTION_DEFINITIONS if s.canonical_slug == section_slug), None
                )
                alias_found = False
                if section_def and section_def.aliases:
                    for alias in section_def.aliases:
                        alias_index = sections_dir / alias / "index.md"
                        alias_flat = sections_dir / f"{alias}.md"
                        if alias_index.exists() or alias_flat.exists():
                            found_sections.append(f"{section_slug} (via alias {alias})")
                            alias_resolutions[section_slug] = "alias"
                            alias_details[section_slug] = f"Found via alias {alias}"
                            alias_found = True
                            break
                if not alias_found:
                    missing_sections.append(section_slug)
                    alias_resolutions[section_slug] = "missing"
                    alias_details[section_slug] = "No canonical or alias path found"

        # Collect legacy file mapping for diagnostics
        legacy_file_mapping: dict[str, str] = {}
        if missing_sections:
            flat_files = [
                p.name for p in sections_dir.glob("*.md") if p.is_file() and not p.is_dir()
            ]
            for f in flat_files:
                if self.LEGACY_SECTION_PATTERN.match(f):
                    legacy_file_mapping[f] = "discovered"

        if missing_sections:
            legacy = self._legacy_section_profile(sections_dir)
            if legacy["qualified"]:
                return CheckResult(
                    name="sections-exist",
                    status="PASS",
                    message="Legacy Qxx/Sxx section profile detected and accepted via compatibility mode",
                    details={
                        "mode": "legacy_qs_compatibility",
                        "required": canonical_required,
                        "missing_canonical": sorted(missing_sections),
                        "alias_resolutions": alias_resolutions,
                        "alias_details": alias_details,
                        "legacy_profile": legacy,
                        "legacy_file_mapping": legacy_file_mapping,
                    },
                    gate_type=GateType.HARD,
                )
            return CheckResult(
                name="sections-exist",
                status="FAIL",
                message=f"Missing required section pages: {', '.join(missing_sections)}",
                details={
                    "missing_sections": sorted(missing_sections),
                    "required": canonical_required,
                    "found": found_sections,
                    "alias_resolutions": alias_resolutions,
                    "alias_details": alias_details,
                    "legacy_profile": self._legacy_section_profile(sections_dir),
                },
                reason_code=ReasonCode.STRUCT_MISSING_SECTIONS,
                gate_type=GateType.HARD,  # Missing sections is hard gate
            )

        return CheckResult(
            name="sections-exist",
            status="PASS",
            message="All required section pages exist",
            details={
                "section_count": len(canonical_required),
                "found": found_sections,
                "alias_resolutions": alias_resolutions,
                "alias_details": alias_details,
            },
            gate_type=GateType.HARD,
        )

    API_MAX_RAW_ENDPOINTS = 50

    def _check_api_aggregated(self) -> CheckResult:
        """Check that docs/04-api-contracts.md is aggregated, not a raw endpoint dump.

        Requirements:
        - Must have service/API grouping section
        - Must have call convention section
        - Must have key entry APIs summary (not all endpoints)
        - Raw endpoint lines must not exceed 50
        """
        api_path = self.root / "docs/04-api-contracts.md"
        if not api_path.exists():
            return CheckResult(
                name="api-aggregated",
                status="FAIL",
                message="docs/04-api-contracts.md does not exist",
                reason_code=ReasonCode.CONTENT_EMPTY,
                gate_type=GateType.HARD,  # Missing file is hard gate
            )

        content = read_text(api_path)
        if not content:
            return CheckResult(
                name="api-aggregated",
                status="FAIL",
                message="docs/04-api-contracts.md is empty",
                reason_code=ReasonCode.CONTENT_EMPTY,
                gate_type=GateType.HARD,  # Empty content is hard gate
            )

        # Check for required sections
        has_grouping = "## 服务/API 分组" in content or "## API Groups" in content
        has_conventions = "## 调用约定" in content or "## Call Conventions" in content
        has_key_apis = "关键入口" in content or "key entry" in content.lower()

        missing_sections = []
        if not has_grouping:
            missing_sections.append("service/API grouping")
        if not has_conventions:
            missing_sections.append("call conventions")
        if not has_key_apis:
            missing_sections.append("key entry APIs")

        if missing_sections:
            return CheckResult(
                name="api-aggregated",
                status="FAIL",
                message=f"API contracts missing: {', '.join(missing_sections)}",
                details={"missing_sections": missing_sections},
                reason_code=ReasonCode.AGG_API_NOT_GROUPED,
                gate_type=GateType.SOFT,  # Quality issue - soft gate
            )

        # Check raw endpoint count
        lines = [l.strip() for l in content.split("\n") if l.strip()]
        endpoint_patterns = [
            "| GET |",
            "| POST |",
            "| PUT |",
            "| PATCH |",
            "| DELETE |",
            "| *GET* |",
            "| *POST* |",
            "| *PUT* |",
            "| *PATCH* |",
            "| *DELETE* |",
        ]
        raw_endpoint_lines = sum(1 for line in lines if any(p in line for p in endpoint_patterns))

        if raw_endpoint_lines > self.API_MAX_RAW_ENDPOINTS:
            return CheckResult(
                name="api-aggregated",
                status="FAIL",
                message=f"API contracts has {raw_endpoint_lines} raw endpoints (>{self.API_MAX_RAW_ENDPOINTS}), should aggregate instead",
                details={
                    "raw_endpoints": raw_endpoint_lines,
                    "max_allowed": self.API_MAX_RAW_ENDPOINTS,
                },
                reason_code=ReasonCode.AGG_API_ENDPOINT_DUMP,
                gate_type=GateType.SOFT,  # Quality issue - soft gate
            )

        return CheckResult(
            name="api-aggregated",
            status="PASS",
            message="API contracts passes aggregation checks",
            details={"raw_endpoints": raw_endpoint_lines},
            gate_type=GateType.SOFT,
        )

    DM_MAX_RAW_MODELS = 30

    def _check_data_model_aggregated(self) -> CheckResult:
        """Check that docs/05-data-model.md is aggregated, not a raw model dump.

        Requirements:
        - Must have three sections: core models, service models, database/migration
        - Must have migration strategy
        - Raw model lines must not exceed 30
        """
        dm_path = self.root / "docs/05-data-model.md"
        if not dm_path.exists():
            return CheckResult(
                name="data-model-aggregated",
                status="FAIL",
                message="docs/05-data-model.md does not exist",
                reason_code=ReasonCode.CONTENT_EMPTY,
                gate_type=GateType.HARD,  # Missing file is hard gate
            )

        content = read_text(dm_path)
        if not content:
            return CheckResult(
                name="data-model-aggregated",
                status="FAIL",
                message="docs/05-data-model.md is empty",
                reason_code=ReasonCode.CONTENT_EMPTY,
                gate_type=GateType.HARD,  # Empty content is hard gate
            )

        # Check for required sections
        has_core = "## 核心数据模型" in content or "## Core Data Models" in content
        has_service = "## 服务数据模型" in content or "## Service Data Models" in content
        has_db = "## 数据库与迁移策略" in content or "## Database" in content

        missing_sections = []
        if not has_core:
            missing_sections.append("core data models")
        if not has_service:
            missing_sections.append("service data models")
        if not has_db:
            missing_sections.append("database/migration")

        if missing_sections:
            return CheckResult(
                name="data-model-aggregated",
                status="FAIL",
                message=f"Data model missing required sections: {', '.join(missing_sections)}",
                details={"missing_sections": missing_sections},
                reason_code=ReasonCode.AGG_DM_NOT_GROUPED,
                gate_type=GateType.SOFT,  # Quality issue - soft gate
            )

        # Check migration strategy
        has_migration = "迁移" in content or "migration" in content.lower()
        if not has_migration:
            return CheckResult(
                name="data-model-aggregated",
                status="FAIL",
                message="Data model missing migration strategy documentation",
                reason_code=ReasonCode.AGG_DM_NOT_GROUPED,
                gate_type=GateType.SOFT,  # Quality issue - soft gate
            )

        # Check raw model count
        lines = [l.strip() for l in content.split("\n") if l.strip()]
        raw_model_lines = sum(
            1 for line in lines if line.startswith("| ") and "model" in line.lower()
        )

        if raw_model_lines > self.DM_MAX_RAW_MODELS:
            return CheckResult(
                name="data-model-aggregated",
                status="FAIL",
                message=f"Data model has {raw_model_lines} raw model entries (>{self.DM_MAX_RAW_MODELS}), should aggregate instead",
                details={"raw_models": raw_model_lines, "max_allowed": self.DM_MAX_RAW_MODELS},
                reason_code=ReasonCode.AGG_DM_MODEL_DUMP,
                gate_type=GateType.SOFT,  # Quality issue - soft gate
            )

        return CheckResult(
            name="data-model-aggregated",
            status="PASS",
            message="Data model passes aggregation checks",
            details={"raw_models": raw_model_lines},
            gate_type=GateType.SOFT,
        )

    def _check_navigation_links(self) -> CheckResult:
        """Check that section pages and overview docs are stitched with valid navigation links.

        This is a PATH-AWARE check that:
        - Resolves markdown links to actual target files
        - Fails when referenced docs do not exist
        - Validates relative path depth is correct
        - Replaces string heuristics with real path parsing
        """
        sections_dir = self.root / "docs/sections"
        broken_links: list[dict[str, str]] = []
        validated_links: list[dict[str, str]] = []

        if sections_dir.exists():
            for section_slug in self.REQUIRED_SECTIONS:
                section_index = sections_dir / section_slug / "index.md"
                if not section_index.exists():
                    continue

                content = read_text(section_index)
                if not content:
                    broken_links.append(
                        {
                            "file": f"{section_slug}/index.md",
                            "reason": "empty content",
                            "code": ReasonCode.CONTENT_EMPTY,
                        }
                    )
                    continue

                # Extract and validate markdown links
                link_issues = self._validate_document_links(section_index, content)
                broken_links.extend(link_issues)

        # Check overview docs for section links
        overview_path = self.root / "docs/00-overview.md"
        if overview_path.exists():
            content = read_text(overview_path)
            link_issues = self._validate_document_links(overview_path, content)
            broken_links.extend(link_issues)

        if broken_links:
            return CheckResult(
                name="navigation-links",
                status="FAIL",
                message=f"Broken navigation links detected: {len(broken_links)} issues",
                details={"broken_links": broken_links},
                reason_code=ReasonCode.STRUCT_NAVIGATION_BROKEN,
                gate_type=GateType.HARD,  # Broken navigation is hard gate
            )

        return CheckResult(
            name="navigation-links",
            status="PASS",
            message="Navigation links are valid",
            details={"checked_sections": len(self.REQUIRED_SECTIONS)},
            gate_type=GateType.HARD,
        )

    def _validate_document_links(self, doc_path: Path, content: str) -> list[dict[str, str]]:
        """Validate all markdown links in a document by resolving them to actual files.

        Returns a list of issues found. Empty list means all links are valid.
        """
        issues: list[dict[str, str]] = []

        # Pattern to match markdown links: [text](path)
        link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

        for match in link_pattern.finditer(content):
            link_text = match.group(1)
            link_target = match.group(2)

            # Skip external links and anchors
            if link_target.startswith(("http://", "https://", "mailto:", "#")):
                continue

            # Skip code block or other special links
            if link_target.startswith(("!", "{", "%")):
                continue

            # Resolve the relative path
            try:
                # Get the directory of the document
                doc_dir = doc_path.parent
                # Resolve the target path (handle ../ properly)
                # Use relative to doc_dir since links are relative to containing doc
                target_path = (doc_dir / link_target).resolve()

                # Check if the target exists
                if not target_path.exists():
                    issues.append(
                        {
                            "file": str(doc_path.relative_to(self.root)),
                            "link": link_target,
                            "resolved": str(target_path),
                            "reason": "linked file does not exist",
                            "code": ReasonCode.STRUCT_NAV_TARGET_MISSING,
                        }
                    )
                else:
                    # Link is valid - could track for later
                    pass

            except (ValueError, OSError) as e:
                issues.append(
                    {
                        "file": str(doc_path.relative_to(self.root)),
                        "link": link_target,
                        "reason": f"path resolution error: {e}",
                        "code": ReasonCode.STRUCT_NAV_BAD_DEPTH,
                    }
                )

        return issues

    # =============================================================================
    # Phase 23: Citation Quality Checks
    # =============================================================================

    # Pattern to match <cite> blocks: <cite>path/to/file:line[-line_end]</cite>
    # Optional symbol in parentheses: <cite>path/to/file:line (symbol)</cite>
    # Optional label after: <cite>path/to/file:line (symbol) label</cite>
    # Supports negative line numbers for invalid citations
    CITE_BLOCK_PATTERN = re.compile(
        r"<cite>\s*([^<>:]+):(-?\d+)(?:-(-?\d+))?\s*(?:\([^)]+\))?\s*(?:[^<]*)?</cite>"
    )

    # Pages that are checked for citation coverage
    CITATION_CHECKED_PAGES = [
        "docs/00-overview.md",
        "docs/01-architecture.md",
        "docs/03-module-map.md",
        "docs/04-api-contracts.md",
        "docs/05-data-model.md",
    ]

    def _check_citation_coverage(self) -> CheckResult:
        """Check that key documentation pages have at least one citation.

        This ensures that generated documentation maintains traceability
        to source code through file/line citations.

        The check is lenient: pages that don't exist or have minimal content
        are skipped. Only pages with substantial content are required to have
        citations for the PASS status.
        """
        pages_checked = 0
        pages_with_citations = 0
        pages_missing: list[str] = []

        # Minimum content threshold to require citations
        MIN_CONTENT_LENGTH = 50

        for page_path in self.CITATION_CHECKED_PAGES:
            full_path = self.root / page_path
            if not full_path.exists():
                # Skip non-existent pages
                continue

            content = read_text(full_path)

            # Skip pages with minimal content (they're likely placeholder content)
            if len(content.strip()) < MIN_CONTENT_LENGTH:
                continue

            pages_checked += 1

            # Look for <cite> blocks in the content
            citations = self.CITE_BLOCK_PATTERN.findall(content)
            if citations:
                pages_with_citations += 1
            else:
                pages_missing.append(page_path)

        if pages_missing:
            return CheckResult(
                name="citation-coverage",
                status="FAIL",
                message=f"Pages missing citations: {', '.join(pages_missing)}",
                details={
                    "pages_checked": pages_checked,
                    "pages_with_citations": pages_with_citations,
                    "pages_missing": pages_missing,
                },
                reason_code=ReasonCode.CITATION_MISSING,
                gate_type=self.severity_thresholds.get_gate_type(ReasonCode.CITATION_MISSING),
            )

        # If no pages were checked (all were minimal/placeholder), consider it a pass
        if pages_checked == 0:
            return CheckResult(
                name="citation-coverage",
                status="PASS",
                message="No pages with substantial content to check for citations",
                details={"pages_checked": 0},
                gate_type=GateType.SOFT,
            )

        return CheckResult(
            name="citation-coverage",
            status="PASS",
            message="All checked pages have citations",
            details={
                "pages_checked": pages_checked,
                "pages_with_citations": pages_with_citations,
            },
            gate_type=GateType.SOFT,
        )

    def _check_citation_validity(self) -> CheckResult:
        """Check that all citations reference valid file paths and line ranges.

        This ensures that citations can be traced back to actual source code.
        """
        all_broken: list[dict[str, Any]] = []

        # Check all documentation pages (use set to avoid duplicates from glob patterns)
        doc_pages: set[Path] = set()
        doc_pages.update(self.root.glob("docs/**/*.md"))
        doc_pages.update(self.root.glob("docs/*.md"))

        for doc_path in doc_pages:
            content = read_text(doc_path)
            issues = self._validate_citations_in_content(doc_path, content)
            all_broken.extend(issues)

        if all_broken:
            # Determine the appropriate reason code based on the actual errors
            has_bad_lines = any(
                issue.get("code") == ReasonCode.CITATION_BAD_LINES for issue in all_broken
            )
            reason_code = (
                ReasonCode.CITATION_BAD_LINES if has_bad_lines else ReasonCode.CITATION_BROKEN_PATH
            )

            return CheckResult(
                name="citation-validity",
                status="FAIL",
                message=f"Found {len(all_broken)} broken citation(s)",
                details={"broken_citations": all_broken},
                reason_code=reason_code,
                gate_type=GateType.SOFT,  # Broken citations are soft gate
            )

        return CheckResult(
            name="citation-validity",
            status="PASS",
            message="All citations are valid",
            details={"citations_checked": len(all_broken)},
            gate_type=GateType.SOFT,
        )

    def _validate_citations_in_content(self, doc_path: Path, content: str) -> list[dict[str, Any]]:
        """Validate all citations in document content.

        Returns list of issues found. Empty list means all citations are valid.
        """
        issues: list[dict[str, Any]] = []

        # Find all <cite> blocks (supports negative line numbers)
        cite_pattern = re.compile(
            r"<cite>\s*([^<>:]+):(-?\d+)(?:-(-?\d+))?\s*(?:\([^)]+\))?\s*(?:[^<]*)?</cite>"
        )

        for match in cite_pattern.finditer(content):
            file_path = match.group(1)
            line_start = int(match.group(2))
            line_end_str = match.group(3)
            line_end = int(line_end_str) if line_end_str else line_start

            # Resolve relative to workspace root
            full_path = (
                self.root / file_path if not Path(file_path).is_absolute() else Path(file_path)
            )

            # Check for obviously invalid line numbers first (negative lines)
            # This doesn't require file existence check
            if line_start < 1:
                issues.append(
                    {
                        "file": str(doc_path.relative_to(self.root)),
                        "citation": match.group(0),
                        "path": file_path,
                        "line_start": line_start,
                        "reason": f"line start must be >= 1, got {line_start}",
                        "code": ReasonCode.CITATION_BAD_LINES,
                    }
                )
                continue

            # Check for reversed range (also obviously invalid)
            if line_end < line_start:
                issues.append(
                    {
                        "file": str(doc_path.relative_to(self.root)),
                        "citation": match.group(0),
                        "path": file_path,
                        "line_start": line_start,
                        "line_end": line_end,
                        "reason": f"line end ({line_end}) must be >= line start ({line_start})",
                        "code": ReasonCode.CITATION_BAD_LINES,
                    }
                )
                continue

            # Now check if file exists
            if not full_path.exists():
                issues.append(
                    {
                        "file": str(doc_path.relative_to(self.root)),
                        "citation": match.group(0),
                        "path": file_path,
                        "reason": "file does not exist",
                        "code": ReasonCode.CITATION_BROKEN_PATH,
                    }
                )
                continue

            # Check line range validity against actual file
            try:
                with open(full_path, encoding="utf-8") as f:
                    line_count = sum(1 for _ in f)

                # Check if line exceeds file
                if line_end > line_count:
                    issues.append(
                        {
                            "file": str(doc_path.relative_to(self.root)),
                            "citation": match.group(0),
                            "path": file_path,
                            "line_start": line_start,
                            "line_end": line_end,
                            "file_lines": line_count,
                            "reason": f"line end ({line_end}) exceeds file length ({line_count})",
                            "code": ReasonCode.CITATION_BAD_LINES,
                        }
                    )
                    continue

            except (ValueError, OSError) as e:
                issues.append(
                    {
                        "file": str(doc_path.relative_to(self.root)),
                        "citation": match.group(0),
                        "path": file_path,
                        "reason": f"error reading file: {e}",
                        "code": ReasonCode.CITATION_BROKEN_PATH,
                    }
                )

        return issues

    def _check_citation_source_empty(self) -> CheckResult:
        """Check that !!! cite blocks are not empty.

        Empty source blocks (!!! cite "sources" with no citations inside)
        indicate incomplete documentation generation.
        """
        all_empty_blocks: list[dict[str, Any]] = []

        # Check all documentation pages (use set to avoid duplicates from glob patterns)
        doc_pages: set[Path] = set()
        doc_pages.update(self.root.glob("docs/**/*.md"))
        doc_pages.update(self.root.glob("docs/*.md"))

        for doc_path in doc_pages:
            content = read_text(doc_path)
            issues = self._validate_source_blocks_in_content(doc_path, content)
            all_empty_blocks.extend(issues)

        if all_empty_blocks:
            return CheckResult(
                name="citation-source-empty",
                status="FAIL",
                message=f"Found {len(all_empty_blocks)} empty source block(s)",
                details={"empty_blocks": all_empty_blocks},
                reason_code=ReasonCode.CITATION_SOURCE_EMPTY,
                gate_type=GateType.HARD,  # Empty source blocks are hard gate
            )

        return CheckResult(
            name="citation-source-empty",
            status="PASS",
            message="All source blocks have citations",
            details={},
            gate_type=GateType.HARD,
        )

    def _validate_source_blocks_in_content(
        self, doc_path: Path, content: str
    ) -> list[dict[str, Any]]:
        """Validate that !!! cite blocks are not empty.

        Returns list of issues found. Empty list means all blocks are valid.
        """
        issues: list[dict[str, Any]] = []

        # Pattern for !!! cite "section_id" blocks
        # These blocks should have at least one <cite> inside
        cite_block_pattern = re.compile(
            r'!!! cite\s+"([^"]+)"\s*\n((?:[ \t]+[^\n]*\n)*)', re.MULTILINE
        )

        for match in cite_block_pattern.finditer(content):
            section_id = match.group(1)
            block_content = match.group(2)

            # Check if block has any <cite> references
            has_citations = bool(self.CITE_BLOCK_PATTERN.search(block_content))

            if not has_citations:
                issues.append(
                    {
                        "file": str(doc_path.relative_to(self.root)),
                        "section_id": section_id,
                        "reason": "source block has no citations",
                        "code": ReasonCode.CITATION_SOURCE_EMPTY,
                    }
                )

        return issues
