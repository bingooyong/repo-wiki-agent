import json
from pathlib import Path

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.orchestration.eval_layout import EvalOutputProfile
from repo_wiki.orchestration.service import RepoWikiService


def _create_sample_repo(root: Path) -> None:
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text(
        """
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
def health():
    return {"ok": True}
""".strip(),
        encoding="utf-8",
    )
    (root / "README.md").write_text("# Sample Service\n\nA small test service.", encoding="utf-8")


def test_qoder_like_generate_writes_only_eval_run(tmp_path):
    repo_root = tmp_path / "target"
    repo_root.mkdir()
    _create_sample_repo(repo_root)

    qoder_baseline = repo_root / ".qoder" / "repowiki" / "zh" / "content"
    qoder_baseline.mkdir(parents=True)
    baseline_file = qoder_baseline / "baseline.md"
    baseline_file.write_text("# Baseline\n", encoding="utf-8")

    config = RepoWikiConfig.model_validate({
        "project": {
            "name": "sample",
            "root": str(repo_root),
            "include": ["**/*"],
            "exclude": [".repo-agent-eval/**", ".qoder/**", ".repo-wiki/**"],
        }
    })
    profile = EvalOutputProfile(
        name="qoder-like",
        root=str(repo_root / ".repo-agent-eval"),
        create_subdirs=True,
        content_subdir="content",
    )

    result = RepoWikiService(config).generate(eval_profile=profile, run_id="test-run")

    run_dir = repo_root / ".repo-agent-eval" / "test-run"
    content_dir = run_dir / "content"
    manifest = run_dir / "manifest.json"

    assert content_dir.exists()
    assert manifest.exists()
    assert len(list(content_dir.rglob("*.md"))) >= 10
    assert not (repo_root / "docs").exists()
    assert not (repo_root / ".repo-wiki").exists()
    assert not (repo_root / "ai").exists()
    assert baseline_file.read_text(encoding="utf-8") == "# Baseline\n"
    assert result["generate"]["content_root"] == str(content_dir)
    assert all(path.endswith(".md") for path in result["generate"]["written_files"])
    assert result["generate"]["llm"]["effective_provider"] == "mock"
    assert result["generate"]["llm"]["llm_call_count"] >= len(result["generate"]["written_files"])

    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    llm_stats = manifest_payload["stats"]["llm"]
    assert llm_stats["effective_provider"] == "mock"
    assert llm_stats["model"] == "mock-gpt"
    assert llm_stats["estimated_tokens"] > 0
    assert "api_key_env" not in json.dumps(manifest_payload).lower()
    assert all((content_dir / entry["path"]).exists() for entry in manifest_payload["page_registry"])
