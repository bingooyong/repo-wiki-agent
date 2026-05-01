from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.core.security import should_scan
from repo_wiki.generator.io import read_json, read_yamlish, write_json
from repo_wiki.indexer.embeddings import build_embedding_provider
from repo_wiki.indexer.hashing import compute_file_hash, diff_hash_maps
from repo_wiki.indexer.state_store import SQLiteStateStore
from repo_wiki.indexer.vector_store import ChromaVectorStore


_CODE_SUFFIXES = {".py", ".go", ".ts", ".tsx", ".js", ".jsx"}
_GLOBAL_TRIGGER_FILES = {
    "pyproject.toml",
    "package.json",
    "go.mod",
    "Dockerfile",
    "Makefile",
    "repo-wiki.yaml",
    ".repo-wiki.yaml",
}


@dataclass
class IncrementalImpact:
    changed_files: list[str]
    deleted_files: list[str]
    renamed_files: dict[str, str]
    changed_modules: list[str]
    impacted_modules: list[str]
    global_doc_regeneration_triggers: bool
    change_source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "changed_files": self.changed_files,
            "deleted_files": self.deleted_files,
            "renamed_files": self.renamed_files,
            "changed_modules": self.changed_modules,
            "impacted_modules": self.impacted_modules,
            "global_doc_regeneration_triggers": self.global_doc_regeneration_triggers,
            "change_source": self.change_source,
        }


