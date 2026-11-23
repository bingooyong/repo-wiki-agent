# LLM Preflight & Fallback Gate — Code Spec

> Executable contract for failing fast on bad LLM configuration and for never publishing fallback/mock prose as READY.
> Implemented in `repo_wiki/llm/preflight.py`, `repo_wiki/llm/adapters.py`, `repo_wiki/llm/diagnostics.py`, `repo_wiki/orchestration/{service,eval_layout}.py`, `repo_wiki/core/config.py`.
> Tests: `tests/test_llm_preflight_gate.py`.

---

## Scenario: Generate a qoder-like run without burning a whole run on a misconfigured provider

### 1. Scope / Trigger

Infra + cross-layer contract: new preflight module, new manifest/metadata fields, new readiness reason codes, new config knob. Three measured failure modes motivated it (see `docs/eval/2026-11-23-repo-agent-self-baseline-gap-report.md` §7):

1. `provider=openai` + `base_url=…/anthropic` → OpenAI protocol POSTs to an Anthropic endpoint → 404.
2. Key valid only on another gateway/host → 401 (`api.minimaxi.com/v1` vs `api.minimax.io/v1` vs console host `platform.minimaxi.com` which returns an HTML 404).
3. Ambient `NO_PROXY` containing bare `[::1]`/`::1` → `httpx.AsyncClient` construction raises `InvalidURL: Invalid port: ':1]'` before any request; composer's broad `except Exception` swallowed it as `Composition error`, circuit-broke after 3 pages, and wrote 80 fallback pages marked READY.

### 2. Signatures

```python
# repo_wiki/llm/preflight.py
@dataclass
class PreflightResult: status: str; reason_code: str | None; hint: str | None; probe_attempted: bool ...
class LLMClientInitError(NonRetryableError): ...
def run_preflight(config: LLMProviderConfig, *, force_mock: bool = False, probe: bool = True) -> PreflightResult
def check_protocol_consistency(config) -> PreflightResult | None      # offline
def create_async_client(config) -> httpx.AsyncClient                  # raises LLMClientInitError
def create_sync_client(config) -> httpx.Client
def client_init_message(exc, config) -> str                           # names proxy env vars, never credentials

# repo_wiki/orchestration/eval_layout.py
def _llm_readiness_reasons(stats, page_registry, min_llm_success_ratio) -> list[str]

# repo_wiki/core/config.py
QoderLikeConfig.min_llm_success_ratio: float = 0.5   # ge=0, le=1; env REPO_WIKI_QODER_LIKE_MIN_LLM_SUCCESS_RATIO
```

CLI: `repo-wiki config --ci [--probe]` (protocol check always; live probe opt-in). `generate --profile qoder-like` always probes before compose.

### 3. Contracts

Reason codes: `OK`, `skipped_mock`, `LLM_ENDPOINT_MISMATCH`, `LLM_AUTH_INVALID`, `LLM_UNREACHABLE` (network/429/5xx), `LLM_CLIENT_INIT_FAILED`, `LLM_EMPTY_RESPONSE`.

Readiness reasons (NOT_READY): `MOCK_LLM_RUN` (mode==mock), `LLM_PROVIDER_DISABLED` (circuit-break), `FALLBACK_ONLY_RUN` (ratio<=0), `LLM_SUCCESS_RATIO_BELOW_MIN` (0<ratio<min). Runs with no `stats.llm` (rule-first default profile) are not gated here.

Manifest additions: `page_registry[*].generation_mode` ∈ {llm, rule, fallback, mock, UNIDENTIFIED} + `rejection_reason`; `metadata.effective_provider`, `preflight_status`, `preflight_reason_code`, `llm_success_ratio`, `is_mock_run`, `min_llm_success_ratio`.

Ratio resolution priority: explicit composer ratio → per-page generation_mode share → composed vs fallback counts → None (no evidence ⇒ do not brand FALLBACK_ONLY_RUN).

Secrets: hints/messages name env vars and status codes only; never key values, never proxy credentials.

