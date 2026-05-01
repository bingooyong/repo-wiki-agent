"""Embedding provider abstractions with safe local fallback."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import List, Protocol, Sequence


class EmbeddingProvider(Protocol):
    """Common embedding interface."""

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        ...

    @property
    def backend_name(self) -> str:
        ...


@dataclass
class DeterministicEmbeddingProvider:
    """Dependency-free fallback embedding provider."""

    dims: int = 64

    @property
    def backend_name(self) -> str:
        return "deterministic-fallback"

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> List[float]:
        vec = [0.0] * self.dims
        for token in re.findall(r"[A-Za-z0-9_]+", text.lower()):
            digest = hashlib.md5(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:2], "big") % self.dims
            sign = 1.0 if digest[2] % 2 == 0 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0.0:
            return vec
        return [v / norm for v in vec]


class SentenceTransformerEmbeddingProvider:
    """Sentence-Transformers provider, defaults to BAAI/bge-m3."""

    def __init__(self, model_name: str = "BAAI/bge-m3") -> None:
        from sentence_transformers import SentenceTransformer

        self._model_name = model_name
        self._model = SentenceTransformer(model_name)

    @property
    def backend_name(self) -> str:
        return f"sentence-transformers:{self._model_name}"

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        vectors = self._model.encode(
            list(texts),
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return [list(map(float, row)) for row in vectors]


def build_embedding_provider(model_name: str = "BAAI/bge-m3") -> EmbeddingProvider:
    try:
        return SentenceTransformerEmbeddingProvider(model_name=model_name)
    except Exception:
        return DeterministicEmbeddingProvider()
