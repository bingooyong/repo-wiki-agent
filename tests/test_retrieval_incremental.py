from __future__ import annotations

from pathlib import Path

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.generator.io import write_json
from repo_wiki.retrieval.service import RetrievalService


def test_retrieval_hash_fallback_and_module_mapping(tmp_path: Path) -> None:
    (tmp_path / "src" / "billing").mkdir(parents=True)
    (tmp_path / "src" / "billing" / "service.py").write_text(
        "def run():\n    return 1\n", encoding="utf-8"
    )

    write_json(
        tmp_path / "ai" / "source-of-truth" / "module-index.yaml",
        {
            "modules": [
                {
                    "name": "billing",
                    "path": "src/billing",
                    "responsibility": "Billing logic",
                    "owner": "unknown",
                    "doc_path": "docs/modules/billing.md",
                }
            ]
        },
    )
    write_json(
        tmp_path / ".repo-wiki" / "graph" / "impact_cache.json",
        {"billing": {"upstream": [], "downstream": [], "depth2": []}},
    )

    cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
    retrieval = RetrievalService(tmp_path, cfg)
    impact = retrieval.analyze_incremental_impact()
    assert "billing" in impact.changed_modules
    assert impact.change_source in {"hash-compare-fallback", "git"}
