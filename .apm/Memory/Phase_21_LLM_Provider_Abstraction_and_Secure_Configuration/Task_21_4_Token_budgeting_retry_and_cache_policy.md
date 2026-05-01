# Task 21.4 - Token budgeting, retry, and cache policy

## Status
COMPLETED

## Summary
Implemented token budget estimator, retry wrapper with backoff, and safe LLM cache policy.

## Deliverables

### Files Created
- `/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/repo_wiki/llm/budget.py` - Token budgeting
- `/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/repo_wiki/llm/retry.py` - Retry wrapper
- `/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/repo_wiki/llm/cache.py` - Cache policy
- `/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/tests/test_llm_budget.py` - Budget tests
- `/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/tests/test_llm_retry_cache.py` - Retry/cache tests

### Updated Files
- `/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/repo_wiki/llm/__init__.py` - Added exports

### Token Budgeting
- `estimate_text_tokens()` - Word/char based estimation
- `estimate_prompt_tokens()` - Message array estimation
- `estimate_request_tokens()` - Combined request estimation
- `check_token_budget()` - Validates against context limits
- `format_budget_report()` - Human-readable output
- 75% context utilization threshold for safety

### Retry Wrapper
- `RetryConfig` - max_retries, base_delay, max_delay, exponential_base, jitter
- `with_retry()` - Generic async retry decorator
- `chat_with_retry()` - Chat-specific retry wrapper
- `is_retryable_error()` - Error classification
- `get_retry_info()` - Extract retry details
- Exponential backoff with jitter

### Cache Policy
- `LLMCache` - Key-based response cache
- `CacheConfig` - TTL, max_entries, enabled
- Cache key from request content hash
- Never caches: errors, secret-bearing content
- Secret detection for: api_key, api key, token, secret, password, credential, sk-
- LRU eviction when max_entries reached

## Test Results
```
uv run pytest tests/test_llm_budget.py tests/test_llm_retry_cache.py -v
34 passed in 0.04s
```

## Compile Check
`uv run repo-wiki --help` - PASSED
