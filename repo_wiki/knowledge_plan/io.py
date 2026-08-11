"""YAML load/dump/persist helpers for knowledge plans."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .schema import (
    DEFAULT_PLAN_PATH,
    ManualEditConflictError,
    attach_fingerprint,
    has_manual_managed_edits,
)


def dump_plan_yaml(plan: dict[str, Any]) -> str:
    """Serialize a knowledge plan to stable, human-editable YAML."""

    return yaml.safe_dump(plan, allow_unicode=True, sort_keys=False)


def load_plan_yaml(text: str) -> dict[str, Any]:
    """Parse a knowledge-plan YAML string."""

    parsed = yaml.safe_load(text) or {}
    if not isinstance(parsed, dict):
        raise ValueError("Knowledge plan YAML must contain a mapping.")
    return parsed


def load_plan(path: str | Path = DEFAULT_PLAN_PATH) -> dict[str, Any]:
    return load_plan_yaml(Path(path).read_text(encoding="utf-8"))


def write_plan(
    plan: dict[str, Any],
    path: str | Path = DEFAULT_PLAN_PATH,
    *,
    overwrite: bool = False,
    merge: bool = False,
) -> dict[str, Any]:
    """Write a plan, protecting manually edited generated sections by default.

    ``overwrite=True`` is the force path. ``merge=True`` preserves the existing
    ``manual_sections`` while refreshing the managed/generated portion.
    """

    target = Path(path)
    output = dict(plan)
    if target.exists() and not overwrite:
        existing = load_plan(target)
        if has_manual_managed_edits(existing) and not merge:
            raise ManualEditConflictError(
                "Existing knowledge plan has manual edits in managed sections; use overwrite=True or merge=True explicitly."
            )
        output["manual_sections"] = existing.get(
            "manual_sections", output.get("manual_sections", [])
        )
    elif target.exists() and merge:
        existing = load_plan(target)
        output["manual_sections"] = existing.get(
            "manual_sections", output.get("manual_sections", [])
        )

    output = attach_fingerprint(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dump_plan_yaml(output), encoding="utf-8")
    return output
