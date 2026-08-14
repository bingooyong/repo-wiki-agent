"""Product identity must come from README, not init stubs or eval notes."""

from __future__ import annotations

from pathlib import Path

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.evidence.ranking import rank_evidence_for_page
from repo_wiki.generator.engine import GenerationEngine
from repo_wiki.orchestration.service import RepoWikiService
from repo_wiki.planner.identity import resolve_repository_identity
from repo_wiki.planner.schema import SourceRequirement, WikiPagePlan, WikiTaxonomyCategory
from repo_wiki.scanner.docs_scanner import scan_repository_docs_inventory

_REPO_ROOT = Path(__file__).resolve().parents[1]

_POLLUTION_PHRASES = (
    "知识管理平台",
    "知识管理和文档生成平台",
    "api-gateway",
    "core-platform",
    "repo-wiki-init-stub",
)
_PRODUCT_MARKERS = ("Conduit", "RealWorld")


def _source_inventory() -> dict:
    return {
        "services": [],
        "api_surfaces": [],
        "data_models": [],
        "frontend_callers": [],
        "deployment_assets": [],
        "tests": [],
    }


def _write_pollution_docs(root: Path) -> None:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "00-overview.md").write_text(
        """# flask - 项目概览

<!-- repo-wiki-init-stub -->

flask 是一个基于 Python (unknown) 的知识管理平台。
系统提供 api-gateway 与 core-platform 等核心能力。
""",
        encoding="utf-8",
    )
    (root / "AGENTS.md").write_text(
        """# AGENTS

This repository is a 知识管理平台 with api-gateway and core-platform.
Conduit is mentioned here only as eval pollution.
""",
        encoding="utf-8",
    )
    (root / "round3-report.md").write_text(
        """# Round 3 report

Eval notes: the wiki still looks like a 知识管理平台 / api-gateway.
""",
        encoding="utf-8",
    )
    eval_dir = root / ".repo-agent-eval" / "repowiki" / "zh"
    eval_dir.mkdir(parents=True, exist_ok=True)
    (eval_dir / "notes.md").write_text(
        "# Eval dump\n\n知识管理平台 api-gateway core-platform\n",
        encoding="utf-8",
    )


