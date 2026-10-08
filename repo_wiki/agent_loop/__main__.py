"""``python -m repo_wiki.agent_loop <repo> --pages overview,install,datamodel,api --out DIR``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from repo_wiki.agent_loop.checklists import PAGE_TYPES
from repo_wiki.agent_loop.llm import CassetteMiss, CassetteVersionMismatch
from repo_wiki.agent_loop.orchestrator import AgentLoopOrchestrator
from repo_wiki.agent_loop.render import run_report_summary
from repo_wiki.core.config import load_config


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m repo_wiki.agent_loop")
    ap.add_argument("repo", type=Path)
    ap.add_argument("--pages", default=",".join(PAGE_TYPES))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument(
        "--config", type=Path, default=None, help="repo-wiki.yaml (llm / security / agent_loop)"
    )
    ap.add_argument("--cassette-mode", choices=("off", "record", "resume", "replay"), default=None)
    ap.add_argument("--cassette-dir", type=Path, default=None)
    ap.add_argument("--max-iters", type=int, default=None)
    ap.add_argument("--page-cap", type=int, default=None, help="prompt-token cap per page")
    ap.add_argument("--global-cap", type=int, default=None, help="prompt-token cap per run")
    a = ap.parse_args(argv)
    cfg = load_config(a.config)
    al = cfg.agent_loop
    upd: dict[str, object] = {}
    if a.cassette_mode:
        upd["cassette_mode"] = a.cassette_mode
    if a.cassette_dir:
        upd["cassette_dir"] = str(a.cassette_dir)
    if a.max_iters is not None:
        upd["max_iters"] = a.max_iters
    if a.page_cap:
        upd["page_prompt_cap"] = a.page_cap
    if a.global_cap:
        upd["global_prompt_cap"] = a.global_cap
    al = al.model_copy(update=upd)
    pages = [p.strip() for p in a.pages.split(",") if p.strip()]
    bad = [p for p in pages if p not in PAGE_TYPES]
    if bad:
        ap.error(f"unknown page types {bad}; choose from {', '.join(PAGE_TYPES)}")
    try:
        orch = AgentLoopOrchestrator(
            a.repo, al, a.out, security=cfg.security, llm_section=cfg.llm.model_dump()
        )
    except (CassetteVersionMismatch, CassetteMiss) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    for p in pages:
        res = orch.run_page(p)
        print(json.dumps({"page": p, **run_report_summary(res)}, ensure_ascii=False), flush=True)
    orch.write_report()
    print(
        json.dumps({"totals": orch.report["totals"], "report": str(a.out / "report.json")}),
        flush=True,
    )
    return 0 if all(r.get("status") == "pass" for r in orch.report["pages"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
