"""LLM protocol/credential preflight shared by ``config --ci`` and qoder-like generate.

Two stages, cheapest first:

1. **Offline checks (no network).** Protocol consistency between ``provider`` and
   ``base_url``, then HTTP client construction. Ambient proxy env vars can make
   ``httpx`` raise *before* any request is sent (measured: ``NO_PROXY`` containing a
   bare IPv6 entry such as ``[::1]`` yields ``InvalidURL: Invalid port: ':1]'``).
2. **Minimal probe (optional).** One ``max_tokens=8`` request with the timeout capped
   at 15s, classifying credential vs endpoint vs reachability failures.

Messages never contain API key or proxy credential values: only env var *names*,
host names and HTTP status codes. The probe is read-only and writes no files.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

import httpx

from repo_wiki.llm.config import LLMProviderConfig, get_api_key_from_env, redact_secrets
from repo_wiki.llm.models import NonRetryableError

STATUS_OK = "OK"
STATUS_FAIL = "FAIL"
STATUS_SKIPPED_MOCK = "skipped_mock"

REASON_ENDPOINT_MISMATCH = "LLM_ENDPOINT_MISMATCH"
REASON_AUTH_INVALID = "LLM_AUTH_INVALID"
REASON_UNREACHABLE = "LLM_UNREACHABLE"
REASON_CLIENT_INIT_FAILED = "LLM_CLIENT_INIT_FAILED"
REASON_EMPTY_RESPONSE = "LLM_EMPTY_RESPONSE"

PROBE_MAX_TOKENS = 8
PROBE_TIMEOUT_CAP_SECONDS = 15.0
PROBE_PROMPT = "ping"

#: Env vars httpx reads when ``trust_env`` is on. Names only — never values.
PROXY_ENV_VARS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
)

_MINIMAX_HOSTS = ("minimaxi.com", "minimax.io", "minimax.chat")
_URL_USERINFO_PATTERN = re.compile(r"://[^/\s:@]+:[^/\s@]+@")


class LLMClientInitError(NonRetryableError):
    """HTTP client could not be constructed (usually ambient proxy env).

    Non-retryable: retrying cannot fix a malformed ``NO_PROXY`` entry, and letting
    the composer retry it burns a whole run into fallback pages.
    """


@dataclass
class PreflightResult:
    """Structured preflight outcome, safe to log and to persist in a manifest."""

    status: str = STATUS_OK
    reason_code: str | None = None
    message: str = ""
    hint: str | None = None
    effective_provider: str = "openai"
    http_status: int | None = None
    probe_attempted: bool = False
    probe_timeout_seconds: float | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when generation may proceed (OK or explicitly skipped for mock)."""
        return self.status in (STATUS_OK, STATUS_SKIPPED_MOCK)

    @property
    def failed(self) -> bool:
        return self.status == STATUS_FAIL

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe dict for diagnostics output and run metadata."""
        return {
            "status": self.status,
            "reason_code": self.reason_code,
            "message": self.message,
            "hint": self.hint,
            "effective_provider": self.effective_provider,
            "http_status": self.http_status,
            "probe_attempted": self.probe_attempted,
            "probe_timeout_seconds": self.probe_timeout_seconds,
            "warnings": list(self.warnings),
        }


def _sanitize_detail(text: str) -> str:
    """Strip credentials from an exception detail before it reaches logs/manifests."""
    return redact_secrets(_URL_USERINFO_PATTERN.sub("://[REDACTED]@", text))


def _present_proxy_env_names() -> list[str]:
    return [name for name in PROXY_ENV_VARS if os.environ.get(name)]


def client_init_message(exc: BaseException, config: LLMProviderConfig) -> str:
    """Actionable client-construction error naming proxy env vars, never their values."""
    present = _present_proxy_env_names()
    names = ", ".join(present) if present else "(none set)"
    return (
        f"LLM HTTP client construction failed ({type(exc).__name__}: "
        f"{_sanitize_detail(str(exc))}). base_url={config.base_url or '(default)'} is not "
        f"the problem: httpx also parses ambient proxy env vars at construction time. "
        f"Proxy env vars currently set: {names}. Check HTTP_PROXY/HTTPS_PROXY/NO_PROXY "
        f"(and lowercase http_proxy/https_proxy/no_proxy): bare IPv6 entries such as "
        f"'[::1]' or '::1', and CIDR entries such as '127.0.0.0/8', are parsed as URLs "
        f"by httpx and crash with errors like \"Invalid port: ':1]'\". "
        f"Remove the bare IPv6/CIDR entries (keep plain hosts, e.g. "
        f"NO_PROXY='localhost,127.0.0.1') or unset the proxy vars for this run."
    )


def _construct_client(
    client_cls: type,
    config: LLMProviderConfig,
    *,
    default_base_url: str,
    headers: dict[str, str],
    timeout: float,
    transport: Any | None = None,
) -> Any:
    kwargs: dict[str, Any] = {
        "base_url": config.base_url or default_base_url,
        "timeout": httpx.Timeout(timeout),
        "headers": headers,
    }
    if transport is not None:
        kwargs["transport"] = transport
    try:
        return client_cls(**kwargs)
    except Exception as exc:  # httpx.InvalidURL and other construction-time failures
        raise LLMClientInitError(
            message=client_init_message(exc, config),
            code=REASON_CLIENT_INIT_FAILED,
            details={"reason_code": REASON_CLIENT_INIT_FAILED},
        ) from exc


def create_async_client(
    config: LLMProviderConfig,
    *,
    default_base_url: str,
    headers: dict[str, str],
    timeout: float | None = None,
) -> httpx.AsyncClient:
    """Build the adapter's async client, converting env crashes into actionable errors."""
    return _construct_client(
        httpx.AsyncClient,
        config,
        default_base_url=default_base_url,
        headers=headers,
        timeout=config.timeout if timeout is None else timeout,
    )