def _write_conduit_readme_rst(root: Path) -> None:
    (root / "README.rst").write_text(
        """
===============================
Conduit RealWorld API
===============================

Conduit is a RealWorld example API for users, articles, comments, and tags.
This FastAPI implementation follows the RealWorld spec rather than a
knowledge-management or documentation platform.
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _write_realworld_badge_readme_rst(root: Path, *, include_product_prose: bool) -> None:
    """Shape like nsidnev/fastapi-realworld-example-app: substitutions + badge field lists."""
    prose = ""
    if include_product_prose:
        prose = (
            "\n**NOTE**: This repository is not actively maintained because this "
            "example is quite complete and does its primary goal - passing Conduit "
            "testsuite.\n"
            "\n"
            "This codebase follows the RealWorld spec from gothinkster rather than "
            "a knowledge-management platform.\n"
        )
    (root / "README.rst").write_text(
        f"""
.. |build| image:: https://github.com/example/fastapi-realworld-example-app/workflows/Tests/badge.svg
    :target: https://github.com/example/fastapi-realworld-example-app
    :alt: Build status

.. image:: https://github.com/example/fastapi-realworld-example-app/workflows/API%20spec/badge.svg
    :target: https://github.com/example/fastapi-realworld-example-app

.. image:: https://codecov.io/gh/example/fastapi-realworld-example-app/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/example/fastapi-realworld-example-app

|build|

----------
{prose}
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _write_realworld_pyproject(root: Path, *, poetry_table: bool = False) -> None:
    table = "[tool.poetry]" if poetry_table else "[project]"
    (root / "pyproject.toml").write_text(
        f"""
{table}
name = "fastapi-realworld-example-app"
version = "0.0.0"
description = "Backend logic implementation for https://github.com/gothinkster/realworld with awesome FastAPI"
""",
        encoding="utf-8",
    )


def _assert_identity_is_realworld_product(identity: object) -> None:
    description = getattr(identity, "description", None) or ""
    display = getattr(identity, "display_name", None) or ""
    blob = f"{description} {display}"
    assert ":target:" not in blob, blob
    assert "知识管理" not in blob, blob
    assert "repo-wiki-init-stub" not in blob, blob
    assert any(
        marker in description for marker in ("Conduit", "RealWorld", "realworld", "gothinkster")
    ), description


def _write_conduit_fixture(root: Path) -> None:
    (root / "app").mkdir()
    (root / "app" / "main.py").write_text(
        "from fastapi import FastAPI\n\napp = FastAPI()\n",
        encoding="utf-8",
    )
    _write_conduit_readme_rst(root)
    _write_pollution_docs(root)


def _assert_product_not_pollution(text: str) -> None:
    blob = text or ""
    assert any(marker in blob for marker in _PRODUCT_MARKERS), blob
    for phrase in _POLLUTION_PHRASES:
        assert phrase not in blob, f"pollution {phrase!r} leaked into product identity: {blob}"


def test_identity_prefers_readme_rst_over_init_stub_agents_and_eval_report(
    tmp_path: Path,
) -> None:
    _write_conduit_fixture(tmp_path)

    identity = resolve_repository_identity(tmp_path)
    blob = " ".join(
        part for part in (identity.name, identity.display_name, identity.description or "") if part
    )
    _assert_product_not_pollution(blob)


def test_identity_skips_rst_badge_junk_and_uses_conduit_prose(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text(
        "from fastapi import FastAPI\n\napp = FastAPI()\n",
        encoding="utf-8",
    )
    _write_realworld_badge_readme_rst(tmp_path, include_product_prose=True)
    _write_realworld_pyproject(tmp_path)
    _write_pollution_docs(tmp_path)

    identity = resolve_repository_identity(tmp_path)
    assert identity.name == "fastapi-realworld-example-app"
    _assert_identity_is_realworld_product(identity)


def test_identity_uses_pyproject_description_when_readme_has_no_product_sentence(
    tmp_path: Path,
) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text(
        "from fastapi import FastAPI\n\napp = FastAPI()\n",
        encoding="utf-8",
    )
    _write_realworld_badge_readme_rst(tmp_path, include_product_prose=False)
    _write_realworld_pyproject(tmp_path, poetry_table=True)
    _write_pollution_docs(tmp_path)

    identity = resolve_repository_identity(tmp_path)
    assert identity.name == "fastapi-realworld-example-app"
    _assert_identity_is_realworld_product(identity)
    assert "gothinkster/realworld" in (identity.description or "")


def test_docs_inventory_does_not_treat_agents_or_eval_reports_as_product_source_docs(
    tmp_path: Path,
) -> None:
    _write_conduit_fixture(tmp_path)

    inventory = scan_repository_docs_inventory(
        tmp_path, _source_inventory(), incremental=False, persist_cache=False
    )
    documents = inventory["documents"]
    by_path = {doc["path"]: doc for doc in documents}

    assert "README.rst" in by_path
    readme = by_path["README.rst"]
    assert readme["authority_level"] == "source_backed"
    assert readme["authority_score"] >= 0.5

    for banned in ("AGENTS.md", "round3-report.md", ".repo-agent-eval/repowiki/zh/notes.md"):
        assert banned not in by_path, f"{banned} must not be a product source-doc"

    overview = by_path["docs/00-overview.md"]
    assert overview["authority_level"] not in {"source_backed"}
    assert overview["authority_score"] < 0.5
    claims = " ".join(overview.get("conflicting_claims") or [])
    assert "知识管理" not in claims
    assert "api-gateway" not in claims


def test_evidence_spans_do_not_cite_agents_eval_reports_or_init_stubs(
    tmp_path: Path,
) -> None:
    _write_conduit_fixture(tmp_path)
    cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
    spans = RepoWikiService(cfg)._extract_evidence_spans()
    paths = {span.file_path.replace("\\", "/") for span in spans}

    assert not any(path == "AGENTS.md" or path.endswith("/AGENTS.md") for path in paths)
    assert not any("round3-report.md" in path for path in paths)
    assert not any(path.startswith(".repo-agent-eval/") for path in paths)
    assert "docs/00-overview.md" not in paths
    assert any(path.lower().startswith("readme") for path in paths)

    page = WikiPagePlan(
        page_id="project-overview",
        title="项目概述",
        category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
        parent=None,
        output_path="docs/pages/overview/project-overview.md",
        source_requirements=SourceRequirement(),
    )
    ranked = rank_evidence_for_page(page, spans)
    ranked_paths = {candidate.span.file_path.replace("\\", "/") for candidate in ranked}
    assert "AGENTS.md" not in ranked_paths
    assert "round3-report.md" not in ranked_paths
    assert "docs/00-overview.md" not in ranked_paths


def test_overview_context_uses_readme_product_identity_not_stub(tmp_path: Path) -> None:
    _write_conduit_fixture(tmp_path)
    engine = GenerationEngine(tmp_path, template_root=_REPO_ROOT / "templates")
    context = engine._build_core_context(
        {
            "repo_map": {
                "repository": {
                    "name": tmp_path.name,
                    "primary_language": "python",
                    "framework": "fastapi",
                },
                "commands": {},
            },
            "module_index": {
                "modules": [
                    {"name": "app", "path": "app", "domain": "api-gateway"},
                    {"name": "core", "path": "core", "domain": "core-platform"},
                ]
            },
            "api_index": {"endpoints": []},
            "data_models": {"models": []},
            "graph": {"modules": {}},
        }
    )
    identity_blob = " ".join(
        str(context.get(key, ""))
        for key in (
            "project_description",
            "project_positioning",
            "core_problem",
            "core_capabilities",
        )
    )
    _assert_product_not_pollution(identity_blob)


def test_does_not_invent_product_name_when_readme_has_none(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "lib.py").write_text("def ping():\n    return True\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "# README\n\nLocal notes for contributors.\n",
        encoding="utf-8",
    )
    _write_pollution_docs(tmp_path)

    identity = resolve_repository_identity(tmp_path)
    blob = " ".join(
        part for part in (identity.name, identity.display_name, identity.description or "") if part
    )
    for phrase in ("知识管理平台", "知识管理和文档生成平台", "api-gateway", "core-platform"):
        assert phrase not in blob
    assert "Conduit" not in blob
    assert identity.name != "知识管理平台"

    engine = GenerationEngine(tmp_path, template_root=_REPO_ROOT / "templates")
    context = engine._build_core_context(
        {
            "repo_map": {
                "repository": {
                    "name": tmp_path.name,
                    "primary_language": "python",
                    "framework": "unknown",
                },
                "commands": {},
            },
            "module_index": {
                "modules": [
                    {"name": "src", "path": "src", "domain": "unknown"},
                ]
            },
            "api_index": {"endpoints": []},
            "data_models": {"models": []},
            "graph": {"modules": {}},
        }
    )
    description = str(context.get("project_description", ""))
    assert "知识管理平台" not in description
    assert "知识管理和文档生成平台" not in description