### 4. Validation & Error Matrix

| Condition | Behavior |
|-----------|----------|
| openai provider + base path `/anthropic` | offline FAIL `LLM_ENDPOINT_MISMATCH`, hint names both fixes (base or provider) |
| probe 401/403 | FAIL `LLM_AUTH_INVALID`, hint names `api_key_env` |
| probe 404/405 with HTML body | FAIL `LLM_ENDPOINT_MISMATCH`, hint says console/host wrong |
| probe 404/405 with JSON body | FAIL `LLM_ENDPOINT_MISMATCH`, hint says path/protocol wrong |
| probe 429/5xx/network/timeout | FAIL `LLM_UNREACHABLE` |
| httpx client construction raises | FAIL `LLM_CLIENT_INIT_FAILED`, hint names HTTP(S)_PROXY/NO_PROXY and bare IPv6/CIDR entries |
| force_mock | probe skipped (`skipped_mock`); run still NOT_READY (`MOCK_LLM_RUN`) |
| preflight FAIL in generate | abort before compose; exit non-zero; **zero pages written** |
| ratio < min | NOT_READY + ratio reason |
| no stats.llm | no LLM readiness reasons (default profile unaffected) |

### 5. Good / Base / Bad Cases

- Good: valid base+key → probe OK → real pages; readiness decided by quality gates only.
- Base: CI mock forced → skipped_mock, NOT_READY + MOCK_LLM_RUN, per-page mode=mock.
- Bad: the historical behavior — 80 fallback pages, `readiness_state=READY`, page_registry without modes.

### 6. Tests Required

`tests/test_llm_preflight_gate.py` (44): offline endpoint mismatch; mocked 401/403; HTML vs JSON 404 hints; NO_PROXY `[::1]` client-init classification (monkeypatch env, no network); mock exemption + NOT_READY; threshold override via env/YAML; per-page modes for llm/fallback/mock; fallback-only NOT_READY; generate aborts with 0 pages on bad config. All network via `httpx.MockTransport` or unset key — never real calls, never real keys (use `sk-test-dummy`).

Related calibrations: `tests/test_release_meta_schema.py` asserts required⊆schema and required∪optional==schema after the invariants required/optional split; `tests/test_qoder_reference_release_interface_fixture.py` accepts both IA families while keeping cite/mermaid/TOC assertions.

### 7. Wrong vs Correct

#### Wrong — swallow client-init errors into per-page composition errors

```python
except Exception as e:
    return ComposerOutput(rejected=True, rejection_reason=f"Composition error: {e}", tokens_used=0)
```

An ambient-proxy parse error then repeats on every page and circuit-breaks the run.

#### Correct — classify at construction, fail before compose

```python
try:
    return httpx.AsyncClient(base_url=..., timeout=..., headers=...)
except httpx.InvalidURL as exc:
    raise LLMClientInitError(client_init_message(exc, config)) from exc
```

#### Wrong — presence-only citation metrics representing citation quality

`citation_coverage=1.0` while `file://` links, `#L` anchors and section sources are all 0 (plain `<cite>path:line</cite>` satisfies presence). Parity reported 11/11 pass, 0.97.

#### Correct — granularity metrics alongside presence

link_form_coverage / line_anchor_coverage / section_source_coverage as HARD gates (task 3); presence alone never sufficient.

---

## Common Mistakes

### Mistake: trusting `config --ci` summary OK as "LLM works"
It validated field format only. Now protocol consistency is always checked; live probe is opt-in for config but mandatory for generate.

### Mistake: assuming the vendor console host is the API host
`platform.minimaxi.com` serves an HTML console (404 HTML); the OpenAI-compatible API is `api.minimaxi.com/v1`; `api.minimax.io/v1` is a different region and rejects CN keys. Distinguish HTML-404 from JSON-404 in hints.

### Mistake: marking mock or fallback runs READY
Mock prose is synthetic; fallback prose is rule-only. Both are process artifacts. READY requires real-LLM share ≥ min plus quality gates.