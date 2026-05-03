"""Tests for token budgeting."""

from __future__ import annotations

from repo_wiki.llm import (
    ChatMessage,
    ChatRequest,
    TokenBudget,
    check_token_budget,
    estimate_prompt_tokens,
    estimate_request_tokens,
    estimate_text_tokens,
    format_budget_report,
)


class TestEstimateTextTokens:
    """Tests for text token estimation."""

    def test_empty_text(self) -> None:
        """Test empty text returns 0."""
        assert estimate_text_tokens("") == 0

    def test_short_text(self) -> None:
        """Test short text estimation."""
        text = "Hello world"
        tokens = estimate_text_tokens(text)
        assert tokens > 0
        assert tokens < 20

    def test_longer_text(self) -> None:
        """Test longer text estimation."""
        text = "This is a longer piece of text that should have more tokens"
        tokens = estimate_text_tokens(text)
        assert tokens > 10


class TestEstimatePromptTokens:
    """Tests for prompt token estimation."""

    def test_single_user_message(self) -> None:
        """Test single user message."""
        messages = [ChatMessage(role="user", content="Hello")]
        tokens = estimate_prompt_tokens(messages)
        assert tokens > 0

    def test_multiple_messages(self) -> None:
        """Test multiple messages."""
        messages = [
            ChatMessage(role="system", content="You are helpful"),
            ChatMessage(role="user", content="Hello"),
            ChatMessage(role="assistant", content="Hi there"),
        ]
        tokens = estimate_prompt_tokens(messages)
        # More messages = more tokens
        assert tokens > estimate_prompt_tokens([messages[0]])

    def test_long_content(self) -> None:
        """Test with long content."""
        content = " ".join(["word"] * 1000)
        messages = [ChatMessage(role="user", content=content)]
        tokens = estimate_prompt_tokens(messages)
        # Should be substantial for 1000 words
        assert tokens > 500


class TestEstimateRequestTokens:
    """Tests for request token estimation."""

    def test_basic_request(self) -> None:
        """Test basic request estimation."""
        request = ChatRequest(
            messages=[ChatMessage(role="user", content="Hello world")],
            model="gpt-4",
            max_tokens=100,
        )
        tokens = estimate_request_tokens(request)
        assert tokens > 0

    def test_large_max_tokens(self) -> None:
        """Test request with large max_tokens."""
        request = ChatRequest(
            messages=[ChatMessage(role="user", content="Hi")],
            model="gpt-4",
            max_tokens=8192,
        )
        tokens = estimate_request_tokens(request)
        # Should include the completion estimate
        assert tokens >= estimate_prompt_tokens(request.messages)


class TestCheckTokenBudget:
    """Tests for token budget checking."""

    def test_small_request_within_budget(self) -> None:
        """Test small request is within budget."""
        request = ChatRequest(
            messages=[ChatMessage(role="user", content="Hello")],
            model="gpt-4",
            max_tokens=100,
        )
        budget = check_token_budget(request, max_context_tokens=128000)
        assert budget.within_budget is True
        assert budget.total_tokens < budget.max_tokens

    def test_exceeds_context_limit(self) -> None:
        """Test request exceeding context limit."""
        request = ChatRequest(
            messages=[ChatMessage(role="user", content="x" * 100000)],
            model="gpt-4",
            max_tokens=128000,
        )
        budget = check_token_budget(request, max_context_tokens=128000)
        assert budget.within_budget is False

    def test_budget_fields(self) -> None:
        """Test budget contains all fields."""
        request = ChatRequest(
            messages=[ChatMessage(role="user", content="Test")],
            model="gpt-4",
            max_tokens=100,
        )
        budget = check_token_budget(request)
        assert budget.prompt_tokens >= 0
        assert budget.completion_tokens == 100
        assert budget.total_tokens > 0
        assert budget.max_tokens > 0


class TestFormatBudgetReport:
    """Tests for budget report formatting."""

    def test_format_within_budget(self) -> None:
        """Test formatting budget that's within limits."""
        budget = TokenBudget(
            prompt_tokens=100,
            completion_tokens=100,
            total_tokens=200,
            max_tokens=10000,
            within_budget=True,
        )
        report = format_budget_report(budget)
        assert "OK" in report
        assert "100" in report

    def test_format_exceeds_budget(self) -> None:
        """Test formatting budget that exceeds limits."""
        budget = TokenBudget(
            prompt_tokens=50000,
            completion_tokens=50000,
            total_tokens=100000,
            max_tokens=10000,
            within_budget=False,
        )
        report = format_budget_report(budget)
        assert "EXCEEDS_BUDGET" in report
