from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.core.contracts import RepositorySnapshot
from repo_wiki.core.security import sanitize_text, should_scan
from repo_wiki.generator.io import relpath, write_json
from repo_wiki.indexer.chunking import chunk_source
from repo_wiki.indexer.embeddings import build_embedding_provider
from repo_wiki.indexer.hashing import compute_file_hash, diff_hash_maps
from repo_wiki.indexer.state_store import SQLiteStateStore
from repo_wiki.indexer.vector_store import ChromaVectorStore, VectorEntry


@dataclass
class IndexingResult:
    indexed_files: int
    changed_files: list[str]
    deleted_files: list[str]
    exported: dict[str, str]


class SemanticIndexer:
    def __init__(self, root: Path, config: RepoWikiConfig) -> None:
        self.root = root
        self.config = config
        self.index_root = root / ".repo-wiki" / "index"
        self.store = SQLiteStateStore(self.index_root / "state.sqlite3")
        self.embedder = build_embedding_provider("BAAI/bge-m3")
        self.vector_store = ChromaVectorStore(self.index_root / "chroma")

    def rebuild(self, snapshot: RepositorySnapshot) -> IndexingResult:
        module_by_path = {m.path: m.name for m in snapshot.modules}
        current_hash: dict[str, str] = {}
        chunk_count = 0
        changed_files: list[str] = []

        previous_hash = self.store.get_file_hash_map()

        for path in sorted(self.root.rglob("*")):
            if not path.is_file():
                continue
            if not should_scan(path, self.config, root=self.root):
                continue
            if path.suffix.lower() not in {".py", ".ts", ".tsx", ".js", ".jsx", ".go"}:
                continue
            relative = relpath(path, self.root)
            file_hash = compute_file_hash(path)
            current_hash[relative] = file_hash
            if previous_hash.get(relative) == file_hash:
                continue
            changed_files.append(relative)

            text = path.read_text(encoding="utf-8", errors="ignore")
            text, _warnings = sanitize_text(text, path=relative)
            module_name = _module_name_for_file(relative, module_by_path)
            language = _language_for_suffix(path.suffix.lower())

            chunks = chunk_source(
                text,
                file_path=relative,
                module_name=module_name,
                language=language,
                sanitize_text=lambda value: sanitize_text(value, path=relative)[0],
            )
            self.store.upsert_file(
                path=relative,
                module_name=module_name,
                language=language,
                content_hash=file_hash,
                size_bytes=path.stat().st_size,
                mtime=path.stat().st_mtime,
            )
            self.store.upsert_file_hash(relative, file_hash)
            self.store.replace_chunks_for_file(relative, [c.to_record() for c in chunks])
            symbols = [
                {
                    "name": c.symbol_name,
                    "kind": c.chunk_type,
                    "module_name": c.module_name,
                    "line_start": c.line_start,
                    "line_end": c.line_end,
                    "signature": c.symbol_name,
                }
                for c in chunks
                if c.chunk_type in {"function", "class"}
            ]
            self.store.replace_symbols_for_file(relative, symbols)

            embeddings = self.embedder.embed([c.text for c in chunks])
            entries = [
                VectorEntry(
                    chunk_id=chunk.chunk_id,
                    embedding=embeddings[idx],
                    metadata={
                        "file_path": chunk.file_path,
                        "module_name": chunk.module_name,
                        "language": chunk.language,
                        "chunk_type": chunk.chunk_type,
                        "symbol_name": chunk.symbol_name,
                        "line_start": chunk.line_start,
                        "line_end": chunk.line_end,
                        "text": chunk.text,
                    },
                )
                for idx, chunk in enumerate(chunks)
            ]
            self.vector_store.upsert(entries)
            chunk_count += len(chunks)

        hash_diff = diff_hash_maps(previous_hash, current_hash)
        deleted_files = sorted(hash_diff["deleted"].keys())
        for deleted in deleted_files:
            old_chunk_ids = self.store.list_chunk_ids_for_file(deleted)
            self.vector_store.delete(old_chunk_ids)
            self.store.delete_file(deleted)

        exported_paths = self.store.export_json_artifacts(self.index_root)
        exported = {name: str(path) for name, path in exported_paths.items()}
        write_json(
            self.index_root / "indexing_summary.json",
            {
                "indexed_files": len(changed_files),
                "deleted_files": deleted_files,
                "chunks_written": chunk_count,
                "embedding_backend": getattr(self.embedder, "backend_name", "unknown"),
            },
        )
        return IndexingResult(
            indexed_files=len(changed_files),
            changed_files=sorted(changed_files),
            deleted_files=deleted_files,
            exported=exported,
        )


def _module_name_for_file(relative_path: str, module_by_path: dict[str, str]) -> str:
    for module_path, module_name in sorted(module_by_path.items(), key=lambda item: len(item[0]), reverse=True):
        if relative_path == module_path or relative_path.startswith(f"{module_path}/"):
            return module_name
    return Path(relative_path).parts[0] if Path(relative_path).parts else "root"


def _language_for_suffix(suffix: str) -> str:
    return {
        ".py": "python",
        ".go": "go",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
    }.get(suffix, "unknown")
