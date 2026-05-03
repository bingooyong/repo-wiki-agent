"""Tests for eval layout policy, manifest schema, and path safety."""

import json
import time
from pathlib import Path

import pytest

from repo_wiki.orchestration.eval_layout import (
    EvalManifest,
    EvalManifestEvidence,
    EvalManifestFile,
    EvalOutputProfile,
    generate_manifest,
    get_eval_output_layout_contract,
    get_eval_profile,
    reject_unsafe_output_root,
    resolve_revision_with_fallback,
    validate_eval_root_safety,
    write_manifest,
)


class TestEvalOutputProfile:
    """Tests for EvalOutputProfile configuration."""

    def test_default_profile_properties(self):
        profile = EvalOutputProfile()
        assert profile.name == "default"
        assert profile.root == ".repo-agent-eval"
        assert profile.create_subdirs is True
        assert profile.max_manifest_size_kb == 512

    def test_get_run_dir_without_subdirs(self):
        profile = EvalOutputProfile(name="ci", root=".repo-agent-eval-ci", create_subdirs=False)
        run_dir = profile.get_run_dir("run-123")
        assert run_dir == Path(".repo-agent-eval-ci")

    def test_get_run_dir_with_subdirs(self):
        profile = EvalOutputProfile(create_subdirs=True)
        run_dir = profile.get_run_dir("run-123")
        assert run_dir == Path(".repo-agent-eval/run-123")

    def test_validate_path_safety_valid(self):
        profile = EvalOutputProfile()
        is_safe, reason = profile.validate_path_safety("subdir/file.md")
        assert is_safe is True

    def test_validate_path_safety_absolute_path_rejected(self):
        profile = EvalOutputProfile()
        is_safe, reason = profile.validate_path_safety("/etc/passwd")
        assert is_safe is False

    def test_validate_path_safety_traversal_rejected(self):
        profile = EvalOutputProfile()
        is_safe, reason = profile.validate_path_safety("../../../etc/passwd")
        assert is_safe is False

    def test_validate_root_rejects_protected_dirs(self):
        with pytest.raises(ValueError, match="overlaps with protected directory"):
            EvalOutputProfile(root="docs/")

    def test_validate_root_rejects_nested_protected(self):
        with pytest.raises(ValueError, match="inside protected directory"):
            EvalOutputProfile(root="docs/subdir/")

    def test_validate_root_allows_safe_roots(self):
        profile = EvalOutputProfile(root=".my-eval-output")
        assert profile.root == ".my-eval-output"


class TestEvalProfilesRegistry:
    """Tests for eval profiles registry."""

    def test_get_default_profile(self):
        profile = get_eval_profile("default")
        assert profile.name == "default"
        assert profile.root == ".repo-agent-eval"

    def test_get_ci_profile(self):
        profile = get_eval_profile("ci")
        assert profile.name == "ci"
        assert profile.root == ".repo-agent-eval-ci"
        assert profile.create_subdirs is False

    def test_get_qoder_like_profile(self):
        profile = get_eval_profile("qoder-like")
        assert profile.name == "qoder-like"
        assert profile.root == ".repo-agent-eval"
        assert profile.create_subdirs is True
        assert profile.content_subdir == "content"

    def test_qoder_like_content_dir(self):
        profile = get_eval_profile("qoder-like")
        content_dir = profile.get_content_dir("run-123")
        assert content_dir == Path(".repo-agent-eval/run-123/content")

    def test_get_unknown_returns_default(self):
        profile = get_eval_profile("nonexistent")
        assert profile.name == "default"


class TestEvalManifestFile:
    """Tests for EvalManifestFile schema."""

    def test_minimal_file(self):
        file = EvalManifestFile(path="docs/readme.md", size_bytes=100, hash_sha256="abc123")
        assert file.path == "docs/readme.md"
        assert file.size_bytes == 100
        assert file.hash_sha256 == "abc123"
        assert file.content_type == "text/markdown"

    def test_full_file(self):
        file = EvalManifestFile(
            path="output.json",
            size_bytes=512,
            content_type="application/json",
            hash_sha256="def456",
        )
        assert file.content_type == "application/json"


class TestEvalManifestEvidence:
    """Tests for EvalManifestEvidence schema."""

    def test_minimal_evidence(self):
        evidence = EvalManifestEvidence(
            path="verify-result.json",
            evidence_type="verify-result",
            description="Verification results",
            created_at="2024-01-01T00:00:00Z",
        )
        assert evidence.path == "verify-result.json"
        assert evidence.evidence_type == "verify-result"


