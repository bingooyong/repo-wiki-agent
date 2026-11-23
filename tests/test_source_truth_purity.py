"""Source-truth purity contract tests (task 11-22-source-truth-purity).

Locks down the anti-pseudo-fact rules:
- D1: unresolved ${...} placeholders fail fast at render time.
- D2: contract required_keys are enforced before rendering (even on cache hits).
- D3: core-entity scoring excludes dependency/test sources, dedups reasons,
  uses word-boundary matching, and protects short names.
- D4: language/framework detection is package-config-first and language-scoped.
- D6: generation cache keys include template bytes.
- GEN-001: curated fact files are preserved; conflicts surface as diagnostics.
- Verifier: unresolved-placeholders is a HARD gate.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.generator.contracts import CORE_DOCUMENT_CONTRACTS
from repo_wiki.generator.engine import DataModelAggregator, GenerationEngine
from repo_wiki.generator.io import write_json
from repo_wiki.generator.templates import TemplateRenderer
from repo_wiki.scanner.artifacts import write_source_of_truth
from repo_wiki.scanner.repository_scanner import RepositoryScanner
from repo_wiki.verifier.service import GateType, VerifierService

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = REPO_ROOT / "templates"
PLACEHOLDER = re.compile(r"\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def _write_minimal_fact_layer(root: Path) -> None:
    """Minimal curated-style fact layer sufficient for core context building."""
    write_json(
        root / "ai/source-of-truth/repo-map.yaml",
        {
            "repository": {
                "name": "demo",
                "root_path": str(root),
                "primary_language": "python",
                "framework": "typer-cli",
            },
            "commands": {"start": "python -m demo"},
        },
    )
    write_json(
        root / "ai/source-of-truth/module-index.yaml",
        {
            "modules": [
                {
                    "name": "demo",
                    "path": "src/demo",
                    "responsibility": "demo logic",
                    "domain": "core-platform",
                    "service_family": "python-backend",
                    "runtime_role": "service",
                    "exports": [],
                    "depends_on": [],
                    "depended_by": [],
                    "interfaces": [],
                    "data_models": ["Invoice"],
                    "owner": "team",
                    "doc_path": "docs/modules/demo.md",
                }
            ]
        },
    )
    write_json(root / "ai/source-of-truth/api-index.yaml", {"endpoints": []})
    write_json(
        root / "ai/source-of-truth/data-models.yaml",
        {
            "models": [
                {
                    "name": "Invoice",
                    "type": "python_class",
                    "module": "demo",
                    "file_path": "src/demo/models.py",
                }
            ]
        },
    )


class TestTemplateContextAudit:
    """All CORE contracts: no unknown placeholders, required_keys subset of context."""

    def test_core_contract_keys_audit(self, tmp_path: Path) -> None:
        _write_minimal_fact_layer(tmp_path)
        engine = GenerationEngine(tmp_path, template_root=TEMPLATE_ROOT)
        context = engine._build_core_context(engine._load_snapshot())

        for contract in CORE_DOCUMENT_CONTRACTS:
            template_text = (TEMPLATE_ROOT / contract.template_path).read_text(encoding="utf-8")
            used_keys = set(PLACEHOLDER.findall(template_text))
            unknown = used_keys - set(context)
            assert not unknown, f"{contract.name}: template keys missing from context: {unknown}"
            missing_required = set(contract.required_keys) - set(context)
            assert not missing_required, (
                f"{contract.name}: required_keys missing from context: {missing_required}"
            )

    def test_architecture_template_uses_real_governance_key(self) -> None:
        for root in (TEMPLATE_ROOT, REPO_ROOT / "repo_wiki" / "templates"):
            text = (root / "docs/01-architecture.md.j2").read_text(encoding="utf-8")
            assert "${incremental_governance}" not in text
            assert "${incremental_update_governance}" in text


class TestPlaceholderGuard:
    """D1: rendering must raise on unresolved placeholders."""

    def test_render_raises_on_missing_key(self, tmp_path: Path) -> None:
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "t.md.j2").write_text(
            "known=${known} unknown=${missing_key}\n", encoding="utf-8"
        )
        renderer = TemplateRenderer(tmp_path)
        with pytest.raises(ValueError, match="missing_key"):
            renderer.render("docs/t.md.j2", {"known": "value"})

    def test_render_succeeds_when_all_keys_present(self, tmp_path: Path) -> None:
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "t.md.j2").write_text("hello ${name}\n", encoding="utf-8")
        renderer = TemplateRenderer(tmp_path)
        assert renderer.render("docs/t.md.j2", {"name": "world"}) == "hello world\n"


class TestRequiredKeysAndCache:
    """D2 + D6: required_keys enforcement and template-aware cache keys."""

    def _engine(self, tmp_path: Path) -> GenerationEngine:
        (tmp_path / "templates" / "docs").mkdir(parents=True)
        (tmp_path / "templates" / "docs" / "t.md.j2").write_text(
            "hello ${name}\n", encoding="utf-8"
        )
        return GenerationEngine(tmp_path, template_root=tmp_path / "templates")

    def test_required_keys_enforced(self, tmp_path: Path) -> None:
        engine = self._engine(tmp_path)
        with pytest.raises(ValueError, match="missing required context keys"):
            engine._render_with_cache("t", "docs/t.md.j2", {}, required_keys=("name",))

    def test_required_keys_enforced_on_cache_hit_path(self, tmp_path: Path) -> None:
        engine = self._engine(tmp_path)
        ctx = {"name": "world"}
        _, cached_first = engine._render_with_cache("t", "docs/t.md.j2", ctx, ("name",))
        assert cached_first is False
        _, cached_second = engine._render_with_cache("t", "docs/t.md.j2", ctx, ("name",))
        assert cached_second is True
        # Same context (cache entry exists) but a stricter contract must still raise.
        with pytest.raises(ValueError, match="extra_key"):
            engine._render_with_cache("t", "docs/t.md.j2", ctx, ("name", "extra_key"))

    def test_cache_invalidated_by_template_edit(self, tmp_path: Path) -> None:
        engine = self._engine(tmp_path)
        ctx = {"name": "world"}
        content1, cached1 = engine._render_with_cache("t", "docs/t.md.j2", ctx)
        assert cached1 is False
        content2, cached2 = engine._render_with_cache("t", "docs/t.md.j2", ctx)
        assert cached2 is True
        assert content2 == content1

        template = tmp_path / "templates" / "docs" / "t.md.j2"
        template.write_text("hi ${name}\n", encoding="utf-8")
        content3, cached3 = engine._render_with_cache("t", "docs/t.md.j2", ctx)
        assert cached3 is False, "template edit must invalidate the cached render"
        assert content3 == "hi world\n"


class TestCoreEntityPurity:
    """D3: dependency/test sources never become core; reasons never stack."""

    def test_node_modules_and_tests_models_are_not_core(self) -> None:
        models = [
            {
                "name": "in",
                "module": "js-yaml",
                "type": "js_schema",
                "file_path": "extensions/repo-wiki-browser/node_modules/js-yaml/lib/schema.js",
            },
            {
                "name": "instanceof",
                "module": "js-yaml",
                "type": "js_schema",
                "file_path": "extensions/repo-wiki-browser/node_modules/js-yaml/lib/schema.js",
            },
            {
                "name": "dm_sales_facts",
                "module": "tests",
                "type": "sql_table",
                "file_path": "tests/test_database_migrations.py",
            },
        ]
        modules = [
            {"name": "js-yaml", "domain": "core-platform", "service_family": "node"},
            {"name": "tests", "domain": "persistence", "service_family": "python-backend"},
        ]
        endpoints = [
            {"module": "api", "handler": "def handle(input): return input in schema"},
            {"module": "api2", "handler": "def check(x): return x instanceof Schema"},
            {"module": "api3", "handler": "def load(): return dm_sales_facts"},
        ]
        aggregator = DataModelAggregator(models=models, modules=modules, endpoints=endpoints)

        by_name = {m.name: m for m in aggregator.data_models}
        # Still present in the index, but never core.
        assert set(by_name) == {"in", "instanceof", "dm_sales_facts"}
        for name in ("in", "instanceof"):
            assert by_name[name].source_role == "dependency"
            assert by_name[name].is_core_entity is False
            assert by_name[name].core_score == 0.0
        assert by_name["dm_sales_facts"].source_role == "test-harness"
        assert by_name["dm_sales_facts"].is_core_entity is False
        assert by_name["dm_sales_facts"].core_score == 0.0

    def test_short_product_name_not_core_via_api_signal_alone(self) -> None:
        models = [
            {"name": "in", "module": "core", "type": "python_class", "file_path": "src/core/t.py"}
        ]
        modules = [{"name": "core", "domain": "unknown", "service_family": "python-backend"}]
        endpoints = [
            {"module": f"api{i}", "handler": "def f(): return value in container"}
            for i in range(5)
        ]
        aggregator = DataModelAggregator(models=models, modules=modules, endpoints=endpoints)
        model = aggregator.data_models[0]
        assert model.is_core_entity is False
        assert "API 参数类型" not in model.core_reason

    def test_word_boundary_matching_not_substring(self) -> None:
        models = [
            {
                "name": "Order",
                "module": "billing",
                "type": "python_class",
                "file_path": "src/billing/models.py",
            }
        ]
        modules = [{"name": "billing", "domain": "unknown", "service_family": "python-backend"}]
        endpoints = [{"module": "api", "handler": "def reorder(): pass"}]
        aggregator = DataModelAggregator(models=models, modules=modules, endpoints=endpoints)
        assert "API 参数类型" not in aggregator.data_models[0].core_reason

    def test_api_reason_recorded_once_across_endpoints(self) -> None:
        models = [
            {
                "name": "Invoice",
                "module": "billing",
                "type": "python_class",
                "file_path": "src/billing/models.py",
            }
        ]
        modules = [{"name": "billing", "domain": "unknown", "service_family": "python-backend"}]
        endpoints = [
            {"module": "api", "handler": "def create_invoice(invoice: Invoice): pass"},
            {"module": "api", "handler": "def update_invoice(invoice: Invoice): pass"},
            {"module": "api2", "handler": "def get_invoice(invoice: Invoice): pass"},
        ]
        aggregator = DataModelAggregator(models=models, modules=modules, endpoints=endpoints)
        model = aggregator.data_models[0]
        assert model.core_reason.count("API 参数类型") == 1
        # billing + api + api2 = 3 referencing modules (signal 1: 6.0) plus a
        # single API signal (1.0). More endpoints must not stack the score.
        assert model.core_score == pytest.approx(7.0)
        more_endpoints = endpoints + [
            {"module": "api", "handler": "def delete_invoice(invoice: Invoice): pass"},
            {"module": "api2", "handler": "def list_invoice(invoice: Invoice): pass"},
        ]
        aggregator2 = DataModelAggregator(models=models, modules=modules, endpoints=more_endpoints)
        model2 = aggregator2.data_models[0]
        assert model2.core_score == pytest.approx(7.0)
        assert model2.core_reason.count("API 参数类型") == 1


class TestLanguageFrameworkDetection:
    """D4: package-config-first, per-language manifest scoping, typer signal."""

    def _scan(self, tmp_path: Path):
        cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
        return RepositoryScanner(cfg).scan()

    def test_python_repo_with_express_devdependency_is_not_express(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "demo"\nversion = "0.1.0"\ndependencies = ["typer>=0.12"]\n',
            encoding="utf-8",
        )
        (tmp_path / "package.json").write_text(
            json.dumps({"devDependencies": {"express": "^4.0.0"}}), encoding="utf-8"
        )
        (tmp_path / "app.py").write_text("import typer\napp = typer.Typer()\n", encoding="utf-8")
        (tmp_path / "cli.py").write_text("def main():\n    pass\n", encoding="utf-8")

        snapshot = self._scan(tmp_path)
        assert snapshot.repository.language == "python"
        assert snapshot.repository.framework == "typer"
        assert snapshot.repository.framework != "express"

    def test_fixture_requirements_cannot_label_product_framework(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "demo"\nversion = "0.1.0"\ndependencies = ["typer>=0.12"]\n',
            encoding="utf-8",
        )
        (tmp_path / "app.py").write_text("import typer\n", encoding="utf-8")
        fixture = tmp_path / "tests" / "fixtures" / "fastapi_service"
        fixture.mkdir(parents=True)
        (fixture / "requirements.txt").write_text("fastapi\n", encoding="utf-8")

        snapshot = self._scan(tmp_path)
        assert snapshot.repository.language == "python"
        assert snapshot.repository.framework == "typer"

    def test_pyproject_presence_forces_python_over_js_volume(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "demo"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        (tmp_path / "main.py").write_text("x = 1\n", encoding="utf-8")
        for i in range(8):
            (tmp_path / f"script{i}.js").write_text("console.log(1)\n", encoding="utf-8")

        snapshot = self._scan(tmp_path)
        assert snapshot.repository.language == "python"

    def test_js_runtime_dependency_still_detected(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text(
            json.dumps({"dependencies": {"express": "^4.0.0"}}), encoding="utf-8"
        )
        (tmp_path / "server.js").write_text("const express = require('express')\n", encoding="utf-8")
        snapshot = self._scan(tmp_path)
        assert snapshot.repository.language == "javascript"
        assert snapshot.repository.framework == "express"

    def test_js_devdependency_alone_is_not_framework(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text(
            json.dumps({"devDependencies": {"express": "^4.0.0"}}), encoding="utf-8"
        )
        (tmp_path / "server.js").write_text("console.log('hi')\n", encoding="utf-8")
        snapshot = self._scan(tmp_path)
        assert snapshot.repository.framework != "express"


class TestNodeModulesPruning:
    """Regression: dependency/generated directories are pruned from scanning."""

    def test_dependency_dirs_pruned(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "keep.py").write_text("x = 1\n", encoding="utf-8")
        for rel in (
            "node_modules/js-yaml/lib/schema.js",
            ".venv/lib/python3.11/site-packages/pkg/mod.py",
            "dist/bundle.js",
            "build/out.js",
        ):
            path = tmp_path / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("pollution\n", encoding="utf-8")

        cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
        scanned = {f.path.as_posix() for f in RepositoryScanner(cfg).iter_scanned_files()}
        assert "src/keep.py" in scanned
        assert not any(
            part in path
            for path in scanned
            for part in ("node_modules", ".venv", "dist/", "build/")
        )


class TestCuratedConflictVisibility:
    """GEN-001: curated values are kept; disagreements become source-conflict diagnostics."""

    def test_curated_repo_map_preserved_and_conflicts_reported(self, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("import typer\n", encoding="utf-8")
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "demo"\nversion = "0.1.0"\ndependencies = ["typer>=0.12"]\n',
            encoding="utf-8",
        )
        cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
        snapshot = RepositoryScanner(cfg).scan()

        curated_repo_map = {
            "repository": {
                "name": "curated-name",
                "root_path": ".",
                "primary_language": "python",
                "framework": "typer-cli",
                "package_manager": "uv",
                "source_of_truth_status": "curated-current",
            },
            "commands": {"generate": "repo-wiki generate"},
            "custom_contract": {"keep": True},
        }
        ai_dir = tmp_path / "ai" / "source-of-truth"
        write_json(ai_dir / "repo-map.yaml", curated_repo_map)
        curated_module_index = {"modules": [{"name": "curated-module", "path": "src"}]}
        write_json(ai_dir / "module-index.yaml", curated_module_index)

        write_source_of_truth(tmp_path, snapshot)

        assert json.loads((ai_dir / "repo-map.yaml").read_text(encoding="utf-8")) == (
            curated_repo_map
        )
        assert json.loads((ai_dir / "module-index.yaml").read_text(encoding="utf-8")) == (
            curated_module_index
        )

        diagnostics = json.loads(
            (ai_dir / "classification-diagnostics.json").read_text(encoding="utf-8")
        )
        conflicts = diagnostics["source_conflicts"]
        assert conflicts, "scanner-vs-curated disagreements must be visible"
        assert all(c["label"] == "source-conflict" for c in conflicts)
        assert all(c["resolution"] == "kept-curated" for c in conflicts)
        fields = {c["field"] for c in conflicts}
        assert "repository.framework" in fields  # typer-cli (curated) vs typer (scanned)
        framework_conflict = next(
            c for c in conflicts if c["field"] == "repository.framework"
        )
        assert framework_conflict["curated_value"] == "typer-cli"
        assert framework_conflict["scanned_value"] == "typer"

    def test_non_curated_repo_map_still_written(self, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
        cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
        snapshot = RepositoryScanner(cfg).scan()
        write_source_of_truth(tmp_path, snapshot)
        repo_map = json.loads(
            (tmp_path / "ai" / "source-of-truth" / "repo-map.yaml").read_text(encoding="utf-8")
        )
        assert repo_map["repository"]["primary_language"] == "python"
        diagnostics = json.loads(
            (tmp_path / "ai" / "source-of-truth" / "classification-diagnostics.json").read_text(
                encoding="utf-8"
            )
        )
        assert diagnostics["source_conflicts"] == []


class TestUnresolvedPlaceholderVerifier:
    """HARD gate: injected ${foo} in generated docs must FAIL verification."""

    def test_injected_placeholder_fails_hard(self, tmp_path: Path) -> None:
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "01-architecture.md").write_text(
            "# Architecture\n\nGovernance: ${foo}\n", encoding="utf-8"
        )
        result = VerifierService(tmp_path).verify(ci=True)
        check = next(
            c for c in result["checks"] if c["name"] == "unresolved-placeholders"
        )
        assert check["status"] == "FAIL"
        assert check["gate_type"] == "HARD"
        assert check["reason_code"] == "CONTENT_UNRESOLVED_PLACEHOLDER"
        assert "CONTENT_UNRESOLVED_PLACEHOLDER" in result["hard_gate_codes"]
        assert result["grade"] == "FAIL"
        detail = check["details"]["unresolved_placeholders"][0]
        assert detail["placeholder"] == "${foo}"
        assert detail["path"] == "docs/01-architecture.md"
        assert detail["line"] == 3

    def test_clean_docs_pass_and_code_samples_ignored(self, tmp_path: Path) -> None:
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "01-architecture.md").write_text(
            "# Architecture\n\nUse `export KEY=${HOME}` in shells:\n\n"
            "```bash\necho ${HOME}\n```\n",
            encoding="utf-8",
        )
        check = VerifierService(tmp_path)._check_unresolved_placeholders()
        assert check.status == "PASS"
        assert check.gate_type == GateType.HARD


class TestGeneratedOutputProtectsCuratedFacts:
    """Generation must not write into curated fact files, not just the scanner."""

    def test_no_contract_targets_a_curated_fact_file(self) -> None:
        from repo_wiki.generator.contracts import (
            PROMPT_FRAGMENT_CONTRACTS,
            TASK_CATALOG_CONTRACT,
            all_section_contracts,
            module_document_contract,
        )
        from repo_wiki.scanner.artifacts import _CURATED_FACT_FILES

        contracts = [
            *CORE_DOCUMENT_CONTRACTS,
            *PROMPT_FRAGMENT_CONTRACTS,
            TASK_CATALOG_CONTRACT,
            *all_section_contracts(),
            module_document_contract("demo"),
        ]
        offenders = [
            c.output_path
            for c in contracts
            if Path(c.output_path).name in _CURATED_FACT_FILES
        ]
        assert offenders == []

    def test_generate_full_keeps_curated_fact_bytes(self, tmp_path: Path) -> None:
        from repo_wiki.scanner.artifacts import _CURATED_FACT_FILES

        ai_dir = tmp_path / "ai" / "source-of-truth"
        ai_dir.mkdir(parents=True)
        for name in sorted(_CURATED_FACT_FILES):
            write_json(ai_dir / name, {"curated_marker": name})
        before = {name: (ai_dir / name).read_bytes() for name in _CURATED_FACT_FILES}

        repo_templates = Path(__file__).resolve().parents[1] / "templates"
        GenerationEngine(tmp_path, template_root=repo_templates).generate_full()

        after = {name: (ai_dir / name).read_bytes() for name in _CURATED_FACT_FILES}
        assert after == before


class TestStubNeverOverwritesCuratedDoc:
    """An init stub must not replace human-authored docs."""

    def _engine(self, tmp_path: Path) -> GenerationEngine:
        repo_templates = Path(__file__).resolve().parents[1] / "templates"
        return GenerationEngine(tmp_path, template_root=repo_templates)

    def test_curated_overview_is_preserved(self, tmp_path: Path) -> None:
        target = tmp_path / "docs" / "00-overview.md"
        target.parent.mkdir(parents=True)
        curated = "# repo-wiki 总览\n\n人工维护的名称对照表。\n"
        target.write_text(curated, encoding="utf-8")
        stub = "# repo-wiki-agent - 项目概览\n\n<!-- repo-wiki-init-stub -->\n"
        assert self._engine(tmp_path)._write_doc(target, "docs/00-overview.md", stub) is False
        assert target.read_text(encoding="utf-8") == curated

    def test_stub_replaces_previous_stub(self, tmp_path: Path) -> None:
        target = tmp_path / "docs" / "00-overview.md"
        target.parent.mkdir(parents=True)
        target.write_text("<!-- repo-wiki-init-stub -->\nold\n", encoding="utf-8")
        stub = "<!-- repo-wiki-init-stub -->\nnew\n"
        assert self._engine(tmp_path)._write_doc(target, "docs/00-overview.md", stub) is True
        assert target.read_text(encoding="utf-8") == stub

    def test_real_content_replaces_curated_doc(self, tmp_path: Path) -> None:
        target = tmp_path / "docs" / "01-architecture.md"
        target.parent.mkdir(parents=True)
        target.write_text("# 旧架构\n\nHandles API routes /path.\n", encoding="utf-8")
        real = "# 架构\n\n| 语言 | Python |\n"
        assert self._engine(tmp_path)._write_doc(target, "docs/01-architecture.md", real) is True
        assert target.read_text(encoding="utf-8") == real

    def test_generate_full_preserves_curated_overview(self, tmp_path: Path) -> None:
        target = tmp_path / "docs" / "00-overview.md"
        target.parent.mkdir(parents=True)
        curated = "# repo-wiki 总览\n\n人工维护内容。\n"
        target.write_text(curated, encoding="utf-8")
        self._engine(tmp_path).generate_full()
        assert target.read_text(encoding="utf-8") == curated