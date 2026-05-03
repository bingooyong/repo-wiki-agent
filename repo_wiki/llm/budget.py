"""Token budgeting for LLM requests."""

from __future__ import annotations

from dataclasses import dataclass

from repo_wiki.llm.models import ChatMessage, ChatRequest

# Approximate tokens per word/character ratios
TOKENS_PER_WORD = 1.33  # Typical English text
TOKENS_PER_CHAR = 0.25  # For non-space separated text


@dataclass
class TokenBudget:
    """Token budget for a request."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    max_tokens: int
    within_budget: bool


def estimate_request_tokens(request: ChatRequest) -> int:
    """Estimate total tokens for a chat request.

    Args:
        request: Chat request

    Returns:
        Estimated total tokens needed
    """
    prompt_tokens = estimate_prompt_tokens(request.messages)
    # Completion estimate is conservative
    completion_estimate = min(request.max_tokens, 2048)
    return prompt_tokens + completion_estimate


def estimate_prompt_tokens(messages: list[ChatMessage]) -> int:
    """Estimate tokens in prompt messages.

    Args:
        messages: List of chat messages

    Returns:
        Estimated prompt tokens
    """
    total = 0
    for message in messages:
        # Base token count for message structure
        total += 4  # rolename + content + overhead
        # Content token estimation
        total += estimate_text_tokens(message.content)
    # Add overhead for message array
    total += 3
    return total


def estimate_text_tokens(text: str) -> int:
    """Estimate tokens in text.

    Args:
        text: Text to estimate

    Returns:
        Estimated token count
    """
    if not text:
        return 0
    # Word-based estimation (more accurate)
    words = text.split()
    word_tokens = len(words) * TOKENS_PER_WORD
    # Character-based estimation (for continuous text)
    char_tokens = len(text) * TOKENS_PER_CHAR
    # Use the higher estimate
    return max(int(word_tokens), int(char_tokens))


def check_token_budget(request: ChatRequest, max_context_tokens: int = 128000) -> TokenBudget:
    """Check if a request fits within token budget.

    Args:
        request: Chat request
        max_context_tokens: Maximum context tokens available

    Returns:
        TokenBudget with estimates and budget check
    """
    prompt_tokens = estimate_prompt_tokens(request.messages)
    completion_tokens = request.max_tokens
    total_tokens = prompt_tokens + completion_tokens

    # Leave some buffer for response (max 75% of context)
    effective_max = int(max_context_tokens * 0.75)
    within_budget = total_tokens <= effective_max

    return TokenBudget(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        max_tokens=effective_max,
        within_budget=within_budget,
    )


def format_budget_report(budget: TokenBudget) -> str:
    """Format token budget as human-readable string.

    Args:
        budget: Token budget

    Returns:
        Formatted string
    """
    status = "OK" if budget.within_budget else "EXCEEDS_BUDGET"
    return (
        f"Token Budget [{status}]:\n"
        f"  Prompt: {budget.prompt_tokens}\n"
        f"  Completion (max): {budget.completion_tokens}\n"
        f"  Total estimated: {budget.total_tokens}\n"
        f"  Budget limit: {budget.max_tokens}"
    )
