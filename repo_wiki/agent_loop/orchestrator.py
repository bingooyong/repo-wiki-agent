"""Orchestrator: one repository profile, then the selected pages one at a time under per-page and
global prompt-token caps. Provider failures abort the run (never retried page after page); a budget
overrun aborts only that page. A page that does not pass is reported as failed and not shipped."""

from __future__ import annotations

import dataclasses
import json
import time
from pathlib import Path
from typing import Any

from repo_wiki.agent_loop import inventory as inv
from repo_wiki.agent_loop.api_page import run_api_page
from repo_wiki.agent_loop.checklists import PAGE_TYPES, PAGES
from repo_wiki.agent_loop.evidence import parse_ev, quote_ok
from repo_wiki.agent_loop.fact_page import Budgets, run_fact_page
from repo_wiki.agent_loop.llm import (
    AgentLoopError,
    BudgetExceeded,
    Cassette,
    CassetteMiss,
    ChatSettings,
    LLMSession,
    NoNetworkClient,
    OpenAICompatibleClient,
    ProviderError,
    ToolChatClient,
    runner_version,
)
from repo_wiki.agent_loop.render import run_report_summary
from repo_wiki.agent_loop.repo import RepoView
from repo_wiki.agent_loop.roles import ROLE_RECOGNIZE, SUBMIT_PROFILE
from repo_wiki.agent_loop.runner import AgentRunner
from repo_wiki.agent_loop.tools import READ_TOOLS, ToolBox
from repo_wiki.core.config import AgentLoopConfig, SecurityConfig

MINIMAX_EXTRA_BODY: dict[str, Any] = {"thinking": {"type": "disabled"}, "reasoning_split": True}
MINIMAX_BASE_URL = "https://api.minimaxi.com/v1"


@dataclasses.dataclass
class ProviderSettings:
    provider: str
    model: str
    base_url: str
    api_key_env: str


def resolve_provider(llm_section: dict[str, Any], cfg: AgentLoopConfig) -> ProviderSettings:
    """Same resolution as the composer (config + LLM_* / APP_LLM_MINIMAX_* env), then the
    agent_loop overrides."""
    from repo_wiki.llm.config import resolve_llm_config

    resolved, _warnings = resolve_llm_config(config=llm_section)
    provider = str(resolved.provider or "openai").lower()
    base_url = (
        cfg.base_url
        or resolved.base_url
        or (MINIMAX_BASE_URL if provider == "minimax" else "https://api.openai.com/v1")
    )
    return ProviderSettings(
        provider=provider,
        model=cfg.model or resolved.model,
        base_url=base_url,
        api_key_env=cfg.api_key_env or resolved.api_key_env,
    )


def make_budgets(overrides: dict[str, int]) -> Budgets:
    known = {f.name for f in dataclasses.fields(Budgets)}
    return Budgets(**{k: int(v) for k, v in overrides.items() if k in known})


