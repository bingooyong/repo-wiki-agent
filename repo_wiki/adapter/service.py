from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from repo_wiki.generator.io import ensure_dir, read_yamlish, write_text


class AdapterService:
    def __init__(self, root: Path) -> None:
        self.root = root

    def sync(self) -> dict[str, Any]:
        refs = self._collect_reference_paths()
        files = {
            ".claude/CLAUDE.md": self._render_claude_md(refs),
            ".claude/settings.json": json.dumps(
                {
                    "knowledge_base": refs,
                    "default_mode": "read_then_reference",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            ".claude/skills/repo-wiki-navigation/SKILL.md": self._render_skill_md(
                "Claude Code", refs
            ),
            "AGENTS.md": self._render_agents_md(refs),
            ".opencode/opencode.json": json.dumps(
                {
                    "knowledge_paths": refs,
                    "entrypoint": "docs/00-overview.md",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            ".agents/skills/repo-wiki-navigation/SKILL.md": self._render_skill_md("OpenCode", refs),
            ".codex/config.toml": self._render_codex_config(refs),
            ".codex/hooks.json": json.dumps(
                {
                    "post_commands": [
                        {"command": "repo-wiki verify --ci", "on": ["init", "update"]},
                    ]
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        }

        written: list[str] = []
        for rel_path, content in files.items():
            target = self.root / rel_path
            ensure_dir(target.parent)
            write_text(target, content)
            written.append(rel_path)

        missing_refs = [path for path in refs if not (self.root / path).exists()]
        return {
            "written_files": sorted(written),
            "reference_paths": refs,
            "missing_references": sorted(missing_refs),
            "valid": not missing_refs,
        }

    def _collect_reference_paths(self) -> list[str]:
        module_index = read_yamlish(
            self.root / "ai" / "source-of-truth" / "module-index.yaml", {"modules": []}
        )
        modules = module_index.get("modules", []) if isinstance(module_index, dict) else []
        module_docs = []
        for module in modules:
            if isinstance(module, dict):
                doc_path = str(module.get("doc_path", "")).strip()
                if doc_path:
                    module_docs.append(doc_path)
        refs = [
            "ai/source-of-truth/repo-map.yaml",
            "ai/source-of-truth/module-index.yaml",
            "ai/source-of-truth/api-index.yaml",
            "ai/source-of-truth/data-models.yaml",
            "ai/source-of-truth/task-catalog.yaml",
            "docs/00-overview.md",
            "docs/01-architecture.md",
            "docs/03-module-map.md",
            "docs/04-api-contracts.md",
            "docs/05-data-model.md",
        ]
        refs.extend(sorted(set(module_docs)))
        return sorted(set(refs))

    def _render_claude_md(self, refs: list[str]) -> str:
        lines = [
            "# Repository AI Knowledge Navigation",
            "",
            "Use these generated artifacts as source of truth before reading raw source code.",
            "",
            "## Canonical Paths",
        ]
        lines.extend(f"- `{path}`" for path in refs)
        return "\n".join(lines) + "\n"

    def _render_agents_md(self, refs: list[str]) -> str:
        lines = [
            "# AGENTS",
            "",
            "This repository maintains generated docs and source-of-truth artifacts for AI tooling.",
            "",
            "## Start Here",
        ]
        lines.extend(f"- `{path}`" for path in refs[:10])
        lines.extend(
            [
                "",
                "## Command Surface",
                "- `repo-wiki init`",
                "- `repo-wiki update`",
                "- `repo-wiki index`",
                "- `repo-wiki search <query>`",
                "- `repo-wiki graph <module>`",
                "- `repo-wiki verify --ci`",
            ]
        )
        return "\n".join(lines) + "\n"

    def _render_skill_md(self, tool_name: str, refs: list[str]) -> str:
        lines = [
            f"# {tool_name} Repo-Wiki Navigation Skill",
            "",
            "Read canonical artifacts first, then open raw files only when needed.",
            "",
            "## Priority Paths",
        ]
        lines.extend(f"- `{path}`" for path in refs[:12])
        return "\n".join(lines) + "\n"

    def _render_codex_config(self, refs: list[str]) -> str:
        lines = [
            'project = "repo-wiki"',
            "",
            "[knowledge]",
        ]
        for idx, path in enumerate(refs, start=1):
            lines.append(f'path_{idx} = "{path}"')
        return "\n".join(lines) + "\n"
