"""Tests for the read-only external Qoder baseline registry."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from repo_wiki.verifier.external_baseline_registry import (
    collect_knowledge_stats,
    collect_longform_stats,
    load_registry,
    refresh_entry,
    resolve_entry_root,
    verify_entry,
    verify_registry,
)

REAL_BASELINE = Path(
    "/Users/bingooyong/Code/01Code/github.com/bingooyong/ai-testing/.qoder/repowiki/knowledge/zh"
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def knowledge_root(tmp_path: Path) -> Path:
    root = tmp_path / "knowledge" / "zh"
    _write(
        root / "_index.yaml",
        yaml.safe_dump(
            {
                "schema_version": 1,
                "locale": "zh-CN",
                "commit": "a" * 40,
                "branch": "main",
                "exported_at": "2026-11-22T06:14:22Z",
                "modules": {
                    "root": {
                        "dir_name": "Repo Title",
                        "title": "Repo Title",
                        "scope": ["README.md"],
                        "children": ["root/child"],
                        "depends_on": [],
                        "related_to": [{"path": "root/child", "reason": "cli.py calls child.run()"}],
                    },
                    "root/child": {
                        "dir_name": "Child Dir",
                        "title": "Child Dir",
                        "scope": ["child/"],
                        "children": [],
                        "depends_on": [],
                        "related_to": [],
                        "version_of": [{"path": "root", "reason": ""}],
                    },
                },
            },
            allow_unicode=True,
        ),
    )
    _write(
        root / "Repo Title" / "_module.yaml",
        yaml.safe_dump(
            {
                "schema_version": 1,
                "module_path": "root",
                "title": "Repo Title",
                "kk_module_id": "m-1",
                "kk_cards": {
                    "overview": {"id": "c-1", "title": "Repo Title"},
                    "architecture_design": {"id": "c-2", "title": "Repo Title"},
                    "build_system": {"id": "c-3", "title": "Build"},
                },
                "kk_repo_cards": ["build_system"],
            },
            allow_unicode=True,
        ),
    )
    _write(root / "Repo Title" / "概述.md", "核心产物见 pyproject.toml 与 Makefile。")
    _write(root / "Repo Title" / "架构设计.md", "编排层调用 child/run.py。")
    _write(root / "Repo Title" / "build_system.md", "构建入口 Makefile。")
    _write(
        root / "Repo Title" / "Child Dir" / "_module.yaml",
        yaml.safe_dump(
            {
                "schema_version": 1,
                "module_path": "root/child",
                "title": "Child Dir",
                "kk_module_id": "m-2",
                "kk_cards": {"overview": {"id": "c-4", "title": "Child Dir"}},
                "kk_repo_cards": [],
            },
            allow_unicode=True,
        ),
    )
    _write(root / "Repo Title" / "Child Dir" / "概述.md", "子模块概述。")
    return root


@pytest.fixture
def longform_root(tmp_path: Path) -> Path:
    root = tmp_path / "zh"
    _write(root / "content" / "项目概述.md", "# 项目概述\n\n<cite>\n- [a.py](file://a.py#L1)\n</cite>\n\n```mermaid\ngraph TD\n```\n")
    _write(root / "content" / "架构设计" / "编排.md", "# 编排\n\n正文段落，无图。")
    _write(
        root / "meta" / "repowiki-metadata.json",
        json.dumps(
            {
                "wiki_repo": {
                    "progress_status": "completed",
                    "wiki_present_status": "COMPLETED",
                    "last_commit_id": "b" * 40,
                },
                "wiki_catalogs": [{"id": "1", "parent_id": None}, {"id": "2", "parent_id": "1"}],
                "wiki_items": [{"id": "i1"}, {"id": "i2"}],
                "knowledge_relations": [{"id": "r1"}],
            }
        ),
    )
    return root


def test_knowledge_stats_counts_and_reason_coverage(knowledge_root: Path) -> None:
    stats = collect_knowledge_stats(knowledge_root)
    assert stats["module_count"] == 2
    assert stats["module_yaml_count"] == 2
    assert stats["markdown_file_count"] == 4
    assert stats["module_card_counts"] == {"overview": 2, "architecture_design": 1}
    assert stats["repo_card_counts"] == {"build_system": 1}
    assert stats["relation_counts"] == {"depends_on": 0, "related_to": 1, "version_of": 1}
    assert stats["relation_reason_coverage"] == 0.5
    assert stats["missing_module_yaml"] == []
    assert stats["missing_card_files"] == []
    assert stats["evidence"]["file_ref_count"] > 0


def test_knowledge_stats_flags_missing_card_file(knowledge_root: Path) -> None:
    (knowledge_root / "Repo Title" / "概述.md").unlink()
    stats = collect_knowledge_stats(knowledge_root)
    assert stats["missing_card_files"] == ["root/概述.md"]


def test_longform_stats(longform_root: Path) -> None:
    stats = collect_longform_stats(longform_root)
    assert stats["page_count"] == 2
    assert stats["catalog_count"] == 2
    assert stats["root_catalog_count"] == 1
    assert stats["knowledge_relation_count"] == 1
    assert stats["progress_status"] == "completed"
    assert stats["mermaid_coverage"] == 0.5
    assert stats["cite_block_coverage"] == 0.5
    assert stats["line_anchor_coverage"] == 0.5


def test_hash_reproducible_and_tamper_detected(knowledge_root: Path) -> None:
    entry = refresh_entry(
        {"id": "k", "kind": "knowledge_cards", "content_hash": "", "file_count": 0, "stats": {}},
        knowledge_root,
    )
    assert verify_entry(entry, knowledge_root)["status"] == "PASS"

    (knowledge_root / "Repo Title" / "概述.md").write_text("tampered", encoding="utf-8")
    result = verify_entry(entry, knowledge_root)
    assert result["status"] == "FAIL"
    assert any("content_hash mismatch" in m for m in result["mismatches"])


def test_verify_entry_missing_root(tmp_path: Path) -> None:
    entry = {"id": "k", "kind": "knowledge_cards", "content_hash": "x", "file_count": 1, "stats": {}}
    result = verify_entry(entry, tmp_path / "absent")
    assert result["status"] == "FAIL"
    assert "baseline root missing" in result["mismatches"][0]


def test_registry_load_and_override(tmp_path: Path, knowledge_root: Path) -> None:
    registry_path = tmp_path / "registry.json"
    entry = refresh_entry(
        {
            "id": "k",
            "kind": "knowledge_cards",
            "source_repo_root": str(tmp_path / "elsewhere"),
            "source_path": "knowledge/zh",
            "content_hash": "",
            "file_count": 0,
            "stats": {},
        },
        knowledge_root,
    )
    registry_path.write_text(
        json.dumps({"schema_version": 1, "baselines": [entry]}), encoding="utf-8"
    )

    assert load_registry(registry_path)["baselines"][0]["id"] == "k"
    assert resolve_entry_root(entry) == (tmp_path / "elsewhere" / "knowledge" / "zh").resolve()
    assert resolve_entry_root(entry, {"k": knowledge_root}) == knowledge_root.resolve()

    assert verify_registry(registry_path)["status"] == "FAIL"
    assert verify_registry(registry_path, {"k": knowledge_root})["status"] == "PASS"


def test_registry_rejects_bad_schema(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema_version": 99, "baselines": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_registry(bad)
    bad.write_text(json.dumps({"schema_version": 1, "baselines": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_registry(bad)


@pytest.mark.skipif(not REAL_BASELINE.is_dir(), reason="ai-testing baseline not checked out")
def test_real_baseline_registry_passes() -> None:
    registry = Path(__file__).resolve().parents[1] / "ai" / "baselines" / "registry.json"
    result = verify_registry(registry)
    assert result["status"] == "PASS", result["failed_entries"]
    knowledge = next(e for e in result["entries"] if e["id"] == "ai-testing-knowledge-zh")
    assert knowledge["stats"]["module_count"] == 15
    assert knowledge["stats"]["relation_reason_coverage"] == 1.0