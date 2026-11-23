"""Contract tests: LLM preflight gate + fallback/mock readiness (task 11-23).

Measured defects this locks down:
1. ``provider=openai`` + ``base_url=.../anthropic`` (HTTP 404) and keys invalid on the
   target host (HTTP 401) used to pass ``config --ci`` and then burn a whole run into
   fallback pages.
2. Ambient ``NO_PROXY`` with a bare IPv6 entry (``[::1]``) makes ``httpx`` client
   construction raise ``InvalidURL: Invalid port: ':1]'``; the composer swallowed it as
   "Composition error" and circuit-broke.
3. A fallback-only run was marked READY and ``page_registry`` carried no per-page mode.

No test here touches the network: the real HTTP transports are blocked by an autouse
fixture and every probe uses ``httpx.MockTransport``. Keys are fake (``sk-test-dummy``).
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.core.errors import RepoWikiError
from repo_wiki.llm.adapters import OpenAICompatibleProvider
from repo_wiki.llm.config import LLMProviderConfig
from repo_wiki.llm.diagnostics import run_llm_diagnostics
from repo_wiki.llm.models import (
    ChatRequest,
    ChatResponse,
    ErrorCode,
    LLMProvider,
    ProviderCapabilities,
    RetryableError,
)
from repo_wiki.llm.preflight import (
    PROBE_MAX_TOKENS,
    PROBE_TIMEOUT_CAP_SECONDS,
    REASON_AUTH_INVALID,
    REASON_CLIENT_INIT_FAILED,
    REASON_ENDPOINT_MISMATCH,
    REASON_UNREACHABLE,
    STATUS_FAIL,
    STATUS_OK,
    STATUS_SKIPPED_MOCK,
    LLMClientInitError,
    run_preflight,
)
from repo_wiki.orchestration.eval_layout import EvalOutputProfile, generate_manifest
from repo_wiki.orchestration.service import RepoWikiService

DUMMY_KEY_ENV = "REPO_WIKI_TEST_LLM_KEY"
DUMMY_KEY = "sk-test-dummy"
MISSING_KEY_ENV = "REPO_WIKI_TEST_ABSENT_LLM_KEY"
ANTHROPIC_BASE = "https://api.minimaxi.com/anthropic"
OPENAI_BASE = "https://api.minimaxi.com/v1"

_LLM_ENV_KEYS = (
    "LLM_PROVIDER",
    "LLM_MODEL",
    "LLM_BASE_URL",
    "LLM_API_KEY_ENV",
    "LLM_MAX_TOKENS",
    "LLM_TEMPERATURE",
    "LLM_TIMEOUT",
    "LLM_MAX_RETRIES",
    "REPO_WIKI_FORCE_MOCK_LLM",
    "REPO_WIKI_LLM_REAL_MAX_CALLS",
    "REPO_WIKI_LLM_PAGE_LIMIT",
    "REPO_WIKI_QODER_LIKE_MIN_LLM_SUCCESS_RATIO",
    "APP_LLM_MINIMAXI_API_KEY",
    "APP_LLM_MINIMAX_API_KEY",
)


@pytest.fixture(autouse=True)
def _no_real_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Block real HTTP transports; ``httpx.MockTransport`` stays usable."""

    def _blocked(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("real network access is forbidden in preflight gate tests")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _blocked)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", _blocked)


