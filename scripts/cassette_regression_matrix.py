#!/usr/bin/env python3
"""Replay handbook cassettes and score the no-regression matrix.

Runs offline ``generate`` (LLM_PROVIDER=cassette), ``handbook_acceptance.py``,
``cite_relevance.py --strict``, and ``repo-wiki verify --ci`` for every
cassette × repo pair. Also counts text gaps and code-integrity violations
(final inline/fence code must appear in cassette raw replies or repo source).

Usage:
    python scripts/cassette_regression_matrix.py --phase before --out /tmp/r17-matrix-before
    python scripts/cassette_regression_matrix.py --phase after --out /tmp/r17-matrix-after
    python scripts/cassette_regression_matrix.py --only probe-25q fastapi-25q
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
ACCEPTANCE = SCRIPT_DIR / "handbook_acceptance.py"
CITE_RELEVANCE = SCRIPT_DIR / "cite_relevance.py"

DEFAULT_CASSETTES = Path(
    os.environ.get("REPO_WIKI_CASSETTE_MATRIX_DIR", "/workspace/cassettes-r17")
)
DEFAULT_PROBE_SRC = Path(os.environ.get("REPO_WIKI_PROBE_SRC", "/workspace/probe_exporter-eval"))
DEFAULT_FASTAPI_SRC = Path(
    os.environ.get("REPO_WIKI_FASTAPI_SRC", "/workspace/fastapi-realworld-example-app")
)
DEFAULT_ACC25R = Path(os.environ.get("REPO_WIKI_ACC25R_DIR", "/tmp/acc-25r"))
DEFAULT_ACCEPTANCE_KIT = Path(os.environ.get("REPO_WIKI_ACCEPTANCE_KIT", "/tmp/acceptance-kit"))
WAVES = ("25m", "25n", "25o", "25p", "25q", "25r")
REPOS = ("probe", "fastapi")

_FENCE_RE = re.compile(r"```([^\n]*)\n(.*?)```", re.S)
_INLINE_RE = re.compile(r"`([^`\n]+)`")
_CITE_RE = re.compile(r"<cite>.*?</cite>", re.I)
_GAP_RE = re.compile(
    r"[\u4e00-\u9fff，、（]\s{2,}[\u4e00-\u9fff（，。、]|[为用非是名在] [，。）]|选择 （"
)


def _cli() -> list[str]:
    found = shutil.which("repo-wiki")
    if found:
        return [found]
    return [sys.executable, "-m", "repo_wiki.main"]


def _cassette_dir(root: Path, repo: str, wave: str) -> Path:
    for name in (f"{repo}-{wave}", f"{repo}-{wave}-raw-cassette"):
        path = root / name
        if path.is_dir():
            return path.resolve()
    raise FileNotFoundError(f"missing cassette directory: {root / (repo + '-' + wave)}")


def _source_for(repo: str, probe_src: Path, fastapi_src: Path) -> Path:
    return probe_src if repo == "probe" else fastapi_src


def _acceptance_repo(repo: str) -> str:
    return "go" if repo == "probe" else "fastapi"


def _content_dir(handbook: Path) -> Path | None:
    for cand in (
        handbook / "repowiki" / "zh" / "content",
        handbook / "content",
        handbook,
    ):
        if cand.is_dir() and any(cand.rglob("*.md")):
            return cand
    return None


def _load_pages(content: Path) -> dict[str, str]:
    return {
        path.relative_to(content).as_posix(): path.read_text(encoding="utf-8", errors="ignore")
        for path in sorted(content.rglob("*.md"))
        if path.is_file()
    }


def _text_gaps(pages: dict[str, str]) -> int:
    hits = 0
    for text in pages.values():
        stripped = re.sub(r"```.*?```", "", text, flags=re.S)
        hits += sum(1 for _ in _GAP_RE.finditer(stripped))
    return hits


def _code_units(markdown: str) -> list[str]:
    from repo_wiki.verifier.handbook import _iter_page_code_units

    return _iter_page_code_units(markdown)


def _cassette_raw_blob(cassette_dir: Path) -> str:
    parts: list[str] = []
    for path in sorted(cassette_dir.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            raw = row.get("raw_reply") or row.get("response_content") or row.get("content") or ""
            if raw:
                parts.append(str(raw))
    return "\n".join(parts)


def _repo_source_blob(source: Path) -> str:
    parts: list[str] = []
    skip = {".git", ".repo-agent-eval", "node_modules", "vendor", "__pycache__", ".venv"}
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip for part in path.parts):
            continue
        if path.suffix.lower() not in {
            ".go",
            ".py",
            ".md",
            ".rst",
            ".yml",
            ".yaml",
            ".toml",
            ".sql",
            ".sh",
            ".txt",
            ".json",
        }:
            continue
        try:
            parts.append(path.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
    return "\n".join(parts)


def _code_integrity_violations(
    pages: dict[str, str], source: Path, cassette_dir: Path
) -> list[dict[str, str]]:
    raw_blob = _cassette_raw_blob(cassette_dir)
    source_blob = _repo_source_blob(source)
    found: list[dict[str, str]] = []
    for rel, text in pages.items():
        for unit in _code_units(text):
            if unit in raw_blob or unit in source_blob:
                continue
            found.append({"page": rel, "unit": unit[:120]})
    return found


def _acc25r_code_integrity(
    content: Path | None, cassette: Path, source: Path, acc25r: Path
) -> dict:
    script = acc25r / "code_integrity.py"
    if content is None or not script.is_file():
        return {"violations": None, "empty_spans": None, "unclosed_fences": None}
    jsonl = next(iter(sorted(cassette.glob("*.jsonl"))), None)
    if jsonl is None:
        return {"violations": None, "empty_spans": None, "unclosed_fences": None}
    try:
        payload = json.loads(
            subprocess.check_output(
                [sys.executable, str(script), str(content), str(jsonl), str(source)],
                text=True,
            )
        )
    except (subprocess.CalledProcessError, json.JSONDecodeError, OSError):
        payload = {}
    empty = 0
    unclosed = 0
    tiny: list[str] = []
    if content is not None:
        from repo_wiki.generator.code_safe import empty_inline_spans
        from repo_wiki.verifier.handbook import (
            MIN_HANDBOOK_BODY_CHARS,
            handbook_page_body_len,
            has_unclosed_fence,
        )

        for path in sorted(content.rglob("*.md")):
            text = path.read_text(encoding="utf-8", errors="ignore")
            empty += len(empty_inline_spans(text))
            if has_unclosed_fence(text):
                unclosed += 1
            if handbook_page_body_len(text) < MIN_HANDBOOK_BODY_CHARS:
                tiny.append(path.relative_to(content).as_posix())
    return {
        "violations": payload.get("violations"),
        "empty_spans": empty,
        "unclosed_fences": unclosed,
        "tiny_pages": tiny,
        "tiny_page_count": len(tiny),
    }


def _kit_cite_relevance(run_dir: Path, source: Path, kit: Path) -> dict[str, object]:
    script = kit / "experimental" / "cite_relevance.py"
    if not script.is_file():
        return {}
    try:
        text = subprocess.check_output(
            [sys.executable, str(script), "--strict", str(run_dir), str(source)],
            text=True,
        )
    except (subprocess.CalledProcessError, OSError) as exc:
        return {"error": str(exc)}
    match = re.search(r"\{.*relevant_pct.*\}", text, re.S)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}


def _run(cmd: list[str], cwd: Path | None, env: dict[str, str], log: Path) -> int:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as handle:
        handle.write(f"$ {' '.join(cmd)}\ncwd={cwd}\n\n")
        handle.flush()
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            env=env,
            stdout=handle,
            stderr=subprocess.STDOUT,
            check=False,
        )
        handle.write(f"\nEXIT={proc.returncode}\n")
    return proc.returncode


def _generate_env(cassette: Path, cache: Path) -> dict[str, str]:
    env = os.environ.copy()
    for key in (
        "REPO_WIKI_FORCE_MOCK_LLM",
        "LLM_API_KEY",
        "OPENAI_API_KEY",
        "REPO_WIKI_LLM_CASSETTE_WRITE_DIR",
        "REPO_WIKI_LLM_CASSETTE_RUN_ID",
        "REPO_WIKI_LLM_REAL_MAX_CALLS",
        "REPO_WIKI_LLM_PAGE_LIMIT",
        "REPO_WIKI_QODER_LIKE_MAX_PAGES",
    ):
        env.pop(key, None)
    env.update(
        {
            "LLM_PROVIDER": "cassette",
            "LLM_MODEL": "MiniMax-M3",
            "LLM_BASE_URL": "http://127.0.0.1:9/v1",
            "LLM_TIMEOUT": "180",
            "REPO_WIKI_LLM_PAGE_TIMEOUT_SECONDS": "180",
            "REPO_WIKI_LLM_CONCURRENCY": "3",
            "REPO_WIKI_LLM_PRIORITY": "qoder",
            "REPO_WIKI_LLM_COMPOSER_MAX_TOKENS": "16384",
            "LLM_MAX_TOKENS": "16384",
            "REPO_WIKI_LLM_CASSETTE_DIR": str(cassette),
            "REPO_WIKI_COMPOSER_CACHE_PATH": str(cache),
            "PYTHONUNBUFFERED": "1",
        }
    )
    return env


def _parse_verify(stdout_path: Path, run_dir: Path) -> dict[str, object]:
    report = run_dir / "reports" / "strict-verify-output.json"
    data: dict[str, object] = {}
    if report.is_file():
        try:
            data = json.loads(report.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    if not data:
        text = (
            stdout_path.read_text(encoding="utf-8", errors="ignore")
            if stdout_path.is_file()
            else ""
        )
        match = re.search(r"\{[\s\S]*\}\s*$", text)
        if match:
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                data = {}
    checks = data.get("checks") if isinstance(data, dict) else None
    if not isinstance(checks, list):
        checks = data.get("results") if isinstance(data, dict) else None
    rows = checks if isinstance(checks, list) else []
    passed = 0
    failed = 0
    failed_names: list[str] = []
    claim_cov = None
    claim_covered = None
    claim_total = None
    for item in rows:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        status = str(item.get("status") or "").upper()
        if status == "PASS":
            passed += 1
        elif status == "FAIL":
            failed += 1
            failed_names.append(name)
        if name == "qoder-claim-citation-coverage":
            details = item.get("details") if isinstance(item.get("details"), dict) else {}
            claim_covered = details.get("covered_claims")
            claim_total = details.get("total_claims")
            ratio = details.get("coverage_ratio")
            if isinstance(ratio, (int, float)):
                claim_cov = round(100 * float(ratio), 2)
            msg = str(item.get("message") or "")
            pct = re.search(r"([0-9]+(?:\.[0-9]+)?)%", msg)
            if claim_cov is None and pct:
                claim_cov = float(pct.group(1))
    quality = run_dir / "repowiki" / "zh" / "meta" / "quality-report.json"
    degraded = 0
    if quality.is_file():
        try:
            qdata = json.loads(quality.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            qdata = {}
        pages = qdata.get("pages") or qdata.get("quality_pages") or []
        if isinstance(pages, list):
            degraded = sum(
                1
                for page in pages
                if isinstance(page, dict)
                and "degraded" in str(page.get("quality_state") or "").lower()
            )
        states = (qdata.get("aggregate_summary") or {}).get("quality_states") or {}
        if isinstance(states, dict) and "DEGRADED" in states:
            degraded = int(states.get("DEGRADED") or degraded)
    return {
        "verify_pass": passed,
        "verify_fail": failed,
        "verify_total": passed + failed,
        "verify_label": f"{passed}/{passed + failed}" if passed + failed else "n/a",
        "failed_checks": failed_names,
        "claim_coverage_pct": claim_cov,
        "claim_covered": claim_covered,
        "claim_total": claim_total,
        "degraded": degraded,
        "verify_report": str(report) if report.is_file() else "",
    }


def _eval_one(
    *,
    which: str,
    source: Path,
    run_id: str,
    cassette: Path,
    out_dir: Path,
    acceptance_repo: str,
    acc25r: Path | None = None,
    acceptance_kit: Path | None = None,
) -> dict[str, object]:
    run_dir = source / ".repo-agent-eval" / "runs" / run_id
    if not (run_dir / "repowiki").exists():
        alt = source / ".repo-agent-eval" / run_id
        if (alt / "repowiki").exists():
            run_dir = alt
    acc_json = out_dir / f"{which}-acceptance.json"
    acc_code = _run(
        [
            sys.executable,
            str(ACCEPTANCE),
            str(run_dir),
            str(source),
            "--repo",
            acceptance_repo,
            "--out",
            str(acc_json),
        ],
        cwd=REPO_ROOT,
        env=os.environ.copy(),
        log=out_dir / f"{which}-acceptance.stdout",
    )
    cite_json = out_dir / f"{which}-cite-strict.json"
    cite_code = _run(
        [sys.executable, str(CITE_RELEVANCE), "--strict", str(run_dir), str(source)],
        cwd=REPO_ROOT,
        env=os.environ.copy(),
        log=out_dir / f"{which}-cite-strict.stdout",
    )
    if cite_json.exists() is False:
        text = (out_dir / f"{which}-cite-strict.stdout").read_text(
            encoding="utf-8", errors="ignore"
        )
        match = re.search(r"\{.*\}\s*$", text, re.S)
        if match:
            cite_json.write_text(match.group(0) + "\n", encoding="utf-8")
    else:
        # cite_relevance prints JSON to stdout; copy from log last line
        pass
    text = (out_dir / f"{which}-cite-strict.stdout").read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"\{[^{}]*relevant_pct[^{}]*\}", text, re.S)
    if match is None:
        match = re.search(r"\{.*relevant_pct.*\}", text, re.S)
    cite_data: dict[str, object] = {}
    if match:
        try:
            cite_data = json.loads(match.group(0))
            cite_json.write_text(
                json.dumps(cite_data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except json.JSONDecodeError:
            cite_data = {}
    verify_log = out_dir / f"{which}-verify.stdout"
    verify_env = os.environ.copy()
    verify_env.pop("REPO_WIKI_FORCE_MOCK_LLM", None)
    _run(
        [
            *_cli(),
            "verify",
            "--profile",
            "qoder-like",
            "--ci",
            "--output",
            str(run_dir),
        ],
        cwd=source,
        env=verify_env,
        log=verify_log,
    )
    verify = _parse_verify(verify_log, run_dir)
    content = _content_dir(run_dir)
    pages = _load_pages(content) if content else {}
    gaps = _text_gaps(pages)
    integrity = _code_integrity_violations(pages, source, cassette)
    acc25r_dir = acc25r or DEFAULT_ACC25R
    kit_dir = acceptance_kit or DEFAULT_ACCEPTANCE_KIT
    acc25r_integrity = _acc25r_code_integrity(content, cassette, source, acc25r_dir)
    kit_cite = _kit_cite_relevance(run_dir, source, kit_dir)
    acc_data: dict[str, object] = {}
    if acc_json.is_file():
        try:
            acc_data = json.loads(acc_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            acc_data = {}
    summary = acc_data.get("summary") if isinstance(acc_data.get("summary"), dict) else {}
    return {
        "which": which,
        "run_dir": str(run_dir),
        "acceptance_exit": acc_code,
        "cite_exit": cite_code,
        "text_gaps": summary.get("text_gaps", gaps),
        "strict_relevant_pct": cite_data.get("relevant_pct"),
        "strict_relevant": cite_data.get("relevant"),
        "strict_checked": cite_data.get("checked"),
        "code_integrity_violations": acc25r_integrity.get("violations", len(integrity)),
        "code_integrity_examples": integrity[:8],
        "acc25r_empty_spans": acc25r_integrity.get("empty_spans"),
        "acc25r_unclosed_fences": acc25r_integrity.get("unclosed_fences"),
        "tiny_pages": acc25r_integrity.get("tiny_pages") or [],
        "tiny_page_count": acc25r_integrity.get("tiny_page_count") or 0,
        "kit_strict_relevant_pct": kit_cite.get("relevant_pct"),
        "pages": len(pages),
        **verify,
    }


def run_one(
    *,
    repo: str,
    wave: str,
    phase: str,
    cassettes: Path,
    probe_src: Path,
    fastapi_src: Path,
    out_dir: Path,
    skip_generate: bool = False,
    acc25r: Path | None = None,
    acceptance_kit: Path | None = None,
) -> dict[str, object]:
    which = f"{repo}-{wave}"
    source = _source_for(repo, probe_src, fastapi_src)
    cassette = _cassette_dir(cassettes, repo, wave)
    run_id = f"{repo}-{phase}-{wave}"
    cache = out_dir / "cache" / f"{which}.sqlite3"
    out_dir.mkdir(parents=True, exist_ok=True)
    if not skip_generate:
        cache.unlink(missing_ok=True)
        gen_log = out_dir / f"{which}-generate.log"
        code = _run(
            [
                *_cli(),
                "generate",
                "--profile",
                "qoder-like",
                "--output",
                ".repo-agent-eval",
                "--run-id",
                run_id,
            ],
            cwd=source,
            env=_generate_env(cassette, cache),
            log=gen_log,
        )
        if code != 0:
            return {
                "which": which,
                "generate_exit": code,
                "error": f"generate failed, see {gen_log}",
            }
    result = _eval_one(
        which=which,
        source=source,
        run_id=run_id,
        cassette=cassette,
        out_dir=out_dir,
        acceptance_repo=_acceptance_repo(repo),
        acc25r=acc25r,
        acceptance_kit=acceptance_kit,
    )
    result["generate_exit"] = 0
    result["cassette"] = str(cassette)
    result["phase"] = phase
    return result


def _markdown_table(rows: list[dict[str, object]]) -> str:
    headers = (
        "cassette",
        "verify",
        "failed",
        "DEGRADED",
        "claim%",
        "strict%",
        "gaps",
        "code-integrity",
        "empty-spans",
        "unclosed-fences",
        "<800",
        "kit-strict%",
    )
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("which") or ""),
                    str(row.get("verify_label") or ""),
                    ",".join((row.get("failed_checks") or [])[:4]) or "-",
                    str(row.get("degraded")),
                    str(row.get("claim_coverage_pct")),
                    str(row.get("strict_relevant_pct")),
                    str(row.get("text_gaps")),
                    str(row.get("code_integrity_violations")),
                    str(row.get("acc25r_empty_spans")),
                    str(row.get("acc25r_unclosed_fences")),
                    str(row.get("tiny_page_count")),
                    str(row.get("kit_strict_relevant_pct") or row.get("strict_relevant_pct")),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("before", "after", "eval"), default="after")
    parser.add_argument("--cassettes", type=Path, default=DEFAULT_CASSETTES)
    parser.add_argument("--probe-src", type=Path, default=DEFAULT_PROBE_SRC)
    parser.add_argument("--fastapi-src", type=Path, default=DEFAULT_FASTAPI_SRC)
    parser.add_argument("--out", type=Path, default=Path("/tmp/cassette-matrix"))
    parser.add_argument("--only", nargs="*", help="Subset like probe-25q fastapi-25p")
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--skip-generate", action="store_true")
    parser.add_argument("--acc25r", type=Path, default=DEFAULT_ACC25R)
    parser.add_argument("--acceptance-kit", type=Path, default=DEFAULT_ACCEPTANCE_KIT)
    args = parser.parse_args()
    targets: list[tuple[str, str]] = []
    only = set(args.only or [])
    for repo in REPOS:
        for wave in WAVES:
            name = f"{repo}-{wave}"
            if only and name not in only:
                continue
            targets.append((repo, wave))
    if not targets:
        print("no cassette targets", file=sys.stderr)
        return 2
    args.out.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []

    def _job(item: tuple[str, str]) -> dict[str, object]:
        repo, wave = item
        print(f"==> {args.phase} {repo}-{wave}", flush=True)
        return run_one(
            repo=repo,
            wave=wave,
            phase=args.phase,
            cassettes=args.cassettes,
            probe_src=args.probe_src,
            fastapi_src=args.fastapi_src,
            out_dir=args.out,
            skip_generate=args.skip_generate or args.phase == "eval",
            acc25r=args.acc25r,
            acceptance_kit=args.acceptance_kit,
        )

    # Same source tree cannot generate two waves at once; pair across repos.
    if args.jobs <= 1:
        rows.extend(_job(item) for item in targets)
    else:
        # Run probe+fastapi of the same wave together; waves stay serial per repo.
        by_wave: dict[str, list[tuple[str, str]]] = {}
        for repo, wave in targets:
            by_wave.setdefault(wave, []).append((repo, wave))
        for wave in WAVES:
            batch = by_wave.get(wave) or []
            if not batch:
                continue
            with ThreadPoolExecutor(max_workers=min(args.jobs, len(batch))) as pool:
                futs = [pool.submit(_job, item) for item in batch]
                for fut in as_completed(futs):
                    rows.append(fut.result())
    rows.sort(key=lambda item: str(item.get("which") or ""))
    payload = {"phase": args.phase, "rows": rows}
    (args.out / "matrix.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    table = _markdown_table(rows)
    (args.out / "matrix.md").write_text(table, encoding="utf-8")
    print(table)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
