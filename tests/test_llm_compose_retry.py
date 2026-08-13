"""Tests that page composition retries transient LLM 5xx/429 instead of emptying pages."""

from __future__ import annotations

import pytest

from repo_wiki.generator.composer import (
    ComposerContext,
    build_composer_input,
    create_composer,
)
from repo_wiki.llm.config import LLMProviderConfig
from repo_wiki.llm.models import (
    ChatRequest,
    ChatResponse,
    ErrorCode,
    LLMProvider,
    NonRetryableError,
    ProviderCapabilities,
    RetryableError,
)
from repo_wiki.llm.retry import RetryConfig
from repo_wiki.planner.schema import WikiPagePlan, WikiTaxonomyCategory

SUCCESS_MARKDOWN = "# Sample Page\n\nRetried LLM content with enough prose for validation."


def _retryable(status: int) -> RetryableError:
    code = ErrorCode.RATE_LIMIT if status == 429 else ErrorCode.SERVER_ERROR
    return RetryableError(
        message=f"Server error: {status}",
        code=code,
        details={"status": status},
    )


def _success_response() -> ChatResponse:
    return ChatResponse(content=SUCCESS_MARKDOWN, model="mock-gpt")


def _empty_response(content: str = "") -> ChatResponse:
    """HTTP 200 ChatResponse with blank/whitespace assistant content."""
    return ChatResponse(content=content, model="mock-gpt")


class SequenceLLMProvider(LLMProvider):
    """Fake provider that yields a scripted sequence of errors or responses."""

    def __init__(self, outcomes: list[Exception | ChatResponse]) -> None:
        self._outcomes = list(outcomes)
        self._call_count = 0
        self._config = LLMProviderConfig(provider="mock", model="mock-gpt")

    @property
    def name(self) -> str:
        return "sequence-fake"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities()

    @property
    def call_count(self) -> int:
        return self._call_count

    async def chat(self, request: ChatRequest) -> ChatResponse:
        self._call_count += 1
        if self._call_count > 20:
            raise AssertionError("retry loop exceeded guard; expected RetryConfig.max_retries")
        if not self._outcomes:
            raise AssertionError("SequenceLLMProvider called more times than outcomes provided")
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def validate_config(self) -> list[tuple[str, str | None, str]]:
        return []


class AlwaysRetryableProvider(LLMProvider):
    """Fake provider that always raises a retryable HTTP error."""

    def __init__(self, status: int = 529) -> None:
        self._status = status
        self._call_count = 0
        self._config = LLMProviderConfig(provider="mock", model="mock-gpt")

    @property
    def name(self) -> str:
        return "always-retryable-fake"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities()

    @property
    def call_count(self) -> int:
        return self._call_count

    async def chat(self, request: ChatRequest) -> ChatResponse:
        self._call_count += 1
        if self._call_count > 20:
            raise AssertionError("retry loop exceeded guard; expected RetryConfig.max_retries")
        raise _retryable(self._status)

    def validate_config(self) -> list[tuple[str, str | None, str]]:
        return []


@pytest.fixture
def sample_page() -> WikiPagePlan:
    return WikiPagePlan(
        page_id="sample-page",
        title="Sample Page",
        category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
        output_path="docs/sample.md",
    )


@pytest.fixture
def sample_context() -> ComposerContext:
    return ComposerContext(
        repository_name="test-repo",
        primary_language="python",
        framework="pytest",
        repository_root=".",
    )


@pytest.fixture
def no_retry_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _instant(_delay: float) -> None:
        return None

    monkeypatch.setattr("repo_wiki.llm.retry.asyncio.sleep", _instant)


@pytest.mark.asyncio
async def test_compose_page_retries_http_529_then_succeeds(
    sample_page: WikiPagePlan,
    sample_context: ComposerContext,
    no_retry_sleep: None,
) -> None:
    provider = SequenceLLMProvider(
        [_retryable(529), _retryable(529), _success_response()],
    )
    composer = create_composer(provider=provider)
    output = await composer.compose_page(build_composer_input(sample_page, None, sample_context))

    assert output.rejected is False
    assert output.markdown
    assert "LLM composer did not return content" not in output.markdown
    assert provider.call_count == 3


