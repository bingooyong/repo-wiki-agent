#!/usr/bin/env python3
"""Verify or refresh the read-only external Qoder baseline registry.

Usage:
    python scripts/verify_baseline_registry.py
    python scripts/verify_baseline_registry.py --json reports/baseline-verify.json
    python scripts/verify_baseline_registry.py --baseline-root ai-testing-knowledge-zh=/path/to/knowledge/zh
    python scripts/verify_baseline_registry.py --update

Baseline repositories are only read. ``--update`` recomputes hashes and stats
into the registry file of *this* repository.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from repo_wiki.verifier.external_baseline_registry import (  # noqa: E402
    load_registry,
    refresh_entry,
    resolve_entry_root,
    verify_registry,
)


def _parse_overrides(values: list[str]) -> dict[str, Path]:
    overrides: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise SystemExit(f"--baseline-root expects <id>=<path>, got: {value}")
        entry_id, path = value.split("=", 1)
        overrides[entry_id] = Path(path)
    return overrides


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry", type=Path, default=REPO_ROOT / "ai" / "baselines" / "registry.json"
    )
    parser.add_argument("--baseline-root", action="append", default=[], metavar="ID=PATH")
    parser.add_argument("--update", action="store_true", help="Recompute hashes and stats in place")
    parser.add_argument("--json", type=Path, default=None, help="Write machine-readable result")
    args = parser.parse_args()

    overrides = _parse_overrides(args.baseline_root)

    if args.update:
        registry = load_registry(args.registry)
        refreshed = []
        for entry in registry["baselines"]:
            root = resolve_entry_root(entry, overrides)
            if not root.is_dir():
                print(f"FAIL {entry['id']}: baseline root missing: {root}")
                return 1
            updated = refresh_entry(entry, root)
            refreshed.append(updated)
            print(f"UPDATED {entry['id']} files={updated['file_count']} hash={updated['content_hash']}")
        registry["baselines"] = refreshed
        args.registry.write_text(
            json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return 0

    result = verify_registry(args.registry, overrides)
    for entry in result["entries"]:
        print(f"{entry['status']} {entry['id']} files={entry.get('file_count')} hash={entry.get('content_hash')}")
        for mismatch in entry["mismatches"]:
            print(f"  - {mismatch}")
    print(f"REGISTRY {result['status']}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())