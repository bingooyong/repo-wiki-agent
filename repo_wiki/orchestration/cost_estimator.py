"""LLM cost estimator and budget gate for generation runs.

This module provides:
- Cost estimation based on provider, model, and token counts
- Budget gate that blocks over-budget runs
- Reason codes for budget failures

Phase 28 - Task 28.2: LLM cost estimator and budget gate

Key features:
- Provider-specific pricing (OpenAI, Anthropic, etc.)
- Per-page and per-run cost estimation
- Budget override support
- Cost tracking with SQLite persistence
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any


# =============================================================================
# PROVIDER PRICING (per 1M tokens as of 2024)
# =============================================================================

# OpenAI pricing (USD per 1M tokens)
OPENAI_PRICING = {
    "gpt-4o": {"input": 5.00, "output": 15.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-4": {"input": 30.00, "output": 60.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
}

# Anthropic pricing (USD per 1M tokens)
ANTHROPIC_PRICING = {
    "claude-opus-4-5": {"input": 15.00, "output": 75.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 0.80, "output": 4.00},
}

# Generic pricing fallback (USD per 1M tokens)
GENERIC_PRICING = {
    "default": {"input": 1.00, "output": 3.00},
}

# Provider to pricing map
PROVIDER_PRICING: dict[str, dict[str, dict[str, float]]] = {
    "openai": OPENAI_PRICING,
    "anthropic": ANTHROPIC_PRICING,
    "generic": GENERIC_PRICING,
}


def get_pricing(provider: str, model: str) -> tuple[float, float]:
    """Get input and output pricing for a provider/model.

    Args:
        provider: Provider name (openai, anthropic, etc.)
        model: Model name

    Returns:
        Tuple of (input_price_per_1m, output_price_per_1m)
    """
    provider_lower = provider.lower()
    model_lower = model.lower()

    # Try exact provider match
    if provider_lower in PROVIDER_PRICING:
        pricing = PROVIDER_PRICING[provider_lower]
        # Try exact model match
        if model_lower in pricing:
            return pricing[model_lower]["input"], pricing[model_lower]["output"]
        # Try partial match
        for model_key, costs in pricing.items():
            if model_key in model_lower or model_lower in model_key:
                return costs["input"], costs["output"]

    # Fallback to generic pricing
    if "default" in PROVIDER_PRICING.get("generic", {}):
        default = PROVIDER_PRICING["generic"]["default"]
        return default["input"], default["output"]

    # Ultimate fallback
    return 1.0, 3.0  # $1/M input, $3/M output


# =============================================================================
# COST ESTIMATION
# =============================================================================

@dataclass
class CostEstimate:
    """Cost estimation for a generation operation."""
    run_id: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    input_cost_usd: float
    output_cost_usd: float
    budget_limit_usd: float | None
    within_budget: bool
    reason_code: str | None = None
    message: str | None = None


@dataclass
class PageCostEstimate:
    """Cost estimation for a single page."""
    run_id: str
    doc_slug: str
    provider: str
    model: str
    prompt_tokens: int
    estimated_cost_usd: float
    within_page_budget: bool


class GenerationCostEstimator:
    """Estimates and tracks LLM costs for generation runs."""

    def __init__(
        self,
        db_path: Path,
        default_budget_usd: float = 10.0,
    ) -> None:
        """Initialize cost estimator.

        Args:
            db_path: Path to SQLite database for cost tracking
            default_budget_usd: Default budget per run in USD
        """
        self.db_path = Path(db_path)
        self.default_budget_usd = default_budget_usd
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Ensure database schema exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS generation_costs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    prompt_tokens INTEGER DEFAULT 0,
                    completion_tokens INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    cost_usd REAL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    UNIQUE(run_id)
                );

                CREATE INDEX IF NOT EXISTS idx_costs_run ON generation_costs(run_id);
            """)
            conn.commit()
        finally:
            conn.close()

    def _conn(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def estimate_page_cost(
        self,
        run_id: str,
        doc_slug: str,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens_estimate: int = 500,
    ) -> PageCostEstimate:
        """Estimate cost for a single page.

        Args:
            run_id: Generation run ID
            doc_slug: Document slug
            provider: LLM provider name
            model: Model name
            prompt_tokens: Estimated prompt tokens
            completion_tokens_estimate: Estimated completion tokens

        Returns:
            PageCostEstimate
        """
        input_price, output_price = get_pricing(provider, model)

        prompt_cost = (prompt_tokens / 1_000_000) * input_price
        completion_cost = (completion_tokens_estimate / 1_000_000) * output_price
        total_cost = prompt_cost + completion_cost

        return PageCostEstimate(
            run_id=run_id,
            doc_slug=doc_slug,
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            estimated_cost_usd=total_cost,
            within_page_budget=total_cost < self.default_budget_usd,
        )

    def estimate_run_cost(
        self,
        run_id: str,
        provider: str,
        model: str,
        total_prompt_tokens: int,
        total_completion_tokens: int,
        budget_override: float | None = None,
    ) -> CostEstimate:
        """Estimate total cost for a generation run.

        Args:
            run_id: Generation run ID
            provider: LLM provider name
            model: Model name
            total_prompt_tokens: Total prompt tokens across all pages
            total_completion_tokens: Total completion tokens across all pages
            budget_override: Override budget limit (USD)

        Returns:
            CostEstimate with budget check
        """
        input_price, output_price = get_pricing(provider, model)

        prompt_cost = (total_prompt_tokens / 1_000_000) * input_price
        completion_cost = (total_completion_tokens / 1_000_000) * output_price
        total_cost = prompt_cost + completion_cost

        budget = budget_override or self.default_budget_usd
        within_budget = total_cost <= budget

        reason_code = None
        message = None
        if not within_budget:
            reason_code = "BUDGET_EXCEEDED"
            message = (
                f"Estimated cost ${total_cost:.4f} exceeds budget ${budget:.4f}. "
                f"Use --override-budget to proceed."
            )

        return CostEstimate(
            run_id=run_id,
            provider=provider,
            model=model,
            prompt_tokens=total_prompt_tokens,
            completion_tokens=total_completion_tokens,
            total_tokens=total_prompt_tokens + total_completion_tokens,
            estimated_cost_usd=total_cost,
            input_cost_usd=prompt_cost,
            output_cost_usd=completion_cost,
            budget_limit_usd=budget,
            within_budget=within_budget,
            reason_code=reason_code,
            message=message,
        )

    def record_page_tokens(
        self,
        run_id: str,
        doc_slug: str,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float:
        """Record actual token usage for a page.

        Args:
            run_id: Generation run ID
            doc_slug: Document slug
            provider: LLM provider name
            model: Model name
            prompt_tokens: Actual prompt tokens used
            completion_tokens: Actual completion tokens used

        Returns:
            Actual cost in USD
        """
        input_price, output_price = get_pricing(provider, model)
        cost = (prompt_tokens / 1_000_000) * input_price
        cost += (completion_tokens / 1_000_000) * output_price

        # Update existing or insert new
        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT INTO generation_costs
                (run_id, provider, model, prompt_tokens, completion_tokens, total_tokens, cost_usd, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    prompt_tokens = prompt_tokens + excluded.prompt_tokens,
                    completion_tokens = completion_tokens + excluded.completion_tokens,
                    total_tokens = total_tokens + excluded.total_tokens,
                    cost_usd = cost_usd + excluded.cost_usd
                """,
                (run_id, provider, model, prompt_tokens, completion_tokens,
                 prompt_tokens + completion_tokens, cost, datetime.now(UTC).isoformat()),
            )
            conn.commit()
        finally:
            conn.close()

        return cost

    def get_run_total_cost(self, run_id: str) -> tuple[float, int, int]:
        """Get total cost for a run.

        Args:
            run_id: Generation run ID

        Returns:
            Tuple of (total_cost_usd, total_prompt_tokens, total_completion_tokens)
        """
        conn = self._conn()
        try:
            row = conn.execute(
                """
                SELECT cost_usd, prompt_tokens, completion_tokens
                FROM generation_costs
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()

            if row:
                return row["cost_usd"], row["prompt_tokens"], row["completion_tokens"]
            return 0.0, 0, 0
        finally:
            conn.close()


class BudgetGate:
    """Budget gate that blocks over-budget generation runs."""

    def __init__(
        self,
        cost_estimator: GenerationCostEstimator,
        default_budget_usd: float = 10.0,
        allow_override: bool = True,
    ) -> None:
        """Initialize budget gate.

        Args:
            cost_estimator: Cost estimator instance
            default_budget_usd: Default budget per run
            allow_override: Whether to allow budget override
        """
        self.cost_estimator = cost_estimator
        self.default_budget_usd = default_budget_usd
        self.allow_override = allow_override

    def check_run_budget(
        self,
        run_id: str,
        provider: str,
        model: str,
        estimated_prompt_tokens: int,
        estimated_completion_tokens: int,
        budget_override: float | None = None,
    ) -> tuple[bool, CostEstimate]:
        """Check if a run is within budget.

        Args:
            run_id: Generation run ID
            provider: LLM provider
            model: Model name
            estimated_prompt_tokens: Estimated prompt tokens
            estimated_completion_tokens: Estimated completion tokens
            budget_override: Override budget (USD)

        Returns:
            Tuple of (allowed, cost_estimate)
        """
        estimate = self.cost_estimator.estimate_run_cost(
            run_id=run_id,
            provider=provider,
            model=model,
            total_prompt_tokens=estimated_prompt_tokens,
            total_completion_tokens=estimated_completion_tokens,
            budget_override=budget_override,
        )

        if estimate.within_budget:
            return True, estimate

        if budget_override is not None and self.allow_override:
            # Override was explicitly provided, allow despite over-budget
            estimate.message = (
                f"Over-budget run allowed via override. "
                f"Estimated cost: ${estimate.estimated_cost_usd:.4f}"
            )
            return True, estimate

        return False, estimate

    def check_page_budget(
        self,
        page_estimate: PageCostEstimate,
        page_budget_override: float | None = None,
    ) -> bool:
        """Check if a page is within budget.

        Args:
            page_estimate: Page cost estimate
            page_budget_override: Override page budget

        Returns:
            True if allowed
        """
        budget = page_budget_override or (self.default_budget_usd * 0.1)  # 10% of run budget per page
        return page_estimate.estimated_cost_usd <= budget


class BudgetExceeded(Exception):
    """Raised when a generation run exceeds its budget."""

    def __init__(
        self,
        message: str,
        reason_code: str,
        estimate: CostEstimate,
    ) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.estimate = estimate


def create_cost_estimator(
    root: Path,
    default_budget_usd: float = 10.0,
) -> GenerationCostEstimator:
    """Create a cost estimator with standard database path.

    Args:
        root: Repository root path
        default_budget_usd: Default budget per run in USD

    Returns:
        GenerationCostEstimator instance
    """
    db_path = root / ".repo-wiki" / "index" / "generation_costs.sqlite3"
    return GenerationCostEstimator(db_path, default_budget_usd)


def create_budget_gate(
    root: Path,
    default_budget_usd: float = 10.0,
    allow_override: bool = True,
) -> BudgetGate:
    """Create a budget gate with standard dependencies.

    Args:
        root: Repository root path
        default_budget_usd: Default budget per run in USD
        allow_override: Whether to allow budget override

    Returns:
        BudgetGate instance
    """
    estimator = create_cost_estimator(root, default_budget_usd)
    return BudgetGate(estimator, default_budget_usd, allow_override)
