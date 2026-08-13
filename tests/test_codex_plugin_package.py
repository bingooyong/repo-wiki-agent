from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from repo_wiki.cli import app

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "repo-wiki"
MARKETPLACE = ROOT / ".agents" / "plugins" / "marketplace.json"
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


def _frontmatter(path: Path) -> dict[str, object]:
    contents = path.read_text(encoding="utf-8")
    assert contents.startswith("---\n")
    end = contents.find("\n---", 4)
    assert end > 4
    payload = yaml.safe_load(contents[4:end])
    assert isinstance(payload, dict)
    return payload


def test_manifest_is_strict_skills_only_plugin() -> None:
    manifest = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))

    assert manifest["name"] == PLUGIN.name == "repo-wiki"
    assert SEMVER.fullmatch(manifest["version"])
    assert manifest["skills"] == "./skills/"
    assert isinstance(manifest["author"]["name"], str)
    assert manifest["interface"]["capabilities"]
    assert manifest["interface"]["defaultPrompt"]
    assert "mcpServers" not in manifest
    assert "apps" not in manifest
    assert not (PLUGIN / ".mcp.json").exists()
    assert not (PLUGIN / ".app.json").exists()


def test_marketplace_resolves_local_plugin_with_supported_policy() -> None:
    marketplace = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    entry = next(plugin for plugin in marketplace["plugins"] if plugin["name"] == "repo-wiki")

    assert marketplace["name"] == "repo-wiki-local"
    assert entry["source"] == {"source": "local", "path": "./plugins/repo-wiki"}
    assert (ROOT / entry["source"]["path"]).resolve() == PLUGIN.resolve()
    assert entry["policy"]["installation"] == "AVAILABLE"
    assert entry["policy"]["authentication"] in {"ON_INSTALL", "ON_USE"}
    assert entry["category"] == "Developer Tools"


def test_skills_have_unique_frontmatter_and_route_writes_through_runner() -> None:
    skill_files = sorted((PLUGIN / "skills").glob("*/SKILL.md"))
    names: set[str] = set()
    write_terms = ("init", "index", "update", "sync", "generate", "improve", "verify", "publish")

    assert len(skill_files) == 4
    for skill_file in skill_files:
        metadata = _frontmatter(skill_file)
        assert metadata["name"] == skill_file.parent.name
        assert isinstance(metadata["description"], str) and metadata["description"].strip()
        assert metadata["name"] not in names
        names.add(str(metadata["name"]))
        content = skill_file.read_text(encoding="utf-8")
        if any(term in content for term in write_terms):
            assert "workflow.py" in content
            assert "<plugin_dir>" in content
            assert "--cwd" in content and "<repo-root>" in content
    safety = (PLUGIN / "references" / "workflow-safety.md").read_text(encoding="utf-8")
    assert "trusted same-user" in safety
    assert "does not create" in (PLUGIN / "skills" / "repo-wiki-maintain" / "SKILL.md").read_text(
        encoding="utf-8"
    )


def test_skill_commands_exist_and_secrets_are_policy_only() -> None:
    live_commands = {command.name for command in app.registered_commands}
    skill_text = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted((PLUGIN / "skills").glob("*/SKILL.md"))
    )

    assert {"search", "graph", "generate", "improve", "verify", "release-publish"} <= live_commands
    assert "API key" in skill_text or "API Key" in skill_text
    assert not re.search(r"\bsk-[A-Za-z0-9_-]{20,}\b", skill_text)
    assert not re.search(r"(?i)bearer\s+[A-Za-z0-9._-]{24,}", skill_text)


def test_source_of_truth_and_ci_index_the_plugin_contract() -> None:
    repo_map = yaml.safe_load(
        (ROOT / "ai/source-of-truth/repo-map.yaml").read_text(encoding="utf-8")
    )
    module_index = yaml.safe_load(
        (ROOT / "ai/source-of-truth/module-index.yaml").read_text(encoding="utf-8")
    )
    task_catalog = yaml.safe_load(
        (ROOT / "ai/source-of-truth/task-catalog.yaml").read_text(encoding="utf-8")
    )
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert repo_map["codex_plugin_contract"]["runner"] == "plugins/repo-wiki/scripts/workflow.py"
    assert "plugins/repo-wiki" in {module["name"] for module in module_index["modules"]}
    assert "validate-codex-plugin" in {task["name"] for task in task_catalog["tasks"]}
    assert "tests/test_codex_plugin_package.py" in ci
    assert "tests/test_codex_plugin_workflow.py" in ci
    assert "plugins .agents/plugins/marketplace.json" in ci