class AgentLoopOrchestrator:
    def __init__(
        self,
        repo_root: Path,
        cfg: AgentLoopConfig,
        out_dir: Path,
        security: SecurityConfig | None = None,
        llm_section: dict[str, Any] | None = None,
        client: ToolChatClient | None = None,
    ) -> None:
        security = security or SecurityConfig()
        self.cfg = cfg
        self.out_dir = Path(out_dir)
        self.repo = RepoView(
            Path(repo_root),
            deny_globs=security.deny_globs,
            deny_dirs=security.deny_dirs,
            max_file_bytes=max(security.max_file_size_kb, 1) * 1024,
            allow_globs=cfg.allow_globs,
        )
        self.budgets = make_budgets(cfg.budgets)
        prov = resolve_provider(llm_section or {}, cfg)
        self.provider = prov
        extra = (
            cfg.extra_body
            if cfg.extra_body is not None
            else (dict(MINIMAX_EXTRA_BODY) if prov.provider == "minimax" else {})
        )
        cassette_dir = Path(cfg.cassette_dir) if cfg.cassette_dir else self.out_dir / "cassette"
        self.cassette = Cassette(
            cassette_dir, cfg.cassette_mode, runner_version(), self.repo.fingerprint()
        )
        if client is None:
            client = (
                NoNetworkClient()
                if cfg.cassette_mode == "replay"
                else OpenAICompatibleClient(
                    prov.base_url,
                    prov.api_key_env,
                    timeout=cfg.timeout,
                    max_retries=cfg.max_retries,
                    chat_path=cfg.chat_path,
                )
            )
        self.session = LLMSession(
            client,
            ChatSettings(prov.model, cfg.temperature, cfg.max_tokens, extra),
            self.cassette,
            global_prompt_cap=cfg.global_prompt_cap,
            ledger_path=self.out_dir / "ledger.jsonl",
        )
        self.runner = AgentRunner(ToolBox(self.repo), self.session)
        self.profile: dict[str, Any] | None = None
        self.provider_down: str | None = None
        self.report: dict[str, Any] = {
            "runner_version": runner_version(),
            "repo": str(self.repo.root),
            "model": prov.model,
            "cassette_mode": cfg.cassette_mode,
            "cassette_rotated": self.cassette.rotated,
            "budgets": dataclasses.asdict(self.budgets),
            "pages": {},
        }

    # ------------------------------------------------------------------ profile
    def recognize(self) -> dict[str, Any]:
        if self.profile is not None:
            return self.profile
        facts = inv.stack_facts(self.repo)
        self.session.start_page(None)
        res = self.runner.run(
            "recognize",
            ROLE_RECOGNIZE,
            "Deterministic facts:\n"
            + json.dumps(facts, ensure_ascii=False, indent=1)
            + f"\n\nTool-call budget: {self.budgets.recognize}. Call submit_profile before the budget "
            "runs out.",
            READ_TOOLS + [SUBMIT_PROFILE],
            self.budgets.recognize,
            ["submit_profile"],
        )
        pr = res.first("submit_profile") or {}
        langs = pr.get("languages")
        profile: dict[str, Any] = {
            "languages": [str(x) for x in langs] if isinstance(langs, list) else [],
            "layout": pr.get("layout") if isinstance(pr.get("layout"), list) else [],
            "frameworks": [],
            "entry_points": [],
        }
        for k in ("frameworks", "entry_points"):
            raw = pr.get(k)
            for item in raw if isinstance(raw, list) else []:
                if not isinstance(item, dict):
                    continue
                evs = item.get("evidence") or []
                evs = evs if isinstance(evs, list) else [evs]
                parsed = [parse_ev(e) for e in evs]
                if parsed and all(
                    p is not None and quote_ok(self.repo, p) is not None for p in parsed
                ):
                    profile[k].append({kk: vv for kk, vv in item.items() if kk != "evidence"})
        self.profile = profile
        self.report["profile"] = profile
        return profile

    # ------------------------------------------------------------------ pages
    def run_page(self, page_type: str) -> dict[str, Any]:
        if page_type not in PAGE_TYPES:
            raise ValueError(f"unknown agent-loop page type {page_type!r}")
        if self.provider_down:
            res: dict[str, Any] = {
                "page_type": page_type,
                "status": "aborted-provider",
                "aborted": self.provider_down,
                "page": "",
            }
            self._store(page_type, res, {}, 0.0)
            return res
        before = self.session.stats.snapshot()
        t0 = time.time()
        self.session.context = {"page": page_type}
        try:
            profile = self.recognize()
            self.session.start_page(self.cfg.page_prompt_cap)
            if page_type == "api":
                res = run_api_page(
                    self.runner, self.repo, profile, self.budgets, self.cfg.max_iters
                )
            else:
                res = run_fact_page(
                    self.runner,
                    self.repo,
                    PAGES[page_type],
                    profile,
                    self.budgets,
                    self.cfg.max_iters,
                )
        except BudgetExceeded as exc:
            res = {"page_type": page_type, "status": "aborted", "aborted": str(exc), "page": ""}
        except ProviderError as exc:
            self.provider_down = str(exc)
            res = {
                "page_type": page_type,
                "status": "aborted-provider",
                "aborted": str(exc),
                "page": "",
            }
        except CassetteMiss as exc:
            res = {
                "page_type": page_type,
                "status": "aborted-cassette",
                "aborted": str(exc),
                "page": "",
            }
        except AgentLoopError as exc:
            res = {"page_type": page_type, "status": "aborted", "aborted": str(exc), "page": ""}
        self._store(page_type, res, self.session.stats.minus(before), time.time() - t0)
        return res

    def _store(
        self, page_type: str, res: dict[str, Any], stats: dict[str, int], seconds: float
    ) -> None:
        res["stats"] = {**stats, "seconds": round(seconds, 1)}
        self.report["pages"][page_type] = res
        self.out_dir.mkdir(parents=True, exist_ok=True)
        (self.out_dir / f"page-{page_type}.md").write_text(res.get("page") or "", encoding="utf-8")
        self.write_report()

    def write_report(self) -> Path:
        self.report["totals"] = self.session.stats.snapshot()
        self.report["summary"] = {p: run_report_summary(r) for p, r in self.report["pages"].items()}
        self.report["trace"] = self.runner.trace
        path = self.out_dir / "report.json"
        path.write_text(
            json.dumps(self.report, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
        )
        return path

    def run(self, page_types: list[str]) -> dict[str, Any]:
        for p in page_types:
            self.run_page(p)
        self.write_report()
        return self.report