@pytest.fixture(autouse=True)
def _hermetic_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralize ambient LLM/proxy env so results do not depend on the developer box."""
    for key in _LLM_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    for key in ("NO_PROXY", "no_proxy"):
        monkeypatch.setenv(key, "localhost,127.0.0.1")
    for key in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "http_proxy",
        "https_proxy",
        "ALL_PROXY",
        "all_proxy",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv(DUMMY_KEY_ENV, DUMMY_KEY)
    monkeypatch.delenv(MISSING_KEY_ENV, raising=False)


def _config(
    *,
    provider: str = "openai",
    base_url: str | None = OPENAI_BASE,
    api_key_env: str = DUMMY_KEY_ENV,
    timeout: float = 60.0,
) -> LLMProviderConfig:
    return LLMProviderConfig(
        provider=provider,
        model="MiniMax-M2.7",
        base_url=base_url,
        api_key_env=api_key_env,
        timeout=timeout,
    )


def _transport(status: int, *, body: str | None = None, payload: dict | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if payload is not None:
            return httpx.Response(status, json=payload)
        return httpx.Response(status, text=body or "")

    return httpx.MockTransport(handler)


def _ok_transport() -> httpx.MockTransport:
    return _transport(200, payload={"choices": [{"message": {"content": "pong"}}]})


# ---------------------------------------------------------------------------
# 1. Protocol consistency — offline, no probe
# ---------------------------------------------------------------------------


def test_openai_provider_with_anthropic_base_fails_without_network() -> None:
    result = run_preflight(_config(base_url=ANTHROPIC_BASE), probe=False)

    assert result.status == STATUS_FAIL
    assert result.reason_code == REASON_ENDPOINT_MISMATCH
    assert result.probe_attempted is False
    assert result.http_status is None
    assert "/anthropic" in result.message
    assert "LLM_BASE_URL" in result.hint
    assert "LLM_PROVIDER=minimax" in result.hint


def test_mismatch_message_names_key_env_but_never_key_value() -> None:
    result = run_preflight(_config(base_url=ANTHROPIC_BASE), probe=False)
    text = result.message + str(result.hint)

    assert DUMMY_KEY_ENV in text
    assert DUMMY_KEY not in text


def test_anthropic_base_suffix_and_infix_both_detected() -> None:
    for base in (
        "https://api.minimaxi.com/anthropic",
        "https://api.minimaxi.com/anthropic/",
        "https://gateway.example.test/anthropic/v1",
    ):
        result = run_preflight(_config(base_url=base), probe=False)
        assert result.reason_code == REASON_ENDPOINT_MISMATCH, base


def test_minimax_provider_may_use_anthropic_gateway() -> None:
    """MinimaxProvider has an Anthropic-compatible branch, so this is not a mismatch."""
    result = run_preflight(_config(provider="minimax", base_url=ANTHROPIC_BASE), probe=False)

    assert result.status == STATUS_OK
    assert result.reason_code is None


def test_minimax_non_minimax_host_is_warning_not_failure() -> None:
    result = run_preflight(
        _config(provider="minimax", base_url="https://llm.proxy.example.test/v1"), probe=False
    )

    assert result.status == STATUS_OK
    assert result.warnings
    assert "proxy" in result.warnings[0]


# ---------------------------------------------------------------------------
# 2. Minimal probe classification (mocked transport)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", [401, 403])
def test_auth_invalid_classification(status: int) -> None:
    result = run_preflight(
        _config(),
        transport=_transport(status, payload={"error": {"message": "invalid api key (2049)"}}),
    )

    assert result.status == STATUS_FAIL
    assert result.reason_code == REASON_AUTH_INVALID
    assert result.reason_code != REASON_ENDPOINT_MISMATCH
    assert result.http_status == status
    assert result.probe_attempted is True
    assert DUMMY_KEY_ENV in result.message
    assert DUMMY_KEY not in result.message + str(result.hint)


def test_html_404_hint_blames_console_host() -> None:
    html = "<!DOCTYPE html><html><head><title>MiniMax Console</title></head><body></body></html>"
    result = run_preflight(
        _config(base_url="https://platform.minimaxi.com/v1"),
        transport=_transport(404, body=html),
    )

    assert result.reason_code == REASON_ENDPOINT_MISMATCH
    assert result.http_status == 404
    assert "HTML" in result.hint
    assert "console" in result.hint
    assert "api.minimaxi.com/v1" in result.hint


def test_json_404_hint_blames_route_not_host() -> None:
    result = run_preflight(
        _config(base_url=ANTHROPIC_BASE.replace("/anthropic", "/v1")),
        transport=_transport(404, payload={"error": {"message": "404 page not found"}}),
    )

    assert result.reason_code == REASON_ENDPOINT_MISMATCH
    assert "console" not in result.hint
    assert "route" in result.hint
    assert "/chat/completions" in result.hint


def test_405_is_endpoint_mismatch() -> None:
    result = run_preflight(_config(), transport=_transport(405, payload={"error": {}}))

    assert result.reason_code == REASON_ENDPOINT_MISMATCH
    assert result.http_status == 405


def test_network_failure_is_unreachable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("name resolution failed", request=request)

    result = run_preflight(_config(), transport=httpx.MockTransport(handler))

    assert result.status == STATUS_FAIL
    assert result.reason_code == REASON_UNREACHABLE
    assert "NO_PROXY" in result.message
    assert DUMMY_KEY not in result.message


def test_timeout_is_unreachable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    result = run_preflight(_config(), transport=httpx.MockTransport(handler))

    assert result.reason_code == REASON_UNREACHABLE


def test_2xx_with_content_is_ok() -> None:
    result = run_preflight(_config(), transport=_ok_transport())

    assert result.status == STATUS_OK
    assert result.reason_code is None
    assert result.http_status == 200
    assert result.ok is True


def test_2xx_without_content_is_not_ok() -> None:
    result = run_preflight(_config(), transport=_transport(200, payload={"choices": []}))

    assert result.status == STATUS_FAIL
    assert result.reason_code == "LLM_EMPTY_RESPONSE"


def test_probe_is_minimal_and_timeout_capped() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "pong"}}]})

    result = run_preflight(_config(timeout=60.0), transport=httpx.MockTransport(handler))

    assert seen["path"] == "/v1/chat/completions"
    assert seen["payload"]["max_tokens"] == PROBE_MAX_TOKENS == 8
    assert len(seen["payload"]["messages"]) == 1
    assert result.probe_timeout_seconds == PROBE_TIMEOUT_CAP_SECONDS == 15.0

    short = run_preflight(_config(timeout=5.0), transport=httpx.MockTransport(handler))
    assert short.probe_timeout_seconds == 5.0


def test_missing_key_skips_probe_instead_of_calling_network() -> None:
    result = run_preflight(_config(api_key_env=MISSING_KEY_ENV), transport=_ok_transport())

    assert result.status == STATUS_OK
    assert result.probe_attempted is False
    assert any(MISSING_KEY_ENV in warning for warning in result.warnings)


# ---------------------------------------------------------------------------
# 3. Client construction failure (ambient NO_PROXY with bare IPv6)
# ---------------------------------------------------------------------------


def test_ipv6_no_proxy_client_init_failure_classification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broken = "localhost,.localhost,127.0.0.1,127.0.0.0/8,[::1],::1"
    monkeypatch.setenv("NO_PROXY", broken)
    monkeypatch.setenv("no_proxy", broken)

    result = run_preflight(_config(), probe=False)

    assert result.status == STATUS_FAIL
    assert result.reason_code == REASON_CLIENT_INIT_FAILED
    assert result.probe_attempted is False
    assert "NO_PROXY" in result.message
    assert "HTTP_PROXY/HTTPS_PROXY/NO_PROXY" in result.message
    assert "[::1]" in result.message
    assert "Invalid port" in result.message


def test_client_init_message_hides_proxy_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NO_PROXY", "[::1]")
    monkeypatch.setenv("no_proxy", "[::1]")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxyuser:supersecretvalue@proxy.internal:8080")
    monkeypatch.setenv("https_proxy", "http://proxyuser:supersecretvalue@proxy.internal:8080")

    result = run_preflight(_config(), probe=False)
    text = json.dumps(result.to_dict(), ensure_ascii=False)

    assert result.reason_code == REASON_CLIENT_INIT_FAILED
    assert "supersecretvalue" not in text
    assert "proxyuser" not in text
    assert DUMMY_KEY not in text
    assert "HTTPS_PROXY" in result.message


def test_adapter_get_client_raises_actionable_client_init_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """adapters.py:62 used to leak a bare httpx.InvalidURL into the composer."""
    monkeypatch.setenv("NO_PROXY", "localhost,127.0.0.1,[::1],::1")
    monkeypatch.setenv("no_proxy", "localhost,127.0.0.1,[::1],::1")
    provider = OpenAICompatibleProvider(_config())

    with pytest.raises(LLMClientInitError) as excinfo:
        provider._get_client()

    assert "NO_PROXY" in excinfo.value.message
    assert excinfo.value.code == REASON_CLIENT_INIT_FAILED
    assert DUMMY_KEY not in excinfo.value.message


def test_preflight_does_not_write_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    run_preflight(_config(), transport=_ok_transport())
    run_preflight(_config(base_url=ANTHROPIC_BASE), probe=False)

    assert list(tmp_path.iterdir()) == []


# ---------------------------------------------------------------------------
# 4. Mock exemption
# ---------------------------------------------------------------------------


def test_mock_forced_skips_probe() -> None:
    result = run_preflight(_config(base_url=ANTHROPIC_BASE), force_mock=True)

    assert result.status == STATUS_SKIPPED_MOCK
    assert result.reason_code is None
    assert result.probe_attempted is False
    assert result.effective_provider == "mock"
    assert result.ok is True


def test_mock_forced_skips_probe_even_with_broken_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NO_PROXY", "[::1]")
    monkeypatch.setenv("no_proxy", "[::1]")

    result = run_preflight(_config(), force_mock=True)

    assert result.status == STATUS_SKIPPED_MOCK


# ---------------------------------------------------------------------------
# 5. Diagnostics wiring (config --ci)
# ---------------------------------------------------------------------------


def test_diagnostics_fail_on_endpoint_mismatch() -> None:
    diagnostics = run_llm_diagnostics(config=_config(base_url=ANTHROPIC_BASE))

    assert diagnostics["summary"] == "FAIL"
    assert diagnostics["preflight_status"] == STATUS_FAIL
    assert diagnostics["preflight_reason_code"] == REASON_ENDPOINT_MISMATCH
    assert "preflight: LLM_ENDPOINT_MISMATCH" in diagnostics["issues"]
    assert diagnostics["preflight"]["probe_attempted"] is False
    assert DUMMY_KEY not in json.dumps(diagnostics, ensure_ascii=False)


def test_diagnostics_fail_on_client_init(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NO_PROXY", "[::1]")
    monkeypatch.setenv("no_proxy", "[::1]")

    diagnostics = run_llm_diagnostics(config=_config())

    assert diagnostics["summary"] == "FAIL"
    assert diagnostics["preflight_reason_code"] == REASON_CLIENT_INIT_FAILED


def test_diagnostics_probe_opt_in_classifies_401(monkeypatch: pytest.MonkeyPatch) -> None:
    import repo_wiki.llm.preflight as preflight_mod

    real_factory = preflight_mod.create_sync_client

    def _factory(config, **kwargs):
        kwargs["transport"] = _transport(
            401, payload={"error": {"message": "invalid api key (2049)"}}
        )
        return real_factory(config, **kwargs)

    monkeypatch.setattr(preflight_mod, "create_sync_client", _factory)

    offline = run_llm_diagnostics(config=_config())
    assert offline["summary"] == "OK"
    assert offline["preflight"]["probe_attempted"] is False

    probed = run_llm_diagnostics(config=_config(), probe=True)
    assert probed["summary"] == "FAIL"
    assert probed["preflight_reason_code"] == REASON_AUTH_INVALID
    assert probed["preflight"]["http_status"] == 401


def test_diagnostics_mock_is_skipped_not_failed() -> None:
    diagnostics = run_llm_diagnostics(config=_config(base_url=ANTHROPIC_BASE), force_mock=True)

    assert diagnostics["preflight_status"] == STATUS_SKIPPED_MOCK
    assert diagnostics["effective_provider"] == "mock"


# ---------------------------------------------------------------------------
# 6. Manifest readiness gate
# ---------------------------------------------------------------------------


def _profile(tmp_path: Path) -> EvalOutputProfile:
    return EvalOutputProfile(
        name="qoder-like",
        root=str(tmp_path / ".repo-agent-eval"),
        create_subdirs=True,
        content_subdir="repowiki/zh/content",
    )


def _candidate_dirs(tmp_path: Path, run_id: str) -> Path:
    run_dir = tmp_path / ".repo-agent-eval" / run_id
    (run_dir / "repowiki" / "zh" / "content").mkdir(parents=True, exist_ok=True)
    (run_dir / "repowiki" / "zh" / "meta").mkdir(parents=True, exist_ok=True)
    return run_dir


def _registry(modes: list[str]) -> list[dict[str, object]]:
    return [
        {
            "path": f"pages/p{idx}.md",
            "slug": f"p{idx}",
            "type": "markdown",
            "title": f"P{idx}",
            "generation_mode": mode,
            "rejection_reason": "provider disabled" if mode == "fallback" else None,
        }
        for idx, mode in enumerate(modes)
    ]


def _manifest(tmp_path: Path, *, modes: list[str], llm: dict, ratio_threshold: float = 0.5):
    run_id = "run-gate"
    run_dir = _candidate_dirs(tmp_path, run_id)
    return generate_manifest(
        run_id=run_id,
        profile=_profile(tmp_path),
        target_repo=str(tmp_path),
        output_dir=run_dir,
        stats={"llm": llm},
        page_registry=_registry(modes),
        min_llm_success_ratio=ratio_threshold,
    )


def test_fallback_only_run_is_not_ready(tmp_path: Path) -> None:
    manifest = _manifest(
        tmp_path,
        modes=["fallback"] * 4,
        llm={
            "mode": "real",
            "llm_success_ratio": 0.0,
            "provider_disabled_after_failures": True,
        },
    )

    assert manifest.readiness_state == "NOT_READY"
    assert "FALLBACK_ONLY_RUN" in manifest.readiness_reasons
    assert "LLM_PROVIDER_DISABLED" in manifest.readiness_reasons
    assert all(p["generation_mode"] == "fallback" for p in manifest.page_registry)
    assert all(p["rejection_reason"] for p in manifest.page_registry)


def test_mock_run_is_not_ready_with_marker(tmp_path: Path) -> None:
    manifest = _manifest(
        tmp_path,
        modes=["mock"] * 3,
        llm={"mode": "mock", "mock_reason": "forced_env", "llm_success_ratio": 0.0},
    )

    assert manifest.readiness_state == "NOT_READY"
    assert "MOCK_LLM_RUN" in manifest.readiness_reasons


def test_low_llm_ratio_is_not_ready(tmp_path: Path) -> None:
    manifest = _manifest(
        tmp_path,
        modes=["llm", "fallback", "fallback", "fallback"],
        llm={"mode": "real", "llm_success_ratio": 0.25},
    )

    assert manifest.readiness_state == "NOT_READY"
    assert "LLM_SUCCESS_RATIO_BELOW_MIN" in manifest.readiness_reasons


def test_ratio_threshold_is_configurable(tmp_path: Path) -> None:
    modes = ["llm", "llm", "fallback", "fallback"]
    llm = {"mode": "real", "llm_success_ratio": 0.5}

    strict = _manifest(tmp_path, modes=modes, llm=llm, ratio_threshold=0.75)
    assert strict.readiness_state == "NOT_READY"
    assert "LLM_SUCCESS_RATIO_BELOW_MIN" in strict.readiness_reasons

    relaxed = _manifest(tmp_path, modes=modes, llm=llm, ratio_threshold=0.5)
    assert relaxed.readiness_state == "READY"
    assert relaxed.readiness_reasons == []


def test_healthy_llm_run_can_still_be_ready(tmp_path: Path) -> None:
    manifest = _manifest(
        tmp_path,
        modes=["llm"] * 3,
        llm={"mode": "real", "llm_success_ratio": 1.0},
    )

    assert manifest.readiness_state == "READY"
    assert manifest.readiness_reasons == []


def test_circuit_broken_run_not_ready_even_with_high_ratio(tmp_path: Path) -> None:
    manifest = _manifest(
        tmp_path,
        modes=["llm"] * 3,
        llm={
            "mode": "real",
            "llm_success_ratio": 1.0,
            "provider_disabled_after_failures": True,
        },
    )

    assert manifest.readiness_state == "NOT_READY"
    assert "LLM_PROVIDER_DISABLED" in manifest.readiness_reasons


def test_ratio_derived_from_page_registry_when_summary_lacks_it(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path, modes=["fallback"] * 2, llm={"mode": "real"})

    assert manifest.readiness_state == "NOT_READY"
    assert "FALLBACK_ONLY_RUN" in manifest.readiness_reasons


def test_ratio_derived_from_page_counts_for_legacy_manifests(tmp_path: Path) -> None:
    """Historical manifests carry neither ratio nor per-page mode, but do carry counts."""
    run_id = "run-gate"
    run_dir = _candidate_dirs(tmp_path, run_id)
    legacy = [
        {"path": f"pages/p{idx}.md", "slug": f"p{idx}", "type": "markdown"} for idx in range(4)
    ]

    def _manifest_for(llm: dict):
        return generate_manifest(
            run_id=run_id,
            profile=_profile(tmp_path),
            target_repo=str(tmp_path),
            output_dir=run_dir,
            stats={"llm": llm},
            page_registry=legacy,
        )

    burned = _manifest_for(
        {"mode": "real", "composed_page_count": 80, "fallback_page_count": 80}
    )
    assert burned.readiness_state == "NOT_READY"
    assert "FALLBACK_ONLY_RUN" in burned.readiness_reasons

    healthy = _manifest_for(
        {"mode": "real", "composed_page_count": 80, "fallback_page_count": 0}
    )
    assert healthy.readiness_state == "READY"
    assert healthy.readiness_reasons == []


def test_llm_stats_without_generation_evidence_are_not_falsely_branded(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path, modes=["llm"], llm={"mode": "real", "actual_tokens": 12})

    assert "FALLBACK_ONLY_RUN" not in manifest.readiness_reasons
    assert "LLM_SUCCESS_RATIO_BELOW_MIN" not in manifest.readiness_reasons


def test_runs_without_llm_stats_are_not_gated(tmp_path: Path) -> None:
    run_id = "run-rule-first"
    run_dir = _candidate_dirs(tmp_path, run_id)
    manifest = generate_manifest(
        run_id=run_id,
        profile=_profile(tmp_path),
        target_repo=str(tmp_path),
        output_dir=run_dir,
        stats={"files_written": ["a.md"]},
        page_registry=[{"path": "pages/a.md", "slug": "a", "type": "markdown"}],
    )

    assert manifest.readiness_state == "READY"


# ---------------------------------------------------------------------------
# 7. Service end-to-end: abort before compose, per-page modes, readiness
# ---------------------------------------------------------------------------

HEALTHY_MARKDOWN = """# Sample Page