def create_sync_client(
    config: LLMProviderConfig,
    *,
    default_base_url: str,
    headers: dict[str, str],
    timeout: float | None = None,
    transport: Any | None = None,
) -> httpx.Client:
    """Build a sync client for the preflight probe (same env failure surface)."""
    return _construct_client(
        httpx.Client,
        config,
        default_base_url=default_base_url,
        headers=headers,
        timeout=config.timeout if timeout is None else timeout,
        transport=transport,
    )


def _base_path(config: LLMProviderConfig) -> str:
    base = config.base_url or ""
    if not base:
        return ""
    try:
        return urlsplit(base).path.rstrip("/")
    except ValueError:
        return ""


def _is_anthropic_protocol_base(config: LLMProviderConfig) -> bool:
    path = _base_path(config).lower()
    return path.endswith("/anthropic") or "/anthropic/" in path


def uses_anthropic_compatible_api(config: LLMProviderConfig) -> bool:
    """True when the resolved adapter speaks the Anthropic Messages protocol.

    Mirrors ``MinimaxProvider._uses_anthropic_compatible_api`` so the probe hits the
    same route real pages will hit.
    """
    return bool(
        config.provider == "minimax"
        and config.base_url
        and "/anthropic" in config.base_url.rstrip("/")
    )


def default_base_url_for(config: LLMProviderConfig) -> str:
    if config.provider == "minimax":
        return "https://api.minimax.chat/v1"
    return "https://api.openai.com/v1"


def probe_request_spec(config: LLMProviderConfig) -> tuple[str, dict[str, Any]]:
    """Return ``(path, payload)`` matching the adapter that will serve real pages."""
    payload: dict[str, Any] = {
        "model": config.model,
        "messages": [{"role": "user", "content": PROBE_PROMPT}],
        "max_tokens": PROBE_MAX_TOKENS,
        "temperature": 0.0,
    }
    if uses_anthropic_compatible_api(config):
        return "/v1/messages", payload
    if config.provider == "minimax":
        return "/text/chatcompletion_v2", payload
    return "/chat/completions", payload


