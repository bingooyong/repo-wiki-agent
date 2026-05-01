"""Tests for generation scheduler."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from repo_wiki.orchestration.generation_scheduler import (
    GenerationScheduler,
    PageJob,
    SchedulerConfig,
    SchedulerError,
    TokenBucketRateLimiter,
    create_scheduler,
)


class TestSchedulerConfig:
    """Tests for SchedulerConfig."""

    def test_default_config(self):
        """Test default scheduler config."""
        config = SchedulerConfig()
        assert config.max_concurrency == 4
        assert config.max_retries == 3
        assert config.retry_base_delay == 1.0

    def test_custom_config(self):
        """Test custom scheduler config."""
        config = SchedulerConfig(
            max_concurrency=8,
            rate_limit_rpm=200,
            max_retries=5,
        )
        assert config.max_concurrency == 8
        assert config.rate_limit_rpm == 200
        assert config.max_retries == 5

    def test_get_rate_limit(self):
        """Test provider rate limit lookup."""
        config = SchedulerConfig(
            provider_rate_limits={"openai": 1000}
        )
        assert config.get_rate_limit("openai") == 1000
        assert config.get_rate_limit("anthropic") == 400  # Default


class TestTokenBucketRateLimiter:
    """Tests for TokenBucketRateLimiter."""

    def test_create_rate_limiter(self):
        """Test creating a rate limiter."""
        limiter = TokenBucketRateLimiter(100, 60.0)
        assert limiter.rate_limit == 100
        assert limiter.tokens == 100.0

    def test_try_acquire_success(self):
        """Test successful token acquisition."""
        limiter = TokenBucketRateLimiter(100, 60.0)
        assert limiter.try_acquire(1) is True
        assert limiter.tokens == 99.0

    def test_try_acquire_failure(self):
        """Test failed token acquisition."""
        limiter = TokenBucketRateLimiter(1, 60.0)
        limiter.try_acquire(1)
        assert limiter.try_acquire(1) is False

    @pytest.mark.asyncio
    async def test_acquire(self):
        """Test async acquire."""
        limiter = TokenBucketRateLimiter(100, 60.0)
        await limiter.acquire(50)
        assert limiter.tokens == 50.0

    @pytest.mark.asyncio
    async def test_acquire_blocks(self):
        """Test acquire blocks when no tokens."""
        limiter = TokenBucketRateLimiter(1, 0.1)  # 1 token per 0.1 seconds
        limiter.try_acquire(1)  # Use the only token

        # This should block until refill
        start = asyncio.get_event_loop().time()
        await limiter.acquire(1)
        elapsed = asyncio.get_event_loop().time() - start

        # Should have waited for refill (at least 0.05 seconds)
        assert elapsed >= 0.05


class TestPageJob:
    """Tests for PageJob."""

    def test_create_page_job(self):
        """Test creating a page job."""
        job = PageJob(
            run_id="gen-test",
            doc_slug="00-overview",
            doc_type="overview",
            doc_path="docs/00-overview.md",
        )
        assert job.run_id == "gen-test"
        assert job.doc_slug == "00-overview"
        assert job.status == "pending"
        assert job.attempts == 0

    def test_page_job_defaults(self):
        """Test page job default values."""
        job = PageJob(
            run_id="gen-test",
            doc_slug="00-overview",
            doc_type="overview",
            doc_path="docs/00-overview.md",
        )
        assert job.priority == 0
        assert job.max_attempts == 3
        assert job.error_message is None


class TestGenerationScheduler:
    """Tests for GenerationScheduler."""

    @pytest.fixture
    def scheduler_setup(self, tmp_path):
        """Set up scheduler with dependencies."""
        from repo_wiki.orchestration.generation_state import GenerationStateMachine
        from repo_wiki.orchestration.cost_estimator import GenerationCostEstimator, BudgetGate

        state_db = tmp_path / "state.sqlite3"
        cost_db = tmp_path / "costs.sqlite3"

        state_machine = GenerationStateMachine(state_db)
        cost_estimator = GenerationCostEstimator(cost_db)
        budget_gate = BudgetGate(cost_estimator)
        config = SchedulerConfig(max_concurrency=2, max_retries=2)

        scheduler = GenerationScheduler(
            state_machine, cost_estimator, budget_gate, config
        )

        return scheduler, state_machine, cost_estimator

    def test_create_scheduler(self, scheduler_setup):
        """Test creating a scheduler."""
        scheduler, sm, ce = scheduler_setup  # noqa: F841
        assert scheduler.config.max_concurrency == 2

    def test_cancel(self, scheduler_setup):
        """Test cancellation."""
        scheduler, _, _ = scheduler_setup
        assert scheduler.is_cancelled() is False
        scheduler.cancel()
        assert scheduler.is_cancelled() is True

    def test_get_rate_limiter(self, scheduler_setup):
        """Test rate limiter creation."""
        scheduler, _, _ = scheduler_setup

        limiter1 = scheduler._get_rate_limiter("openai")
        limiter2 = scheduler._get_rate_limiter("openai")

        assert limiter1 is limiter2  # Same instance
        assert limiter1.rate_limit == 500  # From DEFAULT_RATE_LIMITS

    def test_get_rate_limiter_custom(self, tmp_path):
        """Test custom rate limiter."""
        config = SchedulerConfig(provider_rate_limits={"openai": 1000})
        from repo_wiki.orchestration.generation_state import GenerationStateMachine
        from repo_wiki.orchestration.cost_estimator import GenerationCostEstimator, BudgetGate

        state_db = tmp_path / "state.sqlite3"
        cost_db = tmp_path / "costs.sqlite3"

        scheduler = GenerationScheduler(
            GenerationStateMachine(state_db),
            GenerationCostEstimator(cost_db),
            BudgetGate(GenerationCostEstimator(cost_db)),
            config,
        )

        # Recreate with custom config
        from repo_wiki.orchestration.generation_state import GenerationStateMachine
        from repo_wiki.orchestration.cost_estimator import GenerationCostEstimator, BudgetGate

        state_db = tmp_path / "state.sqlite3"
        cost_db = tmp_path / "costs.sqlite3"

        scheduler = GenerationScheduler(
            GenerationStateMachine(state_db),
            GenerationCostEstimator(cost_db),
            BudgetGate(GenerationCostEstimator(cost_db)),
            config,
        )

        limiter = scheduler._get_rate_limiter("openai")
        assert limiter.rate_limit == 1000

    @pytest.mark.asyncio
    async def test_generate_page_success(self, scheduler_setup):
        """Test successful page generation."""
        scheduler, _, _ = scheduler_setup

        job = PageJob(
            run_id="gen-test",
            doc_slug="00-overview",
            doc_type="overview",
            doc_path="docs/00-overview.md",
        )

        # Mock successful generation
        mock_result = MagicMock()
        mock_generate = AsyncMock(return_value=mock_result)

        success, result = await scheduler._generate_page(
            job, "openai", "gpt-4o-mini", mock_generate
        )

        assert success is True
        assert result == mock_result
        mock_generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_page_retry(self, scheduler_setup):
        """Test page generation with retry."""
        scheduler, _, _ = scheduler_setup

        job = PageJob(
            run_id="gen-test",
            doc_slug="00-overview",
            doc_type="overview",
            doc_path="docs/00-overview.md",
        )

        # Mock generation that fails once then succeeds (max_retries=2 means 2 attempts)
        mock_result = MagicMock()
        mock_generate = AsyncMock(side_effect=[Exception("fail 1"), mock_result])

        success, result = await scheduler._generate_page(
            job, "openai", "gpt-4o-mini", mock_generate
        )

        assert success is True
        assert mock_generate.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_page_max_retries(self, scheduler_setup):
        """Test page generation max retries exceeded."""
        scheduler, _, _ = scheduler_setup

        job = PageJob(
            run_id="gen-test",
            doc_slug="00-overview",
            doc_type="overview",
            doc_path="docs/00-overview.md",
        )

        # Mock always failing generation
        mock_generate = AsyncMock(side_effect=Exception("always fails"))

        success, error = await scheduler._generate_page(
            job, "openai", "gpt-4o-mini", mock_generate
        )

        assert success is False
        assert "always fails" in error
        assert mock_generate.call_count == 2  # max_retries=2 from fixture

    @pytest.mark.asyncio
    async def test_generate_page_cancelled(self, scheduler_setup):
        """Test cancelled job."""
        scheduler, _, _ = scheduler_setup
        scheduler.cancel()

        job = PageJob(
            run_id="gen-test",
            doc_slug="00-overview",
            doc_type="overview",
            doc_path="docs/00-overview.md",
        )

        mock_generate = AsyncMock()

        success, error = await scheduler._generate_page(
            job, "openai", "gpt-4o-mini", mock_generate
        )

        assert success is False
        assert "cancelled" in error.lower()
        mock_generate.assert_not_called()

    def test_run_pages_sync_no_pages(self, scheduler_setup):
        """Test run with no pending pages."""
        scheduler, state_machine, _ = scheduler_setup

        # Create a run with no pages
        run = state_machine.create_run(profile="test", total_pages=0)

        mock_generate = AsyncMock()

        completed, failed, errors = scheduler.run_pages_sync(
            run.run_id, "openai", "gpt-4o-mini", mock_generate
        )

        assert completed == 0
        assert failed == 0
        assert len(errors) == 0


class TestCreateScheduler:
    """Tests for create_scheduler factory."""

    def test_create_scheduler_factory(self, tmp_path):
        """Test create_scheduler factory."""
        scheduler = create_scheduler(tmp_path)
        assert isinstance(scheduler, GenerationScheduler)
        assert scheduler.config.max_concurrency == 4

    def test_create_scheduler_with_config(self, tmp_path):
        """Test create_scheduler with custom config."""
        config = SchedulerConfig(max_concurrency=10)
        scheduler = create_scheduler(tmp_path, config)
        assert scheduler.config.max_concurrency == 10
