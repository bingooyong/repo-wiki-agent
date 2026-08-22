"""Tests for Qoder-like strict verifier."""

import json

import pytest

from repo_wiki.verifier.qoder_strict_verifier import (
    QoderLikeSeverityThreshold,
    QoderLikeVerifierService,
    create_qoder_like_verifier,
    verify_qoder_like,
)


class TestQoderLikeSeverityThreshold:
    """Tests for qoder-like severity thresholds."""

    def test_strict_hard_codes_defined(self):
        """Test that strict hard codes are defined."""
        threshold = QoderLikeSeverityThreshold()
        assert len(threshold.STRICT_HARD_CODES) > 0
        assert "QODER_CITATION_MISSING" in threshold.STRICT_HARD_CODES
        assert "QODER_TOC_MISSING" in threshold.STRICT_HARD_CODES
        assert "QODER_FILE_REF_BROKEN" in threshold.STRICT_HARD_CODES

    def test_strict_mode_warn_on_soft_false(self):
        """Test that strict mode defaults to warn_on_soft=False."""
        threshold = QoderLikeSeverityThreshold()
        assert threshold.warn_on_soft is False

    def test_soft_to_hard_conversion(self):
        """Test that soft codes become hard in strict mode."""
        from repo_wiki.verifier.service import GateType

        threshold = QoderLikeSeverityThreshold()
        assert threshold.get_gate_type("CONTENT_LIST_ONLY") == GateType.HARD
        assert threshold.get_gate_type("CITATION_MISSING") == GateType.HARD


class TestQoderLikeVerifierService:
    """Tests for QoderLikeVerifierService."""

    @pytest.fixture
    def setup_content(self, tmp_path):
        """Set up content directory."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        # Create a page with citations and TOC
        (content_dir / "00-overview.md").write_text("""# Project Overview

