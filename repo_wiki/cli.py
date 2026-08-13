from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import typer

from repo_wiki.core import RepoWikiError, load_config
from repo_wiki.core.logging import error, info
from repo_wiki.llm import resolve_llm_config
from repo_wiki.llm.diagnostics import (
    format_diagnostics_json,
    format_diagnostics_text,
    run_llm_diagnostics,
)
from repo_wiki.orchestration.latest_run_selector import select_run
from repo_wiki.orchestration.service import RepoWikiService

app = typer.Typer(help="repo-wiki: local-first repository wiki generator")


@app.command("init")
def init_command(config: Path | None = typer.Option(None, "--config")) -> None:
    _run_with_service("init", config)


@app.command("index")
def index_command(config: Path | None = typer.Option(None, "--config")) -> None:
    _run_with_service("index", config)


@app.command("update")
def update_command(config: Path | None = typer.Option(None, "--config")) -> None:
    _run_with_service("update", config)


@app.command("sync")
def sync_command(config: Path | None = typer.Option(None, "--config")) -> None:
    _run_with_service("sync", config)


@app.command("search")
def search_command(
    query: str = typer.Argument(..., help="Semantic search query"),
    module: str | None = typer.Option(None, "--module"),
    top_k: int = typer.Option(10, "--top-k"),
    config: Path | None = typer.Option(None, "--config"),
) -> None:
    del config  # G006 local-agent search is READY-bound and does not load config.
    from repo_wiki.local_agent import build_search_contract

    result, exit_code = build_search_contract(Path.cwd(), query=query, module=module, top_k=top_k)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if exit_code:
        raise typer.Exit(code=exit_code)


@app.command("graph")
def graph_command(
    module: str = typer.Argument(..., help="Module name"),
    config: Path | None = typer.Option(None, "--config"),
) -> None:
    del config  # G006 local-agent graph is READY-bound and does not load config.
    from repo_wiki.local_agent import build_graph_contract

    result, exit_code = build_graph_contract(Path.cwd(), module=module)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if exit_code:
        raise typer.Exit(code=exit_code)


@app.command("generate")
def generate_command(
    profile: str = typer.Option(
        "default", "--profile", help="Eval profile name (default, ci, qoder-like)"
    ),
    output: str | None = typer.Option(None, "--output", help="Override eval output root"),
    run_id: str | None = typer.Option(None, "--run-id", help="Custom run identifier"),
    config: Path | None = typer.Option(None, "--config"),
    ci: bool = typer.Option(False, "--ci", help="Run in CI mode (strict verification)"),
) -> None:
    """Generate wiki content using specified eval profile."""
    from repo_wiki.orchestration.eval_layout import get_eval_profile, reject_unsafe_output_root

    # Get the profile
    eval_profile = get_eval_profile(profile)

    # Override output root if specified
    if output:
        from repo_wiki.orchestration.eval_layout import EvalOutputProfile

        eval_profile = EvalOutputProfile(
            name=profile,
            root=output,
            create_subdirs=eval_profile.create_subdirs,
            content_subdir=eval_profile.content_subdir,
        )
        # Validate unsafe output roots
        reject_unsafe_output_root(output)

    _run_with_service("generate", config, eval_profile=eval_profile, run_id=run_id)
    if ci:
        cfg = load_config(config)
        service = RepoWikiService(cfg)
        result = service.verify(ci=True)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result.get("grade") == "FAIL":
            raise typer.Exit(code=1)


