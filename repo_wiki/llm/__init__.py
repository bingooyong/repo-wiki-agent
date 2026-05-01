"""LLM provider abstraction layer."""

from __future__ import annotations

from repo_wiki.llm.config import (
    LLMProviderConfig,
    resolve_llm_config,
    redact_secrets,
    format_redacted_diagnostic,
    get_api_key_from_env,
    ValidationReason,
)
from repo_wiki.llm.models import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ErrorCode,
    LLMProvider,
    LLMError,
    RetryableError,
    NonRetryableError,
    ProviderCapabilities,
)
from repo_wiki.llm.providers import MockLLMProvider, create_mock_provider
from repo_wiki.llm.adapters import OpenAICompatibleProvider
from repo_wiki.llm.minimax import MinimaxProvider, create_minimax_provider
from repo_wiki.llm.budget import (
    TokenBudget,
    estimate_request_tokens,
    estimate_prompt_tokens,
    estimate_text_tokens,
    check_token_budget,
    format_budget_report,
)
from repo_wiki.llm.retry import (
    RetryConfig,
    RetryResult,
    with_retry,
    chat_with_retry,
    is_retryable_error,
    get_retry_info,
)
from repo_wiki.llm.cache import (
    CacheConfig,
    CacheEntry,
    LLMCache,
    create_cache,
)

__all__ = [
    "LLMProviderConfig",
    "resolve_llm_config",
    "redact_secrets",
    "format_redacted_diagnostic",
    "get_api_key_from_env",
    "ValidationReason",
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "ErrorCode",
    "LLMProvider",
    "LLMError",
    "RetryableError",
    "NonRetryableError",
    "ProviderCapabilities",
    "MockLLMProvider",
    "create_mock_provider",
    "OpenAICompatibleProvider",
    "MinimaxProvider",
    "create_minimax_provider",
    "TokenBudget",
    "estimate_request_tokens",
    "estimate_prompt_tokens",
    "estimate_text_tokens",
    "check_token_budget",
    "format_budget_report",
    "RetryConfig",
    "RetryResult",
    "with_retry",
    "chat_with_retry",
    "is_retryable_error",
    "get_retry_info",
    "CacheConfig",
    "CacheEntry",
    "LLMCache",
    "create_cache",
]