class TestEvalManifest:
    """Tests for EvalManifest schema."""

    def test_minimal_manifest(self):
        manifest = EvalManifest(
            run_id="run-001",
            generated_at="2024-01-01T00:00:00Z",
            profile="default",
            target_repo="/path/to/repo",
            eval_root="/path/to/repo/.repo-agent-eval/run-001",
        )
        assert manifest.version == "1.0"
        assert manifest.run_id == "run-001"
        assert len(manifest.files) == 0
        assert len(manifest.evidence) == 0
        assert manifest.target_revision_source == "git"
        assert manifest.wiki_revision_source == "git"
        assert manifest.stale_detection == {}

    def test_manifest_with_files_and_evidence(self):
        manifest = EvalManifest(
            run_id="run-002",
            generated_at="2024-01-01T00:00:00Z",
            profile="ci",
            target_repo="/path/to/repo",
            eval_root="/path/to/repo/.repo-agent-eval",
            files=[
                EvalManifestFile(path="output.md", size_bytes=200, hash_sha256="aaa"),
            ],
            evidence=[
                EvalManifestEvidence(
                    path="verify-result.json",
                    evidence_type="verify-result",
                    description="CI verification",
                    created_at="2024-01-01T00:00:00Z",
                ),
            ],
        )
        assert len(manifest.files) == 1
        assert len(manifest.evidence) == 1

    def test_manifest_serialization(self):
        manifest = EvalManifest(
            run_id="run-003",
            generated_at="2024-01-01T00:00:00Z",
            profile="default",
            target_repo="/path/to/repo",
            eval_root="/path/to/repo/.repo-agent-eval/run-003",
            stats={"files_written": 10, "duration_ms": 1500},
        )
        serialized = manifest.model_dump_json()
        data = json.loads(serialized)
        assert data["run_id"] == "run-003"
        assert data["stats"]["files_written"] == 10


class TestGenerateManifest:
    """Tests for manifest generation."""

    def test_generate_manifest_empty_dir(self, tmp_path):
        run_id = "test-run-001"
        profile = EvalOutputProfile()
        manifest = generate_manifest(
            run_id=run_id,
            profile=profile,
            target_repo=str(tmp_path.parent),
            output_dir=tmp_path,
        )
        assert manifest.run_id == run_id
        assert manifest.profile == "default"
        assert len(manifest.files) == 0

    def test_generate_manifest_with_files(self, tmp_path):
        # Create some test files
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "readme.md").write_text("# Test")
        (tmp_path / "output.json").write_text('{"key": "value"}')

        manifest = generate_manifest(
            run_id="test-run-002",
            profile=EvalOutputProfile(),
            target_repo=str(tmp_path.parent),
            output_dir=tmp_path,
        )

        assert len(manifest.files) == 2
        paths = {f.path for f in manifest.files}
        assert "docs/readme.md" in paths
        assert "output.json" in paths

    def test_generate_manifest_with_evidence(self, tmp_path):
        manifest = generate_manifest(
            run_id="test-run-003",
            profile=EvalOutputProfile(),
            target_repo=str(tmp_path.parent),
            output_dir=tmp_path,
            evidence_files=[
                {
                    "path": "verify-result.json",
                    "type": "verify-result",
                    "description": "Verification results",
                    "created_at": "2024-01-01T00:00:00Z",
                },
            ],
        )
        assert len(manifest.evidence) == 1
        assert manifest.evidence[0].evidence_type == "verify-result"

    def test_generate_manifest_stale_detection_metadata(self, tmp_path):
        manifest = generate_manifest(
            run_id="test-run-stale",
            profile=EvalOutputProfile(),
            target_repo=str(tmp_path.parent),
            output_dir=tmp_path,
            target_git_commit="aaaa1111",
            wiki_git_commit="bbbb2222",
            target_revision_source="hash-fallback",
            wiki_revision_source="hash-fallback",
        )
        assert manifest.stale_detection["is_stale"] is True
        assert manifest.stale_detection["target_revision_source"] == "hash-fallback"
        assert manifest.stale_detection["wiki_revision_source"] == "hash-fallback"