@pytest.mark.asyncio
async def test_compose_page_retries_http_429_then_succeeds(
    sample_page: WikiPagePlan,
    sample_context: ComposerContext,
    no_retry_sleep: None,
) -> None:
    provider = SequenceLLMProvider(
        [_retryable(429), _retryable(429), _success_response()],
    )
    composer = create_composer(provider=provider)
    output = await composer.compose_page(build_composer_input(sample_page, None, sample_context))

    assert output.rejected is False
    assert output.markdown
    assert "LLM composer did not return content" not in output.markdown
    assert provider.call_count == 3


@pytest.mark.asyncio
async def test_compose_page_does_not_retry_http_401(
    sample_page: WikiPagePlan,
    sample_context: ComposerContext,
    no_retry_sleep: None,
) -> None:
    auth_error = NonRetryableError(
        message="Authentication failed",
        code=ErrorCode.AUTH_FAILURE,
        details={"status": 401},
    )
    provider = SequenceLLMProvider([auth_error, _success_response()])
    composer = create_composer(provider=provider)
    output = await composer.compose_page(build_composer_input(sample_page, None, sample_context))

    assert output.rejected is True
    assert output.markdown == ""
    assert provider.call_count == 1


@pytest.mark.asyncio
async def test_compose_page_rejects_after_retries_exhausted(
    sample_page: WikiPagePlan,
    sample_context: ComposerContext,
    no_retry_sleep: None,
) -> None:
    provider = AlwaysRetryableProvider(status=529)
    composer = create_composer(provider=provider)
    output = await composer.compose_page(build_composer_input(sample_page, None, sample_context))

    assert output.rejected is True
    assert "529" in (output.rejection_reason or "")
    assert provider.call_count == RetryConfig().max_retries + 1
    assert provider.call_count <= 20


@pytest.mark.asyncio
async def test_compose_page_retries_empty_content_then_succeeds(
    sample_page: WikiPagePlan,
    sample_context: ComposerContext,
    no_retry_sleep: None,
) -> None:
    """HTTP 200 with blank/whitespace content is retryable, like 5xx/429."""
    provider = SequenceLLMProvider(
        [_empty_response(""), _empty_response("  \n\t"), _success_response()],
    )
    composer = create_composer(provider=provider)
    output = await composer.compose_page(build_composer_input(sample_page, None, sample_context))

    assert output.rejected is False
    assert SUCCESS_MARKDOWN.splitlines()[0] in output.markdown
    assert "LLM composer did not return content" not in output.markdown
    assert provider.call_count == 3


@pytest.mark.asyncio
async def test_compose_page_rejects_after_empty_content_retries_exhausted(
    sample_page: WikiPagePlan,
    sample_context: ComposerContext,
    no_retry_sleep: None,
) -> None:
    """Exhausted empty-content retries must fail, not PASS with a placeholder shell."""
    provider = SequenceLLMProvider([_empty_response("") for _ in range(10)])
    composer = create_composer(provider=provider)
    output = await composer.compose_page(build_composer_input(sample_page, None, sample_context))

    assert output.rejected is True
    assert output.rejection_reason
    assert not (
        output.rejected is False and "LLM composer did not return content" in output.markdown
    )
    assert "LLM composer did not return content" not in output.markdown
    assert provider.call_count == RetryConfig().max_retries + 1
    assert provider.call_count <= 20


@pytest.mark.asyncio
async def test_compose_page_does_not_retry_nonempty_content(
    sample_page: WikiPagePlan,
    sample_context: ComposerContext,
    no_retry_sleep: None,
) -> None:
    provider = SequenceLLMProvider([_success_response(), _empty_response("")])
    composer = create_composer(provider=provider)
    output = await composer.compose_page(build_composer_input(sample_page, None, sample_context))

    assert output.rejected is False
    assert "LLM composer did not return content" not in output.markdown
    assert provider.call_count == 1
