"""Concurrent generation scheduler with rate limiting and retry support.

This module provides:
- Configurable concurrency control
- Provider rate limiting
- Retry with exponential backoff
- Cancellation support
- SQLite state consistency under concurrency

Phase 28 - Task 28.3: Concurrent generation scheduler

Key features:
- Semaphore-based concurrency control
- Token bucket rate limiting per provider
- Retry policy with configurable max attempts
- Thread-safe state transitions
"""

from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Coroutine
import logging

from repo_wiki.orchestration.cost_estimator import (
    BudgetGate,
    GenerationCostEstimator,
    PagePlanCostInput,
)
from repo_wiki.orchestration.generation_state import (
    GenerationStateMachine,
    PageGenerationState,
    PageState,
    RunState,
)


logger = logging.getLogger(__name__)


# =============================================================================
# PROVIDER RATE LIMITS (requests per minute)
# =============================================================================

DEFAULT_RATE_LIMITS: dict[str, int] = {
    "openai": 500,      # GPT-4o: 500 RPM
    "anthropic": 400,    # Claude: 400 RPM
    "generic": 100,
}


# =============================================================================
# SCHEDULER CONFIG
# =============================================================================

@dataclass
class SchedulerConfig:
    """Configuration for the generation scheduler."""
    max_concurrency: int = 4
    rate_limit_rpm: int = 100  # Default for unknown providers
    max_retries: int = 3
    retry_base_delay: float = 1.0  # seconds
    retry_max_delay: float = 60.0  # seconds
    provider_rate_limits: dict[str, int] = field(default_factory=dict)

    def get_rate_limit(self, provider: str) -> int:
        """Get rate limit for a provider."""
        return self.provider_rate_limits.get(
            provider.lower(),
            DEFAULT_RATE_LIMITS.get(provider.lower(), self.rate_limit_rpm)
        )


# =============================================================================
# PAGE JOB
# =============================================================================

@dataclass
class PageJob:
    """A page generation job."""
    run_id: str
    doc_slug: str
    doc_type: str
    doc_path: str
    priority: int = 0
    attempts: int = 0
    max_attempts: int = 3
    status: str = "pending"  # pending, running, completed, failed, cancelled
    error_message: str | None = None
    estimated_cost: float = 0.0
    result: Any = None


# =============================================================================
# RATE LIMITER
# =============================================================================