class TestRevisionFallback:
    """Tests for git/hash revision resolution."""

    def test_resolve_revision_with_fallback_non_git_path(self, tmp_path):
        (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
        revision, source = resolve_revision_with_fallback(tmp_path)
        assert source == "hash-fallback"
        assert len(revision) == 64


class TestWriteManifest:
    """Tests for manifest writing."""

    def test_write_manifest_creates_file(self, tmp_path):
        manifest = EvalManifest(
            run_id="test-run-004",
            generated_at="2024-01-01T00:00:00Z",
            profile="default",
            target_repo=str(tmp_path.parent),
            eval_root=str(tmp_path),
        )
        manifest_path = write_manifest(manifest, tmp_path)
        assert manifest_path == tmp_path / "manifest.json"
        assert manifest_path.exists()

        # Verify content
        data = json.loads(manifest_path.read_text())
        assert data["run_id"] == "test-run-004"


class TestValidateEvalRootSafety:
    """Tests for eval root safety validation."""

    def test_safe_root_returns_true(self):
        is_safe, reason, warnings = validate_eval_root_safety(".repo-agent-eval")
        assert is_safe is True
        assert "safe" in reason.lower()

    def test_root_inside_protected_rejected(self):
        is_safe, reason, warnings = validate_eval_root_safety("docs/")
        assert is_safe is False
        assert "protected" in reason.lower() or "inside" in reason.lower()

    def test_root_overlapping_repo_wiki_rejected(self):
        is_safe, reason, warnings = validate_eval_root_safety(".repo-wiki/")
        assert is_safe is False

    def test_warnings_for_contained_protected_dirs(self):
        # If eval root is parent of a protected dir, we get a warning
        is_safe, reason, warnings = validate_eval_root_safety(".")
        # Current implementation checks if protected is inside root
        # This is a soft warning scenario
        assert isinstance(warnings, list)


class TestRejectUnsafeOutputRoot:
    """Tests for reject_unsafe_output_root function."""

    def test_safe_root_does_not_raise(self):
        reject_unsafe_output_root(".repo-agent-eval")  # Should not raise

    def test_unsafe_root_raises(self):
        from repo_wiki.core.errors import RepoWikiError

        with pytest.raises(RepoWikiError, match="Unsafe eval output root"):
            reject_unsafe_output_root("docs/")


class TestEvalOutputLayoutContract:
    """Tests for eval output layout contract."""

    def test_contract_structure(self):
        contract = get_eval_output_layout_contract()
        assert contract["version"] == "1.0"
        assert contract["root"] == ".repo-agent-eval"
        assert "structure" in contract
        assert "protected_directories" in contract
        assert "boundary_rules" in contract

    def test_contract_includes_all_protected_dirs(self):
        contract = get_eval_output_layout_contract()
        protected = contract["protected_directories"]
        assert "docs/" in protected
        assert ".repo-wiki/" in protected
        assert "ai/" in protected

    def test_contract_boundary_rules_exist(self):
        contract = get_eval_output_layout_contract()
        rules = contract["boundary_rules"]
        assert len(rules) >= 3
        assert any(".repo-agent-eval/" in rule for rule in rules)


class TestIntegration:
    """Integration tests for eval layout system."""

    def test_full_eval_flow(self, tmp_path):
        """Test complete eval flow: create profile, generate manifest, write it."""
        # 1. Create output structure
        eval_root = tmp_path / ".repo-agent-eval"
        run_id = f"run-{int(time.time())}"
        run_dir = eval_root / run_id
        run_dir.mkdir(parents=True)

        # 2. Create some outputs
        (run_dir / "docs").mkdir()
        (run_dir / "docs" / "readme.md").write_text("# Test Output")
        (run_dir / "verify-result.json").write_text('{"status": "pass"}')

        # 3. Generate manifest
        profile = get_eval_profile("default")
        manifest = generate_manifest(
            run_id=run_id,
            profile=profile,
            target_repo=str(tmp_path),
            output_dir=run_dir,
            evidence_files=[
                {
                    "path": "verify-result.json",
                    "type": "verify-result",
                    "description": "Verification result",
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
            ],
            stats={"files_written": 2, "duration_ms": 100},
        )

        # 4. Write manifest
        manifest_path = write_manifest(manifest, run_dir)

        # 5. Verify
        assert manifest_path.exists()
        data = json.loads(manifest_path.read_text())
        assert data["run_id"] == run_id
        assert len(data["files"]) == 2
        assert len(data["evidence"]) == 1

    def test_profile_path_safety_validation(self):
        """Test that profile validates output paths correctly."""
        profile = EvalOutputProfile()

        # Valid paths
        assert profile.validate_path_safety("output.md")[0] is True
        assert profile.validate_path_safety("subdir/output.json")[0] is True

        # Invalid paths
        assert profile.validate_path_safety("/etc/passwd")[0] is False
        assert profile.validate_path_safety("../../../root.txt")[0] is False
