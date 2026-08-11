"""CLI tests for qoder-like verify/compare commands."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from typer.testing import CliRunner

from repo_wiki.cli import _read_composer_cache_summary, app

runner = CliRunner()


def test_read_composer_cache_summary_includes_skip_regeneration_counters(tmp_path: Path) -> None:
    cache_path = tmp_path / "composer.sqlite3"
    cache_path.touch()

    class _FakeCache:
        def __init__(self, _path: Path) -> None:
            pass

        def stats(self) -> SimpleNamespace:
            return SimpleNamespace(
                total_entries=1,
                cache_hits=4,
                cache_misses=5,
                skipped_pages=3,
                regenerated_pages=2,
                total_tokens_saved=12,
                total_cost_saved_usd=0.01,
            )

        def list_entries(self, limit: int) -> list[SimpleNamespace]:
            assert limit == 10
            return []

    with patch("repo_wiki.generator.composer_cache.ComposerCache", _FakeCache):
        summary = _read_composer_cache_summary(cache_path, limit=10)

    assert summary["exists"] is True
    assert summary["stats"]["skipped_pages"] == 3
    assert summary["stats"]["regenerated_pages"] == 2


def _make_qoder_compare_sandbox(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """Build a minimal git repo with canonical `.qoder/repowiki/zh` and a qoder-like target content dir."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(
        ["git", "init"],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )
    zh = repo / ".qoder" / "repowiki" / "zh"
    baseline_content = zh / "content"
    baseline_content.mkdir(parents=True)
    target = repo / ".repo-agent-eval" / "runs" / "run-1" / "repowiki" / "zh" / "content"
    target.mkdir(parents=True)
    output = tmp_path / "reports"
    output.mkdir(parents=True)
    return repo, target, zh, output


def test_compare_generates_markdown_and_json_reports(tmp_path: Path) -> None:
    _repo, target, zh, output = _make_qoder_compare_sandbox(tmp_path)
    baseline_content = zh / "content"

    (target / "00-overview.md").write_text(
        "# 概述\n\n## 目录\n\n- 简介\n\n## 简介\n\n正文。\n\n<cite>src/main.py:1-2</cite>\n",
        encoding="utf-8",
    )
    (baseline_content / "00-overview.md").write_text(
        "# 概述\n\n## 目录\n\n- 简介\n\n## 简介\n\n正文。\n\n<cite>src/main.py:1-2</cite>\n",
        encoding="utf-8",
    )

    baseline_before = (baseline_content / "00-overview.md").read_text(encoding="utf-8")

    class _FakeReport:
        def to_dict(self):
            return {
                "metrics": [
                    {
                        "metric_name": "toc_presence",
                        "status": "pass",
                        "measured_value": 1.0,
                        "threshold": 0.8,
                    },
                    {
                        "metric_name": "citation_coverage",
                        "status": "pass",
                        "measured_value": 1.0,
                        "threshold": 0.7,
                    },
                    {
                        "metric_name": "mermaid_presence",
                        "status": "pass",
                        "measured_value": 0.4,
                        "threshold": 0.3,
                    },
                    {
                        "metric_name": "prose_list_ratio",
                        "status": "pass",
                        "measured_value": 0.8,
                        "threshold": 0.4,
                    },
                    {
                        "metric_name": "api_aggregation",
                        "status": "pass",
                        "measured_value": 0.7,
                        "threshold": 0.6,
                    },
                    {
                        "metric_name": "data_model_aggregation",
                        "status": "pass",
                        "measured_value": 0.7,
                        "threshold": 0.6,
                    },
                    {
                        "metric_name": "file_reference_integrity",
                        "status": "pass",
                        "measured_value": 1.0,
                        "threshold": 1.0,
                        "details": {"broken_refs": []},
                    },
                ],
                "summary": {"overall_score": 0.9},
                "blocked": False,
            }

    with (
        patch(
            "repo_wiki.verifier.qoder_parity_metrics.create_parity_report",
            return_value=_FakeReport(),
        ),
        patch(
            "repo_wiki.verifier.qoder_strict_verifier.verify_qoder_like",
            return_value={"grade": "PASS"},
        ),
    ):
        result = runner.invoke(
            app,
            [
                "compare",
                "--target",
                str(target),
                "--baseline",
                str(zh),
                "--format",
                "both",
                "--output",
                str(output),
            ],
        )

    assert result.exit_code == 0
    assert (output / "qoder-comparison-report.md").exists()
    assert (output / "qoder-comparison-report.json").exists()
    payload = json.loads((output / "qoder-comparison-report.json").read_text(encoding="utf-8"))
    assert "metrics" in payload
    assert payload.get("baseline_read_only_verified") is True
    assert (baseline_content / "00-overview.md").read_text(encoding="utf-8") == baseline_before


