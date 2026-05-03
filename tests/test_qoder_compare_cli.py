"""CLI tests for qoder-like verify/compare commands."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from repo_wiki.cli import app

runner = CliRunner()


def test_compare_generates_markdown_and_json_reports(tmp_path: Path) -> None:
    target = tmp_path / "target" / "content"
    baseline = tmp_path / "baseline" / "content"
    output = tmp_path / "reports"
    target.mkdir(parents=True)
    baseline.mkdir(parents=True)

    (target / "00-overview.md").write_text(
        "# 概述\n\n## 目录\n\n- 简介\n\n## 简介\n\n正文。\n\n<cite>src/main.py:1-2</cite>\n",
        encoding="utf-8",
    )
    (baseline / "00-overview.md").write_text(
        "# 概述\n\n## 目录\n\n- 简介\n\n## 简介\n\n正文。\n\n<cite>src/main.py:1-2</cite>\n",
        encoding="utf-8",
    )

    baseline_before = (baseline / "00-overview.md").read_text(encoding="utf-8")

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
                str(baseline),
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
    assert (baseline / "00-overview.md").read_text(encoding="utf-8") == baseline_before


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
    target = tmp_path / "target" / "content"
    baseline = tmp_path / "baseline" / "content"
    output = tmp_path / "reports"
    target.mkdir(parents=True)
    baseline.mkdir(parents=True)

    (target / "项目概述").mkdir()
    (target / "项目概述" / "项目概述.md").write_text("# 项目概述\n", encoding="utf-8")
    for i in range(5):
        (baseline / f"page-{i}.md").write_text(f"# Page {i}\n", encoding="utf-8")

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
                str(baseline),
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
    run = tmp_path / "run"
    target = run / "content"
    baseline = tmp_path / "baseline" / "content"
    output = run / "reports"
    target.mkdir(parents=True)
    baseline.mkdir(parents=True)
    (target / "项目概述.md").write_text("# 项目概述\n", encoding="utf-8")
    (baseline / "项目概述.md").write_text("# 项目概述\n", encoding="utf-8")
    (run / "manifest.json").write_text(
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
                str(baseline),
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