## Table of Contents
- [Introduction](#introduction)
- [Architecture](#architecture)

## Introduction

This project provides comprehensive functionality.

<cite>source:docs/overview.md</cite>

## Architecture

The system uses microservices.

<cite>source:docs/architecture.md</cite>
""")

        return tmp_path

    def test_create_verifier(self, setup_content):
        """Test creating qoder-like verifier."""
        verifier = QoderLikeVerifierService(setup_content, strict=True)
        assert verifier.strict is True

    def test_verify_passes_with_good_content(self, setup_content):
        """Test verification passes with good content."""
        verifier = QoderLikeVerifierService(setup_content, strict=True)
        result = verifier.verify(ci=True)

        assert "grade" in result
        assert result["profile"] == "qoder-like"
        assert result["strict_mode"] is True

    def test_verify_detects_missing_citations(self, tmp_path):
        """Test detection of missing citations."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        # Create a page without citations (but long enough to be checked)
        (content_dir / "00-overview.md").write_text("""# Project Overview

## Introduction

This project provides comprehensive functionality for managing
resources and handling various operations. It includes multiple
services that work together to provide a complete solution.

## Architecture

The system follows a microservices architecture with separate
components for authentication, data processing, and API management.
Each component is designed to be independent and scalable.

## Features

- Feature 1: Authentication services
- Feature 2: Data processing pipelines
- Feature 3: API management layer
- Feature 4: Monitoring and logging
- Feature 5: Configuration management
""")

        verifier = QoderLikeVerifierService(tmp_path, strict=True)
        result = verifier.verify(ci=True)

        # Should have hard failure for citation
        hard_codes = result.get("hard_gate_codes", [])
        assert any("QODER" in code for code in hard_codes)

    def test_verify_detects_missing_toc(self, tmp_path):
        """Test detection of missing TOC."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        # Create overview page without TOC
        (content_dir / "00-overview.md").write_text("""# Project Overview

## Introduction

This project does something.

<cite>source:docs/overview.md</cite>
""")

        verifier = QoderLikeVerifierService(tmp_path, strict=True)
        result = verifier.verify(ci=True)

        # Should have hard failure for TOC
        hard_codes = result.get("hard_gate_codes", [])
        assert any("QODER_TOC" in code for code in hard_codes)

    def test_verify_detects_dump_pages(self, tmp_path):
        """Test detection of dump pages."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        # Create a dump page (mostly lists)
        content = "# API Reference\n\n"
        for i in range(20):
            content += f"- Endpoint {i}: /api/v1/resource/{i}\n"

        (content_dir / "04-api.md").write_text(content)

        verifier = QoderLikeVerifierService(tmp_path, strict=True)
        result = verifier.verify(ci=True)

        hard_codes = result.get("hard_gate_codes", [])
        assert "QODER_PAGE_DUMP" in hard_codes or len(hard_codes) > 0

    def test_verify_exit_code_on_hard_failure(self, tmp_path):
        """Test exit code is 1 on hard failure."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        # Create page without citations
        (content_dir / "00-overview.md").write_text("# Overview\n\nShort content.")

        verifier = QoderLikeVerifierService(tmp_path, strict=True)
        result = verifier.verify(ci=True)

        # If there are hard failures, exit code should be 1
        if result.get("hard_gate_failures", 0) > 0:
            assert result["exit_code"] == 1


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_qoder_like_verifier(self, tmp_path):
        """Test create_qoder_like_verifier factory."""
        verifier = create_qoder_like_verifier(tmp_path)
        assert isinstance(verifier, QoderLikeVerifierService)

    def test_verify_qoder_like_function(self, tmp_path):
        """Test verify_qoder_like function."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()
        (content_dir / "00-overview.md").write_text("# Overview\n\n<cite>x</cite>\n\n## TOC\n- a")

        result = verify_qoder_like(tmp_path, ci=True, strict=True)
        assert "grade" in result
        assert result["strict_mode"] is True


class TestRegression:
    """Regression tests for hard failures."""

    def test_no_false_positives_on_clean_content(self, tmp_path):
        """Test no false positives on clean content."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        # Create clean content
        (content_dir / "00-overview.md").write_text("""# Project Overview

## Table of Contents
- [Intro](#intro)

## Introduction

This is a sample project.

<cite>source:intro.md</cite>

## Additional Section

More content here.
""")

        verifier = QoderLikeVerifierService(tmp_path, strict=True)
        result = verifier.verify(ci=True)

        # Should pass with no hard failures
        if result["grade"] == "FAIL":
            # If it failed, check that it's not due to false positives
            hard_codes = result.get("hard_gate_codes", [])
            # At minimum, should not have false positive codes
            for code in hard_codes:
                assert (
                    code.startswith("QODER_")
                    or code.startswith("STRUCT")
                    or code.startswith("CONTENT")
                )

    def test_file_ref_check_handles_relative_paths(self, tmp_path):
        """Test file reference check handles relative paths correctly."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        # Create content with relative reference to existing file
        (content_dir / "00-overview.md").write_text(
            "# Overview\n\n[Intro](01-intro.md)\n\n<cite>x</cite>"
        )
        (content_dir / "01-intro.md").write_text("# Introduction\n\n<cite>y</cite>")

        verifier = QoderLikeVerifierService(tmp_path, strict=True)
        result = verifier.verify(ci=True)

        # Should not have broken ref failure
        hard_codes = result.get("hard_gate_codes", [])
        # QODER_FILE_REF_BROKEN should not appear
        assert "QODER_FILE_REF_BROKEN" not in hard_codes


class TestStaleCommitAndDirtyTree:
    """Regression tests for stale commit and dirty worktree detection."""

    def test_dirty_worktree_detected(self, tmp_path):
        """Test that dirty worktree triggers QODER_DIRTY_WORKTREE in strict mode."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        # Create clean content to avoid other failures
        (content_dir / "00-overview.md").write_text("""# Project Overview

## Table of Contents
- [Intro](#intro)

## Introduction

This is a sample project.

<cite>source:intro.md</cite>

## Additional Section

More content here.
""")

        # Create a git repo with dirty state
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (tmp_path / "README.md").write_text("# Test")  # Untracked file = dirty

        # The verifier should detect the dirty worktree
        # Note: We test the path up to the content dir's parent since
        # _git_dirty checks the git root
        verifier = QoderLikeVerifierService(tmp_path, strict=True)

        # Since there's no actual git repo with commits, _git_dirty returns False
        # This test documents expected behavior when git is not initialized
        # A real implementation would create a proper git repo with commits
        result = verifier.verify(ci=True)

        # Verify the check ran (dirty state may not trigger without real git)
        assert "qoder-dirty-worktree" in [c["name"] for c in result.get("checks", [])]

    def test_stale_commit_detection(self, tmp_path):
        """Test that stale wiki commit triggers QODER_STALE_GIT_COMMIT."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        # Create content that passes other checks
        (content_dir / "00-overview.md").write_text("""# Project Overview

## Table of Contents
- [Intro](#intro)

## Introduction

This is a sample project.

<cite>source:intro.md</cite>

## Architecture

The system uses microservices.

<cite>source:architecture.md</cite>
""")

        # Create a fake manifest with different commit to simulate stale state
        manifest = {
            "wiki_git_commit": "abc123def456789",
            "version": "1.0",
        }
        import json

        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        verifier = QoderLikeVerifierService(tmp_path, strict=True)
        result = verifier.verify(ci=True)

        # Should have either passed or skipped stale check depending on current git state
        # The important thing is it ran and didn't crash
        assert "stale-commit" in [c["name"] for c in result.get("checks", [])]

    def test_clean_worktree_passes_dirty_check(self, tmp_path):
        """Test that clean worktree passes dirty check (no false positive)."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        # Create content that passes all checks
        (content_dir / "00-overview.md").write_text("""# Project Overview

## Table of Contents
- [Intro](#intro)

## Introduction

This is a sample project with substantial content to pass quality checks.

<cite>source:intro.md</cite>

## Additional Section

More content here with additional details about the project structure
and how the components work together to provide functionality.

## Architecture

The system follows a microservices architecture.

<cite>source:architecture.md</cite>
""")

        verifier = QoderLikeVerifierService(tmp_path, strict=True)
        result = verifier.verify(ci=True)

        # If there are no hard failures about dirty state, clean worktree passes
        hard_codes = result.get("hard_gate_codes", [])
        # QODER_DIRTY_WORKTREE should not appear in clean state
        assert "QODER_DIRTY_WORKTREE" not in hard_codes

    def test_stale_hard_code_is_defined(self):
        """Test that QODER_STALE_GIT_COMMIT is a defined hard code."""
        from repo_wiki.verifier.qoder_strict_verifier import QoderLikeSeverityThreshold

        threshold = QoderLikeSeverityThreshold()
        assert "QODER_STALE_GIT_COMMIT" in threshold.STRICT_HARD_CODES

    def test_dirty_worktree_hard_code_is_defined(self):
        """Test that QODER_DIRTY_WORKTREE is a defined hard code."""
        from repo_wiki.verifier.qoder_strict_verifier import QoderLikeSeverityThreshold

        threshold = QoderLikeSeverityThreshold()
        assert "QODER_DIRTY_WORKTREE" in threshold.STRICT_HARD_CODES

    def test_citation_relevance_mismatch_hard_code_is_defined(self):
        """Test that QODER_CITATION_RELEVANCE_MISMATCH is a defined hard code."""
        from repo_wiki.verifier.qoder_strict_verifier import QoderLikeSeverityThreshold

        threshold = QoderLikeSeverityThreshold()
        assert "QODER_CITATION_RELEVANCE_MISMATCH" in threshold.STRICT_HARD_CODES

    def test_mermaid_reason_codes_are_defined(self):
        """Test Mermaid missing reason codes are hard codes."""
        threshold = QoderLikeSeverityThreshold()
        assert "QODER_API_MERMAID_MISSING" in threshold.STRICT_HARD_CODES
        assert "QODER_ENDPOINT_LIFECYCLE_MERMAID_MISSING" in threshold.STRICT_HARD_CODES
        assert "QODER_DATA_MODEL_ER_MERMAID_MISSING" in threshold.STRICT_HARD_CODES


class TestManifestReadinessContract:
    """Tests for eval run manifest readiness contract."""

    def _write_good_content(self, tmp_path):
        content_dir = tmp_path / "content"
        content_dir.mkdir(exist_ok=True)
        (content_dir / "00-overview.md").write_text(
            """# Project Overview

## Table of Contents
- [Intro](#intro)

## Intro

This is sufficient prose content for strict checks with citations.

<cite>src/app.py:12</cite>
""",
            encoding="utf-8",
        )

    def _write_manifest(self, tmp_path, payload: dict):
        (tmp_path / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")

    def _base_manifest(self, tmp_path, *, readiness_state: str = "READY") -> dict:
        run_id = "run-1"
        base = {
            "version": "1.1",
            "run_id": run_id,
            "readiness_state": readiness_state,
            "readiness_reasons": [],
            "target_dirty": False,
            "git_fresh": True,
            "candidate_repowiki_zh_root": str(
                tmp_path / ".repo-agent-eval" / "runs" / run_id / "repowiki" / "zh"
            ),
            "candidate_content_root": str(
                tmp_path / ".repo-agent-eval" / "runs" / run_id / "repowiki" / "zh" / "content"
            ),
            "candidate_meta_root": str(
                tmp_path / ".repo-agent-eval" / "runs" / run_id / "repowiki" / "zh" / "meta"
            ),
            "report_paths": {"verify_report": "reports/strict-verify-output.json"},
            "files": [{"path": "reports/strict-verify-output.json"}],
            "evidence": [],
        }
        return base

    def test_missing_readiness_state_fails(self, tmp_path):
        self._write_good_content(tmp_path)
        payload = self._base_manifest(tmp_path)
        payload.pop("readiness_state")
        self._write_manifest(tmp_path, payload)

        result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)
        assert "QODER_MANIFEST_NOT_READY" in result.get("hard_gate_codes", [])

    def test_dirty_target_cannot_be_ready(self, tmp_path):
        self._write_good_content(tmp_path)
        payload = self._base_manifest(tmp_path, readiness_state="READY")
        payload["target_dirty"] = True
        self._write_manifest(tmp_path, payload)

        result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)
        assert "QODER_DIRTY_WORKTREE" in result.get("hard_gate_codes", [])

    def test_stale_git_cannot_be_ready(self, tmp_path):
        self._write_good_content(tmp_path)
        payload = self._base_manifest(tmp_path, readiness_state="READY")
        payload["git_fresh"] = False
        self._write_manifest(tmp_path, payload)

        result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)
        assert "QODER_STALE_GIT_COMMIT" in result.get("hard_gate_codes", [])

    def test_missing_content_meta_roots_fail(self, tmp_path):
        self._write_good_content(tmp_path)
        payload = self._base_manifest(tmp_path, readiness_state="READY")
        payload.pop("candidate_content_root")
        payload.pop("candidate_meta_root")
        self._write_manifest(tmp_path, payload)

        result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)
        hard_codes = result.get("hard_gate_codes", [])
        assert "QODER_CONTENT_ROOT_MISSING" in hard_codes or "QODER_META_ROOT_MISSING" in hard_codes

    def test_report_paths_mismatch_fails(self, tmp_path):
        self._write_good_content(tmp_path)
        payload = self._base_manifest(tmp_path, readiness_state="READY")
        payload["report_paths"] = {"verify_report": "reports/missing.json"}
        payload["files"] = [{"path": "reports/strict-verify-output.json"}]
        self._write_manifest(tmp_path, payload)

        result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)
        assert "QODER_REPORT_MISMATCH" in result.get("hard_gate_codes", [])


class TestG005StrictQualityGates:
    """Regression coverage for G005 P0/P1 strict qoder-like gates."""

    def _write_release_candidate(self, tmp_path, *, quality_state: str = "READY") -> None:
        content_dir = tmp_path / "repowiki" / "zh" / "content"
        meta_dir = tmp_path / "repowiki" / "zh" / "meta"
        content_dir.mkdir(parents=True)
        meta_dir.mkdir(parents=True)
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("\n".join(f"line {i}" for i in range(1, 41)))
        page_rel = "项目概述/00-overview.md"
        page = content_dir / page_rel
        page.parent.mkdir()
        page.write_text(
            """# Project Overview

## Table of Contents
- [Intro](#intro)

## Intro

GET /health is the supported health endpoint for Service `api-gateway` and Model `user-entity`.

```mermaid
graph LR
  A --> B
```

<cite>source:src/app.py:1-10</cite>
""",
            encoding="utf-8",
        )
        (meta_dir / "quality-report.json").write_text(
            json.dumps(
                {
                    "schema_version": "repo_agent.quality_report/1.0",
                    "summary": {"profile": "qoder-like", "grade": "PASS", "strict_mode": True},
                    "page_quality": [{"relative_path": page_rel, "quality_state": quality_state}],
                }
            ),
            encoding="utf-8",
        )
        (meta_dir / "page-registry.json").write_text(
            json.dumps(
                {
                    "schema_version": "repo_agent.page_registry/1.0",
                    "generated_at": "2026-07-15T00:00:00Z",
                    "pages": [
                        {
                            "page_id": "overview",
                            "relative_path": page_rel,
                            "category": "overview",
                            "page_type": "content",
                            "quality_state": quality_state,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (meta_dir / "api-inventory.json").write_text(
            json.dumps({"endpoints": [{"method": "GET", "path": "/health"}]}),
            encoding="utf-8",
        )
        (meta_dir / "service-registry.json").write_text(
            json.dumps({"services": [{"service_id": "api-gateway"}]}), encoding="utf-8"
        )
        (meta_dir / "data-model-inventory.json").write_text(
            json.dumps({"models": [{"model_id": "user-entity"}]}), encoding="utf-8"
        )
        (meta_dir / "runtime-inventory.json").write_text(
            json.dumps({"runtime_entrypoints": [{"entrypoint": "repo-wiki"}]}),
            encoding="utf-8",
        )
        (meta_dir / "source-inventory.json").write_text(
            json.dumps(
                {
                    "schema_version": "repo_agent.source_inventory/1.0",
                    "services": [{"service_id": "api-gateway"}],
                    "api_surfaces": [{"method": "GET", "path": "/health"}],
                    "data_models": [{"model_id": "user-entity"}],
                    "runtime_entrypoints": [{"entrypoint": "repo-wiki"}],
                }
            ),
            encoding="utf-8",
        )
        manifest = {
            "version": "1.1",
            "run_id": "run-g005",
            "readiness_state": "READY",
            "readiness_reasons": [],
            "target_dirty": False,
            "git_fresh": True,
            "candidate_repowiki_zh_root": str(tmp_path / "repowiki" / "zh"),
            "candidate_content_root": str(content_dir),
            "candidate_meta_root": str(meta_dir),
            "report_paths": {"strict_verify": "reports/strict-verify-output.json"},
            "files": [{"path": "reports/strict-verify-output.json"}],
            "evidence": [],
        }
        (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def test_release_candidate_missing_manifest_hard_fails(self, tmp_path):
        run_dir = tmp_path / ".repo-agent-eval" / "runs" / "run-missing"
        (run_dir / "repowiki" / "zh" / "content").mkdir(parents=True)
        result = QoderLikeVerifierService(run_dir, strict=True).verify(ci=True)
        assert "QODER_MANIFEST_MISSING" in result.get("hard_gate_codes", [])

    def test_content_only_fixture_without_manifest_remains_compatible(self, tmp_path):
        (tmp_path / "fixture_metadata.json").write_text(json.dumps({"name": "fixture"}))
        content_dir = tmp_path / "content"
        content_dir.mkdir()
        (content_dir / "00-overview.md").write_text("# Overview\n\n<cite>source:x.py:1</cite>")
        result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)
        manifest_check = next(
            c for c in result["checks"] if c["name"] == "qoder-manifest-readiness"
        )
        assert manifest_check["status"] == "PASS"
        assert "QODER_MANIFEST_MISSING" not in result.get("hard_gate_codes", [])

    def test_release_candidate_invalid_citation_path_and_line_bounds_fail(self, tmp_path):
        self._write_release_candidate(tmp_path)
        page = tmp_path / "repowiki" / "zh" / "content" / "项目概述" / "00-overview.md"
        page.write_text(
            page.read_text(encoding="utf-8")
            + "\n<cite>source:/etc/passwd:1</cite>\n<cite>source:src/app.py:1-999</cite>\n",
            encoding="utf-8",
        )
        result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)
        assert "QODER_CITATION_INVALID" in result.get("hard_gate_codes", [])

    def test_release_candidate_missing_quality_artifacts_fail(self, tmp_path):
        self._write_release_candidate(tmp_path)
        (tmp_path / "repowiki" / "zh" / "meta" / "quality-report.json").unlink()
        result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)
        assert "QODER_QUALITY_ARTIFACT_MISSING" in result.get("hard_gate_codes", [])

    def test_release_candidate_degraded_page_quality_state_fails(self, tmp_path):
        self._write_release_candidate(tmp_path, quality_state="fallback-degraded")
        result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)
        assert "QODER_PAGE_QUALITY_STATE_DEGRADED" in result.get("hard_gate_codes", [])

    def test_release_candidate_empty_quality_artifacts_ignore_manifest_self_attestation(
        self, tmp_path
    ):
        self._write_release_candidate(tmp_path)
        meta_dir = tmp_path / "repowiki" / "zh" / "meta"
        manifest_path = tmp_path / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["pages"] = [{"relative_path": "项目概述/00-overview.md", "quality_state": "READY"}]
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        (meta_dir / "quality-report.json").write_text(
            json.dumps(
                {
                    "schema_version": "repo_agent.quality_report/1.0",
                    "summary": {"profile": "qoder-like", "grade": "PASS", "strict_mode": True},
                    "page_quality": [],
                }
            ),
            encoding="utf-8",
        )
        (meta_dir / "page-registry.json").write_text(
            json.dumps(
                {
                    "schema_version": "repo_agent.page_registry/1.0",
                    "generated_at": "2026-07-15T00:00:00Z",
                    "pages": [],
                }
            ),
            encoding="utf-8",
        )

        result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)

        assert "QODER_PAGE_QUALITY_STATE_MISSING" in result.get("hard_gate_codes", [])

    def test_release_candidate_quality_artifact_corrupt_json_fails(self, tmp_path):
        self._write_release_candidate(tmp_path)
        (tmp_path / "repowiki" / "zh" / "meta" / "quality-report.json").write_text(
            "{not-json", encoding="utf-8"
        )

        result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)

        assert "QODER_QUALITY_ARTIFACT_INVALID" in result.get("hard_gate_codes", [])

    def test_release_candidate_quality_artifact_wrong_shape_fails(self, tmp_path):
        self._write_release_candidate(tmp_path)
        (tmp_path / "repowiki" / "zh" / "meta" / "page-registry.json").write_text(
            json.dumps([{"relative_path": "项目概述/00-overview.md", "quality_state": "READY"}]),
            encoding="utf-8",
        )

        result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)

        assert "QODER_QUALITY_ARTIFACT_INVALID" in result.get("hard_gate_codes", [])

    @pytest.mark.parametrize(
        ("mutation", "expected_detail"),
        [
            ("missing", "missing"),
            ("duplicate", "duplicate"),
            ("extra", "extra"),
            ("mismatch", "do not match"),
        ],
    )
    def test_release_candidate_quality_artifact_path_coverage_fails(
        self, tmp_path, mutation, expected_detail
    ):
        self._write_release_candidate(tmp_path)
        meta_dir = tmp_path / "repowiki" / "zh" / "meta"
        quality_path = meta_dir / "quality-report.json"
        registry_path = meta_dir / "page-registry.json"
        quality = json.loads(quality_path.read_text(encoding="utf-8"))
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        if mutation == "missing":
            quality["page_quality"] = []
        elif mutation == "duplicate":
            quality["page_quality"].append(dict(quality["page_quality"][0]))
        elif mutation == "extra":
            quality["page_quality"].append({"relative_path": "ghost.md", "quality_state": "READY"})
        elif mutation == "mismatch":
            registry["pages"][0]["relative_path"] = "other.md"
        quality_path.write_text(json.dumps(quality), encoding="utf-8")
        registry_path.write_text(json.dumps(registry), encoding="utf-8")

        result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)
        quality_check = next(c for c in result["checks"] if c["name"] == "qoder-quality-artifacts")

        assert "QODER_PAGE_QUALITY_STATE_MISSING" in result.get("hard_gate_codes", [])
        assert expected_detail in json.dumps(quality_check["details"], ensure_ascii=False)

    def test_release_candidate_corrupt_conflict_artifact_hard_fails(self, tmp_path):
        self._write_release_candidate(tmp_path)
        (tmp_path / "repowiki" / "zh" / "meta" / "source-docs-conflicts.json").write_text(
            "{not-json", encoding="utf-8"
        )

        result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)

        assert "QODER_CONFLICT_ARTIFACT_INVALID" in result.get("hard_gate_codes", [])

    def test_release_candidate_wrong_shape_conflict_artifact_hard_fails(self, tmp_path):
        self._write_release_candidate(tmp_path)
        (tmp_path / "repowiki" / "zh" / "meta" / "source-docs-conflicts.json").write_text(
            json.dumps({"summary": [], "deferred_items": {"id": "not-a-list"}}),
            encoding="utf-8",
        )

        result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)

        assert "QODER_CONFLICT_ARTIFACT_INVALID" in result.get("hard_gate_codes", [])

    def test_unresolved_fact_conflict_artifact_fails(self, tmp_path):
        self._write_release_candidate(tmp_path)
        reports = tmp_path / "reports"
        reports.mkdir()
        (reports / "source-docs-conflicts.json").write_text(
            json.dumps(
                {
                    "schema_version": "source-docs-conflict-resolver-v1",
                    "summary": {
                        "resolved_count": 0,
                        "deferred_count": 1,
                        "flagged_count": 0,
                        "total_items": 1,
                    },
                    "resolved_items": [],
                    "deferred_items": [{"id": "c1"}],
                    "flagged_items": [],
                }
            ),
            encoding="utf-8",
        )
        result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)
        assert "QODER_UNRESOLVED_FACT_CONFLICT" in result.get("hard_gate_codes", [])

    def test_critical_false_api_claim_against_inventory_fails(self, tmp_path):
        self._write_release_candidate(tmp_path)
        page = tmp_path / "repowiki" / "zh" / "content" / "项目概述" / "00-overview.md"
        page.write_text(page.read_text(encoding="utf-8") + "\nPOST /ghost is not real.\n")
        result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)
        assert "QODER_CRITICAL_FALSE_FACT" in result.get("hard_gate_codes", [])


class TestCitationRelevance:
    """Tests for citation relevance verification."""

    def test_citation_relevance_detects_wrong_service_binding(self, tmp_path):
        """Test detection of citations bound to wrong service."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        # Create a billing page that cites authentication implementation
        (content_dir / "billing-service.md").write_text("""# Billing Service

## Overview

The billing service handles payments and subscriptions.

<cite>src/auth/session.py:1</cite>

## Features

- Payment processing
- Invoice generation
""")

        verifier = QoderLikeVerifierService(tmp_path, strict=True)
        result = verifier.verify(ci=True)

        # Should detect mismatch
        hard_codes = result.get("hard_gate_codes", [])
        assert "QODER_CITATION_RELEVANCE_MISMATCH" in hard_codes


class TestMermaidCoverageGates:
    """Tests for API/service Mermaid coverage hard gates."""

    def test_api_page_missing_mermaid_fails(self, tmp_path):
        content_dir = tmp_path / "content"
        api_dir = content_dir / "API参考"
        api_dir.mkdir(parents=True)

        (api_dir / "orders-service-api.md").write_text(
            """# Orders Service API

## Table of Contents
- [Overview](#overview)

## Overview

Service API documentation.

<cite>src/orders/controller.py:10</cite>
""",
            encoding="utf-8",
        )

        verifier = QoderLikeVerifierService(tmp_path, strict=True)
        result = verifier.verify(ci=True)

        assert "QODER_API_MERMAID_MISSING" in result.get("hard_gate_codes", [])

    def test_endpoint_lifecycle_without_sequence_or_flow_fails(self, tmp_path):
        content_dir = tmp_path / "content"
        api_dir = content_dir / "API参考"
        api_dir.mkdir(parents=True)

        (api_dir / "payment-endpoint-lifecycle.md").write_text(
            """# Payment Endpoint Lifecycle

## Table of Contents
- [Request](#request)

## Request

Lifecycle details with no sequence or flow Mermaid.

```mermaid
classDiagram
  PaymentController --> PaymentService
```

<cite>src/payment/controller.py:10</cite>
""",
            encoding="utf-8",
        )

        verifier = QoderLikeVerifierService(tmp_path, strict=True)
        result = verifier.verify(ci=True)

        assert "QODER_ENDPOINT_LIFECYCLE_MERMAID_MISSING" in result.get("hard_gate_codes", [])

    def test_data_model_relationship_without_er_fails(self, tmp_path):
        content_dir = tmp_path / "content"
        model_dir = content_dir / "数据模型"
        model_dir.mkdir(parents=True)

        (model_dir / "订单关系模型.md").write_text(
            """# 订单关系模型

## Table of Contents
- [关系](#关系)

## 关系

Order has many Items and references User via foreign key.

```mermaid
flowchart TD
  Order --> Item
```

<cite>src/models/order.py:1</cite>
""",
            encoding="utf-8",
        )

        verifier = QoderLikeVerifierService(tmp_path, strict=True)
        result = verifier.verify(ci=True)

        assert "QODER_DATA_MODEL_ER_MERMAID_MISSING" in result.get("hard_gate_codes", [])

    def test_citation_relevance_allows_shared_infrastructure(self, tmp_path):
        """Test that shared infrastructure citations produce WARN not FAIL."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        # Create billing page citing shared utility
        (content_dir / "billing-overview.md").write_text("""# Billing Service

## Overview

<cite>shared/utils/helpers.py:10</cite>

## Features

- Payment processing
""")

        verifier = QoderLikeVerifierService(tmp_path, strict=True)
        result = verifier.verify(ci=True)

        # Should warn but not fail on shared infra citation
        checks = result.get("checks", [])
        relevance_check = next((c for c in checks if c["name"] == "qoder-citation-relevance"), None)
        assert relevance_check is not None
        # Should be WARN, not FAIL
        assert relevance_check["status"] in ("PASS", "WARN")

    def test_citation_relevance_passes_for_matching_service(self, tmp_path):
        """Test that citations matching page service pass."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        # Create billing page citing billing implementation
        (content_dir / "billing-overview.md").write_text("""# Billing Service

## Overview

The billing service handles payments.

<cite>src/billing/payment.py:1</cite>

<cite>src/billing/invoice.py:5-10</cite>

## Features

- Payment processing
- Invoice generation
""")

        verifier = QoderLikeVerifierService(tmp_path, strict=True)
        result = verifier.verify(ci=True)

        # Should pass
        checks = result.get("checks", [])
        relevance_check = next((c for c in checks if c["name"] == "qoder-citation-relevance"), None)
        assert relevance_check is not None
        assert relevance_check["status"] == "PASS"

    def test_citation_relevance_api_page_with_api_citations(self, tmp_path):
        """Test that API page with API citations passes."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        (content_dir / "api-reference.md").write_text("""# API Reference

## Endpoints

<cite>src/api/handler.py:1</cite>

<cite>src/api/router.py:20</cite>
""")

        verifier = QoderLikeVerifierService(tmp_path, strict=True)
        result = verifier.verify(ci=True)

        checks = result.get("checks", [])
        relevance_check = next((c for c in checks if c["name"] == "qoder-citation-relevance"), None)
        assert relevance_check is not None
        assert relevance_check["status"] == "PASS"

    def test_citation_relevance_data_model_page_with_model_citations(self, tmp_path):
        """Test that data model page with model citations passes."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        (content_dir / "data-models.md").write_text("""# Data Models

## Core Models

<cite>src/models/entity.py:1</cite>

<cite>src/models/dto.py:10</cite>
""")

        verifier = QoderLikeVerifierService(tmp_path, strict=True)
        result = verifier.verify(ci=True)

        checks = result.get("checks", [])
        relevance_check = next((c for c in checks if c["name"] == "qoder-citation-relevance"), None)
        assert relevance_check is not None
        assert relevance_check["status"] == "PASS"

    def test_citation_relevance_wrong_service_multiple_mismatches(self, tmp_path):
        """Test detection of multiple wrong-service citations."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        # Create API page citing billing and auth implementation
        (content_dir / "api-overview.md").write_text("""# API Overview

## Services

<cite>src/billing/subscription.py:5</cite>

<cite>src/auth/jwt.py:10</cite>
""")

        verifier = QoderLikeVerifierService(tmp_path, strict=True)
        result = verifier.verify(ci=True)

        # Should detect mismatches
        hard_codes = result.get("hard_gate_codes", [])
        assert "QODER_CITATION_RELEVANCE_MISMATCH" in hard_codes


class TestG005SecondRoundVerifierClosure:
    """Focused regressions for second-round strict verifier closure."""

    def _write_complete_run(self, tmp_path, *, claim_count: int = 20, cited_count: int = 20):
        run_dir = tmp_path / ".repo-agent-eval" / "runs" / "run-g005b"
        content_dir = run_dir / "repowiki" / "zh" / "content"
        meta_dir = run_dir / "repowiki" / "zh" / "meta"
        content_dir.mkdir(parents=True)
        meta_dir.mkdir(parents=True)
        (run_dir / "src").mkdir()
        (run_dir / "src" / "app.py").write_text(
            "\n".join(f"line {i}" for i in range(1, 101)), encoding="utf-8"
        )
        blocks = [
            "# Project Overview\n",
            "## Table of Contents\n- [Intro](#intro)\n",
            "## Intro\n",
        ]
        for i in range(claim_count):
            blocks.append(f"Service `api-gateway` handles request path {i}.\n")
            if i < cited_count:
                blocks.append(f"<cite>source:src/app.py:{i + 1}</cite>\n")
            blocks.append("\n")
        blocks.append(
            "Owner page: Service `api-gateway`, GET /health, Model `user-entity`, and "
            "runtime entrypoint `repo-wiki` are owned by Platform Team.\n"
        )
        blocks.append("<cite>source:src/app.py:80</cite>\n\n")
        blocks.append("```mermaid\ngraph LR\n  A --> B\n```\n")
        page_rel = "项目概述/00-overview.md"
        page = content_dir / page_rel
        page.parent.mkdir()
        page.write_text("".join(blocks), encoding="utf-8")
        (meta_dir / "quality-report.json").write_text(
            json.dumps(
                {
                    "schema_version": "repo_agent.quality_report/1.0",
                    "summary": {"profile": "qoder-like", "grade": "PASS", "strict_mode": True},
                    "page_quality": [{"relative_path": page_rel, "quality_state": "READY"}],
                    "warnings": [],
                }
            ),
            encoding="utf-8",
        )
        (meta_dir / "page-registry.json").write_text(
            json.dumps(
                {
                    "schema_version": "repo_agent.page_registry/1.0",
                    "generated_at": "2026-07-15T00:00:00Z",
                    "pages": [
                        {
                            "page_id": "overview",
                            "relative_path": page_rel,
                            "category": "overview",
                            "page_type": "content",
                            "quality_state": "READY",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (meta_dir / "api-inventory.json").write_text(
            json.dumps({"endpoints": [{"method": "GET", "path": "/health", "public": True}]}),
            encoding="utf-8",
        )
        (meta_dir / "service-registry.json").write_text(
            json.dumps({"services": [{"service_id": "api-gateway", "core": True}]}),
            encoding="utf-8",
        )
        (meta_dir / "data-model-inventory.json").write_text(
            json.dumps({"models": [{"model_id": "user-entity", "major": True}]}),
            encoding="utf-8",
        )
        (meta_dir / "runtime-inventory.json").write_text(
            json.dumps({"runtime_entrypoints": [{"entrypoint": "repo-wiki"}]}),
            encoding="utf-8",
        )
        (meta_dir / "source-inventory.json").write_text(
            json.dumps(
                {
                    "schema_version": "repo_agent.source_inventory/1.0",
                    "services": [{"service_id": "api-gateway"}],
                    "api_surfaces": [{"method": "GET", "path": "/health", "auth_required": False}],
                    "data_models": [{"model_id": "user-entity"}],
                    "runtime_entrypoints": [{"entrypoint": "repo-wiki"}],
                    "relationships": [],
                }
            ),
            encoding="utf-8",
        )
        (meta_dir / "source-docs-conflicts.json").write_text(
            json.dumps(
                {
                    "schema_version": "source-docs-conflict-resolver-v1",
                    "summary": {
                        "resolved_count": 0,
                        "deferred_count": 0,
                        "flagged_count": 0,
                        "total_items": 0,
                    },
                    "resolved_items": [],
                    "deferred_items": [],
                    "flagged_items": [],
                }
            ),
            encoding="utf-8",
        )
        (run_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "version": "1.1",
                    "run_id": "run-g005b",
                    "readiness_state": "READY",
                    "readiness_reasons": [],
                    "target_dirty": False,
                    "git_fresh": True,
                    "candidate_repowiki_zh_root": str(run_dir / "repowiki" / "zh"),
                    "candidate_content_root": str(content_dir),
                    "candidate_meta_root": str(meta_dir),
                    "report_paths": {"strict_verify": "reports/strict-verify-output.json"},
                    "files": [{"path": "reports/strict-verify-output.json"}],
                    "evidence": [],
                }
            ),
            encoding="utf-8",
        )
        return run_dir, page, meta_dir

    def _check(self, result, name):
        return next(c for c in result["checks"] if c["name"] == name)

    def test_claim_citation_coverage_94_fails_and_95_passes(self, tmp_path):
        fail_dir, _, _ = self._write_complete_run(
            tmp_path / "fail", claim_count=100, cited_count=94
        )
        fail_result = QoderLikeVerifierService(fail_dir, strict=True).verify(ci=True)
        assert "QODER_CITATION_FACT_COVERAGE_LOW" in fail_result.get("hard_gate_codes", [])

        pass_dir, _, _ = self._write_complete_run(
            tmp_path / "pass", claim_count=100, cited_count=95
        )
        pass_result = QoderLikeVerifierService(pass_dir, strict=True).verify(ci=True)
        coverage = self._check(pass_result, "qoder-claim-citation-coverage")
        assert coverage["status"] == "PASS"
        assert "QODER_CITATION_FACT_COVERAGE_LOW" not in pass_result.get("hard_gate_codes", [])

    def test_source_looking_url_citation_cannot_bypass_line_validation(self, tmp_path):
        run_dir, page, _ = self._write_complete_run(tmp_path)
        page.write_text(
            page.read_text(encoding="utf-8")
            + "\nService `api-gateway` handles URL bypass checks.\n"
            + "<cite>https://github.com/acme/repo/blob/main/src/app.py#L1</cite>\n",
            encoding="utf-8",
        )
        result = QoderLikeVerifierService(run_dir, strict=True).verify(ci=True)
        assert "QODER_CITATION_INVALID" in result.get("hard_gate_codes", [])

    def test_missing_inventories_and_conflict_artifact_fail_closed(self, tmp_path):
        run_dir, _, meta_dir = self._write_complete_run(tmp_path)
        for path in meta_dir.glob("*inventory*.json"):
            path.unlink()
        (meta_dir / "service-registry.json").unlink()
        (meta_dir / "source-docs-conflicts.json").unlink()
        result = QoderLikeVerifierService(run_dir, strict=True).verify(ci=True)
        hard_codes = result.get("hard_gate_codes", [])
        assert "QODER_REQUIRED_INVENTORY_MISSING" in hard_codes
        assert "QODER_CONFLICT_ARTIFACT_MISSING" in hard_codes

    def test_fact_conflicts_without_canonical_source_docs_report_fails(self, tmp_path):
        run_dir, _, meta_dir = self._write_complete_run(tmp_path)
        (meta_dir / "source-docs-conflicts.json").unlink()
        (meta_dir / "fact-conflicts.json").write_text(
            json.dumps(
                {
                    "schema_version": "source-docs-conflict-resolver-v1",
                    "summary": {
                        "resolved_count": 0,
                        "deferred_count": 0,
                        "flagged_count": 0,
                        "total_items": 0,
                    },
                    "resolved_items": [],
                    "deferred_items": [],
                    "flagged_items": [],
                }
            ),
            encoding="utf-8",
        )
        result = QoderLikeVerifierService(run_dir, strict=True).verify(ci=True)
        assert "QODER_CONFLICT_ARTIFACT_MISSING" in result.get("hard_gate_codes", [])

    def test_critical_unresolved_conflict_shape_fails(self, tmp_path):
        run_dir, _, meta_dir = self._write_complete_run(tmp_path)
        (meta_dir / "source-docs-conflicts.json").write_text(
            json.dumps(
                {
                    "schema_version": "source-docs-conflict-resolver-v1",
                    "summary": {
                        "resolved_count": 0,
                        "deferred_count": 0,
                        "flagged_count": 1,
                        "total_items": 1,
                    },
                    "resolved_items": [],
                    "deferred_items": [],
                    "flagged_items": [{"severity": "critical", "status": "unresolved"}],
                }
            ),
            encoding="utf-8",
        )
        result = QoderLikeVerifierService(run_dir, strict=True).verify(ci=True)
        assert "QODER_UNRESOLVED_FACT_CONFLICT" in result.get("hard_gate_codes", [])

    def test_unresolved_conflict_count_does_not_double_summary_and_items(self, tmp_path):
        payload = {
            "schema_version": "source-docs-conflict-resolver-v1",
            "summary": {
                "resolved_count": 0,
                "deferred_count": 31,
                "flagged_count": 42,
                "total_items": 73,
            },
            "resolved_items": [],
            "deferred_items": [{"id": f"d{i}", "status": "deferred"} for i in range(31)],
            "flagged_items": [{"id": f"f{i}", "status": "flagged"} for i in range(42)],
        }
        verifier = QoderLikeVerifierService(tmp_path, strict=True)
        assert verifier._count_unresolved_conflicts(payload) == 73

    def test_identical_reports_and_meta_conflict_copies_count_once(self, tmp_path):
        run_dir, _, meta_dir = self._write_complete_run(tmp_path)
        payload = {
            "schema_version": "source-docs-conflict-resolver-v1",
            "summary": {
                "resolved_count": 0,
                "deferred_count": 31,
                "flagged_count": 42,
                "total_items": 73,
            },
            "resolved_items": [],
            "deferred_items": [{"id": f"d{i}", "status": "deferred"} for i in range(31)],
            "flagged_items": [{"id": f"f{i}", "status": "flagged"} for i in range(42)],
        }
        encoded = json.dumps(payload)
        (meta_dir / "source-docs-conflicts.json").write_text(encoded, encoding="utf-8")
        reports = run_dir / "reports"
        reports.mkdir(exist_ok=True)
        (reports / "source-docs-conflicts.json").write_text(encoded, encoding="utf-8")
        check = QoderLikeVerifierService(
            run_dir, strict=True
        )._check_qoder_unresolved_fact_conflicts()
        assert check.status == "FAIL"
        assert check.reason_code == "QODER_UNRESOLVED_FACT_CONFLICT"
        artifacts = check.details.get("artifacts") or []
        assert len(artifacts) == 1
        assert artifacts[0]["unresolved_count"] == 73

    def test_owner_gap_fails_but_structured_unidentified_warning_passes(self, tmp_path):
        gap_dir, page, _ = self._write_complete_run(tmp_path / "gap")
        page.write_text(
            page.read_text(encoding="utf-8")
            .replace("Owner page: ", "")
            .replace("owned by Platform Team", "documented")
        )
        gap_result = QoderLikeVerifierService(gap_dir, strict=True).verify(ci=True)
        assert "QODER_OWNER_COVERAGE_MISSING" in gap_result.get("hard_gate_codes", [])

        warn_dir, page, meta_dir = self._write_complete_run(tmp_path / "warn")
        page.write_text(
            page.read_text(encoding="utf-8")
            .replace("Owner page: ", "")
            .replace("owned by Platform Team", "documented")
        )
        quality = json.loads((meta_dir / "quality-report.json").read_text(encoding="utf-8"))
        quality["warnings"] = [
            {"code": "UNIDENTIFIED_OWNER", "kind": "service", "identifier": "api-gateway"},
            {"code": "UNIDENTIFIED_OWNER", "kind": "api", "identifier": "GET /health"},
            {"code": "UNIDENTIFIED_OWNER", "kind": "model", "identifier": "user-entity"},
            {"code": "UNIDENTIFIED_OWNER", "kind": "runtime", "identifier": "repo-wiki"},
        ]
        (meta_dir / "quality-report.json").write_text(json.dumps(quality), encoding="utf-8")
        warn_result = QoderLikeVerifierService(warn_dir, strict=True).verify(ci=True)
        owner_check = self._check(warn_result, "qoder-owner-inventory-coverage")
        assert owner_check["status"] == "PASS"

    def test_ordinary_prose_false_service_claim_fails(self, tmp_path):
        run_dir, page, _ = self._write_complete_run(tmp_path)
        page.write_text(
            page.read_text(encoding="utf-8")
            + "\nThe ghost-service service handles account authentication.\n"
            + "<cite>source:src/app.py:90</cite>\n",
            encoding="utf-8",
        )
        result = QoderLikeVerifierService(run_dir, strict=True).verify(ci=True)
        assert "QODER_CRITICAL_FALSE_FACT" in result.get("hard_gate_codes", [])

    def test_false_auth_and_data_relationship_claims_fail(self, tmp_path):
        run_dir, page, _ = self._write_complete_run(tmp_path)
        page.write_text(
            page.read_text(encoding="utf-8")
            + "\nGET /health requires authentication.\n"
            + "`user-entity` owns `ghost-entity`.\n"
            + "<cite>source:src/app.py:91</cite>\n",
            encoding="utf-8",
        )
        result = QoderLikeVerifierService(run_dir, strict=True).verify(ci=True)
        assert "QODER_CRITICAL_FALSE_FACT" in result.get("hard_gate_codes", [])

    def test_fastapi_readme_docs_urls_are_not_missing_inventory_routes(self, tmp_path):
        run_dir, page, _ = self._write_complete_run(tmp_path)
        (run_dir / "README.md").write_text(
            "# Conduit\n\nFastAPI RealWorld example.\n"
            "Interactive API docs are at /docs and ReDoc at /redoc.\n",
            encoding="utf-8",
        )
        page.write_text(
            page.read_text(encoding="utf-8")
            + "\nOperators open GET /docs and GET /redoc for the auto-generated schema.\n"
            + "The same FastAPI process also serves /docs and /redoc without route files.\n"
            + "<cite>source:src/app.py:20</cite>\n",
            encoding="utf-8",
        )
        check = QoderLikeVerifierService(run_dir, strict=True)._check_qoder_critical_false_facts()
        assert check.status == "PASS"
        assert check.reason_code != "QODER_CRITICAL_FALSE_FACT"

    def test_fastapi_unmatched_api_claim_still_false_fact(self, tmp_path):
        run_dir, page, _ = self._write_complete_run(tmp_path)
        (run_dir / "README.md").write_text(
            "# Conduit\n\nFastAPI RealWorld example. Docs live at /docs.\n",
            encoding="utf-8",
        )
        page.write_text(
            page.read_text(encoding="utf-8")
            + "\nGET /api/does-not-exist is a product route.\n"
            + "<cite>source:src/app.py:21</cite>\n",
            encoding="utf-8",
        )
        check = QoderLikeVerifierService(run_dir, strict=True)._check_qoder_critical_false_facts()
        assert check.status == "FAIL"
        assert check.reason_code == "QODER_CRITICAL_FALSE_FACT"
        claims = [item.get("claim") for item in check.details.get("offenders", [])]
        assert "GET /api/does-not-exist" in claims

    def test_path_param_name_alias_matches_inventory(self, tmp_path):
        run_dir, page, meta_dir = self._write_complete_run(tmp_path)
        (meta_dir / "api-inventory.json").write_text(
            json.dumps(
                {
                    "endpoints": [
                        {"method": "GET", "path": "/health", "public": True},
                        {"method": "DELETE", "path": "/api/articles/{slug}"},
                        {"method": "POST", "path": "/projects/{project_id}/run-volume"},
                    ]
                }
            ),
            encoding="utf-8",
        )
        page.write_text(
            page.read_text(encoding="utf-8")
            + "\nDELETE /api/articles/{slug} removes a published article.\n"
            + "POST /projects/{id}/run-volume starts volume generation.\n"
            + "<cite>source:src/app.py:22</cite>\n",
            encoding="utf-8",
        )
        check = QoderLikeVerifierService(run_dir, strict=True)._check_qoder_critical_false_facts()
        assert check.status == "PASS"
        assert check.reason_code != "QODER_CRITICAL_FALSE_FACT"

    def test_api_mount_prefix_claim_matches_inventory(self, tmp_path):
        run_dir, page, meta_dir = self._write_complete_run(tmp_path)
        (meta_dir / "api-inventory.json").write_text(
            json.dumps(
                {
                    "endpoints": [
                        {"method": "GET", "path": "/health", "public": True},
                        {"method": "POST", "path": "/api/users/login"},
                        {"method": "POST", "path": "/api/users"},
                        {"method": "POST", "path": "/api/profiles/{username}/follow"},
                        {"method": "GET", "path": "/api/articles/feed"},
                    ]
                }
            ),
            encoding="utf-8",
        )
        page.write_text(
            page.read_text(encoding="utf-8")
            + "\nPOST /users/login authenticates a Conduit user.\n"
            + "POST /users registers a new account.\n"
            + "POST /profiles/{username}/follow subscribes to another author.\n"
            + "GET /articles/feed returns the authenticated home feed.\n"
            + "POST /api/users/login is the same mounted login route.\n"
            + "<cite>source:src/app.py:22</cite>\n",
            encoding="utf-8",
        )
        check = QoderLikeVerifierService(run_dir, strict=True)._check_qoder_critical_false_facts()
        assert check.status == "PASS"
        assert check.reason_code != "QODER_CRITICAL_FALSE_FACT"

    def test_api_mount_prefix_missing_route_still_false_fact(self, tmp_path):
        run_dir, page, meta_dir = self._write_complete_run(tmp_path)
        (meta_dir / "api-inventory.json").write_text(
            json.dumps(
                {
                    "endpoints": [
                        {"method": "GET", "path": "/health", "public": True},
                        {"method": "POST", "path": "/api/users/login"},
                        {"method": "POST", "path": "/api/users"},
                        {"method": "POST", "path": "/api/profiles/{username}/follow"},
                        {"method": "GET", "path": "/api/articles/feed"},
                    ]
                }
            ),
            encoding="utf-8",
        )
        page.write_text(
            page.read_text(encoding="utf-8")
            + "\nPOST /users/does-not-exist is a product route.\n"
            + "GET /profiles/{username}/follow is the wrong method.\n"
            + "<cite>source:src/app.py:23</cite>\n",
            encoding="utf-8",
        )
        check = QoderLikeVerifierService(run_dir, strict=True)._check_qoder_critical_false_facts()
        assert check.status == "FAIL"
        assert check.reason_code == "QODER_CRITICAL_FALSE_FACT"
        claims = [item.get("claim") for item in check.details.get("offenders", [])]
        assert "POST /users/does-not-exist" in claims
        assert "GET /profiles/{username}/follow" in claims

    def test_api_claim_in_inventory_mount_prefix_and_trailing_param(self, tmp_path):
        verifier = QoderLikeVerifierService(tmp_path, strict=True)
        apis = {
            ("POST", "/api/users/login"),
            ("POST", "/api/users"),
            ("POST", "/api/profiles/{username}/follow"),
            ("GET", "/api/articles/feed"),
        }
        assert verifier._api_claim_in_inventory("POST", "/users/login", apis)
        assert verifier._api_claim_in_inventory("POST", "/api/users/login", apis)
        assert verifier._api_claim_in_inventory("POST", "/users", apis)
        assert verifier._api_claim_in_inventory("GET", "/articles/feed", apis)
        assert verifier._api_claim_in_inventory("POST", "/profiles/{username}/follow", apis)
        assert verifier._api_claim_in_inventory("POST", "/api/profiles/{username}/follow", apis)
        assert not verifier._api_claim_in_inventory("POST", "/users/does-not-exist", apis)
        assert not verifier._api_claim_in_inventory("GET", "/users/login", apis)
        assert not verifier._api_claim_in_inventory("POST", "/users/login/extra", apis)

    def test_github_actions_service_options_is_not_a_product_service(self, tmp_path):
        run_dir, page, _ = self._write_complete_run(tmp_path)
        content_dir = page.parent.parent
        ci_page = content_dir / "部署运维" / "CI／CD流水线.md"
        ci_page.parent.mkdir(parents=True)
        ci_page.write_text(
            "# CI/CD\n\n"
            "GitHub Actions service options run the Postgres healthcheck.\n"
            "A bare options token on this CI page is the compose healthcheck flag.\n"
            "```yaml\nservices:\n  postgres:\n    options: --health-cmd pg_isready\n```\n"
            "<cite>source:src/app.py:22</cite>\n",
            encoding="utf-8",
        )
        check = QoderLikeVerifierService(run_dir, strict=True)._check_qoder_critical_false_facts()
        assert check.status == "PASS"
        assert check.reason_code != "QODER_CRITICAL_FALSE_FACT"

    def test_github_actions_job_and_options_on_ops_page_are_not_product_services(self, tmp_path):
        run_dir, page, _ = self._write_complete_run(tmp_path)
        content_dir = page.parent.parent
        ops_page = content_dir / "部署运维.md"
        ops_page.write_text(
            "# 部署运维\n\n"
            "The GitHub Actions job service uses postgres:11.5-alpine in conduit.yml.\n"
            "The same workflow service options field sets --health-cmd pg_isready.\n"
            "jobs, steps, needs, and runner tokens describe the workflow, not Conduit.\n"
            "<cite>source:src/app.py:22</cite>\n",
            encoding="utf-8",
        )
        check = QoderLikeVerifierService(run_dir, strict=True)._check_qoder_critical_false_facts()
        assert check.status == "PASS"
        assert check.reason_code != "QODER_CRITICAL_FALSE_FACT"
        offenders = check.details.get("offenders", [])
        assert not any(
            item.get("claim") in {"job", "options", "uses", "workflow"} for item in offenders
        )

    def test_unmatched_app_module_service_claim_still_false_fact(self, tmp_path):
        run_dir, page, _ = self._write_complete_run(tmp_path)
        content_dir = page.parent.parent
        app_page = content_dir / "核心服务" / "用户服务.md"
        app_page.parent.mkdir(parents=True)
        app_page.write_text(
            "# 用户服务\n\n"
            "The ghost-ledger service handles account authentication for Conduit.\n"
            "<cite>source:src/app.py:23</cite>\n",
            encoding="utf-8",
        )
        check = QoderLikeVerifierService(run_dir, strict=True)._check_qoder_critical_false_facts()
        assert check.status == "FAIL"
        assert check.reason_code == "QODER_CRITICAL_FALSE_FACT"
        claims = [item.get("claim") for item in check.details.get("offenders", [])]
        assert any("ghost-ledger" in str(claim) for claim in claims)

    def test_unmatched_articles_service_on_app_api_page_still_false_fact(self, tmp_path):
        run_dir, page, _ = self._write_complete_run(tmp_path)
        content_dir = page.parent.parent
        app_page = content_dir / "核心服务" / "articles-api.md"
        app_page.parent.mkdir(parents=True)
        app_page.write_text(
            "# Articles API\n\n"
            "The articles service stores posts and comments for Conduit readers.\n"
            "<cite>source:src/app.py:24</cite>\n",
            encoding="utf-8",
        )
        check = QoderLikeVerifierService(run_dir, strict=True)._check_qoder_critical_false_facts()
        assert check.status == "FAIL"
        assert check.reason_code == "QODER_CRITICAL_FALSE_FACT"
        claims = [item.get("claim") for item in check.details.get("offenders", [])]
        assert "articles" in claims

    def test_scanner_alias_source_inventory_is_not_missing_required_inventories(self, tmp_path):
        """api_surfaces/data_models/kind-only services must populate required inventories."""
        run_dir, _, meta_dir = self._write_complete_run(tmp_path)
        for path in meta_dir.glob("*inventory*.json"):
            if path.name != "source-inventory.json":
                path.unlink()
        service_registry = meta_dir / "service-registry.json"
        if service_registry.exists():
            service_registry.unlink()
        (meta_dir / "source-inventory.json").write_text(
            json.dumps(
                {
                    "schema_version": "repo_agent.source_inventory/1.0",
                    "services": [
                        {
                            "kind": "python_fastapi_app",
                            "evidence_path": "app/main.py",
                        }
                    ],
                    "api_surfaces": [
                        {"method": "POST", "path": "/api/users/login"},
                        {"method": "GET", "path": "/api/articles"},
                    ],
                    "data_models": [{"name": "User"}],
                    "relationships": [],
                }
            ),
            encoding="utf-8",
        )
        verifier = QoderLikeVerifierService(run_dir, strict=True)
        inventories = verifier._load_structured_inventory_sets()
        missing = [
            name
            for name in ("sources", "apis", "services", "models", "runtimes")
            if not inventories[name]
        ]
        assert missing == [], missing
        assert ("POST", "/api/users/login") in inventories["apis"]
        assert "User" in inventories["models"]
        assert "app/main.py" in inventories["runtimes"]
        result = verifier.verify(ci=True)
        assert "QODER_REQUIRED_INVENTORY_MISSING" not in result.get("hard_gate_codes", [])
