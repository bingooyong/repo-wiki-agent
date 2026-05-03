"""Golden fixture suite integration tests (Task 29.4).

Covers planner (mock LLM), evidence persistence, composer (mock LLM), strict qoder verifier,
and comparator path repair — all without live API keys.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from repo_wiki.core.contracts import (
    DataModel,
    Endpoint,
    Module,
    RepositoryInfo,
    RepositorySnapshot,
    RepositoryStats,
)
from repo_wiki.generator.composer import ComposerContext, build_composer_input, create_composer
from repo_wiki.orchestration.runtime_store import EvidenceSpanRecord, SQLiteRuntimeStore
from repo_wiki.planner.identity import RepositoryIdentity
from repo_wiki.planner.llm_planner import LLMAssistedPlanner
from repo_wiki.planner.llm_planner import MockLLMProvider as PlannerMockLLM
from repo_wiki.planner.rule_first import RuleFirstPlanner
from repo_wiki.planner.schema import GenerationMode, WikiPagePlan, WikiTaxonomyCategory
from repo_wiki.test.golden_fixtures import (
    GOLDEN_FIXTURES,
    STRICT_QODER_TREE,
    GoldenFixtureBuilder,
    build_strict_qoder_mock_pages,
    create_golden_fixtures,
    get_fixture,
)
from repo_wiki.verifier.qoder_comparator_paths import PathModelRepair
from repo_wiki.verifier.qoder_parity_metrics import create_parity_report
from repo_wiki.verifier.qoder_strict_verifier import QoderLikeVerifierService

FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures" / "golden"
SAMPLE_REPO = FIXTURES_ROOT / "sample_repo"


def _tiny_snapshot() -> RepositorySnapshot:
    """Minimal snapshot for planner smoke tests (no filesystem scan)."""
    modules = [
        Module(
            name="golden_svc",
            path="golden_svc",
            responsibility="Golden CI module",
            exports=["run"],
            depends_on=[],
            depended_by=[],
            interfaces=[],
            data_models=["Row"],
            owner="ci",
            doc_path="docs/modules/golden.md",
            domain="fixture",
            service_family="python-backend",
        ),
    ]
    endpoints = [
        Endpoint(
            method="GET",
            path="/health",
            module="golden_svc",
            handler="health",
            file_path="golden_svc/app.py",
        ),
    ]
    data_models = [
        DataModel(
            name="Row",
            type="python_class",
            module="golden_svc",
            file_path="golden_svc/models.py",
        ),
    ]
    repository = RepositoryInfo(
        name="golden-repo",
        root_path=str(SAMPLE_REPO),
        language="python",
        framework="fastapi",
        package_manager="pip",
        entry_points=["uvicorn golden_svc.app:app"],
        key_directories=["golden_svc", "tests"],
    )
    stats = RepositoryStats(
        total_files=20,
        scanned_files=15,
        skipped_files=5,
        module_count=1,
        endpoint_count=1,
        data_model_count=1,
    )
    return RepositorySnapshot(
        repository=repository,
        modules=modules,
        endpoints=endpoints,
        data_models=data_models,
        commands={"start": "uvicorn golden_svc.app:app"},
        stats=stats,
    )


class TestGoldenFixtureLayout:
    """Checked-in sample_repo layout."""

    def test_sample_repo_multilang_files_exist(self):
        assert (SAMPLE_REPO / "README.md").exists()
        assert (SAMPLE_REPO / "python" / "app.py").exists()
        assert (SAMPLE_REPO / "java" / "com" / "example" / "App.java").exists()
        assert (SAMPLE_REPO / "ts" / "index.ts").exists()
        assert (SAMPLE_REPO / "sql" / "schema.sql").exists()

    def test_strict_tree_matches_mock_slugs(self):
        slugs = {s for docs in STRICT_QODER_TREE.values() for s in docs}
        mock_slugs = set(build_strict_qoder_mock_pages("Python").keys())
        assert slugs == mock_slugs


class TestGoldenStrictVerifier:
    """qoder_strict_verifier.py gates on built fixtures (offline)."""

    @pytest.mark.parametrize("fixture_name", list(GOLDEN_FIXTURES.keys()))
    def test_all_language_fixtures_pass_strict_verifier(self, tmp_path, fixture_name):
        builder = GoldenFixtureBuilder(tmp_path)
        fixture = get_fixture(fixture_name)
        assert fixture is not None
        root = builder.build_fixture(fixture)
        svc = QoderLikeVerifierService(root, strict=True)
        report = svc.verify(ci=True)
        assert report["grade"] == "PASS", (fixture_name, report)


class TestGoldenParityMetrics:
    """Task 29.1 metric schema extractor on golden trees."""

    def test_parity_report_on_python_fixture(self, tmp_path):
        builder = GoldenFixtureBuilder(tmp_path)
        root = builder.build_fixture(get_fixture("python-microservice"))
        report = create_parity_report(root)
        assert report.summary.get("overall_score", 0) > 0


class TestGoldenComparator:
    """Task 29.2 path comparator."""

    def test_comparison_pairs_for_two_trees(self, tmp_path):
        left_b = GoldenFixtureBuilder(tmp_path / "a")
        right_b = GoldenFixtureBuilder(tmp_path / "b")
        left_root = left_b.build_fixture(get_fixture("python-microservice"))
        right_root = right_b.build_fixture(get_fixture("typescript-react"))
        repair = PathModelRepair()
        pairs = repair.build_comparison_pairs(left_root, right_root)
        assert len(pairs) >= 5
        # Same taxonomy-relative paths should appear in both targets
        norms = {p[0] for p in pairs}
        assert any("00-overview" in n for n in norms)


class TestGoldenPlannerWithMockLlm:
    """Planner stack without remote keys."""

    def test_rule_first_then_llm_assisted_expand(self):
        identity = RepositoryIdentity(
            name="golden-repo",
            display_name="Golden",
            root_path=str(SAMPLE_REPO),
            language="python",
            framework="fastapi",
        )
        snapshot = _tiny_snapshot()
        base = RuleFirstPlanner(identity, snapshot).generate()
        expanded = LLMAssistedPlanner(base, PlannerMockLLM()).expand_plan()
        assert expanded.page_count() >= base.page_count()


class TestGoldenEvidenceStore:
    """Evidence spans — SQLite runtime store."""

    def test_evidence_span_roundtrip(self, tmp_path):
        db = tmp_path / "golden_evidence.sqlite3"
        store = SQLiteRuntimeStore(db)
        record = EvidenceSpanRecord(
            digest="goldenfixture001",
            file_path="golden_svc/app.py",
            line_start=1,
            line_end=12,
            language="python",
            symbol="handler",
            span_text="def handler(): ...",
            confidence=1.0,
        )
        eid = store.upsert_evidence_span(record)
        assert eid > 0
        loaded = store.get_evidence_span(eid)
        assert loaded is not None
        assert loaded["symbol"] == "handler"


class TestGoldenComposerMockLlm:
    """Composer uses bundled mock provider — no API keys."""

    @pytest.mark.asyncio
    async def test_compose_page_smoke(self, tmp_path):
        composer = create_composer(workspace_root=tmp_path)
        page = WikiPagePlan(
            page_id="golden-overview",
            title="Golden overview",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            output_path="content/项目概述/00-overview.md",
            generation_mode=GenerationMode.LLM_ASSISTED,
        )
        ctx = ComposerContext(
            repository_name="golden-repo",
            primary_language="python",
            framework="fastapi",
            repository_root=str(tmp_path),
        )
        inp = build_composer_input(page, evidence_binding=None, context=ctx)
        out = await composer.compose_page(inp)
        assert out.markdown.strip()
        assert "golden" in out.markdown.lower() or "#" in out.markdown


class TestGoldenFixtureFactory:
    """create_golden_fixtures builds every catalog entry."""

    def test_create_all(self, tmp_path):
        roots = create_golden_fixtures(tmp_path)
        assert len(roots) == len(GOLDEN_FIXTURES)
        for r in roots:
            assert (r / "fixture_metadata.json").exists()
