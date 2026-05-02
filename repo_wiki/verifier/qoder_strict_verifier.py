"""Strict verifier for qoder-like profile."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from repo_wiki.verifier.service import CheckResult, GateType, VerifierService


class QoderLikeSeverityThreshold:
    """Strict severity thresholds for qoder-like profile."""

    STRICT_HARD_CODES = {
        "QODER_CONTENT_EMPTY",
        "QODER_CITATION_MISSING",
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

    def __init__(self, root: Path, retrieval_service=None, strict: bool = True) -> None:
        super().__init__(
            root,
            retrieval_service,
            severity_thresholds=QoderLikeSeverityThreshold(warn_on_soft=not strict),
        )
        self.strict = strict

    def verify(self, ci: bool = True) -> dict[str, Any]:
        checks: list[CheckResult] = [
            self._check_qoder_content_presence(),
            self._check_qoder_citation_presence(),
            self._check_qoder_toc_presence(),
            self._check_qoder_file_line_ref_coverage(),
            self._check_qoder_file_refs(),
            self._check_qoder_mermaid_coverage(),
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
            if re.search(r"^#{1,6}\s+(Table of Contents|目录|Contents|TOC)", content, re.MULTILINE) or "[TOC]" in content:
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
        api_dirs = [path for path in (content_dir / "pages" / "api", content_dir / "API参考") if path.exists()]
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
        model_dirs = [path for path in (content_dir / "pages" / "data-models", content_dir / "数据模型") if path.exists()]
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
            if stripped.startswith("#") or stripped.startswith("-") or stripped.startswith("*") or stripped.startswith("|"):
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
        candidates = [root / "manifest.json", root.parent / "manifest.json", root / "meta.json", root / "metadata.json"]
        for path in candidates:
            if not path.exists() or not path.is_file():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            for key in ("wiki_git_commit", "target_git_commit", "commit_hash", "git_commit", "commit"):
                value = payload.get(key)
                if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{7,40}", value):
                    return value
        return None


def create_qoder_like_verifier(root: Path, strict: bool = True) -> QoderLikeVerifierService:
    return QoderLikeVerifierService(root, strict=strict)


def verify_qoder_like(root: Path, ci: bool = True, strict: bool = True) -> dict[str, Any]:
    verifier = create_qoder_like_verifier(root, strict)
    return verifier.verify(ci=ci)
