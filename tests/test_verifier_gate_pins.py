"""Pinned verifier thresholds. Any future loosening must show up as a test diff."""

from __future__ import annotations

from repo_wiki.verifier.handbook import (
    _EVIDENCE_META_TALK_RE,
    MIN_HANDBOOK_BODY_CHARS,
    architecture_required_packages,
    contains_evidence_meta_talk,
    has_architecture_core_citation,
    overview_identity_satisfied,
)
from repo_wiki.verifier.qoder_strict_verifier import (
    QoderLikeSeverityThreshold,
    QoderLikeVerifierService,
)
from repo_wiki.verifier.source_evidence import MIN_HANDBOOK_CITATIONS


def test_pinned_verifier_gate_thresholds() -> None:
    pins = {
        "min_handbook_body_chars": MIN_HANDBOOK_BODY_CHARS,
        "min_prose_density": QoderLikeVerifierService.MIN_PROSE_DENSITY,
        "max_list_ratio": QoderLikeVerifierService.MAX_LIST_RATIO,
        "min_mermaid_coverage": QoderLikeVerifierService.MIN_MERMAID_COVERAGE,
        "min_toc_coverage": QoderLikeVerifierService.MIN_TOC_COVERAGE,
        "min_file_line_coverage": QoderLikeVerifierService.MIN_FILE_LINE_COVERAGE,
        "min_handbook_citations": MIN_HANDBOOK_CITATIONS,
        "claim_citation_floor": 0.95,
        "evidence_meta_talk_pattern": _EVIDENCE_META_TALK_RE.pattern,
        "degraded_tokens": ("fallback", "degraded"),
        "architecture_core_requires_all": True,
        "overview_identity_readme_words": False,
        "hard_codes": sorted(QoderLikeSeverityThreshold.STRICT_HARD_CODES),
    }
    assert pins == {
        "min_handbook_body_chars": 800,
        "min_prose_density": 0.30,
        "max_list_ratio": 0.6,
        "min_mermaid_coverage": 0.3,
        "min_toc_coverage": 0.8,
        "min_file_line_coverage": 0.7,
        "min_handbook_citations": 20,
        "claim_citation_floor": 0.95,
        "evidence_meta_talk_pattern": _EVIDENCE_META_TALK_RE.pattern,
        "degraded_tokens": ("fallback", "degraded"),
        "architecture_core_requires_all": True,
        "overview_identity_readme_words": False,
        "hard_codes": sorted(QoderLikeSeverityThreshold.STRICT_HARD_CODES),
    }
    assert "证据片段" in pins["evidence_meta_talk_pattern"]
    assert "证据范围" in pins["evidence_meta_talk_pattern"]
    assert "当前证据" in pins["evidence_meta_talk_pattern"]
    assert "提供的证据" in pins["evidence_meta_talk_pattern"]
    assert "用户当前没有指定" in pins["evidence_meta_talk_pattern"]
    assert "QODER_PAGE_QUALITY_STATE_DEGRADED" in pins["hard_codes"]
    assert "QODER_HANDBOOK_CODE_INTEGRITY" in pins["hard_codes"]
    assert "QODER_HANDBOOK_DOC_CODE_MISMATCH" in pins["hard_codes"]


def test_overview_identity_ignores_random_readme_words(tmp_path) -> None:
    (tmp_path / "README.md").write_text(
        "# Sample Service\n\nQuickstart image backend note documentation.\n",
        encoding="utf-8",
    )
    page = "# 项目概述\n\nThis image backend documentation is ready.\n"
    assert overview_identity_satisfied(page, tmp_path) is False
    assert overview_identity_satisfied("# 项目概述\n\nSample Service 面向开发者。\n", tmp_path)


def test_architecture_required_packages_are_all_cores(tmp_path) -> None:
    (tmp_path / "internal" / "services").mkdir(parents=True)
    (tmp_path / "internal" / "repository").mkdir(parents=True)
    (tmp_path / "app" / "api" / "routes").mkdir(parents=True)
    (tmp_path / "app" / "api" / "routes" / "users.py").write_text(
        "from fastapi import APIRouter\nrouter = APIRouter()\n@router.get('/x')\ndef x():\n    return 1\n",
        encoding="utf-8",
    )
    required = architecture_required_packages(tmp_path)
    cores_needed = [rel for rel in required if rel.startswith("app/")]
    assert cores_needed
    assert required == architecture_required_packages(tmp_path)
    partial = "# 架构\n" + "".join(f"<cite>{rel}/x.py:1-2</cite>\n" for rel in required[:-1])
    assert has_architecture_core_citation(partial, tmp_path) is False
    complete = partial + f"<cite>{required[-1]}/x.py:1-2</cite>\n"
    assert has_architecture_core_citation(complete, tmp_path) is True


def test_twenty_five_r_meta_talk_sentences_fail() -> None:
    assert contains_evidence_meta_talk("提供的证据未覆盖中间件")
    assert contains_evidence_meta_talk("证据范围限定于认证依赖与路由装饰器。")
    assert contains_evidence_meta_talk("当前证据集中在迁移 revision 的 upgrade。")
    assert contains_evidence_meta_talk("虽然用户当前没有指定模块，仍按仓库扫描结果写。")