class RetrievalService:
    def __init__(self, root: Path, config: RepoWikiConfig) -> None:
        self.root = root
        self.config = config
        self.index_root = root / ".repo-wiki" / "index"
        self.graph_root = root / ".repo-wiki" / "graph"
        self.store = SQLiteStateStore(self.index_root / "state.sqlite3")
        self.vector_store = ChromaVectorStore(self.index_root / "chroma")
        self.embedder = build_embedding_provider("BAAI/bge-m3")

    def analyze_incremental_impact(self) -> IncrementalImpact:
        changes, source = self._detect_changes()
        modules = self._load_module_index()
        changed_files = sorted(
            set(changes["added"]) | set(changes["modified"]) | set(changes["renamed"].values())
        )
        deleted_files = sorted(changes["deleted"])
        renamed_files = dict(sorted(changes["renamed"].items()))
        changed_modules = self._map_files_to_modules(changed_files + deleted_files + list(renamed_files.keys()), modules)
        impacted_modules = self._expand_impacted_modules(changed_modules)
        global_trigger = self._needs_global_regeneration(changed_files, deleted_files, renamed_files)
        return IncrementalImpact(
            changed_files=changed_files,
            deleted_files=deleted_files,
            renamed_files=renamed_files,
            changed_modules=changed_modules,
            impacted_modules=impacted_modules,
            global_doc_regeneration_triggers=global_trigger,
            change_source=source,
        )

    def search(
        self,
        *,
        query: str,
        module: str | None = None,
        top_k: int = 10,
        path_prefix: str | None = None,
        language: str | None = None,
        artifact_types: list[str] | None = None,
        token_budget: int = 4000,
    ) -> dict[str, Any]:
        module_filter = [module] if module else None
        fts_hits = self.store.search_chunks_fts(
            query,
            top_k=max(20, top_k * 4),
            module_names=module_filter,
            path_prefix=path_prefix,
            language=language,
            artifact_types=artifact_types,
        )
        query_embedding = self.embedder.embed([query])[0]
        semantic_hits = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=max(20, top_k * 4),
            module_name=module,
        )

        combined: dict[str, dict[str, Any]] = {}
        for item in fts_hits:
            lexical_score = 1.0 / (1.0 + max(item.bm25, 0.0))
            combined[item.chunk_id] = {
                "chunk_id": item.chunk_id,
                "file_path": item.file_path,
                "module_name": item.module_name,
                "language": item.language,
                "chunk_type": item.chunk_type,
                "symbol_name": item.symbol_name,
                "text": item.text,
                "lexical_score": lexical_score,
                "semantic_score": 0.0,
                "graph_bonus": 0.0,
                "reasons": [f"fts5(bm25={item.bm25:.4f})"],
            }

        for item in semantic_hits:
            chunk_id = str(item.get("chunk_id"))
            if chunk_id not in combined:
                combined[chunk_id] = {
                    "chunk_id": chunk_id,
                    "file_path": str(item.get("file_path", "")),
                    "module_name": str(item.get("module_name", "")),
                    "language": str(item.get("language", "")),
                    "chunk_type": str(item.get("chunk_type", "")),
                    "symbol_name": str(item.get("symbol_name", "")),
                    "text": str(item.get("text", "")),
                    "lexical_score": 0.0,
                    "semantic_score": 0.0,
                    "graph_bonus": 0.0,
                    "reasons": [],
                }
            combined[chunk_id]["semantic_score"] = max(
                float(item.get("score", 0.0)),
                float(combined[chunk_id]["semantic_score"]),
            )
            combined[chunk_id]["reasons"].append(f"semantic(score={float(item.get('score', 0.0)):.4f})")

        if not module:
            neighbor_modules = self._expand_modules_from_candidates(list(combined.values())[:20])
            if neighbor_modules:
                neighbor_chunks = self.store.list_chunks(module_names=neighbor_modules, limit=80)
                for item in neighbor_chunks:
                    chunk_id = str(item["chunk_id"])
                    if chunk_id not in combined:
                        combined[chunk_id] = {
                            "chunk_id": chunk_id,
                            "file_path": str(item.get("file_path", "")),
                            "module_name": str(item.get("module_name", "")),
                            "language": str(item.get("language", "")),
                            "chunk_type": str(item.get("chunk_type", "")),
                            "symbol_name": str(item.get("symbol_name", "")),
                            "text": str(item.get("text", "")),
                            "lexical_score": 0.0,
                            "semantic_score": 0.0,
                            "graph_bonus": 0.1,
                            "reasons": ["graph-neighbor-expansion"],
                        }
                    else:
                        combined[chunk_id]["graph_bonus"] = max(float(combined[chunk_id]["graph_bonus"]), 0.1)
                        combined[chunk_id]["reasons"].append("graph-neighbor-expansion")

        ranked = []
        for item in combined.values():
            lexical = float(item["lexical_score"])
            semantic = float(item["semantic_score"])
            graph_bonus = float(item["graph_bonus"])
            score = 0.35 * lexical + 0.55 * semantic + graph_bonus
            item["score"] = score
            ranked.append(item)
        ranked.sort(key=lambda x: (-float(x["score"]), str(x["chunk_id"])))

        results: list[dict[str, Any]] = []
        consumed = 0
        for item in ranked:
            text = str(item.get("text", ""))
            estimated_tokens = max(1, len(text) // 4)
            if results and consumed + estimated_tokens > token_budget:
                continue
            consumed += estimated_tokens
            results.append(
                {
                    "chunk_id": item["chunk_id"],
                    "file_path": item["file_path"],
                    "module_name": item["module_name"],
                    "language": item["language"],
                    "chunk_type": item["chunk_type"],
                    "symbol_name": item["symbol_name"],
                    "score": round(float(item["score"]), 6),
                    "reasons": sorted(set(item["reasons"])),
                    "excerpt": text[:400],
                }
            )
            if len(results) >= top_k:
                break

        return {
            "query": query,
            "top_k": top_k,
            "results": results,
            "diagnostics": {
                "retrieval_order": [
                    "hard_filters",
                    "sqlite_fts5_bm25",
                    "semantic_topk",
                    "graph_neighbor_expansion",
                    "prompt_candidate_assembly",
                ],
                "token_budget": token_budget,
                "token_consumed": consumed,
                "fts_hits": len(fts_hits),
                "semantic_hits": len(semantic_hits),
                "candidate_count": len(combined),
            },
        }

    def build_retrieval_candidates(self, module_names: list[str]) -> Path:
        graph = read_json(self.graph_root / "knowledge_graph.json", {"modules": {}})
        graph_modules = graph.get("modules", {}) if isinstance(graph, dict) else {}
        payload: dict[str, Any] = {
            "generated_at": datetime.now(UTC).isoformat(),
            "modules": {},
        }
        for module_name in sorted(set(module_names)):
            own = self.store.list_chunks(module_names=[module_name], limit=8)
            neighbors = set()
            node = graph_modules.get(module_name, {}) if isinstance(graph_modules, dict) else {}
            if isinstance(node, dict):
                neighbors.update(node.get("upstream", []) or [])
                neighbors.update(node.get("downstream", []) or [])
            neighbor_chunks = self.store.list_chunks(module_names=sorted(neighbors), limit=8) if neighbors else []
            merged = own + [item for item in neighbor_chunks if item["chunk_id"] not in {c["chunk_id"] for c in own}]
            payload["modules"][module_name] = [
                {
                    "chunk_id": item["chunk_id"],
                    "file_path": item["file_path"],
                    "module_name": item["module_name"],
                    "language": item["language"],
                    "chunk_type": item["chunk_type"],
                    "symbol_name": item["symbol_name"],
                }
                for item in merged[:12]
            ]

        output_path = self.index_root / "retrieval_candidates.json"
        write_json(output_path, payload)
        return output_path

    def _detect_changes(self) -> tuple[dict[str, Any], str]:
        git_changes = self._git_changes()
        if git_changes is not None:
            return git_changes, "git"
        return self._hash_compare_changes(), "hash-compare-fallback"

    def _git_changes(self) -> dict[str, Any] | None:
        cmd = ["git", "-C", str(self.root), "rev-parse", "--is-inside-work-tree"]
        probe = subprocess.run(cmd, capture_output=True, text=True)
        if probe.returncode != 0:
            return None
        status_cmd = ["git", "-C", str(self.root), "status", "--porcelain"]
        status = subprocess.run(status_cmd, capture_output=True, text=True)
        if status.returncode != 0:
            return None
        changes = {
            "added": {},
            "modified": {},
            "deleted": {},
            "renamed": {},
            "unchanged": {},
        }
        for line in status.stdout.splitlines():
            if len(line) < 4:
                continue
            code = line[:2].strip()
            payload = line[3:]
            if " -> " in payload:
                old_path, new_path = payload.split(" -> ", 1)
                changes["renamed"][old_path.strip()] = new_path.strip()
                continue
            path = payload.strip()
            if code in {"A", "??"} or code.endswith("A"):
                changes["added"][path] = ""
            elif code == "D" or code.endswith("D"):
                changes["deleted"][path] = ""
            else:
                changes["modified"][path] = ""
        return changes

    def _hash_compare_changes(self) -> dict[str, Any]:
        previous = self.store.get_file_hash_map()
        current: dict[str, str] = {}
        for path in sorted(self.root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in _CODE_SUFFIXES:
                continue
            if not should_scan(path, self.config, root=self.root):
                continue
            rel = path.relative_to(self.root).as_posix()
            current[rel] = compute_file_hash(path)
        return diff_hash_maps(previous, current)

    def _load_module_index(self) -> list[dict[str, Any]]:
        data = read_yamlish(self.root / "ai" / "source-of-truth" / "module-index.yaml", {"modules": []})
        if not isinstance(data, dict):
            return []
        modules = data.get("modules", [])
        if not isinstance(modules, list):
            return []
        return [m for m in modules if isinstance(m, dict)]

    def _map_files_to_modules(self, files: list[str], modules: list[dict[str, Any]]) -> list[str]:
        records = []
        for module in modules:
            module_path = str(module.get("path", "")).strip("/")
            module_name = str(module.get("name", "")).strip()
            if not module_name:
                continue
            records.append((module_path, module_name))
        records.sort(key=lambda item: len(item[0]), reverse=True)

        mapped: set[str] = set()
        for file_path in files:
            normalized = file_path.strip("/")
            matched = False
            for module_path, module_name in records:
                if not module_path:
                    continue
                if normalized == module_path or normalized.startswith(f"{module_path}/"):
                    mapped.add(module_name)
                    matched = True
                    break
            if matched:
                continue
            parts = Path(normalized).parts
            if parts:
                mapped.add(parts[0])
        return sorted(mapped)

    def _expand_impacted_modules(self, changed_modules: list[str]) -> list[str]:
        data = read_json(self.graph_root / "impact_cache.json", {})
        if not isinstance(data, dict):
            return sorted(set(changed_modules))
        impacted = set(changed_modules)
        for module_name in changed_modules:
            node = data.get(module_name, {})
            if not isinstance(node, dict):
                continue
            impacted.update(node.get("upstream", []) or [])
            impacted.update(node.get("downstream", []) or [])
            impacted.update(node.get("depth2", []) or [])
        return sorted(impacted)

    def _needs_global_regeneration(
        self,
        changed_files: list[str],
        deleted_files: list[str],
        renamed_files: dict[str, str],
    ) -> bool:
        candidates = set(changed_files) | set(deleted_files) | set(renamed_files) | set(renamed_files.values())
        for path in candidates:
            if Path(path).name in _GLOBAL_TRIGGER_FILES:
                return True
            if path.startswith("ai/source-of-truth/"):
                return True
        return False

    def _expand_modules_from_candidates(self, candidates: list[dict[str, Any]]) -> list[str]:
        graph = read_json(self.graph_root / "knowledge_graph.json", {"modules": {}})
        modules = graph.get("modules", {}) if isinstance(graph, dict) else {}
        out: set[str] = set()
        for item in candidates:
            module_name = str(item.get("module_name", ""))
            if not module_name:
                continue
            node = modules.get(module_name, {}) if isinstance(modules, dict) else {}
            if not isinstance(node, dict):
                continue
            out.update(node.get("upstream", []) or [])
            out.update(node.get("downstream", []) or [])
        return sorted(out)