def test_verify_qoder_like_profile_exit_non_zero_on_not_ready(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    run_root = repo_root / ".repo-agent-eval" / "run-a" / "content"
    run_root.mkdir(parents=True)
    (run_root / "00-overview.md").write_text("# Overview\n\nNo citation.", encoding="utf-8")

    class _Cfg:
        class _Project:
            root = str(repo_root)

        project = _Project()

    with patch("repo_wiki.cli.load_config", return_value=_Cfg()):
        result = runner.invoke(
            app,
            ["verify", "--profile", "qoder-like", "--ci", "--output", "run-a"],
        )

    assert result.exit_code == 1
    assert "NOT_READY" in result.output or '"FAIL"' in result.output


def test_compare_fails_when_page_coverage_is_below_qoder_baseline(tmp_path: Path) -> None:
    _repo, target, zh, output = _make_qoder_compare_sandbox(tmp_path)
    baseline_content = zh / "content"

    (target / "项目概述").mkdir()
    (target / "项目概述" / "项目概述.md").write_text("# 项目概述\n", encoding="utf-8")
    for i in range(5):
        (baseline_content / f"page-{i}.md").write_text(f"# Page {i}\n", encoding="utf-8")

    class _FakeReport:
        def to_dict(self):
            return {
                "metrics": [],
                "summary": {"overall_score": 0.9},
                "blocked": False,
            }

    with (
        patch(
            "repo_wiki.verifier.qoder_parity_metrics.create_parity_report",
            return_value=_FakeReport(),
        ),
        patch(
            "repo_wiki.verifier.qoder_strict_verifier.verify_qoder_like",
            return_value={"grade": "PASS"},
        ),
    ):
        result = runner.invoke(
            app,
            [
                "compare",
                "--target",
                str(target),
                "--baseline",
                str(zh),
                "--format",
                "both",
                "--output",
                str(output),
                "--ci",
            ],
        )

    assert result.exit_code == 1
    payload = json.loads((output / "qoder-comparison-report.json").read_text(encoding="utf-8"))
    assert payload["status"] == "NOT_READY"
    assert payload["readiness_gates"]["failures"][0]["code"] == "QODER_PAGE_COVERAGE_LOW"


def test_compare_fails_when_llm_generation_coverage_is_low(tmp_path: Path) -> None:
    _repo, target, zh, output = _make_qoder_compare_sandbox(tmp_path)
    baseline_content = zh / "content"

    (target / "项目概述.md").write_text("# 项目概述\n", encoding="utf-8")
    (baseline_content / "项目概述.md").write_text("# 项目概述\n", encoding="utf-8")
    (target.parent / "manifest.json").write_text(
        json.dumps(
            {
                "generation": {
                    "planned_pages": 1,
                    "llm": {
                        "composed_page_count": 1,
                        "llm_call_count": 0,
                        "cache_hits": 0,
                        "fallback_page_count": 1,
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    class _FakeReport:
        def to_dict(self):
            return {"metrics": [], "summary": {"overall_score": 0.9}, "blocked": False}

    with (
        patch(
            "repo_wiki.verifier.qoder_parity_metrics.create_parity_report",
            return_value=_FakeReport(),
        ),
        patch(
            "repo_wiki.verifier.qoder_strict_verifier.verify_qoder_like",
            return_value={"grade": "PASS"},
        ),
    ):
        result = runner.invoke(
            app,
            [
                "compare",
                "--target",
                str(target),
                "--baseline",
                str(zh),
                "--format",
                "json",
                "--output",
                str(output),
                "--ci",
            ],
        )

    assert result.exit_code == 1
    payload = json.loads((output / "qoder-comparison-report.json").read_text(encoding="utf-8"))
    codes = [failure["code"] for failure in payload["readiness_gates"]["failures"]]
    assert "QODER_LLM_COVERAGE_LOW" in codes