class TokenBucketRateLimiter:
    """Token bucket rate limiter for provider API calls."""

    def __init__(self, rate_limit: int, time_window: float = 60.0) -> None:
        """Initialize rate limiter.

        Args:
            rate_limit: Max tokens per time window
            time_window: Time window in seconds
        """
        self.rate_limit = rate_limit
        self.time_window = time_window
        self.tokens = float(rate_limit)
        self.last_refill = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        # Add tokens proportional to elapsed time
        tokens_to_add = (elapsed / self.time_window) * self.rate_limit
        self.tokens = min(self.rate_limit, self.tokens + tokens_to_add)
        self.last_refill = now

    async def acquire(self, tokens: int = 1) -> None:
        """Acquire tokens, waiting if necessary.

        Args:
            tokens: Number of tokens to acquire
        """
        while True:
            with self._lock:
                self._refill()
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return
            # Wait before retrying
            await asyncio.sleep(0.1)

    def try_acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens without blocking.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            True if tokens acquired, False otherwise
        """
        with self._lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False


# =============================================================================
# CONCURRENT GENERATION SCHEDULER
# =============================================================================

class GenerationScheduler:
    """Schedules and executes page generation with concurrency control."""

    def __init__(
        self,
        state_machine: GenerationStateMachine,
        cost_estimator: GenerationCostEstimator,
        budget_gate: BudgetGate,
        config: SchedulerConfig | None = None,
    ) -> None:
        """Initialize scheduler.

        Args:
            state_machine: Generation state machine
            cost_estimator: Cost estimator
            budget_gate: Budget gate
            config: Scheduler configuration
        """
        self.state_machine = state_machine
        self.cost_estimator = cost_estimator
        self.budget_gate = budget_gate
        self.config = config or SchedulerConfig()

        # Rate limiters per provider
        self._rate_limiters: dict[str, TokenBucketRateLimiter] = {}
        self._rate_limiters_lock = threading.Lock()

        # Concurrency semaphore
        self._semaphore: asyncio.Semaphore | None = None

        # Cancellation flag
        self._cancelled = False
        self._cancel_lock = threading.Lock()

    def _get_rate_limiter(self, provider: str) -> TokenBucketRateLimiter:
        """Get or create rate limiter for provider."""
        with self._rate_limiters_lock:
            if provider not in self._rate_limiters:
                rate_limit = self.config.get_rate_limit(provider)
                self._rate_limiters[provider] = TokenBucketRateLimiter(rate_limit)
            return self._rate_limiters[provider]

    def cancel(self) -> None:
        """Cancel all pending jobs."""
        with self._cancel_lock:
            self._cancelled = True

    def is_cancelled(self) -> bool:
        """Check if scheduler is cancelled."""
        with self._cancel_lock:
            return self._cancelled

    async def _generate_page(
        self,
        job: PageJob,
        provider: str,
        model: str,
        generate_fn: Callable[..., Coroutine[Any, Any, Any]],
        **kwargs: Any,
    ) -> tuple[bool, Any]:
        """Generate a single page with rate limiting and retry.

        Args:
            job: Page job
            provider: LLM provider
            model: Model name
            generate_fn: Async function to call for generation
            **kwargs: Additional args for generate_fn

        Returns:
            Tuple of (success, result_or_error)
        """
        rate_limiter = self._get_rate_limiter(provider)

        for attempt in range(self.config.max_retries):
            if self.is_cancelled():
                return False, "Job cancelled"

            try:
                # Check rate limit
                await rate_limiter.acquire(1)

                # Execute generation
                result = await generate_fn(
                    doc_slug=job.doc_slug,
                    doc_type=job.doc_type,
                    doc_path=job.doc_path,
                    provider=provider,
                    model=model,
                    **kwargs,
                )
                return True, result

            except Exception as exc:
                logger.warning(
                    f"Page generation attempt {attempt + 1} failed for {job.doc_slug}: {exc}"
                )
                if attempt < self.config.max_retries - 1:
                    # Exponential backoff
                    delay = min(
                        self.config.retry_base_delay * (2 ** attempt),
                        self.config.retry_max_delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    return False, str(exc)

        return False, "Max retries exceeded"

    async def run_pages(
        self,
        run_id: str,
        provider: str,
        model: str,
        generate_fn: Callable[..., Coroutine[Any, Any, Any]],
        budget_override: float | None = None,
        page_prompt_tokens: dict[str, int] | None = None,
        default_prompt_tokens_per_page: int = 1200,
        completion_tokens_per_page: int = 500,
        enforce_budget_gate: bool = True,
        **kwargs: Any,
    ) -> tuple[int, int, list[tuple[str, str]]]:
        """Run page generation with concurrency control.

        Args:
            run_id: Generation run ID
            provider: LLM provider
            model: Model name
            generate_fn: Async function to call for generation
            **kwargs: Additional args for generate_fn

        Returns:
            Tuple of (completed_count, failed_count, errors)
        """
        # Create semaphore for concurrency control
        self._semaphore = asyncio.Semaphore(self.config.max_concurrency)
        result_lock = asyncio.Lock()

        # Get pending pages
        pending_pages = self.state_machine.get_pending_pages(run_id)

        completed = 0
        failed = 0
        errors: list[tuple[str, str]] = []

        if enforce_budget_gate and pending_pages:
            decision = self.budget_gate.enforce_run_budget_with_state(
                state_machine=self.state_machine,
                run_id=run_id,
                provider=provider,
                model=model,
                pages=self._build_budget_inputs(
                    pending_pages=pending_pages,
                    page_prompt_tokens=page_prompt_tokens,
                    default_prompt_tokens_per_page=default_prompt_tokens_per_page,
                    completion_tokens_per_page=completion_tokens_per_page,
                ),
                budget_override=budget_override,
                completion_tokens_per_page_default=completion_tokens_per_page,
            )
            if not decision.allowed:
                return 0, 0, [("__run__", decision.message or "Budget exceeded")]

        # Run starts once budget check is accepted.
        self.state_machine.start_run(run_id)

        async def process_page(page: PageGenerationState) -> None:
            nonlocal completed, failed
            if self.is_cancelled():
                return

            # Acquire concurrency slot
            async with self._semaphore:
                if self.is_cancelled():
                    return

                # Start page
                self.state_machine.start_page(run_id, page.doc_slug)

                # Create job
                job = PageJob(
                    run_id=run_id,
                    doc_slug=page.doc_slug,
                    doc_type=page.doc_type,
                    doc_path=page.doc_path,
                    max_attempts=page.max_attempts,
                )

                # Execute with rate limiting and retry
                success, result = await self._generate_page(
                    job, provider, model, generate_fn, **kwargs
                )

                if success:
                    self.state_machine.complete_page(run_id, page.doc_slug)
                    # Record tokens if result contains token info
                    if hasattr(result, 'prompt_tokens') and hasattr(result, 'completion_tokens'):
                        self.cost_estimator.record_page_tokens(
                            run_id=run_id,
                            doc_slug=page.doc_slug,
                            provider=provider,
                            model=model,
                            prompt_tokens=result.prompt_tokens,
                            completion_tokens=result.completion_tokens,
                        )
                    async with result_lock:
                        completed += 1
                else:
                    self.state_machine.fail_page(run_id, page.doc_slug, str(result))
                    async with result_lock:
                        errors.append((page.doc_slug, str(result)))
                        failed += 1

        # Create tasks for all pages
        tasks = [process_page(page) for page in pending_pages]

        # Run concurrently with semaphore
        await asyncio.gather(*tasks, return_exceptions=True)

        if self.is_cancelled():
            self.state_machine.cancel_run(run_id)
        else:
            self.state_machine.complete_run(run_id)

        return completed, failed, errors

    def run_pages_sync(
        self,
        run_id: str,
        provider: str,
        model: str,
        generate_fn: Callable[..., Coroutine[Any, Any, Any]],
        budget_override: float | None = None,
        page_prompt_tokens: dict[str, int] | None = None,
        default_prompt_tokens_per_page: int = 1200,
        completion_tokens_per_page: int = 500,
        enforce_budget_gate: bool = True,
        **kwargs: Any,
    ) -> tuple[int, int, list[tuple[str, str]]]:
        """Synchronous wrapper for run_pages.

        Args:
            run_id: Generation run ID
            provider: LLM provider
            model: Model name
            generate_fn: Async function to call for generation
            **kwargs: Additional args for generate_fn

        Returns:
            Tuple of (completed_count, failed_count, errors)
        """
        return asyncio.run(
            self.run_pages(
                run_id=run_id,
                provider=provider,
                model=model,
                generate_fn=generate_fn,
                budget_override=budget_override,
                page_prompt_tokens=page_prompt_tokens,
                default_prompt_tokens_per_page=default_prompt_tokens_per_page,
                completion_tokens_per_page=completion_tokens_per_page,
                enforce_budget_gate=enforce_budget_gate,
                **kwargs,
            )
        )

    def _build_budget_inputs(
        self,
        *,
        pending_pages: list[PageGenerationState],
        page_prompt_tokens: dict[str, int] | None,
        default_prompt_tokens_per_page: int,
        completion_tokens_per_page: int,
    ) -> list[PagePlanCostInput]:
        """Build page-plan cost inputs for budget checks."""
        prompt_lookup = page_prompt_tokens or {}
        return [
            PagePlanCostInput(
                page_id=page.doc_slug,
                estimated_prompt_tokens=prompt_lookup.get(page.doc_slug, default_prompt_tokens_per_page),
                estimated_completion_tokens=completion_tokens_per_page,
            )
            for page in pending_pages
        ]


class SchedulerError(Exception):
    """Raised when scheduler encounters an error."""
    pass


def create_scheduler(
    root: Path,
    config: SchedulerConfig | None = None,
) -> GenerationScheduler:
    """Create a scheduler with standard dependencies.

    Args:
        root: Repository root path
        config: Scheduler configuration

    Returns:
        GenerationScheduler instance
    """
    from repo_wiki.orchestration.cost_estimator import create_budget_gate

    db_path = root / ".repo-wiki" / "index" / "generation_state.sqlite3"
    cost_db_path = root / ".repo-wiki" / "index" / "generation_costs.sqlite3"

    state_machine = GenerationStateMachine(db_path)
    cost_estimator = GenerationCostEstimator(cost_db_path)
    budget_gate = BudgetGate(cost_estimator)

    return GenerationScheduler(state_machine, cost_estimator, budget_gate, config)
