from __future__ import annotations

import importlib.util
from pathlib import Path

from pydantic import BaseModel, Field

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.core.errors import ErrorCategory, RepoWikiError


class BootstrapResult(BaseModel):
    root: str
    warnings: list[str] = Field(default_factory=list)


def bootstrap(config: RepoWikiConfig) -> BootstrapResult:
    root = Path(config.project.root).resolve()
    if not root.exists() or not root.is_dir():
        raise RepoWikiError(
            "Project root does not exist or is not a directory.",
            ErrorCategory.BOOTSTRAP,
            {"root": str(root)},
        )

    required_modules = ["typer", "pydantic", "yaml", "rich"]
    warnings: list[str] = []
    for module in required_modules:
        if importlib.util.find_spec(module) is None:
            warnings.append(f"Dependency not installed: {module}")

    # Create deterministic output folders early so later tasks can write artifacts safely.
    for relative in (config.output.ai_dir, config.output.index_dir):
        (root / relative).mkdir(parents=True, exist_ok=True)

    return BootstrapResult(root=str(root), warnings=warnings)
