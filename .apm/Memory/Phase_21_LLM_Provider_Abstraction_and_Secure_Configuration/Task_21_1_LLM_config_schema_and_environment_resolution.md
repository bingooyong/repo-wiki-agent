# Task 21.1 - LLM config schema and environment resolution

## Status
COMPLETED

## Summary
Implemented LLM provider configuration schema with secure environment variable resolution and secret redaction.

## Deliverables

### Files Created
- `/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/repo_wiki/llm/__init__.py` - LLM module init
- `/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/repo_wiki/llm/config.py` - LLM config schema and redaction
- `/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/repo_wiki/llm/models.py` - ChatRequest/ChatResponse models
- `/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/tests/test_llm_config.py` - Tests

### Schema Fields
- `provider`: Provider name (openai, minimax, anthropic, etc.)
- `model`: Model identifier
- `base_url`: API base URL (optional, for OpenAI-compatible providers)
- `api_key_env`: Environment variable name containing the API key
- `max_tokens`: Maximum tokens in response (1-128000)
- `temperature`: Sampling temperature (0.0-2.0)
- `timeout`: Request timeout in seconds (0.0-300.0)
- `max_retries`: Maximum retry attempts (0-10)

### Environment Resolution
- Priority: CLI overrides > Environment variables > Config file > Defaults
- `resolve_llm_config()` function handles merging
- `get_api_key_from_env()` safely retrieves API keys

### Secret Redaction
- `redact_secrets()` - Redacts API keys, Bearer tokens, secret values
- `format_redacted_diagnostic()` - Formats diagnostics with redaction
- `_is_secret_value()` - Detects secret-like values based on key name

### ValidationReason Enum
Stable reason codes:
- VALID, MISSING_PROVIDER, MISSING_MODEL, MISSING_API_KEY
- INVALID_API_KEY, INVALID_BASE_URL, INVALID_TIMEOUT
- INVALID_MAX_RETRIES, INVALID_MAX_TOKENS, INVALID_TEMPERATURE
- RESOLVED_FROM_ENV, REDACTED

## Test Results
```
uv run pytest tests/test_llm_config.py -v
20 passed in 0.04s
```

## Compile Check
`uv run repo-wiki --help` - PASSED

## Notes
- All fields have Pydantic validation with range constraints
- Tests use pytest with monkeypatch for environment variable testing
- Secrets are never logged, only redacted for diagnostics
