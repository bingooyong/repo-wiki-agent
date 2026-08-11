"""Read-only Reference Qoder baseline interface checks for Phase 41.1.

These tests NEVER mutate ``.qoder/repowiki/zh``. They skip when the external
fixture path is absent so CI/agents without a local clone remain green.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_INV_PATH = _REPO_ROOT / "tests" / "fixtures" / "qoder_release_interface_invariants.json"


def _reference_zh_root() -> Path:
    base = Path(
        os.environ.get(
            "REFERENCE_REPO_ROOT",
            "",
        )
    ).resolve()
    return (base / ".qoder" / "repowiki" / "zh").resolve()


ZH_ROOT = _reference_zh_root()

requires_reference_qoder_fixture = pytest.mark.skipif(
    not ZH_ROOT.is_dir(),
    reason="reference-repo Qoder baseline missing — set REFERENCE_REPO_ROOT or clone fixture",
)


def _load_invariants() -> dict:
    payload = json.loads(_INV_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


@pytest.fixture(scope="module")
def invariants() -> dict:
    return _load_invariants()


@pytest.fixture(scope="module")
def meta_payload() -> dict:
    mp = ZH_ROOT / "meta" / "repowiki-metadata.json"
    data = json.loads(mp.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


@requires_reference_qoder_fixture
class TestQoderZhReleaseLayoutPresence:
    def test_required_directories_and_meta_file_exist(self, invariants: dict) -> None:
        req = invariants["required_paths_relative_to_zh_root"]
        for rel in req["directories"]:
            assert (ZH_ROOT / rel).is_dir(), f"missing directory: {rel}"
        for rel in req["files"]:
            target = ZH_ROOT / rel
            assert target.is_file(), f"missing file: {rel}"

    def test_content_top_level_intersection_with_invariants(self, invariants: dict) -> None:
        expected_mins = invariants["content_top_level"]["minimal_directory_intersection"]
        content_root = ZH_ROOT / "content"
        dirs = {p.name for p in content_root.iterdir() if p.is_dir()}
        for name in expected_mins:
            assert name in dirs, f"missing expected top-level content dir {name}"
        tops = {p.name for p in content_root.iterdir() if p.is_file() and p.suffix == ".md"}
        for mdname in invariants["content_top_level"]["expected_top_level_markdown_basenames_any"]:
            assert mdname in tops, f"missing expected top-level markdown file {mdname}"

    def test_repowiki_metadata_has_required_shapes(
        self, invariants: dict, meta_payload: dict
    ) -> None:
        inv = invariants["meta_repowiki_metadata"]
        keys = sorted(meta_payload.keys())
        for rk in inv["required_top_level_keys"]:
            assert rk in meta_payload, f"missing meta key {rk}"
            assert meta_payload[rk] is not None

        wo = meta_payload.get("wiki_overview")
        assert isinstance(wo, dict), "wiki_overview must be dict"
        for nk in inv["wiki_overview_expected_keys_any"]:
            assert nk in wo

        wr = meta_payload.get("wiki_repo")
        assert isinstance(wr, dict), "wiki_repo must be dict"
        for nk in inv["wiki_repo_expected_keys_any"]:
            assert nk in wr

        # Collections must be populated for a sane fixture
        assert len(meta_payload.get("wiki_catalogs", [])) > 5
        assert len(meta_payload.get("wiki_items", [])) > 5


@requires_reference_qoder_fixture
class TestQoderZhMarkdownStructuralSignals:
    def test_sample_md_files_use_cite_and_mermaid_conventions(self, invariants: dict) -> None:
        conventions = invariants["content_markdown_conventions_observed_fixture"]
        cite_tag = conventions["cite_html_tag"]
        m_fence = conventions["mermaid_fence_marker"]
        toc = conventions["toc_heading_marker"]

        content_root = ZH_ROOT / "content"
        anchors = []
        anchors.append(next(content_root.rglob("*.md")))
        api = content_root / "API参考"
        assert api.is_dir(), "fixture must include API dir"
        anchors.append(next(api.rglob("*.md")))

        for path in anchors:
            text = path.read_text(encoding="utf-8", errors="replace")
            assert cite_tag in text
            assert m_fence in text
            assert toc in text


@requires_reference_qoder_fixture
class TestQoderFixtureReadOnly:
    """Stat-based guard: ingest path must remain read-only."""

    def test_metadata_not_mutated_after_reads(self, meta_payload: dict) -> None:
        mp = ZH_ROOT / "meta" / "repowiki-metadata.json"
        before = mp.stat()
        _ = mp.read_bytes()[:512]
        # exercise JSON parse twice
        json.loads(mp.read_text(encoding="utf-8"))
        after = mp.stat()
        assert before.st_mtime_ns == after.st_mtime_ns
        assert before.st_size == after.st_size
        assert meta_payload  # use fixture to silence unused-arg linters intent
