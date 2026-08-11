"""Inventory-to-owner-page coverage helpers for qoder-like strict verification."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class OwnerInventoryItem:
    """A service/API/model/runtime inventory item that requires owner-page coverage."""

    kind: str
    identifier: str
    source: str


OWNER_HINT_PATTERN = re.compile(
    r"\b(?:owner page|owner|owned by|service owner|module owner|所属|负责人|归属|责任|维护)\b",
    re.IGNORECASE,
)
UNIDENTIFIED_PATTERN = re.compile(r"\bUNIDENTIFIED\b|未识别|未知归属|无归属", re.IGNORECASE)


def collect_owner_inventory_items(meta_root: Path) -> list[OwnerInventoryItem]:
    """Collect core inventory items from JSON artifacts under a meta root."""

    items: list[OwnerInventoryItem] = []
    for path in sorted(meta_root.glob("*.json")):
        data = _read_json_object(path)
        source = path.name
        _collect_services(data, source, items)
        _collect_apis(data, source, items)
        _collect_models(data, source, items)
        _collect_runtime_entrypoints(data, source, items)
    deduped: dict[tuple[str, str], OwnerInventoryItem] = {}
    for item in items:
        deduped[(item.kind, item.identifier)] = item
    return list(deduped.values())


def page_has_owner_or_warning(page_text: str, identifier: str) -> tuple[bool, str]:
    """Return whether a page maps an item to an owner page or explicit UNIDENTIFIED warning."""

    if identifier not in page_text:
        return False, "identifier missing from content"
    for match in re.finditer(re.escape(identifier), page_text):
        identifier_index = match.start()
        window = page_text[max(0, identifier_index - 300) : identifier_index + 500]
        if OWNER_HINT_PATTERN.search(window):
            return True, "owner mapping"
        if UNIDENTIFIED_PATTERN.search(window):
            return True, "structured unidentified warning"
    return False, "identifier lacks owner mapping or UNIDENTIFIED warning"


def _collect_services(data: dict[str, Any], source: str, items: list[OwnerInventoryItem]) -> None:
    for item in _list_value(data, "services"):
        if isinstance(item, dict):
            identifier = _first_str(item, ("service_id", "id", "name", "display_name"))
            if identifier and _is_core(item):
                items.append(OwnerInventoryItem("service", identifier, source))


def _collect_apis(data: dict[str, Any], source: str, items: list[OwnerInventoryItem]) -> None:
    for item in (
        _list_value(data, "endpoints")
        + _list_value(data, "apis")
        + _list_value(data, "api_surfaces")
    ):
        if isinstance(item, dict):
            method = _first_str(item, ("method",))
            path = _first_str(item, ("path", "route", "url", "endpoint"))
            visibility = str(item.get("visibility") or item.get("access") or "").lower()
            public = bool(item.get("public") is True or visibility == "public" or method and path)
            if method and path and public:
                items.append(OwnerInventoryItem("api", f"{method.upper()} {path}", source))


def _collect_models(data: dict[str, Any], source: str, items: list[OwnerInventoryItem]) -> None:
    for item in _list_value(data, "models") + _list_value(data, "data_models"):
        if isinstance(item, dict):
            identifier = _first_str(item, ("model_id", "id", "name", "display_name"))
            if identifier and _is_major(item):
                items.append(OwnerInventoryItem("model", identifier, source))


def _collect_runtime_entrypoints(
    data: dict[str, Any], source: str, items: list[OwnerInventoryItem]
) -> None:
    for key in ("runtime_entrypoints", "entrypoints", "commands"):
        for item in _list_value(data, key):
            if isinstance(item, dict):
                identifier = _first_str(item, ("entrypoint", "command", "name", "id", "path"))
                if identifier:
                    items.append(OwnerInventoryItem("runtime", identifier, source))
            elif isinstance(item, str) and item.strip():
                items.append(OwnerInventoryItem("runtime", item.strip(), source))


def _is_core(item: dict[str, Any]) -> bool:
    value = str(item.get("tier") or item.get("kind") or item.get("category") or "").lower()
    return item.get("core") is not False and value not in {"minor", "internal-helper", "helper"}


def _is_major(item: dict[str, Any]) -> bool:
    value = str(item.get("tier") or item.get("kind") or item.get("category") or "").lower()
    return item.get("major") is not False and value not in {"minor", "internal", "helper"}


def _first_str(item: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _list_value(data: dict[str, Any], key: str) -> list[Any]:
    value = data.get(key)
    return value if isinstance(value, list) else []


def _read_json_object(path: Path) -> dict[str, Any]:
    import json

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}