## 简介

This page was composed by a fake provider for preflight gate contract tests.
It carries enough prose so the composer keeps the page instead of rejecting it
for insufficient content, and it avoids strong unsupported claims.

## 项目结构

The repository layout is described here with extra padding sentences so that
validation passes without falling back to templates during the success path.
Readers can follow the entry point, the service layer and the persistence layer.

## 核心组件

Each component is explained with its responsibility and its upstream and
downstream collaborators, so the page reads as a topic rather than a file list.
"""


class _FakeProvider(LLMProvider):
    """Deterministic provider; never opens a socket."""

    def __init__(self, markdown: str = HEALTHY_MARKDOWN) -> None:
        self._markdown = markdown
        self._config = LLMProviderConfig(
            provider="openai",
            model="fake-model",
            api_key_env=MISSING_KEY_ENV,
            timeout=5.0,
            max_retries=0,
        )

    @property
    def name(self) -> str:
        return "fake-real"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities()

    async def chat(self, request: ChatRequest) -> ChatResponse:
        return ChatResponse(content=self._markdown, model=request.model)

    def validate_config(self) -> list[tuple[str, str | None, str]]:
        return []


def _write_sample_repo(root: Path) -> None:
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text(
        "from fastapi import FastAPI\n\napp = FastAPI()\n\n\n"
        "@app.get('/health')\ndef health():\n    return {'status': 'ok'}\n\n\n"
        "class Item:\n    id: str\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        "# Sample Service\n\nSmall FastAPI service used by preflight gate tests.\n",
        encoding="utf-8",
    )


def _service(root: Path, **llm_overrides: object) -> RepoWikiService:
    cfg = RepoWikiConfig()
    cfg.project.root = str(root)
    cfg.project.exclude = [".repo-agent-eval/**", ".repo-wiki/**"]
    cfg.qoder_like.min_pages = 11
    cfg.qoder_like.max_pages = 11
    for key, value in llm_overrides.items():
        setattr(cfg.llm, key, value)
    return RepoWikiService(cfg)


def _install_fake_real_provider(
    monkeypatch: pytest.MonkeyPatch, service: RepoWikiService, markdown: str = HEALTHY_MARKDOWN
) -> None:
    """Force the real-provider code path without credentials or network."""
    provider = _FakeProvider(markdown)
    summary = {
        "effective_provider": provider.name,
        "model": provider._config.model,
        "mode": "real",
        "mock_reason": None,
        "fallback_warning": None,
        "api_key_env": MISSING_KEY_ENV,
        "api_key_present": False,
    }
    monkeypatch.setattr(
        service,
        "_resolve_qoder_like_llm",
        lambda: (provider, provider._config, summary),
    )


def _generate(service: RepoWikiService, tmp_path: Path, run_id: str) -> dict:
    return service.generate(eval_profile=_profile(tmp_path), run_id=run_id)


def test_generate_aborts_on_mismatch_before_compose(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_sample_repo(repo)
    service = _service(
        repo,
        provider="openai",
        base_url=ANTHROPIC_BASE,
        api_key_env=DUMMY_KEY_ENV,
        force_mock_llm=False,
    )

    with pytest.raises(RepoWikiError) as excinfo:
        _generate(service, tmp_path, "run-mismatch")

    assert excinfo.value.details["reason_code"] == REASON_ENDPOINT_MISMATCH
    assert excinfo.value.details["api_key_env"] == DUMMY_KEY_ENV
    assert DUMMY_KEY not in json.dumps(excinfo.value.details, ensure_ascii=False)
    # No fallback run may be produced.
    assert not (tmp_path / ".repo-agent-eval" / "run-mismatch").exists()
    assert not (repo / "docs").exists()


def test_generate_aborts_on_client_init_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NO_PROXY", "localhost,127.0.0.1,[::1],::1")
    monkeypatch.setenv("no_proxy", "localhost,127.0.0.1,[::1],::1")
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_sample_repo(repo)
    service = _service(repo, api_key_env=DUMMY_KEY_ENV, base_url=OPENAI_BASE)

    with pytest.raises(RepoWikiError) as excinfo:
        _generate(service, tmp_path, "run-client-init")

    assert excinfo.value.details["reason_code"] == REASON_CLIENT_INIT_FAILED
    assert not (tmp_path / ".repo-agent-eval" / "run-client-init").exists()


def test_mock_generate_is_not_ready_and_pages_marked_mock(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_sample_repo(repo)
    service = _service(repo, force_mock_llm=True)

    result = _generate(service, tmp_path, "run-mock")
    manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))

    assert manifest["readiness_state"] == "NOT_READY"
    assert "MOCK_LLM_RUN" in manifest["readiness_reasons"]
    assert manifest["metadata"]["is_mock_run"] is True
    assert manifest["metadata"]["preflight_status"] == STATUS_SKIPPED_MOCK
    assert manifest["metadata"]["effective_provider"] == "mock"
    assert manifest["metadata"]["llm_success_ratio"] == 0.0
    assert manifest["page_registry"]
    for page in manifest["page_registry"]:
        assert page["generation_mode"] == "mock"
        assert "rejection_reason" in page
        assert page["cited_files"] == []
        assert page["line_anchor_count"] == 0


def test_fallback_only_generate_is_not_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPO_WIKI_LLM_REAL_MAX_CALLS", "0")
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_sample_repo(repo)
    service = _service(repo)
    _install_fake_real_provider(monkeypatch, service)

    result = _generate(service, tmp_path, "run-fallback")
    manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))

    assert manifest["readiness_state"] == "NOT_READY"
    assert "FALLBACK_ONLY_RUN" in manifest["readiness_reasons"]
    assert "LLM_PROVIDER_DISABLED" in manifest["readiness_reasons"]
    assert "MOCK_LLM_RUN" not in manifest["readiness_reasons"]
    assert manifest["metadata"]["llm_success_ratio"] == 0.0
    assert manifest["metadata"]["preflight_status"] == STATUS_OK
    for page in manifest["page_registry"]:
        assert page["generation_mode"] in {"fallback", "rule"}
        assert page["rejection_reason"]


def test_llm_generate_marks_pages_llm_and_can_be_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_sample_repo(repo)
    service = _service(repo)
    _install_fake_real_provider(monkeypatch, service)

    result = _generate(service, tmp_path, "run-llm")
    manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))

    modes = {page["generation_mode"] for page in manifest["page_registry"]}
    assert modes == {"llm"}
    assert manifest["metadata"]["llm_success_ratio"] == 1.0
    assert manifest["metadata"]["preflight_status"] == STATUS_OK
    assert manifest["metadata"]["effective_provider"] == "fake-real"
    assert "MOCK_LLM_RUN" not in manifest["readiness_reasons"]
    assert "FALLBACK_ONLY_RUN" not in manifest["readiness_reasons"]
    assert manifest["readiness_state"] == "READY"
    assert all(page["rejection_reason"] is None for page in manifest["page_registry"])


def test_min_llm_success_ratio_env_override_changes_readiness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A run with half real pages is READY at 0.5 and NOT_READY at 0.9."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_sample_repo(repo)

    class _HalfRealProvider(_FakeProvider):
        """Every second call fails, so roughly half the pages fall back."""

        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        async def chat(self, request: ChatRequest) -> ChatResponse:
            self.calls += 1
            if self.calls % 2 == 0:
                raise RetryableError(
                    message="Server error: 529",
                    code=ErrorCode.SERVER_ERROR,
                    details={"status": 529},
                )
            return ChatResponse(content=self._markdown, model=request.model)

    provider = _HalfRealProvider()
    summary = {
        "effective_provider": provider.name,
        "model": provider._config.model,
        "mode": "real",
        "mock_reason": None,
        "fallback_warning": None,
    }
    service = _service(repo)
    monkeypatch.setattr(
        service, "_resolve_qoder_like_llm", lambda: (provider, provider._config, summary)
    )
    monkeypatch.setenv("REPO_WIKI_LLM_MAX_FAILURES", "99")

    monkeypatch.setenv("REPO_WIKI_QODER_LIKE_MIN_LLM_SUCCESS_RATIO", "0.9")
    strict = _generate(service, tmp_path, "run-strict")
    strict_manifest = json.loads(Path(strict["manifest_path"]).read_text(encoding="utf-8"))
    assert strict_manifest["metadata"]["min_llm_success_ratio"] == 0.9
    assert strict_manifest["readiness_state"] == "NOT_READY"

    monkeypatch.setenv("REPO_WIKI_QODER_LIKE_MIN_LLM_SUCCESS_RATIO", "0.1")
    relaxed = _generate(service, tmp_path, "run-relaxed")
    relaxed_manifest = json.loads(Path(relaxed["manifest_path"]).read_text(encoding="utf-8"))
    assert relaxed_manifest["metadata"]["min_llm_success_ratio"] == 0.1
    assert "LLM_SUCCESS_RATIO_BELOW_MIN" not in relaxed_manifest["readiness_reasons"]
    assert "FALLBACK_ONLY_RUN" not in relaxed_manifest["readiness_reasons"]


def test_yaml_min_llm_success_ratio_is_honoured(tmp_path: Path) -> None:
    cfg = RepoWikiConfig.model_validate({"qoder_like": {"min_llm_success_ratio": 0.8}})
    assert cfg.qoder_like.min_llm_success_ratio == 0.8
    service = RepoWikiService(cfg)
    assert service._resolve_min_llm_success_ratio() == 0.8


def test_force_mock_env_is_not_blocked_by_preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """REPO_WIKI_FORCE_MOCK_LLM must bypass a config that would otherwise abort."""
    monkeypatch.setenv("REPO_WIKI_FORCE_MOCK_LLM", "1")
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_sample_repo(repo)
    service = _service(repo, base_url=ANTHROPIC_BASE, api_key_env=DUMMY_KEY_ENV)

    result = _generate(service, tmp_path, "run-forced-mock")
    manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))

    assert manifest["metadata"]["preflight_status"] == STATUS_SKIPPED_MOCK
    assert manifest["readiness_state"] == "NOT_READY"
    assert "MOCK_LLM_RUN" in manifest["readiness_reasons"]