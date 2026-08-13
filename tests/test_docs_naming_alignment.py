from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIR_NAMES = {"node_modules", ".git", "repo_wiki.egg-info"}
STALE_CLONE = "github.com/bingooyong/" + "repo-agent"
EVAL_PATH = ".repo-agent-eval/repowiki/zh/manifest.json"


def _iter_text_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        if path.suffix.lower() not in {".md", ".yml", ".yaml", ".json", ".toml", ".txt"}:
            continue
        yield path


def test_no_stale_github_clone_url() -> None:
    hits = []
    for path in _iter_text_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        if STALE_CLONE in text:
            hits.append(str(path.relative_to(ROOT)))
    assert hits == [], f"stale clone URL still in: {hits}"


def test_overview_doc_exists() -> None:
    assert (ROOT / "docs" / "00-overview.md").is_file()


def test_repo_map_repository_name_matches_github() -> None:
    text = (ROOT / "ai" / "source-of-truth" / "repo-map.yaml").read_text(encoding="utf-8")
    assert "name: repo-wiki-agent" in text
    assert "name: repo-agent\n" not in text


def test_ready_eval_path_contract_still_documented() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert EVAL_PATH in readme
    assert EVAL_PATH in agents
