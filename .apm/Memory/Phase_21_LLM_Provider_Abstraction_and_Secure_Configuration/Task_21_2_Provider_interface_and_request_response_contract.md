# Task 21.2 - Provider interface and request/response contract

## Status
COMPLETED

## Summary
Defined unified LLM client request/response/error contract with MockLLMProvider for CI.

## Deliverables

### Files Created
- `/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/repo_wiki/llm/providers.py` - Mock provider implementation
- `/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/tests/test_llm_provider_contract.py` - Contract tests

### Updated Files
- `/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/repo_wiki/llm/__init__.py` - Added exports

### Models
- `ChatMessage`: role/content/name dataclass for messages
- `ChatRequest`: messages, model, temperature, max_tokens, timeout, stream, extra_headers, extra_body
- `ChatResponse`: content, model, usage, finish_reason, raw_response, error
- `ProviderCapabilities`: supports_streaming, supports_functions, supports_vision, etc.

### Error Types
- `LLMError`: Base exception with message, code, details
- `RetryableError`: For timeout, rate limit, server errors
- `NonRetryableError`: For auth failure, invalid request

### ErrorCode Enum
- SUCCESS, TIMEOUT, RATE_LIMIT, SERVER_ERROR, NETWORK_ERROR
- AUTH_FAILURE, INVALID_API_KEY, MISSING_API_KEY, INVALID_REQUEST, INVALID_MODEL
- CONTEXT_LENGTH, UNKNOWN

### Mock Provider
- `MockLLMProvider`: Configurable mock for CI/testing
- `MockResponse`: Response configuration (content, usage, finish_reason, delay)
- `create_mock_provider()`: Factory function
- Tracks call_count and last_request
- reset() method for test cleanup

## Test Results
```
uv run pytest tests/test_llm_provider_contract.py tests/test_llm_config.py -v
42 passed in 0.06s
```

## Compile Check
`uv run repo-wiki --help` - PASSED
