"""LLM provider configuration with environment resolution and secret redaction."""

from __future__ import annotations

import os
import re
from enum import Enum
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field

# Load .env file if it exists
_env_path = Path(".env")
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path)


class ValidationReason(str, Enum):
    """Stable validation reason codes for diagnostics."""

    VALID = "VALID"
    MISSING_PROVIDER = "MISSING_PROVIDER"
    MISSING_MODEL = "MISSING_MODEL"
    MISSING_API_KEY = "MISSING_API_KEY"
    INVALID_API_KEY = "INVALID_API_KEY"
    INVALID_BASE_URL = "INVALID_BASE_URL"
    INVALID_TIMEOUT = "INVALID_TIMEOUT"
    INVALID_MAX_RETRIES = "INVALID_MAX_RETRIES"
    INVALID_MAX_TOKENS = "INVALID_MAX_TOKENS"
    INVALID_TEMPERATURE = "INVALID_TEMPERATURE"
    RESOLVED_FROM_ENV = "RESOLVED_FROM_ENV"
    REDACTED = "REDACTED"


class LLMProviderConfig(BaseModel):
    """LLM provider configuration with secure env resolution.

    Fields:
        provider: Provider name (openai, minimax, anthropic, etc.)
        model: Model identifier
        base_url: API base URL (optional, for OpenAI-compatible providers)
        api_key_env: Environment variable name containing the API key
        max_tokens: Maximum tokens in response
        temperature: Sampling temperature
        timeout: Request timeout in seconds
        max_retries: Maximum retry attempts
    """

    model_config = ConfigDict(protected_namespaces=())

    provider: str = Field(default="openai", description="LLM provider name")
    model: str = Field(default="gpt-4o-mini", description="Model identifier")
    base_url: str | None = Field(default=None, description="API base URL for OpenAI-compatible providers")
    api_key_env: str = Field(default="OPENAI_API_KEY", description="Env var name for API key")
    max_tokens: int = Field(default=4096, ge=1, le=128000, description="Max tokens in response")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    timeout: float = Field(default=60.0, gt=0.0, le=300.0, description="Request timeout in seconds")
    max_retries: int = Field(default=3, ge=0, le=10, description="Max retry attempts")


def resolve_llm_config(
    config: dict[str, Any] | None = None,
    cli_overrides: dict[str, Any] | None = None,
) -> tuple[LLMProviderConfig, list[tuple[ValidationReason, str]]]:
    """Resolve LLM config from config dict, environment, and CLI overrides.

    Priority (highest to lowest):
    1. CLI overrides
    2. Environment variables (if api_key_env specifies a var that exists)
    3. Config file values

    Args:
        config: Configuration dictionary (e.g., from YAML)
        cli_overrides: CLI flag overrides (dot-notation supported)

    Returns:
        Tuple of (resolved config, list of validation warnings)
    """
    warnings: list[tuple[ValidationReason, str]] = []

    # Start with defaults
    resolved: dict[str, Any] = {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "base_url": None,
        "api_key_env": "OPENAI_API_KEY",
        "max_tokens": 4096,
        "temperature": 0.7,
        "timeout": 60.0,
        "max_retries": 3,
    }

    # Merge config file values
    if config:
        if config.get("provider") is not None:
            resolved["provider"] = config["provider"]
        if config.get("model") is not None:
            resolved["model"] = config["model"]
        if config.get("base_url") is not None:
            resolved["base_url"] = config["base_url"]
        if config.get("api_key_env") is not None:
            resolved["api_key_env"] = config["api_key_env"]
        if config.get("max_tokens") is not None:
            resolved["max_tokens"] = config["max_tokens"]
        if config.get("temperature") is not None:
            resolved["temperature"] = config["temperature"]
        if config.get("timeout") is not None:
            resolved["timeout"] = config["timeout"]
        if config.get("max_retries") is not None:
            resolved["max_retries"] = config["max_retries"]

    # Check for environment variable overrides
    env_overrides: dict[str, Any] = {}
    env_mappings = {
        "LLM_PROVIDER": "provider",
        "LLM_MODEL": "model",
        "LLM_BASE_URL": "base_url",
        "LLM_API_KEY_ENV": "api_key_env",
        "LLM_MAX_TOKENS": "max_tokens",
        "LLM_TEMPERATURE": "temperature",
        "LLM_TIMEOUT": "timeout",
        "LLM_MAX_RETRIES": "max_retries",
    }
    for env_var, config_key in env_mappings.items():
        if env_var in os.environ:
            env_overrides[config_key] = os.environ[env_var]
            warnings.append((ValidationReason.RESOLVED_FROM_ENV, f"{env_var} -> {config_key}"))

    # Application-specific Minimax aliases used by target repositories.
    # Keep the historical MINIMAXI spelling for compatibility with existing .env files.
    for prefix in ("APP_LLM_MINIMAXI", "APP_LLM_MINIMAX"):
        api_key_var = f"{prefix}_API_KEY"
        if api_key_var in os.environ:
            env_overrides["provider"] = "minimax"
            env_overrides["api_key_env"] = api_key_var
            warnings.append((ValidationReason.RESOLVED_FROM_ENV, f"{api_key_var} -> api_key_env"))

            model_var = f"{prefix}_MODEL"
            if model_var in os.environ:
                env_overrides["model"] = os.environ[model_var]
                warnings.append((ValidationReason.RESOLVED_FROM_ENV, f"{model_var} -> model"))

            base_url_var = f"{prefix}_BASE_URL"
            if base_url_var in os.environ:
                env_overrides["base_url"] = os.environ[base_url_var]
                warnings.append((ValidationReason.RESOLVED_FROM_ENV, f"{base_url_var} -> base_url"))
            break

    # Apply environment overrides
    for key, value in env_overrides.items():
        if key in resolved:
            resolved[key] = value

    # Apply CLI overrides (highest priority)
    if cli_overrides:
        for key, value in cli_overrides.items():
            if key in resolved:
                resolved[key] = value
                warnings.append((ValidationReason.RESOLVED_FROM_ENV, f"cli_override -> {key}"))

    if resolved.get("provider") == "minimax":
        if resolved.get("api_key_env") == "OPENAI_API_KEY":
            resolved["api_key_env"] = "MINIMAX_API_KEY"
        if resolved.get("model") == "gpt-4o-mini":
            resolved["model"] = "abab6-chat"

    return LLMProviderConfig.model_validate(resolved), warnings