def check_protocol_consistency(config: LLMProviderConfig) -> PreflightResult | None:
    """Offline provider/base_url protocol check. Returns a FAIL result or None."""
    if config.provider == "minimax":
        # MinimaxProvider has an Anthropic-compatible branch, so /anthropic is legal.
        return None
    if not _is_anthropic_protocol_base(config):
        return None
    path, _payload = probe_request_spec(config)
    base = config.base_url or ""
    return PreflightResult(
        status=STATUS_FAIL,
        reason_code=REASON_ENDPOINT_MISMATCH,
        message=(
            f"Protocol mismatch: provider={config.provider} speaks the OpenAI-compatible "
            f"protocol and would POST {base}{path}, but LLM_BASE_URL points at an "
            f"Anthropic-protocol gateway path ('/anthropic'). Measured result: HTTP 404."
        ),
        hint=(
            f"Either set LLM_BASE_URL to the OpenAI-compatible endpoint of the same vendor "
            f"(for MiniMax: https://api.minimaxi.com/v1), or set LLM_PROVIDER=minimax so the "
            f"Anthropic-compatible adapter is used. Current api_key_env={config.api_key_env} "
            f"must hold a key issued for whichever endpoint you pick."
        ),
        effective_provider=config.provider,
    )


def minimax_host_warning(config: LLMProviderConfig) -> str | None:
    """Warning-level hint when provider=minimax points at a non-MiniMax host (self-hosted proxy OK)."""
    if config.provider != "minimax" or not config.base_url:
        return None
    try:
        host = (urlsplit(config.base_url).hostname or "").lower()
    except ValueError:
        return None
    if not host or any(host == h or host.endswith("." + h) for h in _MINIMAX_HOSTS):
        return None
    return (
        f"provider=minimax but LLM_BASE_URL host '{host}' is not a MiniMax host. "
        f"This is allowed for self-hosted proxies; verify the proxy forwards the MiniMax "
        f"protocol and that {config.api_key_env} holds a key it accepts."
    )


def _looks_like_html(response: httpx.Response) -> bool:
    content_type = response.headers.get("content-type", "").lower()
    if "text/html" in content_type:
        return True
    body = response.text.lstrip()[:200].lower()
    return body.startswith("<!doctype html") or body.startswith("<html") or body.startswith("<head")


