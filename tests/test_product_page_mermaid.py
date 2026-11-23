"""API and data-model product pages must emit mermaid the HARD gates require.

R9 (FastAPI RealWorld): after #64 dropped empty taxonomy pages, verify still
HARD-fails ``QODER_API_MERMAID_MISSING`` on 6 API pages and
``QODER_DATA_MODEL_ER_MERMAID_MISSING`` on 3 data-model pages.
Aggregation itself PASS 9/9. The pages exist; they lack the mermaid block.

Do not pass by skipping those checks or shrinking the required set.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.generator.composer import (
    ComposerContext,
    build_composer_input,
    create_composer,
)
from repo_wiki.llm.providers import create_mock_provider
from repo_wiki.orchestration.service import RepoWikiService
from repo_wiki.planner.schema import (
    GenerationMode,
    SourceRequirement,
    WikiPagePlan,
    WikiPlanManifest,
    WikiTaxonomyCategory,
)
from repo_wiki.scanner.repository_scanner import RepositoryScanner
from repo_wiki.verifier.qoder_strict_verifier import (
    QoderLikeSeverityThreshold,
    QoderLikeVerifierService,
)

_STUB_PROSE = (
    "This service mounts GET /items and accepts a Pydantic Item body. "
    "Item belongs to an owner via owner_id and references the catalog record."
)


def _write_fastapi_app(root: Path) -> None:
    """Fixture FastAPI app: one mounted route and one Pydantic model."""
    app_dir = root / "app"
    app_dir.mkdir()
    (app_dir / "__init__.py").write_text("", encoding="utf-8")
    (app_dir / "main.py").write_text(
        """
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class Item(BaseModel):
    name: str
    owner_id: str


@app.get("/items")
def list_items():
    return []


@app.post("/items")
def create_item(item: Item):
    return item
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (root / "requirements.txt").write_text("fastapi\npydantic\n", encoding="utf-8")
    (root / "README.md").write_text("# items-api\n\nA tiny FastAPI catalog.\n", encoding="utf-8")


def _scan(root: Path):
    cfg = RepoWikiConfig.model_validate(
        {
            "project": {"root": str(root), "include": ["**/*"]},
            "llm": {"force_mock_llm": True},
        }
    )
    return cfg, RepositoryScanner(cfg).scan()


def _stub_heading_prose(title: str) -> str:
    return f"# {title}\n\n{_STUB_PROSE}\n"


def _page(
    page_id: str,
    title: str,
    category: WikiTaxonomyCategory,
    output_path: str,
    *,
    endpoints: list[str] | None = None,
    data_models: list[str] | None = None,
) -> WikiPagePlan:
    return WikiPagePlan(
        page_id=page_id,
        title=title,
        category=category,
        output_path=output_path,
        generation_mode=GenerationMode.LLM_ASSISTED,
        source_requirements=SourceRequirement(
            endpoints=endpoints or [],
            data_models=data_models or [],
        ),
    )


def _compose_product_pages(root: Path) -> tuple[str, str, str]:
    """Compose overview/API/data-model pages with a no-mermaid LLM stub.

    Page order matches generate: overview first (may take the 30% mermaid
    quota), then API and data-model product pages that currently miss it.
    """
    cfg, snapshot = _scan(root)
    assert snapshot.endpoints, "fixture must expose a mounted FastAPI route"
    assert snapshot.data_models, "fixture must expose a Pydantic model"

    overview = _page(
        "project-overview",
        "项目概述",
        WikiTaxonomyCategory.PROJECT_OVERVIEW,
        "docs/pages/overview/project-overview.md",
    )
    api = _page(
        "items-service-api",
        "Items Service API",
        WikiTaxonomyCategory.API_REFERENCE,
        "docs/pages/api/items-service-api.md",
        endpoints=["GET /items", "POST /items"],
    )
    model = _page(
        "item-data-model",
        "Item 数据模型",
        WikiTaxonomyCategory.DATA_MODELS,
        "docs/pages/data-models/item-data-model.md",
        data_models=["Item"],
    )
    plan = WikiPlanManifest(pages=[overview, api, model])
    service = RepoWikiService(cfg)
    composition = asyncio.run(
        service._compose_qoder_like_pages(
            plan=plan,
            evidence_bindings={},
            snapshot=snapshot,
            output_dir=root / "compose-out",
        )
    )
    pages = {source: markdown for source, markdown in composition["pages"]}
    return (
        pages[overview.output_path],
        pages[api.output_path],
        pages[model.output_path],
    )


def _write_content_tree(
    root: Path,
    *,
    overview: str,
    api: str,
    data_model: str,
) -> None:
    content = root / "content"
    (content / "项目概述").mkdir(parents=True)
    (content / "API参考").mkdir(parents=True)
    (content / "数据模型").mkdir(parents=True)
    (content / "项目概述" / "00-overview.md").write_text(overview, encoding="utf-8")
    (content / "API参考" / "items-service-api.md").write_text(api, encoding="utf-8")
    (content / "数据模型" / "item-data-model.md").write_text(data_model, encoding="utf-8")


def _mermaid_checks(root: Path) -> tuple[object, object]:
    verifier = QoderLikeVerifierService(root, strict=True)
    return (
        verifier._check_qoder_api_mermaid_presence(),
        verifier._check_qoder_data_model_er_mermaid_presence(),
    )


