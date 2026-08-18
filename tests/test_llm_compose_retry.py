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
    assert provider.call_count == 2 * (RetryConfig().max_retries + 1)
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


LIST_HEAVY_MARKDOWN = """# Sample Page

## 简介

- bullet one with extra words for length and a fake endpoint list
- bullet two with extra words for length and a fake endpoint list
- bullet three with extra words for length and a fake endpoint list
- bullet four with extra words for length and a fake endpoint list
- bullet five with extra words for length and a fake endpoint list
- bullet six with extra words for length and a fake endpoint list
- bullet seven with extra words for length and a fake endpoint list
- bullet eight with extra words for length and a fake endpoint list
"""

PARAGRAPH_MARKDOWN = """# Sample Page

## 简介

This page explains how the FastAPI service authenticates requests and stores articles.
The implementation lives in the application package and is described with paragraph prose
rather than a bullet dump so the composer prose floor can pass. Readers should start at
the settings module, then follow the request path into the route handlers.
"""


def _list_heavy_response() -> ChatResponse:
    return ChatResponse(content=LIST_HEAVY_MARKDOWN, model="mock-gpt")


def _paragraph_response() -> ChatResponse:
    return ChatResponse(content=PARAGRAPH_MARKDOWN, model="mock-gpt")


@pytest.mark.asyncio
async def test_compose_page_retries_insufficient_prose_once(
    sample_page: WikiPagePlan,
    sample_context: ComposerContext,
    no_retry_sleep: None,
) -> None:
    provider = SequenceLLMProvider([_list_heavy_response(), _paragraph_response()])
    composer = create_composer(provider=provider)
    output = await composer.compose_page(build_composer_input(sample_page, None, sample_context))

    assert output.rejected is False
    assert "authenticates requests" in output.markdown
    assert provider.call_count == 2


@pytest.mark.asyncio
async def test_compose_page_rejects_insufficient_prose_after_one_recovery(
    sample_page: WikiPagePlan,
    sample_context: ComposerContext,
    no_retry_sleep: None,
) -> None:
    provider = SequenceLLMProvider([_list_heavy_response(), _list_heavy_response()])
    composer = create_composer(provider=provider)
    output = await composer.compose_page(build_composer_input(sample_page, None, sample_context))

    assert output.rejected is True
    assert output.rejection_reason == "Insufficient prose content"
    assert provider.call_count == 2


FENCE_HEAVY_MARKDOWN = """# Sample Page

## 简介

```python
from app.core import settings
DATABASE_URL = settings.database_url
def get_current_user(authorization: str = Header(...)):
    token = authorization.removeprefix("Token ")
    return lookup_user_by_api_token(token)
```

```python
router = APIRouter()
@router.post("/articles")
def create_article():
    return {"ok": True}
```
"""


def _fence_heavy_response() -> ChatResponse:
    return ChatResponse(content=FENCE_HEAVY_MARKDOWN, model="mock-gpt")


@pytest.mark.asyncio
async def test_compose_page_retries_empty_content_with_paragraph_rewrite(
    sample_page: WikiPagePlan,
    sample_context: ComposerContext,
    no_retry_sleep: None,
) -> None:
    provider = SequenceLLMProvider(
        [_empty_response("") for _ in range(RetryConfig().max_retries + 1)]
        + [_paragraph_response()]
    )
    composer = create_composer(provider=provider)
    output = await composer.compose_page(build_composer_input(sample_page, None, sample_context))

    assert output.rejected is False
    assert "authenticates requests" in output.markdown
    assert provider.call_count == RetryConfig().max_retries + 2


@pytest.mark.asyncio
async def test_compose_page_retries_fence_heavy_insufficient_prose_once(
    sample_page: WikiPagePlan,
    sample_context: ComposerContext,
    no_retry_sleep: None,
) -> None:
    provider = SequenceLLMProvider([_fence_heavy_response(), _paragraph_response()])
    composer = create_composer(provider=provider)
    output = await composer.compose_page(build_composer_input(sample_page, None, sample_context))

    assert output.rejected is False
    assert "authenticates requests" in output.markdown
    assert provider.call_count == 2


def test_prose_recovery_prompt_forbids_evidence_fences(
    sample_page: WikiPagePlan,
    sample_context: ComposerContext,
) -> None:
    composer = create_composer()
    prompt = composer._build_prose_recovery_prompt(
        build_composer_input(sample_page, None, sample_context),
        composer._build_context(build_composer_input(sample_page, None, sample_context)),
        FENCE_HEAVY_MARKDOWN,
    )
    assert "代码" in prompt or "围栏" in prompt or "fence" in prompt.lower()
    assert "段落" in prompt
    assert "mermaid" in prompt.lower()
    assert "def get_current_user" not in prompt


UNCLOSED_FENCE_MARKDOWN = """# Sample Page

Operators monitor FastAPI latency with Prometheus scrapes and Grafana boards for production.
This opening paragraph is long enough to pass the one-hundred character prose floor.

```
Prometheus scrapes /metrics and the remaining body is trapped in this fence.
Grafana dashboards show request latency, error rate, and saturation.
The unclosed fence must not be accepted as a passing composed page.
"""


def _unclosed_fence_response() -> ChatResponse:
    return ChatResponse(content=UNCLOSED_FENCE_MARKDOWN, model="mock-gpt")


@pytest.mark.asyncio
async def test_compose_page_retries_unclosed_fence_once(
    sample_page: WikiPagePlan,
    sample_context: ComposerContext,
    no_retry_sleep: None,
) -> None:
    provider = SequenceLLMProvider([_unclosed_fence_response(), _paragraph_response()])
    composer = create_composer(provider=provider)
    output = await composer.compose_page(build_composer_input(sample_page, None, sample_context))

    assert output.rejected is False
    assert "authenticates requests" in output.markdown
    assert provider.call_count == 2


@pytest.mark.asyncio
async def test_compose_page_rejects_unclosed_fence_after_one_recovery(
    sample_page: WikiPagePlan,
    sample_context: ComposerContext,
    no_retry_sleep: None,
) -> None:
    provider = SequenceLLMProvider([_unclosed_fence_response(), _unclosed_fence_response()])
    composer = create_composer(provider=provider)
    output = await composer.compose_page(build_composer_input(sample_page, None, sample_context))

    assert output.rejected is True
    assert output.rejection_reason == "Unclosed fenced code block"
    assert provider.call_count == 2
