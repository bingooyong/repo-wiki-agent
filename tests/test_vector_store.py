from __future__ import annotations

import sys
from pathlib import Path

import pytest

from repo_wiki.indexer import vector_store as vector_store_mod
from repo_wiki.indexer.vector_store import ChromaVectorStore


def test_chroma_fallback_notice_does_not_write_to_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(vector_store_mod, "_CHROMA_FALLBACK_LOGGED", False)
    monkeypatch.setitem(sys.modules, "chromadb", None)

    ChromaVectorStore(tmp_path)

    captured = capsys.readouterr()
    assert "ChromaDB" not in captured.out
    assert "ChromaDB" in captured.err
