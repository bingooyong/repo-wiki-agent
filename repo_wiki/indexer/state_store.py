"""SQLite operational state store with deterministic migrations and FTS5."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


SCHEMA_VERSION = 1

MIGRATIONS = {
    1: """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        path TEXT NOT NULL UNIQUE,
        module_name TEXT NOT NULL,
        language TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        size_bytes INTEGER NOT NULL DEFAULT 0,
        mtime REAL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS file_hashes (
        file_path TEXT PRIMARY KEY,
        content_hash TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS chunks (
        chunk_id TEXT PRIMARY KEY,
        file_path TEXT NOT NULL,
        module_name TEXT NOT NULL,
        language TEXT NOT NULL,
        chunk_type TEXT NOT NULL,
        symbol_name TEXT NOT NULL,
        line_start INTEGER NOT NULL,
        line_end INTEGER NOT NULL,
        dependencies_json TEXT NOT NULL,
        text TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_chunks_file_path ON chunks(file_path);
    CREATE INDEX IF NOT EXISTS idx_chunks_module_name ON chunks(module_name);
    CREATE INDEX IF NOT EXISTS idx_chunks_language ON chunks(language);
    CREATE INDEX IF NOT EXISTS idx_chunks_type ON chunks(chunk_type);

    CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
        chunk_id UNINDEXED,
        text,
        module_name,
        file_path,
        symbol_name,
        tokenize = 'porter'
    );

    CREATE TRIGGER IF NOT EXISTS trg_chunks_ai AFTER INSERT ON chunks BEGIN
        INSERT INTO chunks_fts(chunk_id, text, module_name, file_path, symbol_name)
        VALUES (new.chunk_id, new.text, new.module_name, new.file_path, new.symbol_name);
    END;
    CREATE TRIGGER IF NOT EXISTS trg_chunks_ad AFTER DELETE ON chunks BEGIN
        INSERT INTO chunks_fts(chunks_fts, rowid, chunk_id, text, module_name, file_path, symbol_name)
        VALUES('delete', old.rowid, old.chunk_id, old.text, old.module_name, old.file_path, old.symbol_name);
    END;
    CREATE TRIGGER IF NOT EXISTS trg_chunks_au AFTER UPDATE ON chunks BEGIN
        INSERT INTO chunks_fts(chunks_fts, rowid, chunk_id, text, module_name, file_path, symbol_name)
        VALUES('delete', old.rowid, old.chunk_id, old.text, old.module_name, old.file_path, old.symbol_name);
        INSERT INTO chunks_fts(chunk_id, text, module_name, file_path, symbol_name)
        VALUES (new.chunk_id, new.text, new.module_name, new.file_path, new.symbol_name);
    END;

    CREATE TABLE IF NOT EXISTS symbols (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        kind TEXT NOT NULL,
        module_name TEXT NOT NULL,
        file_path TEXT NOT NULL,
        line_start INTEGER,
        line_end INTEGER,
        signature TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_symbols_file_path ON symbols(file_path);
    CREATE INDEX IF NOT EXISTS idx_symbols_module_name ON symbols(module_name);

    CREATE TABLE IF NOT EXISTS generation_cache (
        cache_key TEXT PRIMARY KEY,
        input_hash TEXT NOT NULL,
        output_hash TEXT,
        model_name TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS verify_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        status TEXT NOT NULL,
        result_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS metadata (
        key TEXT PRIMARY KEY,
        value_json TEXT NOT NULL
    );
    """,
}


@dataclass
class FTSResult:
    chunk_id: str
    file_path: str
    module_name: str
    language: str
    chunk_type: str
    symbol_name: str
    text: str
    bm25: float

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "file_path": self.file_path,
            "module_name": self.module_name,
            "language": self.language,
            "chunk_type": self.chunk_type,
            "symbol_name": self.symbol_name,
            "text": self.text,
            "bm25": self.bm25,
        }


class SQLiteStateStore:
    """SQLite canonical operational state for Phase 2 indexing and retrieval."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._configure_pragmas()
        self._apply_migrations()
        self._stabilize_fts_triggers()

    def _configure_pragmas(self) -> None:
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self.conn.execute("PRAGMA foreign_keys=ON;")

    def close(self) -> None:
        self.conn.close()

    def _apply_migrations(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            );
            """
        )
        applied = {
            int(row["version"])
            for row in self.conn.execute("SELECT version FROM schema_migrations")
        }
        for version in sorted(MIGRATIONS):
            if version in applied:
                continue
            with self.conn:
                self.conn.executescript(MIGRATIONS[version])
                self.conn.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES(?, ?)",
                    (version, _now_iso()),
                )
        self.conn.execute(
            """
            INSERT INTO metadata(key, value_json) VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json
            """,
            ("schema_version", json.dumps({"version": SCHEMA_VERSION})),
        )
        self.conn.commit()

    def _stabilize_fts_triggers(self) -> None:
        # Some SQLite builds reject FTS5 delete commands used by delete/update triggers.
        # Use explicit rebuild-based sync for deterministic compatibility.
        with self.conn:
            self.conn.execute("DROP TRIGGER IF EXISTS trg_chunks_ai;")
            self.conn.execute("DROP TRIGGER IF EXISTS trg_chunks_ad;")
            self.conn.execute("DROP TRIGGER IF EXISTS trg_chunks_au;")

    def current_schema_version(self) -> int:
        row = self.conn.execute(
            "SELECT value_json FROM metadata WHERE key='schema_version'"
        ).fetchone()
        if not row:
            return 0
        return int(json.loads(row["value_json"])["version"])

    def upsert_file(
        self,
        *,
        path: str,
        module_name: str,
        language: str,
        content_hash: str,
        size_bytes: int = 0,
        mtime: float | None = None,
    ) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO files(path, module_name, language, content_hash, size_bytes, mtime, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    module_name=excluded.module_name,
                    language=excluded.language,
                    content_hash=excluded.content_hash,
                    size_bytes=excluded.size_bytes,
                    mtime=excluded.mtime,
                    updated_at=excluded.updated_at
                """,
                (
                    path,
                    module_name,
                    language,
                    content_hash,
                    size_bytes,
                    mtime,
                    _now_iso(),
                ),
            )

    def upsert_file_hash(self, file_path: str, content_hash: str) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO file_hashes(file_path, content_hash, updated_at)
                VALUES(?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    content_hash=excluded.content_hash,
                    updated_at=excluded.updated_at
                """,
                (file_path, content_hash, _now_iso()),
            )

    def get_file_hash_map(self) -> dict[str, str]:
        rows = self.conn.execute(
            "SELECT file_path, content_hash FROM file_hashes ORDER BY file_path"
        ).fetchall()
        return {row["file_path"]: row["content_hash"] for row in rows}

    def replace_chunks_for_file(self, file_path: str, chunks: Sequence[Mapping]) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM chunks WHERE file_path = ?", (file_path,))
            for chunk in chunks:
                self.conn.execute(
                    """
                    INSERT INTO chunks(
                        chunk_id, file_path, module_name, language, chunk_type,
                        symbol_name, line_start, line_end, dependencies_json, text, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk["chunk_id"],
                        chunk["file_path"],
                        chunk["module_name"],
                        chunk["language"],
                        chunk["chunk_type"],
                        chunk["symbol_name"],
                        int(chunk["line_start"]),
                        int(chunk["line_end"]),
                        json.dumps(chunk.get("dependencies", []), ensure_ascii=True),
                        chunk["text"],
                        _now_iso(),
                    ),
                )
        self.rebuild_fts()

    def list_chunk_ids_for_file(self, file_path: str) -> list[str]:
        rows = self.conn.execute(
            "SELECT chunk_id FROM chunks WHERE file_path=? ORDER BY chunk_id", (file_path,)
        ).fetchall()
        return [row["chunk_id"] for row in rows]

    def delete_file(self, file_path: str) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM chunks WHERE file_path=?", (file_path,))
            self.conn.execute("DELETE FROM file_hashes WHERE file_path=?", (file_path,))
            self.conn.execute("DELETE FROM files WHERE path=?", (file_path,))
            self.conn.execute("DELETE FROM symbols WHERE file_path=?", (file_path,))
        self.rebuild_fts()

    def replace_symbols_for_file(self, file_path: str, symbols: Sequence[Mapping]) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM symbols WHERE file_path=?", (file_path,))
            for symbol in symbols:
                self.conn.execute(
                    """
                    INSERT INTO symbols(name, kind, module_name, file_path, line_start, line_end, signature)
                    VALUES(?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        symbol["name"],
                        symbol["kind"],
                        symbol["module_name"],
                        file_path,
                        symbol.get("line_start"),
                        symbol.get("line_end"),
                        symbol.get("signature"),
                    ),
                )

    def search_chunks_fts(
        self,
        query: str,
        *,
        top_k: int = 20,
        module_names: Iterable[str] | None = None,
        path_prefix: str | None = None,
        language: str | None = None,
        artifact_types: Iterable[str] | None = None,
    ) -> list[FTSResult]:
        where = ["chunks_fts MATCH ?"]
        params: list[object] = [query]

        if module_names:
            names = sorted(set(module_names))
            where.append(f"c.module_name IN ({','.join('?' for _ in names)})")
            params.extend(names)
        if path_prefix:
            where.append("c.file_path LIKE ?")
            params.append(f"{path_prefix}%")
        if language:
            where.append("c.language = ?")
            params.append(language)
        if artifact_types:
            types = sorted(set(artifact_types))
            where.append(f"c.chunk_type IN ({','.join('?' for _ in types)})")
            params.extend(types)

        sql = f"""
            SELECT
                c.chunk_id,
                c.file_path,
                c.module_name,
                c.language,
                c.chunk_type,
                c.symbol_name,
                c.text,
                bm25(chunks_fts) AS bm25_score
            FROM chunks_fts
            JOIN chunks c ON c.chunk_id = chunks_fts.chunk_id
            WHERE {" AND ".join(where)}
            ORDER BY bm25_score ASC, c.chunk_id ASC
            LIMIT ?
        """
        params.append(int(top_k))
        rows = self.conn.execute(sql, params).fetchall()
        return [
            FTSResult(
                chunk_id=row["chunk_id"],
                file_path=row["file_path"],
                module_name=row["module_name"],
                language=row["language"],
                chunk_type=row["chunk_type"],
                symbol_name=row["symbol_name"],
                text=row["text"],
                bm25=float(row["bm25_score"]),
            )
            for row in rows
        ]

    def list_chunks(
        self,
        *,
        module_names: Iterable[str] | None = None,
        path_prefix: str | None = None,
        language: str | None = None,
        artifact_types: Iterable[str] | None = None,
        limit: int = 200,
    ) -> list[dict]:
        where = ["1=1"]
        params: list[object] = []
        if module_names:
            names = sorted(set(module_names))
            where.append(f"module_name IN ({','.join('?' for _ in names)})")
            params.extend(names)
        if path_prefix:
            where.append("file_path LIKE ?")
            params.append(f"{path_prefix}%")
        if language:
            where.append("language = ?")
            params.append(language)
        if artifact_types:
            types = sorted(set(artifact_types))
            where.append(f"chunk_type IN ({','.join('?' for _ in types)})")
            params.extend(types)
        sql = f"""
            SELECT chunk_id, file_path, module_name, language, chunk_type, symbol_name, text
            FROM chunks
            WHERE {" AND ".join(where)}
            ORDER BY chunk_id ASC
            LIMIT ?
        """
        params.append(int(limit))
        rows = self.conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def get_chunks_by_ids(self, chunk_ids: Sequence[str]) -> list[dict]:
        if not chunk_ids:
            return []
        placeholders = ",".join("?" for _ in chunk_ids)
        sql = f"""
            SELECT chunk_id, file_path, module_name, language, chunk_type, symbol_name, text
            FROM chunks
            WHERE chunk_id IN ({placeholders})
        """
        rows = self.conn.execute(sql, list(chunk_ids)).fetchall()
        by_id = {row["chunk_id"]: dict(row) for row in rows}
        return [by_id[chunk_id] for chunk_id in chunk_ids if chunk_id in by_id]

    def rebuild_fts(self) -> None:
        with self.conn:
            self.conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild');")

    def integrity_check(self) -> str:
        row = self.conn.execute("PRAGMA integrity_check;").fetchone()
        return row[0] if row else "unknown"

    def export_json_artifacts(self, output_dir: str | Path) -> dict[str, Path]:
        target = Path(output_dir)
        target.mkdir(parents=True, exist_ok=True)

        symbols_rows = self.conn.execute(
            """
            SELECT name, kind, module_name, file_path, line_start, line_end, signature
            FROM symbols
            ORDER BY file_path, line_start, name
            """
        ).fetchall()
        symbols = [dict(row) for row in symbols_rows]

        file_hash = self.get_file_hash_map()

        meta = {
            "schema_version": self.current_schema_version(),
            "exported_at": _now_iso(),
            "counts": {
                "files": self._count("files"),
                "chunks": self._count("chunks"),
                "symbols": self._count("symbols"),
            },
        }

        symbols_path = target / "symbols.json"
        file_hash_path = target / "file-hash.json"
        meta_path = target / "meta.json"
        symbols_path.write_text(json.dumps(symbols, indent=2, sort_keys=True), encoding="utf-8")
        file_hash_path.write_text(
            json.dumps(file_hash, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")
        return {
            "symbols.json": symbols_path,
            "file-hash.json": file_hash_path,
            "meta.json": meta_path,
        }

    def _count(self, table_name: str) -> int:
        row = self.conn.execute(f"SELECT COUNT(*) AS c FROM {table_name}").fetchone()
        return int(row["c"])
