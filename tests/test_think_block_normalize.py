"""Leaked model think dumps must not be written to wiki pages.

R8 (FastAPI RealWorld / MiniMax-M3): 89/89 pages contained leaked <think>;
QODER_PAGE_DUMP HARD only listed 12. This is an emit/normalize bug.
"""

from __future__ import annotations

from pathlib import Path

from repo_wiki.generator.composer import (
    EMPTY_COMPOSER_STUB_PHRASE,
    create_composer,
    is_empty_composer_markdown,
)
from repo_wiki.verifier.qoder_strict_verifier import QoderLikeSeverityThreshold


def test_closed_think_block_before_heading_is_stripped(tmp_path: Path) -> None:
    """Raw LLM text starting with <think>…</think> then # 项目概述 writes heading+body only."""
    composer = create_composer(workspace_root=tmp_path)
    raw = (
        "<think>\n"
        "The model is planning an overview page and reviewing evidence.\n"
        "</think>\n"
        "# 项目概述\n"
        "\n"
        "这是一个基于 FastAPI 的 RealWorld 后端实现。\n"
    )
    page = composer._normalize_markdown_response(raw, "项目概述")
    written = tmp_path / "项目概述.md"
    written.write_text(page, encoding="utf-8")
    on_disk = written.read_text(encoding="utf-8")

    assert on_disk.lstrip().startswith("# 项目概述")
    assert "<think" not in on_disk
    assert "</think>" not in on_disk
    assert "planning an overview page" not in on_disk
    assert "这是一个基于 FastAPI 的 RealWorld 后端实现。" in on_disk


def test_unclosed_think_prefix_before_first_heading_is_dropped(tmp_path: Path) -> None:
    """Unclosed <think> prefix before the first heading is discarded."""
    composer = create_composer(workspace_root=tmp_path)
    raw = (
        "<think>\n"
        "I am still reasoning about structure and have not closed the dump.\n"
        "# 项目概述\n"
        "\n"
        "正文从这里开始。\n"
    )
    page = composer._normalize_markdown_response(raw, "项目概述")
    written = tmp_path / "项目概述.md"
    written.write_text(page, encoding="utf-8")
    on_disk = written.read_text(encoding="utf-8")

    assert on_disk.lstrip().startswith("# 项目概述")
    assert "<think" not in on_disk
    assert "still reasoning about structure" not in on_disk
    assert "正文从这里开始。" in on_disk


def test_prose_word_think_is_kept(tmp_path: Path) -> None:
    """A page that mentions the word think in prose, not the tag, is kept."""
    composer = create_composer(workspace_root=tmp_path)
    raw = "# 项目概述\n\nReaders should think of this service as the Conduit API backend.\n"
    page = composer._normalize_markdown_response(raw, "项目概述")

    assert "think of this service" in page
    assert "<think" not in page


def test_qoder_page_dump_remains_hard() -> None:
    """Do not weaken QODER_PAGE_DUMP to hide leftover think dumps."""
    threshold = QoderLikeSeverityThreshold()
    assert threshold.is_blocking("QODER_PAGE_DUMP") is True


def test_think_only_normalize_is_empty_not_pass_stub() -> None:
    """Think-only LLM output must not become the historic titled stub."""
    composer = create_composer()
    raw = "<think>\n" + ("planning the install page. " * 40) + "\n</think>\n"
    page = composer._normalize_markdown_response(raw, "安装指南")

    assert page == ""
    assert EMPTY_COMPOSER_STUB_PHRASE not in page
    assert is_empty_composer_markdown(page)


def test_historic_empty_stub_is_empty_content() -> None:
    stub = f"# 安装指南\n\n{EMPTY_COMPOSER_STUB_PHRASE}."
    assert is_empty_composer_markdown(stub)
    assert is_empty_composer_markdown("")
    assert not is_empty_composer_markdown("# 安装指南\n\n设置 DATABASE_URL 后启动。\n")
