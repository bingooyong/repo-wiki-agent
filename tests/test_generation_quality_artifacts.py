from __future__ import annotations

import json
from pathlib import Path

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.orchestration.eval_layout import EvalOutputProfile
from repo_wiki.orchestration.quality_artifacts import build_evidence_index
from repo_wiki.orchestration.service import RepoWikiService
from repo_wiki.verifier.qoder_strict_verifier import QoderLikeVerifierService


def _write_small_repo(root: Path) -> None:
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text(
        """
from fastapi import FastAPI

app = FastAPI()

@app.get('/health')
def health():
    return {'status': 'ok'}

class Item:
    id: str
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        "# Sample Service\n\nSmall FastAPI service.\n", encoding="utf-8"
    )


def _service(root: Path) -> RepoWikiService:
    cfg = RepoWikiConfig()
    cfg.project.root = str(root)
    cfg.project.exclude = [".repo-agent-eval/**"]
    cfg.qoder_like.min_pages = 11
    cfg.qoder_like.max_pages = 11
    cfg.llm.force_mock_llm = False
    return RepoWikiService(cfg)


def test_qoder_like_generation_emits_quality_registry_and_conflict_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_small_repo(repo)

    monkeypatch.setenv("REPO_WIKI_LLM_PAGE_LIMIT", "3")
    monkeypatch.setenv("REPO_WIKI_LLM_REAL_MAX_CALLS", "0")
    monkeypatch.setenv("REPO_WIKI_LLM_PRIORITY", "plan")

    profile = EvalOutputProfile(
        name="qoder-like",
        root=str(repo / ".repo-agent-eval" / "runs"),
        create_subdirs=True,
        content_subdir="repowiki/zh/content",
    )
    result = _service(repo).generate(eval_profile=profile, run_id="run-g005")

    run_dir = Path(result["manifest_path"]).parent
    content_dir = run_dir / "repowiki" / "zh" / "content"
    meta_dir = run_dir / "repowiki" / "zh" / "meta"
    reports_dir = run_dir / "reports"

    content_pages = sorted(p.relative_to(content_dir).as_posix() for p in content_dir.rglob("*.md"))
    assert content_pages

    page_registry = json.loads((meta_dir / "page-registry.json").read_text(encoding="utf-8"))
    evidence_index = json.loads((meta_dir / "evidence-index.json").read_text(encoding="utf-8"))
    quality_report = json.loads((meta_dir / "quality-report.json").read_text(encoding="utf-8"))
    registry_paths = {p["relative_path"] for p in page_registry["pages"]}
    quality_paths = {p["relative_path"] for p in quality_report["page_quality"]}

    assert registry_paths == set(content_pages)
    assert quality_paths == set(content_pages)
    verifier = QoderLikeVerifierService(run_dir, strict=True)
    _, quality_path_errors = verifier._collect_artifact_page_quality_states(
        quality_report, containers=("page_quality", "pages")
    )
    assert not any("duplicate page entry" in err for err in quality_path_errors)
    assert all(p["page_id"] and p["stable_page_id"] for p in page_registry["pages"])
    assert {p["generation_mode"] for p in page_registry["pages"]} == {"fallback"}
    assert {p["quality_state"] for p in page_registry["pages"]} == {"DEGRADED"}
    assert quality_report["summary"]["degraded_count"] == len(content_pages)
    assert quality_report["summary"]["ready_count"] == 0
    assert evidence_index["schema_version"] == "repo_agent.evidence_index/1.0"
    assert evidence_index["run_id"] == "run-g005"
    assert all(span["page_relative_path"] in registry_paths for span in evidence_index["spans"])

    rendered = "\n".join(p.read_text(encoding="utf-8") for p in content_dir.rglob("*.md"))
    assert "Bearer Token" not in rendered
    assert "/resources" not in rendered

    conflict_report = json.loads(
        (reports_dir / "source-docs-conflicts.json").read_text(encoding="utf-8")
    )
    assert (meta_dir / "source-docs-conflicts.json").exists()
    assert conflict_report["resolved_items"] == []
    assert "resolved_count" in conflict_report["summary"]
    assert (meta_dir / "source-inventory.json").exists()
    assert (meta_dir / "docs-inventory.json").exists()

    manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
    manifest_paths = {item["path"] for item in manifest["files"]}
    assert "repowiki/zh/meta/page-registry.json" in manifest_paths
    assert "repowiki/zh/meta/evidence-index.json" in manifest_paths
    assert "repowiki/zh/meta/quality-report.json" in manifest_paths
    assert "reports/source-docs-conflicts.json" in manifest_paths


def test_evidence_index_is_deterministic_deduplicated_and_rejects_unsafe_citations(
    tmp_path: Path,
) -> None:
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "overview.md").write_text(
        "\n".join(
            [
                "# Overview",
                "<cite>source:src/app.py:2-4 (handler)</cite>",
                "<cite>src/app.py:2-4</cite>",
                "<cite>src/model.py:9</cite>",
                "<cite>/etc/passwd:1</cite>",
                "<cite>../secret.py:1</cite>",
                "<cite>src/reversed.py:7-3</cite>",
                "<cite>src/no-lines.py</cite>",
            ]
        ),
        encoding="utf-8",
    )
    registry = {
        "generated_at": "2026-07-15T00:00:00Z",
        "pages": [{"relative_path": "overview.md"}],
    }

    first = build_evidence_index(
        run_id="run-evidence", content_dir=content_dir, page_registry=registry
    )
    second = build_evidence_index(
        run_id="run-evidence", content_dir=content_dir, page_registry=registry
    )

    assert first == second
    assert first["spans"] == [
        {
            "span_id": first["spans"][0]["span_id"],
            "page_relative_path": "overview.md",
            "source_path": "src/app.py",
            "start_line": 2,
            "end_line": 4,
        },
        {
            "span_id": first["spans"][1]["span_id"],
            "page_relative_path": "overview.md",
            "source_path": "src/model.py",
            "start_line": 9,
            "end_line": 9,
        },
    ]
    assert all(span["span_id"].startswith("cite-") for span in first["spans"])
