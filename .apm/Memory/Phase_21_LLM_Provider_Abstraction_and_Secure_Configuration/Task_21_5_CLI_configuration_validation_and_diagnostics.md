# Task 21.5 - CLI configuration validation and diagnostics

## Status
COMPLETED

## Summary
Implemented `repo-wiki config` command for LLM configuration diagnostics with secret redaction.

## Deliverables

### Files Created
- `/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/repo_wiki/llm/diagnostics.py` - Diagnostics logic
- `/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/tests/test_cli_config_doctor.py` - Tests

### Updated Files
- `/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/repo_wiki/cli.py` - Added `config` command
- `/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/pyproject.toml` - Added httpx dependency

### Config Command
Added `repo-wiki config` command with options:
- `--provider`: LLM provider (openai, minimax)
- `--model`: Model identifier
- `--base-url`: API base URL
- `--api-key-env`: Environment variable for API key
- `--max-tokens`: Max tokens in response
- `--temperature`: Sampling temperature
- `--timeout`: Request timeout in seconds
- `--max-retries`: Max retry attempts
- `--ci`: Machine-readable JSON output

### Features
- Validates provider/model/base_url/api_key_env/budget fields
- Outputs stable reason codes (VALID, MISSING_*, INVALID_*, REDACTED)
- Redacts all secrets in terminal and JSON outputs
- JSON output with `--ci` flag for CI integration
- Exit code 1 on FAIL for CI integration

## Test Results
```
uv run pytest tests/test_llm_config.py tests/test_llm_provider_contract.py tests/test_llm_providers.py tests/test_llm_budget.py tests/test_llm_retry_cache.py tests/test_cli_config_doctor.py -v
103 passed in 0.09s
```

## Compile Check
`uv run repo-wiki --help` - PASSED (config command visible)
