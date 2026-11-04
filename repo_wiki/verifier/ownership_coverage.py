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
    defining_file: str = ""
    defining_handler: str = ""
    defining_class: str = ""


@dataclass(frozen=True)
class ApiOwnerBinding:
    """Mounted ``METHOD path`` bound to the handler file that defines it."""

    identifier: str
    defining_file: str
    defining_handler: str


@dataclass(frozen=True)
class ModelOwnerBinding:
    """Scanned data-model identifier bound to the file/class that defines it."""

    identifier: str
    defining_file: str
    defining_class: str


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
        key = (item.kind, item.identifier)
        existing = deduped.get(key)
        if existing is None or (not _has_defining_owner(existing) and _has_defining_owner(item)):
            deduped[key] = item
    return list(deduped.values())


def map_mounted_api_owners(surfaces: Any) -> dict[str, ApiOwnerBinding]:
    """Join scanned API surfaces to mounted ``METHOD path`` owner keys."""
    bindings: dict[str, ApiOwnerBinding] = {}
    if not surfaces:
        return bindings
    for item in surfaces:
        method = _surface_str(item, ("method",))
        path = _surface_str(item, ("path", "route", "url", "endpoint"))
        if not method or not path:
            continue
        defining_file = _surface_str(item, ("file_path", "evidence_path", "handler_hint"))
        defining_handler = _surface_str(item, ("handler",))
        if not defining_file and not defining_handler:
            continue
        identifier = f"{method.upper()} {path}"
        bindings[identifier] = ApiOwnerBinding(
            identifier=identifier,
            defining_file=defining_file,
            defining_handler=defining_handler,
        )
    return bindings


def map_scanned_model_owners(models: Any) -> dict[str, ModelOwnerBinding]:
    """Join scanned Pydantic/data-model types to defining file/class owner keys."""
    bindings: dict[str, ModelOwnerBinding] = {}
    if not models:
        return bindings
    for item in models:
        identifier = _surface_str(item, ("model_id", "id", "name", "display_name"))
        defining_file = _surface_str(item, ("file_path", "evidence_path"))
        defining_class = _surface_str(item, ("defining_class", "class_name", "name"))
        if not identifier or not defining_file:
            continue
        if not defining_class:
            defining_class = identifier
        bindings[identifier] = ModelOwnerBinding(
            identifier=identifier,
            defining_file=defining_file,
            defining_class=defining_class,
        )
    return bindings


def owner_coverage_gaps(
    items: list[OwnerInventoryItem],
    pages: list[str],
    warnings: set[Any],
) -> list[OwnerInventoryItem]:
    """Return inventory items that still lack owner mapping or UNIDENTIFIED warning."""
    missing: list[OwnerInventoryItem] = []
    for item in items:
        covered, _reason = item_owner_coverage(item, pages, warnings)
        if not covered:
            missing.append(item)
    return missing


def item_owner_coverage(
    item: OwnerInventoryItem,
    pages: list[str],
    warnings: set[Any],
) -> tuple[bool, str]:
    """Return whether an inventory item has owner mapping, defining owner, or warning."""
    if (item.kind, item.identifier) in warnings or item.identifier in warnings:
        return True, "structured unidentified warning"
    if item.kind == "api" and _has_defining_owner(item):
        return True, "defining file/handler"
    if item.kind == "model" and _has_defining_owner(item):
        return True, "defining file/class"
    if item.kind == "service" and _has_defining_owner(item):
        return True, "defining file"
    for page_text in pages:
        covered, reason = page_has_owner_or_warning(page_text, item.identifier)
        if covered:
            return True, reason
    return False, "identifier lacks owner mapping or UNIDENTIFIED warning"


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
                items.append(
                    OwnerInventoryItem(
                        "service",
                        identifier,
                        source,
                        defining_file=_first_str(item, ("file_path", "evidence_path")) or "",
                    )
                )


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
                items.append(
                    OwnerInventoryItem(
                        "api",
                        f"{method.upper()} {path}",
                        source,
                        defining_file=_first_str(
                            item, ("file_path", "evidence_path", "handler_hint")
                        )
                        or "",
                        defining_handler=_first_str(item, ("handler",)) or "",
                    )
                )


def _collect_models(data: dict[str, Any], source: str, items: list[OwnerInventoryItem]) -> None:
    for item in _list_value(data, "models") + _list_value(data, "data_models"):
        if isinstance(item, dict):
            identifier = _first_str(item, ("model_id", "id", "name", "display_name"))
            if identifier and _is_major(item):
                defining_file = _first_str(item, ("file_path", "evidence_path")) or ""
                defining_class = ""
                if defining_file:
                    defining_class = (
                        _first_str(item, ("defining_class", "class_name", "name")) or identifier
                    )
                items.append(
                    OwnerInventoryItem(
                        "model",
                        identifier,
                        source,
                        defining_file=defining_file,
                        defining_class=defining_class,
                    )
                )


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


def _has_defining_owner(item: OwnerInventoryItem) -> bool:
    if item.kind == "model":
        return bool(item.defining_file.strip())
    return bool(item.defining_file.strip() or item.defining_handler.strip())


def _surface_str(item: Any, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = item.get(key) if isinstance(item, dict) else getattr(item, key, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


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
