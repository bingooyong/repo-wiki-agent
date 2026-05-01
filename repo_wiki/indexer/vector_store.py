from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from repo_wiki.generator.io import ensure_dir


@dataclass
class VectorEntry:
    chunk_id: str
    embedding: list[float]
    metadata: dict


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(n))
    na = math.sqrt(sum(x * x for x in a[:n]))
    nb = math.sqrt(sum(x * x for x in b[:n]))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


class ChromaVectorStore:
    """ChromaDB wrapper with deterministic JSON fallback."""

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        ensure_dir(root_dir)
        self._fallback_path = root_dir / "vectors.json"
        self._chroma = None
        self._collection = None
        try:
            import chromadb  # type: ignore

            self._chroma = chromadb.PersistentClient(path=str(root_dir))
            self._collection = self._chroma.get_or_create_collection("repo_wiki_chunks")
        except Exception:
            self._chroma = None
            self._collection = None

    def upsert(self, entries: Iterable[VectorEntry]) -> None:
        items = list(entries)
        if not items:
            return
        if self._collection is not None:
            self._collection.upsert(
                ids=[e.chunk_id for e in items],
                embeddings=[e.embedding for e in items],
                metadatas=[e.metadata for e in items],
                documents=[e.metadata.get("text", "") for e in items],
            )
            return
        data = self._load_fallback()
        for item in items:
            data[item.chunk_id] = {"embedding": item.embedding, "metadata": item.metadata}
        self._save_fallback(data)

    def delete(self, chunk_ids: Iterable[str]) -> None:
        ids = list(chunk_ids)
        if not ids:
            return
        if self._collection is not None:
            self._collection.delete(ids=ids)
            return
        data = self._load_fallback()
        for cid in ids:
            data.pop(cid, None)
        self._save_fallback(data)

    def search(self, query_embedding: list[float], top_k: int = 20, module_name: str | None = None) -> list[dict]:
        if self._collection is not None:
            where = {"module_name": module_name} if module_name else None
            result = self._collection.query(query_embeddings=[query_embedding], n_results=top_k, where=where)
            ids = (result.get("ids") or [[]])[0]
            distances = (result.get("distances") or [[]])[0]
            metadatas = (result.get("metadatas") or [[]])[0]
            out = []
            for cid, dist, meta in zip(ids, distances, metadatas):
                out.append({"chunk_id": cid, "score": 1.0 - float(dist), **(meta or {})})
            return out

        data = self._load_fallback()
        out = []
        for chunk_id, payload in data.items():
            meta = payload.get("metadata", {})
            if module_name and meta.get("module_name") != module_name:
                continue
            score = _cosine(query_embedding, payload.get("embedding", []))
            out.append({"chunk_id": chunk_id, "score": score, **meta})
        out.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        return out[:top_k]

    def _load_fallback(self) -> dict:
        if not self._fallback_path.exists():
            return {}
        try:
            return json.loads(self._fallback_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _save_fallback(self, data: dict) -> None:
        self._fallback_path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