# Secret patterns for redaction
_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # API key patterns with explicit key names
    (re.compile(r"(?i)(api[_-]?key|apikey|secret[_-]?key|access[_-]?token)\s*[=:]\s*['\"]?([a-zA-Z0-9_\-]{20,})['\"]?"), r"\1=[REDACTED]"),
    # Bearer tokens in Authorization headers
    (re.compile(r"(?i)bearer\s+([a-zA-Z0-9_\-\.]{20,})"), "Bearer [REDACTED]"),
    # OpenAI/Minimax style API key formats (sk- prefix)
    (re.compile(r"(?i)(sk-[a-zA-Z0-9_\-]{20,})"), "[REDACTED]"),
    # Generic long alphanumeric only when clearly labeled as secret in context
    # This is intentionally conservative to avoid false positives
]


def redact_secrets(text: str) -> str:
    """Redact secrets from text for safe logging/output.

    Args:
        text: Text that may contain secrets

    Returns:
        Text with secrets redacted
    """
    result = text
    for pattern, replacement in _SECRET_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def format_redacted_diagnostic(key: str, value: str | None, reason: ValidationReason) -> str:
    """Format a diagnostic line with redaction.

    Args:
        key: Configuration key name
        value: Configuration value (may be None or secret)
        reason: Validation reason code

    Returns:
        Formatted diagnostic string
    """
    if value is None:
        return f"  {key}: (not set) [{reason.value}]"

    # Check if value looks like a secret
    if _is_secret_value(key, value):
        return f"  {key}: [REDACTED] [{reason.value}]"

    return f"  {key}: {value} [{reason.value}]"


def _is_secret_value(key: str, value: str) -> bool:
    """Check if a value looks like a secret based on its content.

    Args:
        key: Configuration key name
        value: Configuration value

    Returns:
        True if the value appears to be a secret
    """
    key_lower = key.lower()
    secret_indicators = ["key", "token", "secret", "password", "credential"]
    return any(indicator in key_lower for indicator in secret_indicators)


def get_api_key_from_env(api_key_env: str) -> str | None:
    """Get API key from environment variable.

    Args:
        api_key_env: Name of the environment variable

    Returns:
        API key value or None if not found
    """
    return os.environ.get(api_key_env)
