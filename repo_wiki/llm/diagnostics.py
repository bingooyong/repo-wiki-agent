"""LLM configuration diagnostics."""

from __future__ import annotations

import json
from typing import Any

from repo_wiki.llm import (
    LLMProviderConfig,
    MinimaxProvider,
    OpenAICompatibleProvider,
    ValidationReason,
    get_api_key_from_env,
)


def create_provider_from_config(
    config: LLMProviderConfig,
) -> OpenAICompatibleProvider | MinimaxProvider:
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
    # Create redacted copy for display
    display_data = dict(diagnostics)
    api_key_env = display_data.get("api_key_env", "")
    display_data["api_key_env"] = "[REDACTED]" if api_key_env else ""
    display_data["api_key_present"] = "Yes" if diagnostics.get("api_key_present") else "No"
    lines = [
        f"LLM Configuration Diagnostics [{display_data['summary']}]",
        "",
        f"  Provider: {display_data['provider']}",
        f"  Model: {display_data['model']}",
        f"  Base URL: {display_data['base_url'] or '(default)'}",
        f"  API Key Env: {display_data['api_key_env']}",
        f"  API Key Present: {display_data['api_key_present']}",
        "",
        "  Settings:",
        f"    Max Tokens: {display_data['max_tokens']}",
        f"    Temperature: {display_data['temperature']}",
        f"    Timeout: {display_data['timeout']}s",
        f"    Max Retries: {display_data['max_retries']}",
        "",
        "  Validations:",
    ]

    for validation in display_data["validations"]:
        key = validation["key"]
        value = validation["value"]
        reason = validation["reason"]

        if key == "api_key_env" and value:
            lines.append(f"    {key}: [REDACTED] [{reason}]")
        elif value:
            lines.append(f"    {key}: {value} [{reason}]")
        else:
            lines.append(f"    {key}: (not set) [{reason}]")

    lines.extend(
        [
            "",
            "  Capabilities:",
            f"    Streaming: {display_data['capabilities']['supports_streaming']}",
            f"    Functions: {display_data['capabilities']['supports_functions']}",
            f"    Vision: {display_data['capabilities']['supports_vision']}",
            f"    JSON Mode: {display_data['capabilities']['supports_json_mode']}",
            f"    Max Context: {display_data['capabilities']['max_context_tokens']} tokens",
        ]
    )

    if display_data["issues"]:
        lines.extend(["", "  Issues:"])
        for issue in display_data["issues"]:
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