def _probe_content(config: LLMProviderConfig, data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    if uses_anthropic_compatible_api(config):
        blocks = data.get("content") or []
        if isinstance(blocks, list):
            return "".join(
                str(b.get("text") or "") for b in blocks if isinstance(b, dict)
            ).strip()
        return ""
    choices = data.get("choices") or []
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        message = choices[0].get("message") or {}
        if isinstance(message, dict):
            return str(message.get("content") or "").strip()
    return ""


def _host_of(config: LLMProviderConfig) -> str:
    base = config.base_url or default_base_url_for(config)
    try:
        return urlsplit(base).hostname or base
    except ValueError:
        return base


def _endpoint_mismatch_hint(config: LLMProviderConfig, response: httpx.Response) -> str:
    base = config.base_url or default_base_url_for(config)
    path, _payload = probe_request_spec(config)
    if _looks_like_html(response):
        return (
            f"HTTP {response.status_code} returned an HTML page, not a JSON API error: "
            f"'{_host_of(config)}' is a web console host, not an API host. Point LLM_BASE_URL "
            f"at the vendor's API host (for MiniMax: https://api.minimaxi.com/v1) instead of "
            f"the platform/console domain."
        )
    return (
        f"HTTP {response.status_code} with a JSON/text API error: the host is reachable but "
        f"{base}{path} is not a valid route for provider={config.provider}. Fix the "
        f"LLM_BASE_URL path (OpenAI-compatible endpoints usually end in '/v1') or switch "
        f"LLM_PROVIDER to the protocol that gateway actually serves."
    )


def _auth_hint(config: LLMProviderConfig, status: int) -> str:
    return (
        f"HTTP {status} from {_host_of(config)}: the API key in env var "
        f"{config.api_key_env} is not accepted by this endpoint. Keys are host/protocol "
        f"specific — a key issued for an Anthropic-protocol gateway is rejected by the "
        f"OpenAI-compatible endpoint (measured: HTTP 401 'invalid api key'). Set a key "
        f"issued for this host, or point LLM_BASE_URL at the gateway that issued the key. "
        f"The key value is never logged."
    )


def run_preflight(
    config: LLMProviderConfig,
    *,
    force_mock: bool = False,
    probe: bool = True,
    transport: Any | None = None,
) -> PreflightResult:
    """Run offline checks and (optionally) one minimal probe.

    Args:
        config: Resolved provider config.
        force_mock: Mock LLM forced (env ``REPO_WIKI_FORCE_MOCK_LLM`` / YAML
            ``llm.force_mock_llm``). Skips the probe entirely; status ``skipped_mock``.
        probe: When False, only offline checks run (no network at all).
        transport: Optional ``httpx`` transport override (tests use ``MockTransport``).

    Returns:
        PreflightResult; ``status`` is ``OK``, ``skipped_mock`` or ``FAIL``.
    """
    if force_mock:
        return PreflightResult(
            status=STATUS_SKIPPED_MOCK,
            effective_provider="mock",
            message=(
                "Mock LLM forced; protocol/credential probe skipped. Mock runs are "
                "synthetic and must not be published as READY."
            ),
        )

    warnings: list[str] = []
    host_warning = minimax_host_warning(config)
    if host_warning:
        warnings.append(host_warning)

    mismatch = check_protocol_consistency(config)
    if mismatch is not None:
        mismatch.warnings = warnings
        return mismatch

    timeout = min(float(config.timeout), PROBE_TIMEOUT_CAP_SECONDS)
    api_key = get_api_key_from_env(config.api_key_env)
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        client = create_sync_client(
            config,
            default_base_url=default_base_url_for(config),
            headers=headers,
            timeout=timeout,
            transport=transport,
        )
    except LLMClientInitError as exc:
        return PreflightResult(
            status=STATUS_FAIL,
            reason_code=REASON_CLIENT_INIT_FAILED,
            message=exc.message,
            hint=(
                "Fix the ambient proxy environment before generating; this failure happens "
                "before any request is sent and would otherwise repeat on every page."
            ),
            effective_provider=config.provider,
            warnings=warnings,
        )

    try:
        if not probe:
            return PreflightResult(
                status=STATUS_OK,
                effective_provider=config.provider,
                message=(
                    "Offline preflight passed (protocol consistency + client construction). "
                    "Credential/endpoint probe disabled."
                ),
                probe_attempted=False,
                probe_timeout_seconds=timeout,
                warnings=warnings,
            )

        if not api_key:
            warnings.append(
                f"api_key_env {config.api_key_env} is unset; credential probe skipped "
                f"(keyless/local endpoint assumed)."
            )
            return PreflightResult(
                status=STATUS_OK,
                effective_provider=config.provider,
                message="Offline preflight passed; no API key present so no probe was sent.",
                probe_attempted=False,
                probe_timeout_seconds=timeout,
                warnings=warnings,
            )

        path, payload = probe_request_spec(config)
        try:
            response = client.post(path, json=payload)
        except httpx.InvalidURL as exc:
            return PreflightResult(
                status=STATUS_FAIL,
                reason_code=REASON_CLIENT_INIT_FAILED,
                message=client_init_message(exc, config),
                effective_provider=config.provider,
                probe_attempted=True,
                probe_timeout_seconds=timeout,
                warnings=warnings,
            )
        except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPError) as exc:
            return PreflightResult(
                status=STATUS_FAIL,
                reason_code=REASON_UNREACHABLE,
                message=(
                    f"LLM endpoint unreachable: {type(exc).__name__} while probing "
                    f"{_host_of(config)} within {timeout:.1f}s. Check LLM_BASE_URL, DNS, "
                    f"VPN/firewall and HTTP_PROXY/HTTPS_PROXY/NO_PROXY (names only; values "
                    f"are never logged)."
                ),
                hint=(
                    f"Verify the host resolves and is reachable from this machine, then "
                    f"re-run. api_key_env={config.api_key_env}."
                ),
                effective_provider=config.provider,
                probe_attempted=True,
                probe_timeout_seconds=timeout,
                warnings=warnings,
            )

        status = response.status_code
        if status in (401, 403):
            return PreflightResult(
                status=STATUS_FAIL,
                reason_code=REASON_AUTH_INVALID,
                message=(
                    f"LLM credential rejected: HTTP {status} from {_host_of(config)} "
                    f"(api_key_env={config.api_key_env})."
                ),
                hint=_auth_hint(config, status),
                effective_provider=config.provider,
                http_status=status,
                probe_attempted=True,
                probe_timeout_seconds=timeout,
                warnings=warnings,
            )
        if status in (404, 405):
            return PreflightResult(
                status=STATUS_FAIL,
                reason_code=REASON_ENDPOINT_MISMATCH,
                message=(
                    f"LLM endpoint mismatch: HTTP {status} from {_host_of(config)} for "
                    f"provider={config.provider} (api_key_env={config.api_key_env})."
                ),
                hint=_endpoint_mismatch_hint(config, response),
                effective_provider=config.provider,
                http_status=status,
                probe_attempted=True,
                probe_timeout_seconds=timeout,
                warnings=warnings,
            )
        if status == 429 or status >= 500:
            return PreflightResult(
                status=STATUS_FAIL,
                reason_code=REASON_UNREACHABLE,
                message=(
                    f"LLM endpoint not usable: HTTP {status} from {_host_of(config)} "
                    f"(rate limit or server-side outage)."
                ),
                hint="Retry later or reduce concurrency; this is not a credential problem.",
                effective_provider=config.provider,
                http_status=status,
                probe_attempted=True,
                probe_timeout_seconds=timeout,
                warnings=warnings,
            )
        if status >= 400:
            return PreflightResult(
                status=STATUS_FAIL,
                reason_code=REASON_ENDPOINT_MISMATCH,
                message=(
                    f"LLM probe rejected: HTTP {status} from {_host_of(config)} for "
                    f"provider={config.provider}, model={config.model}."
                ),
                hint=(
                    f"Check LLM_MODEL is served by this endpoint and that LLM_BASE_URL "
                    f"matches provider={config.provider}. api_key_env={config.api_key_env}."
                ),
                effective_provider=config.provider,
                http_status=status,
                probe_attempted=True,
                probe_timeout_seconds=timeout,
                warnings=warnings,
            )

        try:
            data = response.json()
        except ValueError:
            data = None
        content = _probe_content(config, data)
        if not content:
            return PreflightResult(
                status=STATUS_FAIL,
                reason_code=REASON_EMPTY_RESPONSE,
                message=(
                    f"LLM probe returned HTTP {status} but no assistant content from "
                    f"{_host_of(config)} (model={config.model})."
                ),
                hint=(
                    f"The endpoint answered but produced an empty completion. Verify "
                    f"LLM_MODEL is a chat model served by this host and that the response "
                    f"shape matches provider={config.provider}."
                ),
                effective_provider=config.provider,
                http_status=status,
                probe_attempted=True,
                probe_timeout_seconds=timeout,
                warnings=warnings,
            )

        return PreflightResult(
            status=STATUS_OK,
            effective_provider=config.provider,
            message=(
                f"LLM preflight OK: HTTP {status} from {_host_of(config)} with "
                f"max_tokens={PROBE_MAX_TOKENS} probe (model={config.model})."
            ),
            http_status=status,
            probe_attempted=True,
            probe_timeout_seconds=timeout,
            warnings=warnings,
        )
    finally:
        client.close()