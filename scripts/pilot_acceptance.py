#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def run_command(cmd: list[str], cwd: Path) -> dict:
    started = time.perf_counter()
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    duration = round(time.perf_counter() - started, 4)
    return {
        "command": cmd,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "duration_sec": duration,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run repo-wiki pilot acceptance scenarios.")
    parser.add_argument("--target", default=".", help="Target repository root to scan.")
    parser.add_argument(
        "--out", default=".repo-wiki/pilot", help="Output directory for pilot evidence."
    )
    args = parser.parse_args()

    workspace = Path(__file__).resolve().parents[1]
    target = Path(args.target).resolve()
    out_dir = Path(args.out).resolve()
    logs_dir = out_dir / "scenario-logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as fp:
        config_path = Path(fp.name)
        fp.write(
            "project:\n"
            f'  root: "{target.as_posix()}"\n'
            "output:\n"
            '  docs_dir: "docs/"\n'
            '  ai_dir: "ai/source-of-truth/"\n'
            '  index_dir: ".repo-wiki/"\n'
            '  claude_dir: ".claude/"\n'
        )

    base = [sys.executable, "-m", "repo_wiki.main"]
    scenarios = {
        "init": base + ["init", "--config", str(config_path)],
        "search": base
        + ["search", "module architecture", "--top-k", "3", "--config", str(config_path)],
        "graph": base + ["graph", "root", "--config", str(config_path)],
        "update": base + ["update", "--config", str(config_path)],
        "verify": base + ["verify", "--ci", "--config", str(config_path)],
    }

    scenario_results = {}
    for name, cmd in scenarios.items():
        result = run_command(cmd, cwd=workspace)
        scenario_results[name] = result
        (logs_dir / f"{name}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    metrics = {
        "module_identification_accuracy": None,
        "rest_extraction_accuracy": None,
        "module_doc_coverage_ratio": None,
        "search_top3_hit_rate": None,
        "impact_chain_reasonableness": None,
        "init_success_rate": 1.0 if scenario_results["init"]["returncode"] == 0 else 0.0,
        "notes": "Fill metric values after manual pilot review against golden samples.",
    }
    metrics_path = out_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    acceptance = {
        "target": str(target),
        "generated_at_epoch": int(time.time()),
        "scenarios": {
            key: {
                "returncode": value["returncode"],
                "duration_sec": value["duration_sec"],
            }
            for key, value in scenario_results.items()
        },
        "pass": all(value["returncode"] == 0 for value in scenario_results.values()),
    }
    acceptance_path = out_dir / "acceptance-report.json"
    acceptance_path.write_text(
        json.dumps(acceptance, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {"acceptance_report": str(acceptance_path), "metrics": str(metrics_path)},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
