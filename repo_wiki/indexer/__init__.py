"""Indexing utilities for repo-wiki Phase 2."""

from .chunking import Chunk, chunk_source
from .embeddings import (
    DeterministicEmbeddingProvider,
    EmbeddingProvider,
    SentenceTransformerEmbeddingProvider,
    build_embedding_provider,
)
from .hashing import (
    compute_file_hash,
    compute_text_hash,
    diff_hash_maps,
)
from .indexing import SemanticIndexer
from .state_store import SQLiteStateStore
from .vector_store import ChromaVectorStore, VectorEntry

__all__ = [
    "Chunk",
    "chunk_source",
    "EmbeddingProvider",
    "DeterministicEmbeddingProvider",
    "SentenceTransformerEmbeddingProvider",
    "build_embedding_provider",
    "compute_file_hash",
    "compute_text_hash",
    "diff_hash_maps",
    "SemanticIndexer",
    "SQLiteStateStore",
    "ChromaVectorStore",
    "VectorEntry",
]
