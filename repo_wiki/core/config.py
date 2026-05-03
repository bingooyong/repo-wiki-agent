from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field

from repo_wiki.core.errors import ErrorCategory, RepoWikiError


class ProjectConfig(BaseModel):
    name: str = "auto"
    root: str = "."
    include: list[str] = Field(default_factory=lambda: ["**/*"])
    exclude: list[str] = Field(default_factory=list)


class ScanConfig(BaseModel):
    include_hidden: bool = False
    follow_symlinks: bool = False
    exclude_dirs: list[str] = Field(
        default_factory=lambda: [".git", "node_modules", "dist", "build", "coverage"]
    )
    max_file_count: int = 50000


class IndexConfig(BaseModel):
    enabled: bool = True
    vector_backend: str = "chromadb"
    embedding_model: str = "local"
    chunk_strategy: str = "auto"


class LlmConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    provider: str = "anthropic"
    model: str | None = None
    base_url: str | None = None
    api_key_env: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: float = 60.0
    max_retries: int = 3
    model_init: str = "claude-opus-4-5"
    model_update: str = "claude-sonnet-4-5"
    model_verify: str = "claude-haiku-4-5-20251001"
    max_concurrent: int = 3
    cache: bool = True
    force_mock_llm: bool = Field(
        default=False,
        description="If true, qoder-like composer always uses MockLLMProvider (CI / reproducible runs).",
    )


class OutputConfig(BaseModel):
    docs_dir: str = "docs/"
    ai_dir: str = "ai/source-of-truth/"
    index_dir: str = ".repo-wiki/"
    claude_dir: str = ".claude/"


class QoderLikeConfig(BaseModel):
    """Sizing for isolated qoder-like eval generation (page-plan floor and cap)."""

    min_pages: int = Field(
        default=24,
        ge=1,
        le=2000,
        description="Minimum planned pages after taxonomy roots and optional 'deep-dive' top-up (before max cap).",
    )
    max_pages: int = Field(
        default=220,
        ge=1,
        le=2000,
        description="Upper bound on planned pages for qoder-like curation (env may override).",
    )


class SecurityConfig(BaseModel):
    redact_secrets: bool = True
    skip_binary_files: bool = True
    max_file_size_kb: int = 512
    deny_globs: list[str] = Field(
        default_factory=lambda: [
            ".env",
            ".env.*",
            "*.pem",
            "*.key",
            "*.p12",
            "*.sqlite",
            "*.db",
            "*.log",
            "*.bin",
            "*.exe",
            "*.dll",
        ]
    )
    deny_dirs: list[str] = Field(
        default_factory=lambda: [
            ".git",
            ".repo-wiki",
            ".apm",
            ".claude",
            ".codex",
            ".opencode",
            ".tmp",
            ".cursor",
            ".vscode",
            "node_modules",
            "dist",
            "build",
            "coverage",
            ".venv",
            "venv",
            "__pycache__",
        ]
    )


class RepoWikiConfig(BaseModel):
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    scan: ScanConfig = Field(default_factory=ScanConfig)
    index: IndexConfig = Field(default_factory=IndexConfig)
    llm: LlmConfig = Field(default_factory=LlmConfig)
    qoder_like: QoderLikeConfig = Field(default_factory=QoderLikeConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)


def load_config(config_path: Path | None = None, cli_overrides: dict[str, Any] | None = None) -> RepoWikiConfig:
    raw: dict[str, Any] = {}
    resolved_path = _resolve_config_path(config_path)
    if resolved_path and resolved_path.exists():
        try:
            parsed = yaml.safe_load(resolved_path.read_text(encoding="utf-8")) or {}
            if not isinstance(parsed, dict):
                raise RepoWikiError(
                    "Configuration file must be a YAML object.",
                    ErrorCategory.CONFIG,
                    {"path": str(resolved_path)},
                )
            raw = parsed
        except yaml.YAMLError as exc:
            raise RepoWikiError(
                "Failed to parse YAML configuration.",
                ErrorCategory.CONFIG,
                {"path": str(resolved_path), "error": str(exc)},
            ) from exc

    merged = _deep_merge_dict({}, raw)
    if cli_overrides:
        _apply_dot_overrides(merged, cli_overrides)
    config = RepoWikiConfig.model_validate(merged)
    _load_project_env(Path(config.project.root))
    return config


def _load_project_env(project_root: Path) -> None:
    """Load target repository .env without overriding process-provided values."""
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)


def _resolve_config_path(config_path: Path | None) -> Path | None:
    if config_path:
        return config_path
    for candidate in (Path("repo-wiki.yaml"), Path(".repo-wiki.yaml")):
        if candidate.exists():
            return candidate
    return None


def _apply_dot_overrides(target: dict[str, Any], overrides: dict[str, Any]) -> None:
    for key, value in overrides.items():
        parts = key.split(".")
        cursor = target
        for part in parts[:-1]:
            if part not in cursor or not isinstance(cursor[part], dict):
                cursor[part] = {}
            cursor = cursor[part]
        cursor[parts[-1]] = value


def _deep_merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge_dict(result[key], value)
        else:
            result[key] = value
    return result
