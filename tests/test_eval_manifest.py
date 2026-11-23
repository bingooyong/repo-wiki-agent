import json
from pathlib import Path

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.orchestration.eval_layout import EvalOutputProfile
from repo_wiki.orchestration.service import RepoWikiService


def _create_sample_repo(root: Path) -> None:
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "service.py").write_text(
        """
class UserService:
    def list_users(self):
        return []
""".strip(),
        encoding="utf-8",
    )
    (root / "README.md").write_text("# Manifest Fixture\n", encoding="utf-8")


def test_qoder_like_manifest_references_materialized_content(tmp_path):
    repo_root = tmp_path / "target"
    repo_root.mkdir()
    _create_sample_repo(repo_root)

    config = RepoWikiConfig.model_validate(
        {
            "project": {
                "name": "manifest-fixture",
                "root": str(repo_root),
                "include": ["**/*"],
                "exclude": [".repo-agent-eval/**", ".qoder/**", ".repo-wiki/**"],
            },
            # Deterministic CI path: developers may have OPENAI_API_KEY; tests must not
            # hit the network (preflight would otherwise probe the configured endpoint).
            "llm": {"force_mock_llm": True},
        }
    )
    profile = EvalOutputProfile(
        name="qoder-like",
        root=str(repo_root / ".repo-agent-eval"),
        create_subdirs=True,
        content_subdir="content",
    )

    RepoWikiService(config).generate(eval_profile=profile, run_id="test-run")

    manifest_path = repo_root / ".repo-agent-eval" / "test-run" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    content_root = Path(manifest["content_root"])

    assert content_root.exists()
    assert manifest["profile"] == "qoder-like"
    assert manifest["navigation_tree"]
    assert manifest["page_registry"]
    assert "wiki_git_commit" in manifest
    assert "target_git_commit" in manifest
    assert "target_revision_source" in manifest
    assert "wiki_revision_source" in manifest
    assert manifest["stale_detection"]["strategy"] == "git-or-hash"
    assert manifest["readiness_state"] in {"READY", "NOT_READY", "REVIEW_ONLY"}
    assert "readiness_reasons" in manifest
    assert "report_paths" in manifest
    assert manifest["candidate_repowiki_zh_root"].endswith("/repowiki/zh")
    assert manifest["candidate_content_root"].endswith("/repowiki/zh/content")
    assert manifest["candidate_meta_root"].endswith("/repowiki/zh/meta")
    # Existing qoder-like content path remains usable; readiness contract tracks candidate runs path separately.
    assert manifest["readiness_state"] != "READY"
    # Mock pilot + legacy flat content layout: never READY (task 11-23 fallback/mock gate).
    assert manifest["readiness_state"] == "NOT_READY"
    assert "MOCK_LLM_RUN" in manifest["readiness_reasons"]
    assert "missing_candidate_content_root" in manifest["readiness_reasons"]
    assert manifest["metadata"]["preflight_status"] == "skipped_mock"
    for page in manifest["page_registry"]:
        assert page["generation_mode"] == "mock"
        assert "rejection_reason" in page

    for page in manifest["page_registry"]:
        assert (content_root / page["path"]).exists()

    def _assert_nav_paths(nodes):
        for node in nodes:
            if node.get("type") == "page":
                assert (content_root / node["path"]).exists()
                assert Path(node["absolutePath"]).exists()
            _assert_nav_paths(node.get("children", []))

    _assert_nav_paths(manifest["navigation_tree"])

    manifest_files = {entry["path"] for entry in manifest["files"]}
    assert any(path.startswith("content/") and path.endswith(".md") for path in manifest_files)
