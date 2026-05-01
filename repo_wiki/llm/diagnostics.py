"""LLM configuration diagnostics."""

from __future__ import annotations

import json
from typing import Any

from repo_wiki.llm import (
    LLMProviderConfig,
    OpenAICompatibleProvider,
    MinimaxProvider,
    create_minimax_provider,
    format_redacted_diagnostic,
    redact_secrets,
    ValidationReason,
    get_api_key_from_env,
)


def create_provider_from_config(config: LLMProviderConfig) -> OpenAICompatibleProvider | MinimaxProvider:
    """Create provider instance from config.

    Args:
        config: LLM provider configuration

    Returns:
        Provider instance
    """
    if config.provider == "minimax":
        return MinimaxProvider(config)
    else:
        return OpenAICompatibleProvider(config)


def run_llm_diagnostics(
    config: LLMProviderConfig | None = None,
    json_output: bool = False,
) -> dict[str, Any]:
    """Run LLM configuration diagnostics.

    Args:
        config: Optional LLM config to diagnose
        json_output: Whether to return JSON format

    Returns:
        Diagnostics results dict
    """
    if config is None:
        config = LLMProviderConfig()

    provider = create_provider_from_config(config)
    validations = provider.validate_config()

    # Build diagnostic output
    diagnostics: dict[str, Any] = {
        "provider": config.provider,
        "model": config.model,
        "base_url": config.base_url,
        "api_key_env": config.api_key_env,
        "api_key_present": get_api_key_from_env(config.api_key_env) is not None,
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
        "timeout": config.timeout,
        "max_retries": config.max_retries,
        "validations": [],
        "issues": [],
        "summary": "OK",
    }

    # Process validations
    for key, value, reason in validations:
        validation_entry = {
            "key": key,
            "value": value if value else None,
            "reason": reason,
        }

        # Redact secret values
        if key == "api_key_env" and value and "***" not in str(value):
            validation_entry["value"] = "[REDACTED]"

        diagnostics["validations"].append(validation_entry)

        # Track issues
        if reason in (
            ValidationReason.MISSING_PROVIDER.value,
            ValidationReason.MISSING_MODEL.value,
            ValidationReason.MISSING_API_KEY.value,
            ValidationReason.INVALID_API_KEY.value,
        ):
            diagnostics["issues"].append(f"{key}: {reason}")
            diagnostics["summary"] = "FAIL"

    # Add provider-specific capabilities
    caps = provider.capabilities
    diagnostics["capabilities"] = {
        "supports_streaming": caps.supports_streaming,
        "supports_functions": caps.supports_functions,
        "supports_vision": caps.supports_vision,
        "supports_json_mode": caps.supports_json_mode,
        "supports_reasoning": caps.supports_reasoning,
        "max_context_tokens": caps.max_context_tokens,
    }

    return diagnostics


def format_diagnostics_text(diagnostics: dict[str, Any]) -> str:
    """Format diagnostics as human-readable text.

    Args:
        diagnostics: Diagnostics results

    Returns:
        Formatted text output
    """
    lines = [
        f"LLM Configuration Diagnostics [{diagnostics['summary']}]",
        "",
        f"  Provider: {diagnostics['provider']}",
        f"  Model: {diagnostics['model']}",
        f"  Base URL: {diagnostics['base_url'] or '(default)'}",
        f"  API Key Env: {diagnostics['api_key_env']}",
        f"  API Key Present: {'Yes' if diagnostics['api_key_present'] else 'No'}",
        "",
        "  Settings:",
        f"    Max Tokens: {diagnostics['max_tokens']}",
        f"    Temperature: {diagnostics['temperature']}",
        f"    Timeout: {diagnostics['timeout']}s",
        f"    Max Retries: {diagnostics['max_retries']}",
        "",
        "  Validations:",
    ]

    for validation in diagnostics["validations"]:
        key = validation["key"]
        value = validation["value"]
        reason = validation["reason"]

        if key == "api_key_env" and value:
            lines.append(f"    {key}: [REDACTED] [{reason}]")
        elif value:
            lines.append(f"    {key}: {value} [{reason}]")
        else:
            lines.append(f"    {key}: (not set) [{reason}]")

    lines.extend([
        "",
        "  Capabilities:",
        f"    Streaming: {diagnostics['capabilities']['supports_streaming']}",
        f"    Functions: {diagnostics['capabilities']['supports_functions']}",
        f"    Vision: {diagnostics['capabilities']['supports_vision']}",
        f"    JSON Mode: {diagnostics['capabilities']['supports_json_mode']}",
        f"    Max Context: {diagnostics['capabilities']['max_context_tokens']} tokens",
    ])

    if diagnostics["issues"]:
        lines.extend(["", "  Issues:"])
        for issue in diagnostics["issues"]:
            lines.append(f"    - {issue}")

    return "\n".join(lines)


def format_diagnostics_json(diagnostics: dict[str, Any]) -> str:
    """Format diagnostics as JSON.

    Args:
        diagnostics: Diagnostics results

    Returns:
        JSON string with redacted secrets
    """
    # Create a copy and redact secrets
    output = dict(diagnostics)
    if output.get("api_key_env"):
        output["api_key_env"] = "[REDACTED]"
    if output.get("api_key_present"):
        output["api_key_present"] = True

    return json.dumps(output, ensure_ascii=False, indent=2)
