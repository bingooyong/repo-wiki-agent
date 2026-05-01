# LLM Provider Configuration Guide

This guide explains how to configure LLM providers for repo-wiki.

## Supported Providers

| Provider | Model Examples | API Type |
|----------|-----------------|----------|
| Minimax | abab6-chat, abab6.5-chat | Minimax API |
| OpenAI-compatible | gpt-4o-mini, gpt-4o, claude-3.5-sonnet | OpenAI-compatible REST |
| Anthropic-compatible | claude-3-5-sonnet-20241022, claude-3-opus | Anthropic-compatible REST |
| Local (Ollama) | llama3.3, qwen2.5, mistral | OpenAI-compatible REST |

## Quick Start

```bash
# Set your API key
export MINIMAX_API_KEY="your-api-key-here"

# Generate wiki with Minimax
uv run repo-wiki generate --provider minimax --model abab6-chat
```

## Configuration Methods

### 1. Environment Variables

Set provider configuration via environment variables:

```bash
# Minimax
export MINIMAX_API_KEY="your-minimax-key"
export LLM_PROVIDER="minimax"
export LLM_MODEL="abab6-chat"

# OpenAI-compatible
export OPENAI_API_KEY="your-openai-key"
export LLM_PROVIDER="openai"
export LLM_MODEL="gpt-4o-mini"

# Anthropic-compatible
export ANTHROPIC_API_KEY="your-anthropic-key"
export LLM_PROVIDER="anthropic"
export LLM_MODEL="claude-3-5-sonnet-20241022"

# Local Ollama
export OLLAMA_BASE_URL="http://localhost:11434"
export LLM_PROVIDER="openai"  # Ollama is OpenAI-compatible
export LLM_MODEL="llama3.3"
```

### 2. YAML Configuration File

Create `repo-wiki.yaml` in your project root:

```yaml
llm:
  provider: minimax
  model: abab6-chat
  api_key_env: MINIMAX_API_KEY
  max_tokens: 4096
  temperature: 0.7
  timeout: 60.0
  max_retries: 3
```

For OpenAI-compatible:
```yaml
llm:
  provider: openai
  model: gpt-4o-mini
  base_url: https://api.openai.com/v1  # Optional, for compatible providers
  api_key_env: OPENAI_API_KEY
```

### 3. CLI Overrides

Override configuration via CLI flags:

```bash
uv run repo-wiki generate \
  --provider openai \
  --model gpt-4o-mini \
  --llm-api-key-env OPENAI_API_KEY
```

## Provider-Specific Configuration

### Minimax

```bash
export MINIMAX_API_KEY="your-very-long-api-key-here"

# Environment variable method
export LLM_PROVIDER="minimax"
export LLM_MODEL="abab6-chat"
```

Minimax requires `MINIMAX_API_KEY` environment variable.

### OpenAI-Compatible

For OpenAI, Azure OpenAI, or any OpenAI-compatible API:

```bash
# OpenAI direct
export OPENAI_API_KEY="sk-your-key-here"
export LLM_PROVIDER="openai"
export LLM_MODEL="gpt-4o-mini"

# Azure OpenAI (using base_url)
export AZURE_OPENAI_KEY="your-azure-key"
export LLM_PROVIDER="openai"
export LLM_BASE_URL="https://your-resource.openai.azure.com"
export LLM_MODEL="gpt-4o-mini"
```

YAML configuration for Azure OpenAI:
```yaml
llm:
  provider: openai
  model: gpt-4o-mini
  base_url: https://your-resource.openai.azure.com/v1
  api_key_env: AZURE_OPENAI_KEY
```

### Anthropic-Compatible

For Anthropic or Anthropic-compatible providers:

```bash
export ANTHROPIC_API_KEY="sk-ant-api03-your-key-here"
export LLM_PROVIDER="anthropic"
export LLM_MODEL="claude-3-5-sonnet-20241022"
```

Anthropic-compatible (e.g., AWS Bedrock):
```yaml
llm:
  provider: anthropic
  model: anthropic.claude-3-5-sonnet-20241022
  base_url: https://your-bedrock-endpoint
  api_key_env: AWS_BEDROCK_API_KEY
```

### Local Provider (Ollama)

```bash
# Start Ollama locally
ollama serve

# Default local endpoint
export LLM_BASE_URL="http://localhost:11434/v1"
export LLM_PROVIDER="openai"  # Ollama is OpenAI-compatible
export LLM_MODEL="llama3.3"
```

YAML configuration:
```yaml
llm:
  provider: openai
  model: llama3.3
  base_url: http://localhost:11434/v1
  api_key_env: OLLAMA_API_KEY  # Usually not needed for local
```

## Configuration Priority

Configuration is resolved in this order (highest to lowest):

1. **CLI overrides** - `--provider`, `--model`, etc.
2. **Environment variables** - `LLM_PROVIDER`, `LLM_MODEL`, etc.
3. **YAML config file** - `repo-wiki.yaml`
4. **Defaults** - provider=openai, model=gpt-4o-mini

## Configuration Diagnostic

Run the config doctor to validate your setup:

```bash
uv run repo-wiki config-doctor
```

Example output:
```
LLM Configuration Diagnostics
============================
Provider: minimax [RESOLVED_FROM_ENV]
Model: abab6-chat [RESOLVED_FROM_ENV]
API Key: [REDACTED] [MISSING_API_KEY]
Base URL: None [VALID]
Max Tokens: 4096 [VALID]
Temperature: 0.7 [VALID]
Timeout: 60.0 [VALID]
Max Retries: 3 [VALID]

Summary: FAIL - API key missing
Issues:
  - MISSING_API_KEY: MINIMAX_API_KEY not found in environment
```

## Troubleshooting

### Issue: "API key not found"

**Cause**: The environment variable for your API key is not set.

**Solution**:
1. Check which env var name you configured: `echo $LLM_API_KEY_ENV`
2. Set the correct environment variable:
   ```bash
   export MINIMAX_API_KEY="your-key"  # or whatever you configured
   ```

### Issue: "Connection timeout"

**Cause**: Network issues or incorrect base_url.

**Solution**:
1. Verify your base_url is correct
2. Increase timeout:
   ```bash
   export LLM_TIMEOUT=120
   ```

### Issue: "Model not found"

**Cause**: Model name is incorrect for the provider.

**Solution**:
1. Check available models for your provider
2. Use a known working model:
   ```bash
   export LLM_MODEL="gpt-4o-mini"  # OpenAI default
   export LLM_MODEL="abab6-chat"     # Minimax default
   ```

### Issue: "Rate limit exceeded"

**Cause**: Too many requests.

**Solution**:
1. Reduce request rate
2. Increase max_retries:
   ```yaml
   llm:
     max_retries: 5
   ```

## Security Notes

- API keys are never logged or displayed in plain text
- Use `api_key_env` to reference environment variables, never hardcode keys
- All diagnostic output automatically redacts sensitive values
- Keys stored in environment variables are automatically redacted in logs

## Complete Example

```yaml
# repo-wiki.yaml
llm:
  provider: minimax
  model: abab6-chat
  api_key_env: MINIMAX_API_KEY
  max_tokens: 4096
  temperature: 0.7
  timeout: 60.0
  max_retries: 3
```

```bash
# Set the key
export MINIMAX_API_KEY="your-key-here"

# Verify configuration
uv run repo-wiki config-doctor

# Generate wiki
uv run repo-wiki generate
```