def test_composed_api_and_data_model_pages_emit_qoder_mermaid(tmp_path: Path) -> None:
    """After compose/normalize, product pages on disk pass the existing mermaid HARD checks."""
    _write_fastapi_app(tmp_path)
    overview, api, data_model = _compose_product_pages(tmp_path)
    _write_content_tree(tmp_path, overview=overview, api=api, data_model=data_model)

    assert "```mermaid" in api or ":::mermaid" in api
    assert "```mermaid" in data_model
    assert "erdiagram" in data_model.lower()

    api_check, er_check = _mermaid_checks(tmp_path)
    assert api_check.status == "PASS", api_check.message
    assert api_check.reason_code != "QODER_API_MERMAID_MISSING"
    assert int(api_check.details.get("checked_pages") or 0) >= 1
    assert er_check.status == "PASS", er_check.message
    assert er_check.reason_code != "QODER_DATA_MODEL_ER_MERMAID_MISSING"
    assert int(er_check.details.get("checked_pages") or 0) >= 1


def test_overview_page_is_not_forced_to_have_api_mermaid(tmp_path: Path) -> None:
    """A non-API overview page must not be required to carry API mermaid."""
    _write_fastapi_app(tmp_path)
    overview, api, data_model = _compose_product_pages(tmp_path)
    _write_content_tree(tmp_path, overview=overview, api=api, data_model=data_model)

    assert "UNRESOLVED_API_FLOW" not in overview
    api_check, _ = _mermaid_checks(tmp_path)
    offenders = list((api_check.details or {}).get("pages") or [])
    assert not any("overview" in str(path).lower() or "概述" in str(path) for path in offenders)


def test_stub_llm_without_mermaid_still_gets_product_diagrams(tmp_path: Path) -> None:
    """Composer/normalize must inject mermaid when the LLM returns heading+prose only."""
    _write_fastapi_app(tmp_path)
    cfg, snapshot = _scan(tmp_path)
    context = ComposerContext(
        repository_name=snapshot.repository.name,
        primary_language=snapshot.repository.language,
        framework=snapshot.repository.framework,
        repository_root=str(tmp_path),
        modules=[module.model_dump() for module in snapshot.modules],
        endpoints=[endpoint.model_dump() for endpoint in snapshot.endpoints],
        models=[model.model_dump() for model in snapshot.data_models],
        commands=snapshot.commands,
    )
    provider = create_mock_provider(response_content=_stub_heading_prose("Items Service API"))
    composer = create_composer(provider=provider, workspace_root=tmp_path)
    api_page = _page(
        "items-service-api",
        "Items Service API",
        WikiTaxonomyCategory.API_REFERENCE,
        "docs/pages/api/items-service-api.md",
        endpoints=["GET /items"],
    )
    model_page = _page(
        "item-data-model",
        "Item 数据模型",
        WikiTaxonomyCategory.DATA_MODELS,
        "docs/pages/data-models/item-data-model.md",
        data_models=["Item"],
    )
    overview_page = _page(
        "project-overview",
        "项目概述",
        WikiTaxonomyCategory.PROJECT_OVERVIEW,
        "docs/pages/overview/project-overview.md",
    )

    api_raw = asyncio.run(
        composer.compose_page(build_composer_input(api_page, None, context))
    ).markdown
    model_raw = asyncio.run(
        composer.compose_page(
            build_composer_input(
                model_page,
                None,
                context,
            )
        )
    ).markdown
    overview_raw = asyncio.run(
        composer.compose_page(build_composer_input(overview_page, None, context))
    ).markdown
    assert "```mermaid" not in api_raw
    assert "```mermaid" not in model_raw

    service = RepoWikiService(cfg)
    # Generate currently skips mermaid for most API/data-model pages (broken quota
    # / category match). Product pages must still emit the HARD-required diagrams.
    api_written = service._enforce_qoder_page_contract(
        page=api_page,
        markdown=api_raw,
        binding=None,
        add_mermaid=False,
        composition_context=context,
    )
    model_written = service._enforce_qoder_page_contract(
        page=model_page,
        markdown=model_raw,
        binding=None,
        add_mermaid=False,
        composition_context=context,
    )
    overview_written = service._enforce_qoder_page_contract(
        page=overview_page,
        markdown=overview_raw,
        binding=None,
        add_mermaid=False,
        composition_context=context,
    )

    _write_content_tree(
        tmp_path,
        overview=overview_written,
        api=api_written,
        data_model=model_written,
    )
    api_check, er_check = _mermaid_checks(tmp_path)
    assert api_check.status == "PASS", api_check.message
    assert er_check.status == "PASS", er_check.message
    assert "UNRESOLVED_API_FLOW" not in overview_written


def test_api_and_er_mermaid_gates_remain_hard() -> None:
    """Do not relax QODER_API_MERMAID_MISSING / QODER_DATA_MODEL_ER_MERMAID_MISSING."""
    threshold = QoderLikeSeverityThreshold()
    assert threshold.is_blocking("QODER_API_MERMAID_MISSING") is True
    assert threshold.is_blocking("QODER_DATA_MODEL_ER_MERMAID_MISSING") is True
    assert "QODER_API_MERMAID_MISSING" in threshold.STRICT_HARD_CODES
    assert "QODER_DATA_MODEL_ER_MERMAID_MISSING" in threshold.STRICT_HARD_CODES
