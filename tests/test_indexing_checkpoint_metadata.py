from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import repo_wiki.indexer.indexing as indexing
from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.core.contracts import Module, RepositoryInfo, RepositorySnapshot
from repo_wiki.indexer.indexing import SemanticIndexer
from repo_wiki.indexer.vector_store import VectorEntry


class FakeEmbedder:
    backend_name = "fake"

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]


class FakeVectorStore:
    def __init__(self) -> None:
        self.upserted: list[VectorEntry] = []
        self.deleted: list[str] = []

    def upsert(self, entries) -> None:
        self.upserted.extend(list(entries))

    def delete(self, chunk_ids) -> None:
        self.deleted.extend(list(chunk_ids))


def test_indexing_summary_includes_checkpoint_and_fingerprint(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
    snapshot = RepositorySnapshot(
        repository=RepositoryInfo(name="tmp", root_path=str(tmp_path)),
        modules=[
            Module(
                name="src",
                path="src",
                responsibility="source",
                doc_path="docs/src.md",
            )
        ],
    )
    monkeypatch.setattr(indexing, "build_embedding_provider", lambda _model_name: FakeEmbedder())
    indexer = SemanticIndexer(tmp_path, cfg)
    indexer.vector_store = FakeVectorStore()

    result = indexer.rebuild(snapshot)

    summary = json.loads(
        (tmp_path / ".repo-wiki" / "index" / "indexing_summary.json").read_text(encoding="utf-8")
    )
    assert result.indexed_files == 1
    assert summary["total_candidates"] == 1
    assert summary["changed_files_count"] == 1
    assert summary["deleted_files_count"] == 0
    assert summary["batches_processed"] >= 1
    assert summary["elapsed_seconds"] >= 0
    assert summary["index_input_fingerprint"]
    assert summary["checkpoint"]["index_input_fingerprint"] == summary["index_input_fingerprint"]
