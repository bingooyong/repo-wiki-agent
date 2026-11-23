"""Deterministic template renderer."""

from __future__ import annotations

import re
from pathlib import Path
from string import Template
from typing import Any

from .io import read_text

_UNRESOLVED_PLACEHOLDER = re.compile(r"\$\{([^{}]+)\}")


class TemplateRenderer:
    """
    Template renderer with stdlib fallback.
    Templates use `${var}` placeholders for deterministic rendering.
    """

    def __init__(self, template_root: Path) -> None:
        self.template_root = template_root

    def render(self, template_path: str, context: dict[str, Any]) -> str:
        raw = read_text(self.template_root / template_path)
        materialized = {k: self._coerce_value(v) for k, v in context.items()}
        rendered = Template(raw).safe_substitute(materialized)
        unresolved = sorted(set(_UNRESOLVED_PLACEHOLDER.findall(rendered)))
        if unresolved:
            raise ValueError(
                f"Unresolved template placeholders in {template_path}: "
                + ", ".join(f"${{{key}}}" for key in unresolved)
            )
        return rendered

    @staticmethod
    def _coerce_value(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (list, tuple)):
            return "\n".join(str(x) for x in value)
        return str(value)
