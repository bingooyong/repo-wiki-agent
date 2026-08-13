"""Init-generated docs must not become the target repo's product identity."""

from __future__ import annotations

from pathlib import Path

from repo_wiki.generator.engine import GenerationEngine, NarrativeBuilder
from repo_wiki.generator.templates import TemplateRenderer
from repo_wiki.scanner.docs_scanner import scan_repository_docs_inventory

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PACKAGED_OVERVIEW = _REPO_ROOT / "repo_wiki" / "templates" / "docs" / "00-overview.md.j2"
_SOURCE_OVERVIEW = _REPO_ROOT / "templates" / "docs" / "00-overview.md.j2"

_INVENTED_IDENTITY_PHRASES = (
    "知识管理和文档生成平台",
    "知识管理平台",
    "RESTful API 接口（12 个端点）",
    "RESTful API 接口（",
)


def _source_inventory() -> dict:
    return {
        "services": [],
        "api_surfaces": [],
        "data_models": [],
        "frontend_callers": [],
        "deployment_assets": [],
        "tests": [],
    }


def test_init_overview_template_does_not_invent_product_identity() -> None:
    for template_path in (_PACKAGED_OVERVIEW, _SOURCE_OVERVIEW):
        text = template_path.read_text(encoding="utf-8")
        for phrase in _INVENTED_IDENTITY_PHRASES:
            assert phrase not in text, f"{template_path} must not hardcode {phrase!r}"


def test_init_stub_overview_is_not_used_as_product_identity(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "lib.py").write_text("def ping():\n    return True\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    stub = """# flask - 项目概览

flask 是一个基于 Python (unknown) 的知识管理和文档生成平台。
系统提供 RESTful API 接口（12 个端点）等核心能力。

知识管理平台面向开发者。
"""
    (tmp_path / "docs" / "00-overview.md").write_text(stub, encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "# Flask\n\nA lightweight WSGI web application framework.\n",
        encoding="utf-8",
    )

    inventory = scan_repository_docs_inventory(
        tmp_path, _source_inventory(), incremental=False, persist_cache=False
    )
    overview = next(doc for doc in inventory["documents"] if doc["path"] == "docs/00-overview.md")
    claims = " ".join(overview.get("conflicting_claims") or [])
    stale = " ".join(overview.get("stale_references") or [])
    assert overview["authority_level"] not in {"source_backed"}
    assert overview["authority_score"] < 0.5
    assert "知识管理" not in claims
    assert "12" not in stale

    builder = NarrativeBuilder(
        repo_name="flask",
        primary_language="python",
        framework="flask",
        modules=[
            {"name": "src", "path": "src", "domain": "unknown", "exports": ["ping"]},
            {"name": "docs", "path": "docs", "domain": "documentation", "exports": []},
            {
                "name": "examples",
                "path": "examples",
                "domain": "examples",
                "exports": ["index", "result"],
            },
        ],
        endpoints=[],
        models=[],
        commands={},
    )
    description = builder.build_project_description()
    capabilities = builder.build_core_capabilities()
    for phrase in ("知识管理和文档生成平台", "知识管理平台", "RESTful API 接口"):
        assert phrase not in description
        assert phrase not in capabilities

    engine = GenerationEngine(tmp_path, template_root=_REPO_ROOT / "templates")
    context = engine._build_core_context(
        {
            "repo_map": {
                "repository": {
                    "name": "flask",
                    "primary_language": "python",
                    "framework": "flask",
                },
                "commands": {},
            },
            "module_index": {
                "modules": [
                    {"name": "src", "path": "src", "domain": "unknown"},
                    {"name": "docs", "path": "docs", "domain": "documentation"},
                ]
            },
            "api_index": {"endpoints": []},
            "data_models": {"models": []},
            "graph": {"modules": {}},
        }
    )
    blob = " ".join(str(context.get(key, "")) for key in context)
    assert "知识管理和文档生成平台" not in blob
    assert "RESTful API 接口（12 个端点）" not in blob


def test_rendered_init_overview_is_marked_as_placeholder(tmp_path: Path) -> None:
    renderer = TemplateRenderer(_REPO_ROOT / "repo_wiki" / "templates")
    content = renderer.render(
        "docs/00-overview.md.j2",
        {
            "repository_name": "flask",
            "primary_cite": "<cite>src/lib.py:1</cite>",
            "project_description": "Placeholder description pending source-backed identity.",
            "project_positioning": "Placeholder positioning.",
            "architecture_description": "Placeholder architecture.",
            "core_problem": "Placeholder problem statement.",
            "core_capabilities": "Placeholder capabilities.",
            "environment_requirements": "Python 3.11+",
            "startup_commands": "See README.",
            "reading_navigation": "Start with the README.",
            "repository_root": str(tmp_path),
            "primary_language": "python",
            "framework": "flask",
            "module_count": "1",
            "endpoint_count": "0",
            "model_count": "0",
            "domain_groups_markdown": "",
        },
    )
    assert "repo-wiki-init-stub" in content
    for phrase in _INVENTED_IDENTITY_PHRASES:
        assert phrase not in content


def test_init_stub_section_docs_are_not_product_identity_claims(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "lib.py").write_text("def ping():\n    return True\n", encoding="utf-8")
    (tmp_path / "docs" / "sections" / "api").mkdir(parents=True)
    (tmp_path / "docs" / "sections" / "services").mkdir(parents=True)
    stub = """# API Reference and Contracts

<!-- repo-wiki-init-stub -->

本节涵盖 core-platform 等 3 个模块的内容。
系统提供 api-gateway 与核心平台基础设施。
知识管理和文档生成平台面向开发者。
"""
    (tmp_path / "docs" / "sections" / "api" / "index.md").write_text(stub, encoding="utf-8")
    (tmp_path / "docs" / "sections" / "services" / "index.md").write_text(
        "# Core Services\n\n<!-- repo-wiki-init-stub -->\n\ncore-platform api-gateway\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text(
        "# Conduit\n\nRealWorld FastAPI example app for users and articles.\n",
        encoding="utf-8",
    )

    inventory = scan_repository_docs_inventory(
        tmp_path, _source_inventory(), incremental=False, persist_cache=False
    )
    section_docs = [
        doc
        for doc in inventory["documents"]
        if str(doc.get("path", "")).startswith("docs/sections/")
    ]
    assert section_docs
    for doc in section_docs:
        claims = " ".join(doc.get("conflicting_claims") or [])
        stale = " ".join(doc.get("stale_references") or [])
        assert doc["authority_level"] not in {"source_backed"}
        assert doc["authority_score"] < 0.5
        assert "知识管理" not in claims
        assert "api-gateway" not in claims
        assert "core-platform" not in claims
        assert "知识管理" not in stale
        assert "api-gateway" not in stale
        assert "core-platform" not in stale
