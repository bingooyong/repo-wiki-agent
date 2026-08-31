"""Shared API claim matching used by CRITICAL_FALSE_FACT and page compose."""

from __future__ import annotations

import re
from typing import Any

API_CLAIM_PATTERN = re.compile(
    r"\b(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\s+(/[-A-Za-z0-9_./{}:]+)"
)
FASTAPI_AUTODOC_PATHS = frozenset({"/docs", "/redoc"})
# Extra denylist for obvious test-404 fixtures; inventory check is the primary gate.
TEST_ONLY_API_PATH_TOKENS = frozenset({"wrong_path"})
_TEST_ONLY_PATH_PATTERN = re.compile(
    r"/wrong_path(?:/[-A-Za-z0-9_./{}:]*)?",
    re.IGNORECASE,
)


def normalize_claimed_api_path(path: str) -> str:
    if path != "/" and path.endswith("/"):
        return path.rstrip("/")
    return path


def api_path_slot_key(path: str) -> str:
    """Treat `{id}` and `{project_id}` as the same path slot."""
    normalized = normalize_claimed_api_path(path)
    return re.sub(r"\{[^}/]+\}", "{}", normalized)


def inventory_api_mount_prefix(apis: set[tuple[str, str]]) -> str:
    """Shared first segment (commonly `/api`) when it dominates inventory routes."""
    counts: dict[str, int] = {}
    total = 0
    for _method, path in apis:
        parts = [part for part in normalize_claimed_api_path(path).split("/") if part]
        if not parts or parts[0].startswith("{") or parts[0].startswith(":"):
            continue
        total += 1
        counts[parts[0]] = counts.get(parts[0], 0) + 1
    if total and counts:
        segment, count = max(counts.items(), key=lambda item: (item[1], item[0]))
        if count * 2 > total:
            return f"/{segment}"
        if "api" in counts:
            return "/api"
    return "/api"


def apply_api_mount_prefix(path: str, prefix: str) -> str:
    """Join a mount prefix onto a claim without doubling an existing prefix."""
    claimed = normalize_claimed_api_path(path)
    prefix = normalize_claimed_api_path(prefix)
    if not prefix or prefix == "/":
        return claimed
    if claimed == prefix or claimed.startswith(f"{prefix}/"):
        return claimed
    return f"{prefix}/{claimed.lstrip('/')}"


def api_claim_in_inventory(method: str, path: str, apis: set[tuple[str, str]]) -> bool:
    """True when method+path is a product route, including `/api` mount-prefix matches."""
    method = method.upper()
    claimed = normalize_claimed_api_path(path)
    if (method, path) in apis or (method, claimed) in apis:
        return True
    claimed_key = api_path_slot_key(claimed)
    prefixed_key = api_path_slot_key(
        apply_api_mount_prefix(claimed, inventory_api_mount_prefix(apis))
    )
    candidate_keys = {claimed_key, prefixed_key}
    return any(
        inv_method == method and api_path_slot_key(inv_path) in candidate_keys
        for inv_method, inv_path in apis
    )


def is_fastapi_framework_docs_path(path: str) -> bool:
    """FastAPI auto-docs URLs are framework-generated, not scanned route files."""
    return normalize_claimed_api_path(path) in FASTAPI_AUTODOC_PATHS


def is_test_only_api_path(path: str) -> bool:
    lowered = normalize_claimed_api_path(path).lower()
    return any(
        token == part or f"/{token}/" in f"{lowered}/"
        for token in TEST_ONLY_API_PATH_TOKENS
        for part in lowered.strip("/").split("/")
    )


def endpoints_to_api_inventory(endpoints: list[Any] | None) -> set[tuple[str, str]]:
    """Build the same (method, path) inventory CRITICAL_FALSE_FACT uses."""
    apis: set[tuple[str, str]] = set()
    for endpoint in endpoints or []:
        if isinstance(endpoint, dict):
            method = str(endpoint.get("method") or "").upper().strip()
            path = str(endpoint.get("path") or "").strip()
        else:
            method = str(getattr(endpoint, "method", "") or "").upper().strip()
            path = str(getattr(endpoint, "path", "") or "").strip()
        if method and path:
            apis.add((method, path))
    return apis


def drop_uninventoried_api_claims(
    content: str,
    apis: set[tuple[str, str]],
    *,
    fastapi_app: bool = False,
) -> str:
    """Remove METHOD /path mentions that are not product inventory routes.

    Inventory matching is the same as QODER_CRITICAL_FALSE_FACT, including
    `/api` mount-prefix aliases. Test-only 404 fixtures such as
    ``/wrong_path/asd`` are always dropped, even if they appear in tests.
    """

    def keep_claim(method: str, path: str) -> bool:
        if is_test_only_api_path(path):
            return False
        if fastapi_app and is_fastapi_framework_docs_path(path):
            return True
        if not apis:
            return True
        return api_claim_in_inventory(method, path, apis)

    def replace_claim(match: re.Match[str]) -> str:
        method, path = match.group(1), match.group(2)
        if keep_claim(method.upper(), path):
            return match.group(0)
        return ""

    cleaned_lines: list[str] = []
    for line in content.splitlines():
        rewritten = API_CLAIM_PATTERN.sub(replace_claim, line)
        rewritten = _TEST_ONLY_PATH_PATTERN.sub("", rewritten)
        if rewritten != line:
            leading_ws_len = len(rewritten) - len(rewritten.lstrip(" \t"))
            prefix, body = rewritten[:leading_ws_len], rewritten[leading_ws_len:]
            body = re.sub(r"[ \t]{2,}", " ", body)
            rewritten = (prefix + body).rstrip()
        if re.fullmatch(r"\s*[-*]\s*", rewritten):
            continue
        cleaned_lines.append(rewritten)
    return "\n".join(cleaned_lines).strip()
