"""Record and replay raw LLM replies for offline generate.

Recording is opt-in via ``REPO_WIKI_LLM_CASSETTE_DIR``. Each ``_call_llm``
attempt appends one JSONL line with the page id, attempt, hashes, messages,
and the raw model reply. Replay uses ``LLM_PROVIDER=cassette`` and looks up
``(page_id, attempt)``. A prompt-hash mismatch falls back to the page id and
is logged as ``cassette_prompt_mismatch``. API keys and auth headers are
never written.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from repo_wiki.core.logging import warn as console_warn
from repo_wiki.llm.config import LLMProviderConfig, ValidationReason, redact_secrets
from repo_wiki.llm.models import (
    ChatRequest,
    ChatResponse,
    ErrorCode,
    LLMProvider,
    NonRetryableError,
    ProviderCapabilities,
)

logger = logging.getLogger(__name__)

ENV_CASSETTE_DIR = "REPO_WIKI_LLM_CASSETTE_DIR"
ENV_CASSETTE_RUN_ID = "REPO_WIKI_LLM_CASSETTE_RUN_ID"
ENV_CASSETTE_WRITE_DIR = "REPO_WIKI_LLM_CASSETTE_WRITE_DIR"

_write_lock = threading.Lock()


def _generator_version() -> str:
    from repo_wiki.generator.composer_cache import COMPOSER_GENERATOR_VERSION

    return COMPOSER_GENERATOR_VERSION


@dataclass(frozen=True)
class CassetteCallContext:
    page_id: str
    attempt: int
    prompt_hash: str
    input_hash: str = ""
    generator_version: str = ""


_call_context: ContextVar[CassetteCallContext | None] = ContextVar(
    "repo_wiki_cassette_call_context",
    default=None,
)


def set_cassette_call_context(
    *,
    page_id: str,
    attempt: int,
    prompt_hash: str,
    input_hash: str = "",
    generator_version: str = "",
) -> CassetteCallContext:
    """Bind the current compose attempt so the cassette provider can look it up."""
    ctx = CassetteCallContext(
        page_id=page_id,
        attempt=int(attempt),
        prompt_hash=prompt_hash,
        input_hash=input_hash,
        generator_version=generator_version or _generator_version(),
    )
    _call_context.set(ctx)
    return ctx


def current_cassette_context() -> CassetteCallContext | None:
    return _call_context.get()


def prompt_hash_for_messages(messages: list[Any]) -> str:
    payload = []
    for message in messages:
        if hasattr(message, "role"):
            role = getattr(message, "role", "")
            content = getattr(message, "content", "")
        elif isinstance(message, dict):
            role = message.get("role", "")
            content = message.get("content", "")
        else:
            role = ""
            content = str(message)
        payload.append({"role": str(role), "content": str(content)})
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def cassette_dir() -> Path | None:
    raw = os.environ.get(ENV_CASSETTE_DIR, "").strip()
    return Path(raw) if raw else None


def cassette_write_dir() -> Path | None:
    raw = os.environ.get(ENV_CASSETTE_WRITE_DIR, "").strip()
    return Path(raw) if raw else None


def cassette_jsonl_path(directory: Path | None = None) -> Path | None:
    write_root = cassette_write_dir()
    root: Path | None
    if write_root is not None:
        root = write_root
    else:
        if os.environ.get("LLM_PROVIDER", "").strip().lower() == "cassette":
            return None
        root = directory or cassette_dir()
    if root is None:
        return None
    run_id = os.environ.get(ENV_CASSETTE_RUN_ID, "").strip()
    name = f"{run_id}.jsonl" if run_id else "llm-cassette.jsonl"
    return root / name


def load_cassette_rows(directory: str | Path) -> list[dict[str, Any]]:
    """Load every JSONL recording under ``directory`` (or a single file)."""
    root = Path(directory)
    if not root.exists():
        return []
    paths = [root] if root.is_file() else sorted(root.glob("*.jsonl"))
    rows: list[dict[str, Any]] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _safe_messages(messages: list[Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for message in messages:
        if hasattr(message, "role"):
            role = str(getattr(message, "role", "") or "")
            content = str(getattr(message, "content", "") or "")
        elif isinstance(message, dict):
            role = str(message.get("role") or "")
            content = str(message.get("content") or "")
        else:
            role = ""
            content = str(message)
        out.append({"role": role, "content": redact_secrets(content)})
    return out


def record_cassette_attempt(
    *,
    page_id: str,
    attempt: int,
    input_hash: str,
    prompt_hash: str,
    generator_version: str,
    model: str,
    messages: list[Any],
    raw_reply: str,
    usage: dict[str, Any] | None = None,
    finish_reason: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> Path | None:
    """Append one JSONL line when ``REPO_WIKI_LLM_CASSETTE_DIR`` is set."""
    path = cassette_jsonl_path()
    if path is None:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    row: dict[str, Any] = {
        "page_id": page_id,
        "attempt": int(attempt),
        "input_hash": input_hash,
        "prompt_hash": prompt_hash,
        "generator_version": generator_version,
        "model": model,
        "messages": _safe_messages(messages),
        "raw_reply": raw_reply if raw_reply is not None else "",
        "usage": usage or {},
        "finish_reason": finish_reason,
    }
    if temperature is not None:
        row["temperature"] = temperature
    if max_tokens is not None:
        row["max_tokens"] = max_tokens
    line = redact_secrets(json.dumps(row, ensure_ascii=False))
    with _write_lock:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    return path


class CassetteLLMProvider(LLMProvider):
    """Offline provider that replays recorded raw replies by page id + attempt."""

    def __init__(
        self,
        config: LLMProviderConfig | None = None,
        rows: list[dict[str, Any]] | None = None,
        directory: str | Path | None = None,
    ) -> None:
        self._config = config or LLMProviderConfig(provider="cassette", model="cassette")
        self._directory = Path(directory) if directory is not None else cassette_dir()
        if rows is not None:
            self._rows = list(rows)
        elif self._directory is not None:
            self._rows = load_cassette_rows(self._directory)
        else:
            self._rows = []
        self.prompt_mismatches: list[dict[str, Any]] = []

    @classmethod
    def from_dir(
        cls,
        directory: str | Path,
        config: LLMProviderConfig | None = None,
    ) -> CassetteLLMProvider:
        return cls(config=config, directory=directory)

    @classmethod
    def from_env(cls, config: LLMProviderConfig | None = None) -> CassetteLLMProvider:
        return cls(config=config)

    @property
    def name(self) -> str:
        return "cassette"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_streaming=False,
            supports_functions=False,
            supports_vision=False,
            supports_json_mode=False,
            supports_reasoning=False,
            max_context_tokens=128000,
        )

    def _lookup(
        self,
        page_id: str,
        attempt: int,
        prompt_hash: str,
    ) -> tuple[dict[str, Any] | None, bool]:
        page_rows = [row for row in self._rows if row.get("page_id") == page_id]
        if not page_rows:
            return None, False
        attempt_rows = [row for row in page_rows if int(row.get("attempt", 0) or 0) == int(attempt)]
        if attempt_rows:
            exact = [row for row in attempt_rows if row.get("prompt_hash") == prompt_hash]
            if exact:
                return exact[-1], False
            return attempt_rows[-1], True
        return page_rows[-1], True

    def _note_mismatch(self, page_id: str, attempt: int, expected: str, recorded: Any) -> None:
        info = {
            "page_id": page_id,
            "attempt": attempt,
            "expected_prompt_hash": expected,
            "recorded_prompt_hash": recorded,
        }
        self.prompt_mismatches.append(info)
        logger.warning(
            "cassette_prompt_mismatch page_id=%s attempt=%s expected=%s recorded=%s",
            page_id,
            attempt,
            expected,
            recorded,
        )
        console_warn(
            "cassette_prompt_mismatch "
            f"page_id={page_id} attempt={attempt} "
            f"expected={expected} recorded={recorded}"
        )

    async def chat(self, request: ChatRequest) -> ChatResponse:
        ctx = current_cassette_context()
        if ctx is None:
            raise NonRetryableError(
                "cassette provider requires page_id/attempt context from compose_page",
                code=ErrorCode.INVALID_REQUEST.value,
            )
        row, mismatch = self._lookup(ctx.page_id, ctx.attempt, ctx.prompt_hash)
        if row is None:
            raise NonRetryableError(
                f"cassette has no recording for page_id={ctx.page_id!r}",
                code=ErrorCode.INVALID_REQUEST.value,
            )
        if mismatch:
            self._note_mismatch(
                ctx.page_id,
                ctx.attempt,
                ctx.prompt_hash,
                row.get("prompt_hash"),
            )
        raw = row.get("raw_reply")
        if raw is None:
            raw = row.get("response_content") or row.get("content") or ""
        usage = row.get("usage") if isinstance(row.get("usage"), dict) else {}
        return ChatResponse(
            content=str(raw),
            model=request.model or str(row.get("model") or "cassette"),
            usage=usage,
            finish_reason=str(row.get("finish_reason") or "stop"),
            raw_response={"cassette": True, "prompt_mismatch": mismatch},
        )

    def validate_config(self) -> list[tuple[str, str | None, str]]:
        return [
            ("provider", "cassette", ValidationReason.VALID.value),
            ("model", self._config.model, ValidationReason.VALID.value),
            ("base_url", self._config.base_url, ValidationReason.VALID.value),
            ("api_key_env", None, ValidationReason.VALID.value),
            ("max_tokens", str(self._config.max_tokens), ValidationReason.VALID.value),
            ("temperature", str(self._config.temperature), ValidationReason.VALID.value),
            ("timeout", str(self._config.timeout), ValidationReason.VALID.value),
            ("max_retries", str(self._config.max_retries), ValidationReason.VALID.value),
        ]
