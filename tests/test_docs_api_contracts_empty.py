"""Committed API contracts page must not invent HTTP endpoints."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_CONTRACTS = ROOT / "docs" / "04-api-contracts.md"


def test_committed_api_contracts_has_no_fake_http_inventory() -> None:
    text = API_CONTRACTS.read_text(encoding="utf-8")
    first_line = text.splitlines()[0]

    assert "/webhook/github" not in text
    assert "/items" not in text
    assert "端点数 | 10" not in text
    assert "**端点数量**: 10" not in text
    assert "repo-agent" not in first_line
