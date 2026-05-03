"""LLM provider abstraction layer."""

from __future__ import annotations

from repo_wiki.llm.adapters import OpenAICompatibleProvider
from repo_wiki.llm.budget import (
    TokenBudget,
    check_token_budget,
    estimate_prompt_tokens,
    estimate_request_tokens,
    estimate_text_tokens,
    format_budget_report,
)
from repo_wiki.llm.cache import (
    CacheConfig,
    CacheEntry,
    LLMCache,
    create_cache,
)
from repo_wiki.llm.config import (
    LLMProviderConfig,
    ValidationReason,
    format_redacted_diagnostic,
    get_api_key_from_env,
    redact_secrets,
    resolve_llm_config,
)
from repo_wiki.llm.minimax import MinimaxProvider, create_minimax_provider
from repo_wiki.llm.models import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ErrorCode,
    LLMError,
    LLMProvider,
    NonRetryableError,
    ProviderCapabilities,
    RetryableError,
)
from repo_wiki.llm.providers import MockLLMProvider, create_mock_provider
from repo_wiki.llm.retry import (
    RetryConfig,
    RetryResult,
    chat_with_retry,
    get_retry_info,
    is_retryable_error,
    with_retry,
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
