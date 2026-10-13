"""List-heavy pages must leave write/normalize below HARD dump and prose floors.

R11 (FastAPI RealWorld / MiniMax-M3): QODER_PAGE_DUMP 25 (listed 10) and
QODER_PROSE_TOO_LOW x6. Think dumps were already stripped (#63). Remaining
failures are list-heavy LLM pages plus page-contract injections (API grouping,
schema, cites) that `_ensure_minimum_prose_density` cannot repair (6-loop cap).

Do not pass by relaxing QODER_PAGE_DUMP / QODER_PROSE_TOO_LOW or 95% coverage.
"""

from __future__ import annotations

from pathlib import Path

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.generator.composer import ComposerContext
from repo_wiki.orchestration.service import RepoWikiService
from repo_wiki.planner.schema import WikiPagePlan, WikiTaxonomyCategory
from repo_wiki.verifier.qoder_strict_verifier import (
    QoderLikeSeverityThreshold,
    QoderLikeVerifierService,
)


def _service(tmp_path: Path) -> RepoWikiService:
    cfg = RepoWikiConfig()
    cfg.project.root = str(tmp_path)
    return RepoWikiService(cfg)


def _context(tmp_path: Path, **kwargs) -> ComposerContext:
    return ComposerContext(
        repository_name="conduit",
        primary_language="python",
        framework="fastapi",
        repository_root=str(tmp_path),
        **kwargs,
    )


def _dump_and_density(tmp_path: Path, filename: str, markdown: str):
    content_dir = tmp_path / "content"
    content_dir.mkdir(parents=True, exist_ok=True)
    (content_dir / filename).write_text(markdown, encoding="utf-8")
    verifier = QoderLikeVerifierService(tmp_path, strict=True)
    return verifier._check_qoder_page_dumps(), verifier._check_qoder_prose_density()


def test_list_heavy_llm_page_is_not_a_dump_after_write(tmp_path: Path) -> None:
    """LLM list dumps still contain the facts after write, without tripping PAGE_DUMP."""
    bullets = "\n".join(
        f"- `{i:02d}` core component `Component{i}` lives in "
        f"`app/services/mod{i}.py` and handles request {i}."
        for i in range(40)
    )
    raw = f"# 核心服务\n\n## 简介\n\n本页说明核心服务边界。\n\n## 组件\n\n{bullets}\n"
    page = WikiPagePlan(
        page_id="core-services",
        title="核心服务",
        category=WikiTaxonomyCategory.CORE_SERVICES,
        output_path="核心服务/核心服务.md",
    )
    written = _service(tmp_path)._enforce_qoder_page_contract(
        page=page,
        markdown=raw,
        binding=None,
        add_mermaid=False,
        composition_context=_context(tmp_path),
    )
    on_disk = tmp_path / "核心服务.md"
    on_disk.write_text(written, encoding="utf-8")
    disk_text = on_disk.read_text(encoding="utf-8")

    assert "Component12" in disk_text
    assert "app/services/mod12.py" in disk_text
    dump, density = _dump_and_density(tmp_path, "核心服务.md", disk_text)
    assert dump.status == "PASS", dump.message
    assert density.status == "PASS", density.message


def test_huge_list_dump_meets_prose_density_after_write(tmp_path: Path) -> None:
    """Six padding paragraphs cannot lift a long dump; write-floor must."""
    bullets = "\n".join(
        f"- Endpoint {i}: GET /api/v1/resource/{i} handler `h{i}` "
        f"in `app/api/routes/mod{i}.py` serializes the Conduit payload."
        for i in range(40)
    )
    raw = f"# API参考\n\n## 简介\n\n短说明。\n\n## 端点\n\n{bullets}\n"
    page = WikiPagePlan(
        page_id="api-reference",
        title="API参考",
        category=WikiTaxonomyCategory.API_REFERENCE,
        output_path="API参考/API参考.md",
    )
    endpoints = [
        {
            "method": "GET",
            "path": f"/api/items/{i}",
            "handler": f"h{i}",
            "file_path": f"app/api/r{i}.py",
            "line_number": i + 1,
            "response_type": "json",
        }
        for i in range(19)
    ]
    written = _service(tmp_path)._enforce_qoder_page_contract(
        page=page,
        markdown=raw,
        binding=None,
        add_mermaid=False,
        composition_context=_context(tmp_path, endpoints=endpoints),
    )
    dump, density = _dump_and_density(tmp_path, "API参考.md", written)
    assert "GET /api/items/3" in written
    assert "handler `h3`" in written
    assert dump.status == "PASS", dump.message
    assert density.status == "PASS", density.message
    verifier = QoderLikeVerifierService(tmp_path, strict=True)
    assert verifier._count_prose_chars(written) / max(len(written), 1) >= 0.30


def test_unprocessed_list_dump_still_fails_hard(tmp_path: Path) -> None:
    """Verifier still HARD-fails a raw dump that never went through write-floor."""
    content = "# API Reference\n\n" + "\n".join(
        f"- Endpoint {i}: /api/v1/resource/{i}" for i in range(20)
    )
    dump, density = _dump_and_density(tmp_path, "04-api.md", content)
    assert dump.status == "FAIL"
    assert dump.reason_code == "QODER_PAGE_DUMP"
    assert dump.gate_type.value == "HARD" or str(dump.gate_type).endswith("HARD")
    assert density.status == "FAIL"
    assert density.reason_code == "QODER_PROSE_TOO_LOW"


def test_qoder_page_dump_and_prose_gates_remain_hard() -> None:
    """Do not weaken QODER_PAGE_DUMP or QODER_PROSE_TOO_LOW to hide list dumps."""
    threshold = QoderLikeSeverityThreshold()
    assert threshold.is_blocking("QODER_PAGE_DUMP") is True
    assert threshold.is_blocking("QODER_PROSE_TOO_LOW") is True
    assert "QODER_PAGE_DUMP" in threshold.STRICT_HARD_CODES
    assert "QODER_PROSE_TOO_LOW" in threshold.STRICT_HARD_CODES
    assert QoderLikeVerifierService.MAX_LIST_RATIO == 0.6
    assert QoderLikeVerifierService.MIN_PROSE_DENSITY == 0.30