@app.command("improve")
def improve_command(
    profile: str = typer.Option(
        "qoder-like", "--profile", help="Improvement profile; currently qoder-like is supported"
    ),
    output: str = typer.Option(".repo-agent-eval", "--output", help="Eval output root"),
    run_id: str | None = typer.Option(None, "--run-id", help="Custom run identifier"),
    real_max_calls: int = typer.Option(
        5, "--real-max-calls", help="Maximum real LLM page calls for this batch"
    ),
    timeout_seconds: float = typer.Option(90.0, "--timeout-seconds", help="Per-page LLM timeout"),
    concurrency: int = typer.Option(1, "--concurrency", help="Concurrent real LLM page calls"),
    max_tokens: int = typer.Option(1000, "--max-tokens", help="Max completion tokens per page"),
    max_pages: int = typer.Option(220, "--max-pages", help="Curated qoder-like page-plan cap"),
    priority: str = typer.Option(
        "qoder", "--priority", help="LLM call priority: qoder, overview, api, plan"
    ),
    priority_page_ids: str | None = typer.Option(
        None, "--priority-page-ids", help="Comma-separated page IDs to attempt first"
    ),
    baseline: Path | None = typer.Option(
        None, "--baseline", exists=True, file_okay=False, resolve_path=True
    ),
    ci: bool = typer.Option(False, "--ci", help="Run strict verify and optional baseline compare"),
    config: Path | None = typer.Option(None, "--config"),
) -> None:
    """Incrementally improve qoder-like wiki pages using real LLM calls.

    This command reuses the profile-level composer cache under
    `.repo-agent-eval/.runtime/composer_cache.sqlite3`, so repeated batches can
    gradually replace fallback pages without starting from zero.
    """
    if profile != "qoder-like":
        raise typer.BadParameter("improve currently supports --profile qoder-like only")

    from repo_wiki.orchestration.eval_layout import (
        EvalOutputProfile,
        get_eval_profile,
        reject_unsafe_output_root,
    )

    eval_profile = get_eval_profile(profile)
    eval_profile = EvalOutputProfile(
        name=profile,
        root=output,
        create_subdirs=eval_profile.create_subdirs,
        content_subdir=eval_profile.content_subdir,
    )
    reject_unsafe_output_root(output)

    env_updates = {
        "REPO_WIKI_LLM_PAGE_TIMEOUT_SECONDS": str(timeout_seconds),
        "REPO_WIKI_LLM_MAX_FAILURES": str(max(real_max_calls, 1)),
        "REPO_WIKI_LLM_REAL_MAX_CALLS": str(max(real_max_calls, 0)),
        "REPO_WIKI_LLM_CONCURRENCY": str(max(concurrency, 1)),
        "REPO_WIKI_QODER_LIKE_MAX_PAGES": str(max(1, max_pages)),
        "REPO_WIKI_COMPACT_LLM_PROMPT": "1",
        "REPO_WIKI_LLM_COMPOSER_MAX_TOKENS": str(max(max_tokens, 256)),
        "REPO_WIKI_LLM_PRIORITY": priority,
    }
    if priority_page_ids:
        env_updates["REPO_WIKI_LLM_PRIORITY_PAGE_IDS"] = priority_page_ids

    with _temporary_env(env_updates):
        cfg = load_config(config)
        service = RepoWikiService(cfg)
        result = service.generate(eval_profile=eval_profile, run_id=run_id)

    info("improve completed")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    generated_root = (
        Path(result.get("manifest_path", "")).parent if result.get("manifest_path") else None
    )
    if ci and generated_root:
        from repo_wiki.verifier.qoder_strict_verifier import verify_qoder_like

        info(f"strict verify started root={generated_root}")
        verify_result = verify_qoder_like(generated_root, ci=True, strict=True)
        reports_dir = generated_root / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "strict-verify-output.json").write_text(
            json.dumps(verify_result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps({"strict_verify": verify_result}, ensure_ascii=False, indent=2))
        if verify_result.get("grade") == "FAIL":
            raise typer.Exit(code=1)
        info(f"strict verify completed grade={verify_result.get('grade')}")

        if baseline:
            info(f"qoder compare started baseline={baseline}")
            compare_command(
                target=generated_root / "content",
                baseline=baseline,
                format="both",
                output=reports_dir,
                ci=True,
            )
            info("qoder compare completed")


@app.command("improve-status")
def improve_status_command(
    output: Path = typer.Option(
        Path(".repo-agent-eval"),
        "--output",
        file_okay=False,
        resolve_path=True,
        help="Eval output root that contains qoder-like runs",
    ),
    run: str | None = typer.Option(
        None,
        "--run",
        help="Run id or run directory. Defaults to the latest run with manifest.json.",
    ),
    limit: int = typer.Option(10, "--limit", help="Number of recent cache entries to include"),
) -> None:
    """Inspect the latest qoder-like improvement run and shared LLM cache."""
    run_dir = _resolve_improve_run(output, run)
    manifest = _read_json_file(run_dir / "manifest.json", {})
    reports_dir = run_dir / "reports"
    compare_report = _read_json_file(reports_dir / "qoder-comparison-report.json", {})
    strict_report = _read_json_file(reports_dir / "strict-verify-output.json", {})

    stats = manifest.get("stats", {}) if isinstance(manifest, dict) else {}
    llm_stats = stats.get("llm", {}) if isinstance(stats, dict) else {}
    cache_path = _resolve_status_cache_path(output, run_dir, llm_stats)
    cache_summary = _read_composer_cache_summary(cache_path, limit=limit)

    content_root = (
        Path(manifest.get("content_root") or run_dir / "content")
        if isinstance(manifest, dict)
        else run_dir / "content"
    )
    status_payload = {
        "run_id": manifest.get("run_id") if isinstance(manifest, dict) else run_dir.name,
        "run_dir": str(run_dir),
        "content_root": str(content_root),
        "content_page_count": _count_markdown_pages(content_root),
        "manifest_path": str(run_dir / "manifest.json"),
        "strict_verify": _summarize_strict_verify(strict_report),
        "qoder_compare": _summarize_qoder_compare(compare_report),
        "llm": {
            "mode": llm_stats.get("mode"),
            "provider": llm_stats.get("effective_provider") or llm_stats.get("requested_provider"),
            "model": llm_stats.get("model"),
            "llm_call_count": llm_stats.get("llm_call_count"),
            "fallback_page_count": llm_stats.get("fallback_page_count"),
            "provider_failure_count": llm_stats.get("provider_failure_count"),
            "provider_disabled_after_failures": llm_stats.get("provider_disabled_after_failures"),
            "attempted_page_ids": llm_stats.get("attempted_page_ids", []),
            "priority_mode": llm_stats.get("priority_mode"),
            "page_timeout_seconds": llm_stats.get("page_timeout_seconds"),
            "compose_concurrency": llm_stats.get("compose_concurrency"),
            "actual_tokens": llm_stats.get("actual_tokens"),
            "actual_cost_usd": llm_stats.get("actual_cost_usd"),
        },
        "composer_cache": cache_summary,
        "reports": {
            "qoder_comparison_markdown": str(reports_dir / "qoder-comparison-report.md"),
            "qoder_comparison_json": str(reports_dir / "qoder-comparison-report.json"),
            "strict_verify_json": str(reports_dir / "strict-verify-output.json"),
        },
    }
    print(json.dumps(status_payload, ensure_ascii=False, indent=2))


def _resolve_release_publish_run(output: Path, run: str | None) -> Path:
    root = output.resolve()
    if run:
        raw = Path(run)
        if raw.is_absolute() or len(raw.parts) != 1:
            candidate = raw if raw.is_absolute() else root / raw
            resolved = candidate.resolve()
            try:
                resolved.relative_to(root)
            except ValueError as exc:
                raise typer.BadParameter(f"run_ref path escapes eval root: {run!r}") from exc
            if not (resolved / "manifest.json").is_file():
                raise typer.BadParameter(f"Run does not contain manifest.json: {resolved}")
            return resolved
    try:
        return select_run(root, run_id=run).resolve()
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command("release-publish")
def release_publish_command(
    output: Path = typer.Option(
        Path(".repo-agent-eval"),
        "--output",
        file_okay=False,
        resolve_path=True,
        help="Eval output root containing qoder-like runs",
    ),
    run: str | None = typer.Option(
        None,
        "--run",
        help="Explicit run id/directory to publish or inspect",
    ),
    inspect_only: bool = typer.Option(
        False,
        "--inspect-only",
        help="Validate candidate run only; do not change current release",
    ),
    review_allowed_signers: Path | None = typer.Option(
        None,
        "--review-allowed-signers",
        dir_okay=False,
        resolve_path=True,
        help="Trusted OpenSSH allowed-signers file outside the run for blind-review attestation",
    ),
) -> None:
    """Publish READY run to fixed `.repo-agent-eval/repowiki/zh` release directory."""
    from repo_wiki.orchestration.release_publisher import (
        ReleasePublishError,
        publish_ready_run,
    )

    eval_root = output.resolve()
    try:
        run_dir = _resolve_release_publish_run(eval_root, run)
        result = publish_ready_run(
            eval_root, run_dir, dry_run=inspect_only, review_allowed_signers=review_allowed_signers
        )
    except (ReleasePublishError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    print(json.dumps(result, ensure_ascii=False, indent=2))


@app.command("quality-gate")
def quality_gate_command(
    output: Path = typer.Option(
        Path(".repo-agent-eval"),
        "--output",
        file_okay=False,
        resolve_path=True,
        help="Eval output root containing qoder-like runs",
    ),
    run: str = typer.Option(..., "--run", help="Exact run id/directory to compile"),
    qoder_comparison: Path = typer.Option(
        Path("reports/qoder-comparison-report.json"),
        "--qoder-comparison",
        dir_okay=False,
        help="Concrete Qoder comparison JSON artifact inside the run",
    ),
    blind_review_v3: Path = typer.Option(
        Path("reports/blind-review-v3.json"),
        "--blind-review-v3",
        dir_okay=False,
        help="Human blind-review-v3 matrix artifact inside the run",
    ),
    acceptance_fixture_registry: Path = typer.Option(
        Path("reports/acceptance-fixture-registry.json"),
        "--acceptance-fixture-registry",
        dir_okay=False,
        help="Acceptance fixture registry artifact inside the run",
    ),
    strict_verify: Path = typer.Option(
        Path("reports/strict-verify-output.json"),
        "--strict-verify",
        dir_okay=False,
        help="Canonical strict verify report inside the run",
    ),
    citation_evidence: Path | None = typer.Option(
        None,
        "--citation-evidence",
        dir_okay=False,
        help="Citation hard-gate evidence artifact; defaults to strict verify report",
    ),
    critical_false_fact_evidence: Path | None = typer.Option(
        None,
        "--critical-false-fact-evidence",
        dir_okay=False,
        help="Critical false-fact evidence artifact; defaults to strict verify report",
    ),
    quality_evidence: Path | None = typer.Option(
        None,
        "--quality-evidence",
        dir_okay=False,
        help="Quality hard-gate evidence artifact; defaults to strict verify report",
    ),
    conflict_evidence: Path | None = typer.Option(
        None,
        "--conflict-evidence",
        dir_okay=False,
        help="Conflict hard-gate evidence artifact; defaults to strict verify report",
    ),
    acceptance_artifact_root: Path | None = typer.Option(
        None,
        "--acceptance-artifact-root",
        file_okay=False,
        resolve_path=True,
        help="Optional root for filesystem hash validation of acceptance baseline artifacts",
    ),
    blind_review_attestation: Path | None = typer.Option(
        None,
        "--blind-review-attestation",
        dir_okay=False,
        help="Detached blind-review attestation JSON inside the run",
    ),
    review_allowed_signers: Path | None = typer.Option(
        None,
        "--review-allowed-signers",
        dir_okay=False,
        resolve_path=True,
        help="Trusted OpenSSH allowed-signers file outside the run for blind-review attestation",
    ),
) -> None:
    """Compile reports/g005-quality-gates.json from real external evidence artifacts."""
    from repo_wiki.orchestration.g005_quality_gate import (
        G005Inputs,
        G005QualityGateError,
        atomic_write_json,
        compile_g005_quality_gate,
    )

    try:
        run_dir = _resolve_release_publish_run(output.resolve(), run)
        inputs = G005Inputs(
            run_dir=run_dir,
            qoder_comparison=qoder_comparison,
            blind_review_v3=blind_review_v3,
            acceptance_fixture_registry=acceptance_fixture_registry,
            strict_verify=strict_verify,
            citation_hard_gate_evidence=citation_evidence,
            critical_false_fact_evidence=critical_false_fact_evidence,
            quality_hard_gate_evidence=quality_evidence,
            conflict_hard_gate_evidence=conflict_evidence,
            acceptance_artifact_root=acceptance_artifact_root,
            blind_review_attestation=blind_review_attestation,
            review_allowed_signers=review_allowed_signers,
        )
        compile_g005_quality_gate(inputs)
        report_rel = "reports/g005-quality-gates.json"
        report_path = run_dir / report_rel

        manifest_path = run_dir / "manifest.json"
        manifest = _read_json_file(manifest_path, {})
        if isinstance(manifest, dict):
            report_paths = manifest.get("report_paths")
            if not isinstance(report_paths, dict):
                report_paths = {}
            report_paths["g005_quality_gates"] = report_rel
            manifest["report_paths"] = report_paths
            files = manifest.get("files")
            if not isinstance(files, list):
                files = []
            if not any(isinstance(item, dict) and item.get("path") == report_rel for item in files):
                files.append({"path": report_rel})
            manifest["files"] = files
            atomic_write_json(manifest_path, manifest)
        bundle = compile_g005_quality_gate(inputs)
        atomic_write_json(report_path, bundle)
    except (G005QualityGateError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    print(
        json.dumps(
            {
                "status": "PASS",
                "run_id": bundle.get("run_id"),
                "report_json": str(report_path),
                "artifact_references": bundle.get("artifact_references", {}),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


@app.command("eval-layout-report")
def eval_layout_report_command(
    output: Path = typer.Option(
        Path(".repo-agent-eval"),
        "--output",
        file_okay=False,
        resolve_path=True,
        help="Eval output root to scan for run layouts",
    ),
) -> None:
    """Print canonical vs legacy content layout per run (diagnostic only, no migration)."""
    from repo_wiki.orchestration.release_publisher import diagnose_eval_run_layouts

    report = diagnose_eval_run_layouts(output.resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))


def _atomic_write_json_file(path: Path, payload: dict[str, Any]) -> None:
    from repo_wiki.orchestration.g005_quality_gate import atomic_write_json

    atomic_write_json(path, payload)


def _find_run_manifest_root(verify_root: Path) -> Path | None:
    current = verify_root.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "manifest.json").is_file():
            return candidate
        if candidate.name == ".repo-agent-eval":
            break
    return None


def _persist_qoder_strict_report(verify_root: Path, result: dict[str, Any]) -> Path | None:
    run_root = _find_run_manifest_root(verify_root)
    if run_root is None:
        return None
    report_rel = "reports/strict-verify-output.json"
    report_path = run_root / report_rel
    payload = dict(result)
    payload["verify_root"] = str(verify_root)
    payload["run_dir"] = str(run_root)
    _atomic_write_json_file(report_path, payload)

    manifest_path = run_root / "manifest.json"
    manifest = _read_json_file(manifest_path, {})
    if isinstance(manifest, dict):
        report_paths = manifest.get("report_paths")
        if not isinstance(report_paths, dict):
            report_paths = {}
        report_paths["strict_verify"] = report_rel
        manifest["report_paths"] = report_paths
        files = manifest.get("files")
        if not isinstance(files, list):
            files = []
        if not any(isinstance(item, dict) and item.get("path") == report_rel for item in files):
            files.append({"path": report_rel})
        manifest["files"] = files
        evidence = manifest.get("evidence")
        if not isinstance(evidence, list):
            evidence = []
        if not any(isinstance(item, dict) and item.get("path") == report_rel for item in evidence):
            evidence.append(
                {
                    "evidence_type": "report",
                    "path": report_rel,
                    "description": "Canonical qoder-like strict verification report",
                    "created_at": payload.get("generated_at", ""),
                }
            )
        manifest["evidence"] = evidence
        _atomic_write_json_file(manifest_path, manifest)
    return report_path


@app.command("verify")
def verify_command(
    profile: str = typer.Option(
        "default", "--profile", help="Verification profile (default, qoder-like)"
    ),
    output: str | None = typer.Option(
        None,
        "--output",
        help="For qoder-like: run id, run dir, or content dir under .repo-agent-eval",
    ),
    ci: bool = typer.Option(False, "--ci", help="CI strict mode (exit non-zero on failure)"),
    config: Path | None = typer.Option(None, "--config"),
) -> None:
    """Run wiki verification checks without regenerating content."""
    cfg = load_config(config)
    if profile == "qoder-like":
        from repo_wiki.verifier.qoder_strict_verifier import verify_qoder_like

        verify_root = _resolve_verify_root(Path(cfg.project.root), output)
        result = verify_qoder_like(verify_root, ci=ci, strict=True)
        result["verify_root"] = str(verify_root)
        if ci:
            strict_report_path = _persist_qoder_strict_report(verify_root, result)
            if strict_report_path is not None:
                result["canonical_report_path"] = str(strict_report_path)
        if result.get("grade") != "PASS":
            result["status"] = "NOT_READY"
    else:
        service = RepoWikiService(cfg)
        result = service.verify(ci=ci)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if ci and (result.get("grade") == "FAIL" or result.get("status") == "NOT_READY"):
        raise typer.Exit(code=1)


@app.command("knowledge-plan-init")
def knowledge_plan_init_command(
    path: Path = typer.Option(
        Path(".repo-wiki/knowledge-plan.yaml"),
        "--path",
        help="Knowledge plan file to create",
    ),
    repo_root: Path = typer.Option(Path("."), "--repo-root", file_okay=False),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing plan"),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable output"),
) -> None:
    """Create a knowledge plan from cached KM data, or a minimal default."""
    repo_root = repo_root.resolve()
    plan_path = _resolve_plan_path(repo_root, path)
    plan = _generate_knowledge_plan_for_repo(repo_root)
    written = _write_knowledge_plan(plan, plan_path, force=force)
    _print_knowledge_plan_result(
        {"status": "created", "path": str(plan_path), "plan": written},
        json_output=json_output,
    )


@app.command("knowledge-plan-generate")
def knowledge_plan_generate_command(
    path: Path = typer.Option(
        Path(".repo-wiki/knowledge-plan.yaml"),
        "--path",
        help="Knowledge plan file to write",
    ),
    repo_root: Path = typer.Option(Path("."), "--repo-root", file_okay=False),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing plan"),
    stdout: bool = typer.Option(False, "--stdout", help="Print generated plan without writing"),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable write output"),
) -> None:
    """Regenerate a knowledge plan from cached KM data."""
    repo_root = repo_root.resolve()
    plan_path = _resolve_plan_path(repo_root, path)
    plan = _generate_knowledge_plan_for_repo(repo_root)
    if stdout:
        from repo_wiki.knowledge_plan import dump_plan_yaml

        print(dump_plan_yaml(plan), end="")
        return
    written = _write_knowledge_plan(plan, plan_path, force=force)
    _print_knowledge_plan_result(
        {"status": "written", "path": str(plan_path), "plan": written},
        json_output=json_output,
    )


@app.command("knowledge-plan-validate")
def knowledge_plan_validate_command(
    path: Path = typer.Option(
        Path(".repo-wiki/knowledge-plan.yaml"),
        "--path",
        dir_okay=False,
        help="Knowledge plan file to validate",
    ),
    repo_root: Path = typer.Option(Path("."), "--repo-root", file_okay=False),
    ci: bool = typer.Option(False, "--ci", help="Exit non-zero on error issues"),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable output"),
) -> None:
    """Validate a knowledge plan and report issues."""
    repo_root = repo_root.resolve()
    plan_path = _resolve_plan_path(repo_root, path)
    if not plan_path.exists():
        raise typer.BadParameter(f"Knowledge plan does not exist: {plan_path}")
    from repo_wiki.knowledge_plan import load_plan, validate_plan

    issues = validate_plan(load_plan(plan_path))
    result_dict = {
        "valid": not any(issue.severity == "error" for issue in issues),
        "issues": [issue.as_dict() for issue in issues],
    }
    _print_knowledge_plan_result(result_dict, json_output=json_output)
    if ci and _knowledge_plan_has_errors(result_dict):
        raise typer.Exit(code=1)


@app.command("knowledge-plan-impact")
def knowledge_plan_impact_command(
    path: Path = typer.Option(
        Path(".repo-wiki/knowledge-plan.yaml"),
        "--path",
        dir_okay=False,
        help="Knowledge plan file to inspect",
    ),
    baseline: Path | None = typer.Option(
        None,
        "--baseline",
        dir_okay=False,
        help="Baseline plan path; when omitted, core may use current KM diff data",
    ),
    repo_root: Path = typer.Option(Path("."), "--repo-root", file_okay=False),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable output"),
) -> None:
    """Report pages, templates, docs, domains, and directories impacted by plan changes."""
    repo_root = repo_root.resolve()
    plan_path = _resolve_plan_path(repo_root, path)
    baseline_path = _resolve_plan_path(repo_root, baseline) if baseline is not None else None
    if not plan_path.exists():
        raise typer.BadParameter(f"Knowledge plan does not exist: {plan_path}")
    if baseline_path is not None and not baseline_path.exists():
        raise typer.BadParameter(f"Baseline knowledge plan does not exist: {baseline_path}")
    from repo_wiki.knowledge_plan import analyze_impact, load_plan

    current = load_plan(plan_path)
    baseline_plan = load_plan(baseline_path) if baseline_path is not None else None
    result_dict = analyze_impact(old_plan=baseline_plan, new_plan=current)
    _print_knowledge_plan_result(result_dict, json_output=json_output)


@app.command("compare")
def compare_command(
    target: Path = typer.Option(..., "--target", exists=True, file_okay=False, resolve_path=True),
    baseline: Path = typer.Option(
        ..., "--baseline", exists=True, file_okay=False, resolve_path=True
    ),
    format: str = typer.Option("both", "--format", help="markdown,json,both"),
    output: Path = typer.Option(..., "--output", file_okay=False, resolve_path=True),
    ci: bool = typer.Option(False, "--ci", help="Exit non-zero when NOT_READY"),
) -> None:
    """Compare repo-agent output with qoder baseline and emit report artifacts."""
    from repo_wiki.orchestration.readiness_schema import evaluate_replacement_readiness_v2
    from repo_wiki.verifier.qoder_baseline_registry import (
        baseline_unchanged,
        register_single_qoder_baseline,
    )
    from repo_wiki.verifier.qoder_comparator_paths import create_repaired_comparator
    from repo_wiki.verifier.qoder_parity_metrics import create_parity_report
    from repo_wiki.verifier.qoder_strict_verifier import verify_qoder_like

    requested_formats = _normalize_formats(format)
    try:
        baseline_entry = register_single_qoder_baseline(target_root=target, baseline_root=baseline)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    baseline = baseline_entry.root

    comparator = create_repaired_comparator(target, baseline)
    path_result = comparator.compare()

    parity_report = create_parity_report(target, baseline_root=baseline)
    parity_dict = parity_report.to_dict()
    metrics_by_name = {m["metric_name"]: m for m in parity_dict.get("metrics", [])}

    strict_result = verify_qoder_like(target, ci=True, strict=True)
    stale_git = _compute_stale_git(target, baseline)
    pages_target = _count_markdown_pages(target)
    pages_baseline = _count_markdown_pages(baseline)
    chinese_depth = _compute_chinese_directory_depth(target, baseline)
    file_line = _compute_file_line_citation_coverage(target)
    llm_generation = _compute_llm_generation_coverage(target)

    report_json = {
        "target": str(target),
        "baseline": str(baseline),
        "baseline_registry": {
            "source": baseline_entry.source,
            "root": str(baseline_entry.root),
            "fingerprint": baseline_entry.fingerprint,
            "file_count": baseline_entry.file_count,
            "immutable": baseline_entry.immutable,
        },
        "status": "READY",
        "strict_verify": strict_result,
        "path_comparison": path_result,
        "metrics": {
            "page_count": {
                "target": pages_target,
                "baseline": pages_baseline,
                "delta": pages_target - pages_baseline,
                "ratio_vs_baseline": round((pages_target / pages_baseline), 4)
                if pages_baseline
                else None,
            },
            "chinese_directory_depth": chinese_depth,
            "toc_coverage": _metric_score(metrics_by_name.get("toc_presence")),
            "citation_coverage": _metric_score(metrics_by_name.get("citation_coverage")),
            "file_line_reference_coverage": file_line,
            "mermaid_coverage": _metric_score(metrics_by_name.get("mermaid_presence")),
            "prose_list_ratio": _metric_score(metrics_by_name.get("prose_list_ratio")),
            "api_aggregation_quality": _metric_score(metrics_by_name.get("api_aggregation")),
            "data_model_aggregation_quality": _metric_score(
                metrics_by_name.get("data_model_aggregation")
            ),
            "broken_links": _broken_links(metrics_by_name.get("file_reference_integrity")),
            "stale_git_commit": stale_git,
            "llm_generation_coverage": llm_generation,
        },
        "parity_summary": parity_dict.get("summary", {}),
        "parity_blocked": parity_dict.get("blocked", False),
    }

    baseline_untouched = baseline_unchanged(baseline_entry)
    report_json["baseline_read_only_verified"] = baseline_untouched
    readiness_failures = _compare_readiness_failures(report_json)
    manual_review_result = _load_manual_review_result(target=target, output_dir=output)
    comparison_status = "READY"
    if parity_dict.get("blocked") or readiness_failures:
        comparison_status = "NOT_READY"
    report_json["readiness_gates"] = {
        "status": "PASS" if comparison_status == "READY" else "FAIL",
        "failures": readiness_failures,
        "thresholds": {
            "page_count_ratio_vs_baseline": 0.80,
            "chinese_directory_depth_ratio_vs_baseline": 0.70,
            "llm_generation_coverage": 0.80,
            "baseline_read_only_verified": True,
        },
    }
    report_json["manual_review"] = manual_review_result

    replacement_readiness = evaluate_replacement_readiness_v2(
        strict_verify=strict_result,
        comparison_result={
            "status": comparison_status,
            "readiness_gates": report_json["readiness_gates"],
        },
        manual_review_result=manual_review_result,
    )
    report_json["replacement_readiness"] = replacement_readiness
    report_json["status"] = replacement_readiness["readiness_state"]
    report_json["readiness_reasons"] = replacement_readiness["readiness_reasons"]

    output.mkdir(parents=True, exist_ok=True)
    md_path = output / "qoder-comparison-report.md"
    json_path = output / "qoder-comparison-report.json"

    if "markdown" in requested_formats:
        md_path.write_text(_render_compare_markdown(report_json), encoding="utf-8")
    if "json" in requested_formats:
        json_path.write_text(
            json.dumps(report_json, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    print(
        json.dumps(
            {
                "status": report_json["status"],
                "report_markdown": str(md_path) if "markdown" in requested_formats else None,
                "report_json": str(json_path) if "json" in requested_formats else None,
                "baseline_read_only_verified": baseline_untouched,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    if ci and report_json["status"] != "READY":
        raise typer.Exit(code=1)


@app.command("cost-estimate")
def cost_estimate_command(config: Path | None = typer.Option(None, "--config")) -> None:
    cfg = load_config(config)
    service = RepoWikiService(cfg)
    result = service.cost_estimate()
    print(json.dumps(result, ensure_ascii=False, indent=2))


@app.command("config")
def config_command(
    provider: str = typer.Option(None, "--provider", help="LLM provider (openai, minimax)"),
    model: str = typer.Option(None, "--model", help="Model identifier"),
    base_url: str = typer.Option(None, "--base-url", help="API base URL"),
    api_key_env: str = typer.Option(None, "--api-key-env", help="Environment variable for API key"),
    max_tokens: int = typer.Option(None, "--max-tokens", help="Max tokens in response"),
    temperature: float = typer.Option(None, "--temperature", help="Sampling temperature"),
    timeout: float = typer.Option(None, "--timeout", help="Request timeout in seconds"),
    max_retries: int = typer.Option(None, "--max-retries", help="Max retry attempts"),
    ci: bool = typer.Option(False, "--ci", help="Machine-readable JSON output"),
    config: Path | None = typer.Option(None, "--config", help="Config file path"),
) -> None:
    """Run LLM configuration diagnostics.

    Validates provider/model/base_url/api_key_env/budget fields and outputs reason codes.
    All secrets are redacted in terminal and JSON outputs.
    """
    # Build overrides from CLI flags
    cli_overrides: dict[str, Any] = {}
    if provider is not None:
        cli_overrides["provider"] = provider
    if model is not None:
        cli_overrides["model"] = model
    if base_url is not None:
        cli_overrides["base_url"] = base_url
    if api_key_env is not None:
        cli_overrides["api_key_env"] = api_key_env
    if max_tokens is not None:
        cli_overrides["max_tokens"] = max_tokens
    if temperature is not None:
        cli_overrides["temperature"] = temperature
    if timeout is not None:
        cli_overrides["timeout"] = timeout
    if max_retries is not None:
        cli_overrides["max_retries"] = max_retries

    # Load base config
    try:
        base_cfg = load_config(config)
        llm_config_dict = base_cfg.llm.model_dump() if hasattr(base_cfg, "llm") else {}
    except Exception:
        llm_config_dict = {}

    # Resolve with CLI overrides
    resolved_config, warnings = resolve_llm_config(
        config=llm_config_dict, cli_overrides=cli_overrides
    )

    # Run diagnostics
    diagnostics = run_llm_diagnostics(config=resolved_config, json_output=ci)

    if ci:
        print(format_diagnostics_json(diagnostics))
    else:
        print(format_diagnostics_text(diagnostics))

    # Exit with error code if issues found
    if diagnostics["summary"] == "FAIL":
        raise typer.Exit(code=1)


def _run_with_service(
    action: str,
    config: Path | None,
    eval_profile: Any = None,
    run_id: str | None = None,
) -> None:
    try:
        cfg = load_config(config)
        service = RepoWikiService(cfg)
        if action == "generate" and eval_profile is not None:
            result = service.generate(eval_profile=eval_profile, run_id=run_id)
        else:
            result = getattr(service, action)()
        info(f"{action} completed")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except RepoWikiError as exc:
        error(f"{exc.category.value}: {exc.message}")
        if exc.details:
            print(json.dumps(exc.details, ensure_ascii=False, indent=2))
        raise typer.Exit(code=1)


def _resolve_plan_path(repo_root: Path, path: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    return (repo_root / path).resolve()


def _refuse_existing_plan(path: Path, *, force: bool) -> None:
    if path.exists() and not force:
        raise typer.BadParameter(
            f"Refusing to overwrite existing knowledge plan without --force: {path}"
        )


def _minimal_knowledge_model_v3() -> dict[str, Any]:
    return {
        "schema_version": "repo_agent.knowledge_model_v3/1.0",
        "input_fingerprints": {},
        "summary": {},
        "records": {},
    }


def _load_knowledge_model_for_plan(repo_root: Path) -> dict[str, Any]:
    from repo_wiki.scanner import load_knowledge_model_v3

    model = load_knowledge_model_v3(repo_root)
    if isinstance(model, dict):
        return model
    return _minimal_knowledge_model_v3()


def _generate_knowledge_plan_for_repo(repo_root: Path) -> dict[str, Any]:
    from repo_wiki.knowledge_plan import generate_plan

    return generate_plan(_load_knowledge_model_for_plan(repo_root))


def _write_knowledge_plan(plan: dict[str, Any], path: Path, *, force: bool) -> dict[str, Any]:
    from repo_wiki.knowledge_plan import ManualEditConflictError, load_plan, write_plan

    if path.exists() and not force:
        try:
            existing = load_plan(path)
        except Exception as exc:
            raise typer.BadParameter(
                f"Refusing to overwrite existing knowledge plan without --force: {path}"
            ) from exc
        if not _is_managed_knowledge_plan(existing):
            raise typer.BadParameter(
                f"Refusing to overwrite existing knowledge plan without --force: {path}"
            )

    try:
        return write_plan(plan, path, overwrite=force)
    except ManualEditConflictError as exc:
        raise typer.BadParameter(f"{exc} Use --force to overwrite.") from exc


def _is_managed_knowledge_plan(plan: dict[str, Any]) -> bool:
    generated = plan.get("generated")
    return isinstance(generated, dict) and isinstance(generated.get("fingerprint"), str)


def _knowledge_plan_call(action: str, **kwargs: Any) -> Any:
    try:
        import importlib

        module = importlib.import_module("repo_wiki.knowledge_plan")
    except ModuleNotFoundError as exc:
        if exc.name != "repo_wiki.knowledge_plan":
            raise
        raise typer.BadParameter(
            "repo_wiki.knowledge_plan is not available yet; run after the core package is present"
        ) from exc

    service_cls = getattr(module, "KnowledgePlanService", None)
    if service_cls is not None:
        service = _instantiate_knowledge_plan_service(service_cls, kwargs)
        method = getattr(service, action, None) or getattr(
            service, f"{action}_knowledge_plan", None
        )
        if method is not None:
            return _invoke_knowledge_plan_callable(method, kwargs)

    candidates = [
        f"{action}_knowledge_plan",
        f"knowledge_plan_{action}",
        action,
    ]
    for name in candidates:
        fn = getattr(module, name, None)
        if fn is not None:
            return _invoke_knowledge_plan_callable(fn, kwargs)
    raise typer.BadParameter(
        "repo_wiki.knowledge_plan does not expose an expected "
        f"{action!r} API ({', '.join(candidates)} or KnowledgePlanService.{action})"
    )


def _instantiate_knowledge_plan_service(service_cls: Any, kwargs: dict[str, Any]) -> Any:
    repo_root = kwargs.get("repo_root")
    try:
        return service_cls(repo_root=repo_root)
    except TypeError:
        try:
            return service_cls(repo_root)
        except TypeError:
            return service_cls()


def _invoke_knowledge_plan_callable(fn: Any, kwargs: dict[str, Any]) -> Any:
    import inspect

    signature = inspect.signature(fn)
    if any(param.kind is inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()):
        return fn(**kwargs)
    accepted = {
        name: value
        for name, value in kwargs.items()
        if name in signature.parameters
        and signature.parameters[name].kind
        in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    }
    return fn(**accepted)


def _write_knowledge_plan_result(result: Any, path: Path) -> None:
    if _result_declares_written_path(result):
        return
    text = _extract_knowledge_plan_text(result)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _result_declares_written_path(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    return bool(result.get("path") or result.get("plan_path") or result.get("written_path"))


def _extract_knowledge_plan_text(result: Any) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, bytes):
        return result.decode("utf-8")
    if isinstance(result, dict):
        for key in ("content", "yaml", "plan_yaml", "text"):
            value = result.get(key)
            if isinstance(value, str):
                return value
        plan = result.get("plan")
        if isinstance(plan, str):
            return plan
        if plan is not None:
            return _dump_knowledge_plan_yaml(plan)
        return _dump_knowledge_plan_yaml(result)
    if hasattr(result, "to_yaml"):
        value = result.to_yaml()
        if isinstance(value, str):
            return value
    if hasattr(result, "model_dump"):
        return _dump_knowledge_plan_yaml(result.model_dump())
    if hasattr(result, "dict"):
        return _dump_knowledge_plan_yaml(result.dict())
    return str(result)


def _dump_knowledge_plan_yaml(value: Any) -> str:
    import yaml

    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False)


def _ensure_dict_result(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        return result
    if hasattr(result, "model_dump"):
        dumped = result.model_dump()
        if isinstance(dumped, dict):
            return dumped
    if hasattr(result, "dict"):
        dumped = result.dict()
        if isinstance(dumped, dict):
            return dumped
    return {"result": result}


def _knowledge_plan_has_errors(result: dict[str, Any]) -> bool:
    if result.get("valid") is False or result.get("status") in {"error", "failed", "invalid"}:
        return True
    issues = result.get("issues", [])
    if not isinstance(issues, list):
        return False
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        severity = str(issue.get("severity") or issue.get("level") or "").lower()
        if severity == "error":
            return True
    return False


def _print_knowledge_plan_result(result: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    for line in _format_knowledge_plan_human(result):
        print(line)


def _format_knowledge_plan_human(result: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    status = result.get("status") or ("valid" if result.get("valid") is True else None)
    if status is not None:
        lines.append(f"status: {status}")
    if result.get("path"):
        lines.append(f"path: {result['path']}")
    issues = result.get("issues", [])
    if isinstance(issues, list) and issues:
        lines.append("issues:")
        for issue in issues:
            if isinstance(issue, dict):
                severity = issue.get("severity") or issue.get("level") or "info"
                code = issue.get("code") or issue.get("id") or "issue"
                message = issue.get("message") or issue.get("detail") or ""
                lines.append(f"- [{severity}] {code}: {message}")
            else:
                lines.append(f"- {issue}")
    elif "issues" in result:
        lines.append("issues: none")

    impacted = result.get("impacted", result)
    if isinstance(impacted, dict):
        for key in ("directories", "pages", "templates", "domains", "docs"):
            value = (
                impacted.get(key)
                or impacted.get(f"changed_{key}")
                or impacted.get(f"impacted_{key}")
            )
            if value:
                lines.append(f"{key}:")
                for item in value if isinstance(value, list) else [value]:
                    lines.append(f"- {item}")
    if not lines:
        lines.append(json.dumps(result, ensure_ascii=False, indent=2))
    return lines


def _jsonable_knowledge_result(result: Any) -> Any:
    if isinstance(result, (str, int, float, bool)) or result is None:
        return result
    if isinstance(result, bytes):
        return result.decode("utf-8", errors="replace")
    if isinstance(result, dict):
        return result
    if hasattr(result, "model_dump"):
        return result.model_dump()
    if hasattr(result, "dict"):
        return result.dict()
    return str(result)


class _temporary_env:
    def __init__(self, updates: dict[str, str]) -> None:
        self.updates = updates
        self.previous: dict[str, str | None] = {}

    def __enter__(self) -> None:
        for key, value in self.updates.items():
            self.previous[key] = os.environ.get(key)
            os.environ[key] = value

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _resolve_verify_root(project_root: Path, output: str | None) -> Path:
    if not output:
        return project_root
    raw = Path(output)
    if raw.exists():
        resolved = raw.resolve()
        if (resolved / "manifest.json").is_file():
            return resolved
        try:
            return select_run(resolved).resolve()
        except ValueError:
            return resolved
    # run-id mode: nested qoder-like layout under .repo-agent-eval/runs/<id>/
    nested = project_root / ".repo-agent-eval" / "runs" / output
    if nested.exists():
        return nested.resolve()
    candidate = project_root / ".repo-agent-eval" / output
    if candidate.exists():
        return candidate.resolve()
    # Prefer nested contract path for new runs when neither exists yet
    return nested.resolve()


def _resolve_improve_run(output: Path, run: str | None) -> Path:
    root = output.resolve()
    raw = Path(run).resolve() if run and Path(run).exists() else None
    if raw:
        if not (raw / "manifest.json").exists():
            raise typer.BadParameter(f"Run does not contain manifest.json: {raw}")
        return raw
    try:
        return select_run(root, run_id=run).resolve()
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _read_json_file(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _resolve_status_cache_path(output: Path, run_dir: Path, llm_stats: dict[str, Any]) -> Path:
    raw = llm_stats.get("composer_cache_path") if isinstance(llm_stats, dict) else None
    if isinstance(raw, str) and raw:
        return Path(raw).resolve()
    return (output.resolve() / ".runtime" / "composer_cache.sqlite3").resolve()


def _read_composer_cache_summary(cache_path: Path, limit: int) -> dict[str, Any]:
    if not cache_path.exists():
        return {
            "path": str(cache_path),
            "exists": False,
            "stats": None,
            "recent_entries": [],
        }
    from repo_wiki.generator.composer_cache import ComposerCache

    cache = ComposerCache(cache_path)
    stats = cache.stats()
    entries = cache.list_entries(limit=max(limit, 0))
    return {
        "path": str(cache_path),
        "exists": True,
        "stats": {
            "total_entries": stats.total_entries,
            "cache_hits": stats.cache_hits,
            "cache_misses": stats.cache_misses,
            "skipped_pages": getattr(stats, "skipped_pages", 0),
            "regenerated_pages": getattr(stats, "regenerated_pages", 0),
            "total_tokens_saved": stats.total_tokens_saved,
            "total_cost_saved_usd": stats.total_cost_saved_usd,
        },
        "recent_entries": [
            {
                "page_id": entry.page_id,
                "doc_type": entry.doc_type,
                "model_name": entry.model_name,
                "tokens_used": entry.tokens_used,
                "cost_usd": entry.cost_usd,
                "cached_at": entry.cached_at,
                "output_hash": entry.output_hash,
            }
            for entry in entries
        ],
    }


def _summarize_strict_verify(report: dict[str, Any]) -> dict[str, Any]:
    if not report:
        return {"available": False}
    return {
        "available": True,
        "grade": report.get("grade"),
        "status": report.get("status"),
        "summary": report.get("summary"),
        "failure_count": len(report.get("failures", []))
        if isinstance(report.get("failures"), list)
        else None,
        "warning_count": len(report.get("warnings", []))
        if isinstance(report.get("warnings"), list)
        else None,
    }


def _summarize_qoder_compare(report: dict[str, Any]) -> dict[str, Any]:
    if not report:
        return {"available": False}
    metrics = report.get("metrics", {}) if isinstance(report.get("metrics"), dict) else {}
    page_count = (
        metrics.get("page_count", {}) if isinstance(metrics.get("page_count"), dict) else {}
    )
    return {
        "available": True,
        "status": report.get("status"),
        "target": report.get("target"),
        "baseline": report.get("baseline"),
        "baseline_read_only_verified": report.get("baseline_read_only_verified"),
        "page_count": page_count,
        "parity_summary": report.get("parity_summary"),
    }


def _normalize_formats(value: str) -> set[str]:
    normalized = value.strip().lower()
    if normalized == "both":
        return {"markdown", "json"}
    items = {part.strip() for part in normalized.split(",") if part.strip()}
    valid = {"markdown", "json"}
    unknown = items - valid
    if unknown:
        raise typer.BadParameter(f"Unsupported format value(s): {', '.join(sorted(unknown))}")
    if not items:
        return {"markdown", "json"}
    return items


def _hash_tree(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.exists():
        return digest.hexdigest()
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        digest.update(rel.encode("utf-8"))
        if path.is_file():
            try:
                digest.update(path.read_bytes())
            except OSError:
                continue
    return digest.hexdigest()


def _count_markdown_pages(root: Path) -> int:
    return len(list(root.rglob("*.md"))) if root.exists() else 0


def _compute_chinese_directory_depth(target: Path, baseline: Path) -> dict[str, Any]:
    def calc(root: Path) -> int:
        max_depth = 0
        for md in root.rglob("*.md"):
            try:
                rel = md.relative_to(root)
            except ValueError:
                continue
            depth = len(rel.parts) - 1
            if depth > max_depth:
                max_depth = depth
        return max_depth

    t = calc(target)
    b = calc(baseline)
    ratio = round((t / b), 4) if b else None
    return {"target_depth": t, "baseline_depth": b, "ratio_vs_baseline": ratio}


def _compare_readiness_failures(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Return hard comparison gate failures against the Qoder baseline."""
    failures: list[dict[str, Any]] = []
    metrics = report.get("metrics", {})

    page_ratio = metrics.get("page_count", {}).get("ratio_vs_baseline")
    if page_ratio is not None and page_ratio < 0.80:
        failures.append(
            {
                "code": "QODER_PAGE_COVERAGE_LOW",
                "message": "Generated page count is below 80% of Qoder baseline",
                "actual": page_ratio,
                "threshold": 0.80,
            }
        )

    depth = metrics.get("chinese_directory_depth", {})
    depth_ratio = depth.get("ratio_vs_baseline")
    baseline_depth = depth.get("baseline_depth")
    if baseline_depth and depth_ratio is not None and depth_ratio < 0.70:
        failures.append(
            {
                "code": "QODER_DIRECTORY_DEPTH_LOW",
                "message": "Generated Chinese directory hierarchy is shallower than Qoder baseline",
                "actual": depth_ratio,
                "threshold": 0.70,
            }
        )

    if report.get("baseline_read_only_verified") is False:
        failures.append(
            {
                "code": "QODER_BASELINE_MODIFIED",
                "message": "Qoder baseline changed during comparison",
                "actual": False,
                "threshold": True,
            }
        )

    llm_coverage = metrics.get("llm_generation_coverage", {}).get("coverage")
    if llm_coverage is not None and llm_coverage < 0.80:
        failures.append(
            {
                "code": "QODER_LLM_COVERAGE_LOW",
                "message": "LLM-composed plus cached page coverage is below 80%",
                "actual": llm_coverage,
                "threshold": 0.80,
            }
        )

    path_comparison = report.get("path_comparison", {})
    required_counterpart_failures = path_comparison.get("required_counterpart_failures", [])
    for failure in required_counterpart_failures:
        if not isinstance(failure, dict):
            continue
        failure_type = failure.get("failure_type")
        code = (
            "QODER_REQUIRED_COUNTERPART_QUALITY_LOW"
            if failure_type == "quality_low"
            else "QODER_REQUIRED_COUNTERPART_MISSING"
        )
        failures.append(
            {
                "code": code,
                "message": failure.get("message", "Missing required baseline counterpart page"),
                "actual": failure.get("baseline_matches", []),
                "threshold": failure.get("required_prefixes", []),
                "rule_id": failure.get("rule_id"),
                "pair_score": failure.get("pair_score"),
            }
        )

    return failures


def _compute_file_line_citation_coverage(root: Path) -> dict[str, Any]:
    cite = re.compile(r"<cite>[^<]*:[0-9]+(?:-[0-9]+)?[^<]*</cite>")
    link = re.compile(r"\[[^\]]+\]\((?:\./)?[^)]+#L?[0-9]+(?:-L?[0-9]+)?\)")
    pages = list(root.rglob("*.md")) if root.exists() else []
    covered = 0
    for page in pages:
        try:
            text = page.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if cite.search(text) or link.search(text):
            covered += 1
    coverage = round((covered / len(pages)), 4) if pages else 0.0
    return {"pages_with_file_line_refs": covered, "total_pages": len(pages), "coverage": coverage}


def _compute_llm_generation_coverage(target: Path) -> dict[str, Any]:
    manifest_path = (
        target.parent / "manifest.json" if target.name == "content" else target / "manifest.json"
    )
    if not manifest_path.exists():
        return {"coverage": None, "status": "missing", "manifest": None}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return {"coverage": None, "status": "invalid", "manifest": str(manifest_path)}

    generation = (
        manifest.get("generation") or manifest.get("generate") or manifest.get("stats") or {}
    )
    llm = generation.get("llm") if isinstance(generation, dict) else {}
    if not isinstance(llm, dict):
        return {"coverage": None, "status": "missing", "manifest": str(manifest_path)}

    page_count = (
        llm.get("composed_page_count")
        or generation.get("planned_pages")
        or manifest.get("file_count")
        or _count_markdown_pages(target)
    )
    llm_pages = int(llm.get("llm_call_count") or 0) + int(llm.get("cache_hits") or 0)
    coverage = round((llm_pages / page_count), 4) if page_count else 0.0
    return {
        "coverage": coverage,
        "status": "pass" if coverage >= 0.80 else "fail",
        "llm_pages": llm_pages,
        "page_count": page_count,
        "llm_call_count": llm.get("llm_call_count"),
        "cache_hits": llm.get("cache_hits"),
        "fallback_page_count": llm.get("fallback_page_count"),
        "manifest": str(manifest_path),
    }


def _metric_score(metric: dict[str, Any] | None) -> dict[str, Any]:
    if not metric:
        return {"score": None, "status": "missing"}
    return {
        "score": metric.get("measured_value"),
        "status": metric.get("status"),
        "threshold": metric.get("threshold"),
    }


def _broken_links(metric: dict[str, Any] | None) -> dict[str, Any]:
    if not metric:
        return {"count": None, "status": "missing"}
    details = metric.get("details", {})
    broken = details.get("broken_refs", []) if isinstance(details, dict) else []
    return {"count": len(broken), "status": metric.get("status"), "examples": broken[:10]}


def _compute_stale_git(target: Path, baseline: Path) -> dict[str, Any]:
    current = _git_commit(target)
    target_commit = _find_manifest_commit(target)
    baseline_commit = _find_manifest_commit(baseline)
    target_stale = bool(
        current
        and target_commit
        and not (current.startswith(target_commit) or target_commit.startswith(current))
    )
    baseline_stale = bool(
        current
        and baseline_commit
        and not (current.startswith(baseline_commit) or baseline_commit.startswith(current))
    )
    return {
        "current_repo_commit": current,
        "target_wiki_commit": target_commit,
        "baseline_wiki_commit": baseline_commit,
        "target_is_stale": target_stale,
        "baseline_is_stale": baseline_stale,
    }


def _git_commit(path: Path) -> str | None:
    cwd = _find_git_root(path)
    if cwd is None:
        return None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=True,
        )
    except Exception:
        return None
    value = result.stdout.strip()
    return value or None


def _find_git_root(path: Path) -> Path | None:
    current = path if path.is_dir() else path.parent
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists():
            return candidate
    return None


def _find_manifest_commit(root: Path) -> str | None:
    candidates = [
        root / "manifest.json",
        root.parent / "manifest.json",
        root / "meta.json",
        root / "metadata.json",
    ]
    for c in candidates:
        if not c.exists() or not c.is_file():
            continue
        try:
            payload = json.loads(c.read_text(encoding="utf-8"))
        except Exception:
            continue
        for key in ("wiki_git_commit", "target_git_commit", "commit_hash", "git_commit", "commit"):
            value = payload.get(key) if isinstance(payload, dict) else None
            if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{7,40}", value):
                return value
    return None


def _render_compare_markdown(report: dict[str, Any]) -> str:
    m = report.get("metrics", {})
    page = m.get("page_count", {})
    depth = m.get("chinese_directory_depth", {})
    toc = m.get("toc_coverage", {})
    citation = m.get("citation_coverage", {})
    fl = m.get("file_line_reference_coverage", {})
    mermaid = m.get("mermaid_coverage", {})
    prose = m.get("prose_list_ratio", {})
    api = m.get("api_aggregation_quality", {})
    dm = m.get("data_model_aggregation_quality", {})
    broken = m.get("broken_links", {})
    stale = m.get("stale_git_commit", {})
    llm = m.get("llm_generation_coverage", {})
    gates = report.get("readiness_gates", {})
    failures = gates.get("failures", []) if isinstance(gates, dict) else []
    replacement = report.get("replacement_readiness", {})
    readiness_reasons = report.get("readiness_reasons", [])
    manual_review = report.get("manual_review", {})
    manual_summary = manual_review.get("summary", {}) if isinstance(manual_review, dict) else {}
    lines = [
        "# Qoder Comparison Report",
        "",
        f"- Status: **{report.get('status', 'UNKNOWN')}**",
        f"- Target: `{report.get('target', '')}`",
        f"- Baseline: `{report.get('baseline', '')}`",
        "",
        "| 指标 | 目标值 | 基线值 | 说明 |",
        "|---|---:|---:|---|",
        f"| 页面数量 | {page.get('target')} | {page.get('baseline')} | ratio={page.get('ratio_vs_baseline')} |",
        f"| 中文目录深度 | {depth.get('target_depth')} | {depth.get('baseline_depth')} | ratio={depth.get('ratio_vs_baseline')} |",
        f"| TOC 覆盖 | {toc.get('score')} | - | status={toc.get('status')} |",
        f"| citation 覆盖 | {citation.get('score')} | - | status={citation.get('status')} |",
        f"| file/line 引用覆盖 | {fl.get('coverage')} | - | pages={fl.get('pages_with_file_line_refs')}/{fl.get('total_pages')} |",
        f"| Mermaid 覆盖 | {mermaid.get('score')} | - | status={mermaid.get('status')} |",
        f"| prose/list ratio | {prose.get('score')} | - | status={prose.get('status')} |",
        f"| API 聚合质量 | {api.get('score')} | - | status={api.get('status')} |",
        f"| Data Model 聚合质量 | {dm.get('score')} | - | status={dm.get('status')} |",
        f"| broken links | {broken.get('count')} | - | status={broken.get('status')} |",
        f"| LLM 生成覆盖 | {llm.get('coverage')} | - | pages={llm.get('llm_pages')}/{llm.get('page_count')} status={llm.get('status')} |",
        f"| stale git commit | target_stale={stale.get('target_is_stale')} | baseline_stale={stale.get('baseline_is_stale')} | current={stale.get('current_repo_commit')} |",
        "",
        "## Readiness Gates",
        "",
        f"- Gate status: **{gates.get('status', 'UNKNOWN') if isinstance(gates, dict) else 'UNKNOWN'}**",
        f"- Baseline read-only verified: **{report.get('baseline_read_only_verified')}**",
        "",
    ]
    if failures:
        lines.extend(
            [
                "| Code | Actual | Threshold | Message |",
                "|---|---:|---:|---|",
            ]
        )
        for failure in failures:
            lines.append(
                f"| {failure.get('code')} | {failure.get('actual')} | {failure.get('threshold')} | {failure.get('message')} |"
            )
        lines.append("")
    else:
        lines.extend(["No comparison gate failures.", ""])
    lines.extend(
        [
            "## Replacement Readiness v2",
            "",
            f"- replacement_go: **{replacement.get('replacement_go')}**",
            f"- strict_verify_pass: **{replacement.get('checks', {}).get('strict_verify_pass')}**",
            f"- qoder_comparison_ready: **{replacement.get('checks', {}).get('qoder_comparison_ready')}**",
            f"- manual_review_pass: **{replacement.get('checks', {}).get('manual_review_pass')}**",
            f"- manual_review_status: `{manual_summary.get('status', 'MISSING')}`",
        ]
    )
    if isinstance(readiness_reasons, list) and readiness_reasons:
        lines.append("- readiness_reasons:")
        for reason in readiness_reasons:
            lines.append(f"  - `{reason}`")
    else:
        lines.append("- readiness_reasons: none")
    lines.append("")
    lines.extend(
        [
            "## Strict Verify",
            "",
            "```json",
            json.dumps(report.get("strict_verify", {}), ensure_ascii=False, indent=2),
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def _load_manual_review_result(target: Path, output_dir: Path) -> dict[str, Any] | None:
    candidates = [
        output_dir / "manual-review-matrix-v2.json",
        target.parent / "reports" / "manual-review-matrix-v2.json",
        target.parent / "manual-review-matrix-v2.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict):
            return payload
    return None
