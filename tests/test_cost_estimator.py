"""Tests for LLM cost estimator and budget gate."""

import tempfile
from pathlib import Path

import pytest

from repo_wiki.orchestration.cost_estimator import (
    BudgetExceeded,
    BudgetGate,
    GenerationCostEstimator,
    PageCostEstimate,
    get_pricing,
    create_cost_estimator,
    create_budget_gate,
)


class TestGetPricing:
    """Tests for get_pricing function."""

    def test_openai_gpt4o(self):
        """Test OpenAI GPT-4o pricing."""
        input_price, output_price = get_pricing("openai", "gpt-4o")
        assert input_price == 5.00
        assert output_price == 15.00

    def test_openai_gpt4o_mini(self):
        """Test OpenAI GPT-4o-mini pricing."""
        input_price, output_price = get_pricing("openai", "gpt-4o-mini")
        assert input_price == 0.15
        assert output_price == 0.60

    def test_anthropic_claude_sonnet(self):
        """Test Anthropic Claude Sonnet pricing."""
        input_price, output_price = get_pricing("anthropic", "claude-sonnet-4-6")
        assert input_price == 3.00
        assert output_price == 15.00

    def test_anthropic_claude_haiku(self):
        """Test Anthropic Claude Haiku pricing."""
        input_price, output_price = get_pricing("anthropic", "claude-haiku-4-5")
        assert input_price == 0.80
        assert output_price == 4.00

    def test_case_insensitive(self):
        """Test provider and model lookup is case insensitive."""
        input_price, output_price = get_pricing("OPENAI", "GPT-4O")
        assert input_price == 5.00
        assert output_price == 15.00

    def test_partial_model_match(self):
        """Test partial model name matching."""
        input_price, output_price = get_pricing("openai", "gpt-4o-test")
        assert input_price == 5.00
        assert output_price == 15.00

    def test_unknown_provider_fallback(self):
        """Test fallback pricing for unknown providers."""
        input_price, output_price = get_pricing("unknown", "some-model")
        # Should fall back to generic pricing
        assert input_price == 1.00
        assert output_price == 3.00


class TestGenerationCostEstimator:
    """Tests for GenerationCostEstimator."""

    def test_create_estimator(self, tmp_path):
        """Test creating a cost estimator."""
        db_path = tmp_path / "test_costs.sqlite3"
        estimator = GenerationCostEstimator(db_path, default_budget_usd=5.0)
        assert estimator.db_path == db_path
        assert estimator.default_budget_usd == 5.0

    def test_estimate_page_cost(self, tmp_path):
        """Test estimating page cost."""
        estimator = GenerationCostEstimator(tmp_path / "test.db")
        estimate = estimator.estimate_page_cost(
            run_id="gen-test",
            doc_slug="00-overview",
            provider="openai",
            model="gpt-4o-mini",
            prompt_tokens=1000,
            completion_tokens_estimate=500,
        )

        assert estimate.run_id == "gen-test"
        assert estimate.doc_slug == "00-overview"
        assert estimate.provider == "openai"
        assert estimate.model == "gpt-4o-mini"
        assert estimate.prompt_tokens == 1000
        # gpt-4o-mini: $0.15/1M input, $0.60/1M output
        # prompt: 1000/1M * 0.15 = $0.00015
        # completion: 500/1M * 0.60 = $0.0003
        # total: $0.00045
        expected_cost = (1000 / 1_000_000) * 0.15 + (500 / 1_000_000) * 0.60
        assert abs(estimate.estimated_cost_usd - expected_cost) < 0.0001

    def test_estimate_page_cost_within_budget(self, tmp_path):
        """Test page cost within default budget."""
        estimator = GenerationCostEstimator(tmp_path / "test.db", default_budget_usd=10.0)
        estimate = estimator.estimate_page_cost(
            run_id="gen-test",
            doc_slug="00-overview",
            provider="openai",
            model="gpt-4o-mini",
            prompt_tokens=1000,
            completion_tokens_estimate=500,
        )
        assert estimate.within_page_budget is True

    def test_estimate_run_cost(self, tmp_path):
        """Test estimating run cost."""
        estimator = GenerationCostEstimator(tmp_path / "test.db")
        estimate = estimator.estimate_run_cost(
            run_id="gen-test",
            provider="openai",
            model="gpt-4o",
            total_prompt_tokens=10000,
            total_completion_tokens=5000,
        )

        assert estimate.run_id == "gen-test"
        assert estimate.provider == "openai"
        assert estimate.model == "gpt-4o"
        assert estimate.prompt_tokens == 10000
        assert estimate.completion_tokens == 5000
        assert estimate.total_tokens == 15000
        # gpt-4o: $5/1M input, $15/1M output
        expected_cost = (10000 / 1_000_000) * 5.0 + (5000 / 1_000_000) * 15.0
        assert abs(estimate.estimated_cost_usd - expected_cost) < 0.0001

    def test_estimate_run_cost_within_budget(self, tmp_path):
        """Test run cost within budget."""
        estimator = GenerationCostEstimator(tmp_path / "test.db", default_budget_usd=10.0)
        estimate = estimator.estimate_run_cost(
            run_id="gen-test",
            provider="openai",
            model="gpt-4o-mini",
            total_prompt_tokens=10000,
            total_completion_tokens=5000,
        )
        # gpt-4o-mini: very cheap
        assert estimate.within_budget is True
        assert estimate.reason_code is None

    def test_estimate_run_cost_exceeds_budget(self, tmp_path):
        """Test run cost exceeding budget."""
        estimator = GenerationCostEstimator(tmp_path / "test.db", default_budget_usd=0.001)
        estimate = estimator.estimate_run_cost(
            run_id="gen-test",
            provider="openai",
            model="gpt-4o",
            total_prompt_tokens=1000000,  # 1M tokens
            total_completion_tokens=500000,
        )
        assert estimate.within_budget is False
        assert estimate.reason_code == "BUDGET_EXCEEDED"
        assert estimate.message is not None

    def test_estimate_run_cost_with_budget_override(self, tmp_path):
        """Test budget override."""
        estimator = GenerationCostEstimator(tmp_path / "test.db", default_budget_usd=0.001)
        estimate = estimator.estimate_run_cost(
            run_id="gen-test",
            provider="openai",
            model="gpt-4o",
            total_prompt_tokens=1000000,
            total_completion_tokens=500000,
            budget_override=100.0,  # High override
        )
        assert estimate.within_budget is True
        assert estimate.budget_limit_usd == 100.0

    def test_record_page_tokens(self, tmp_path):
        """Test recording actual token usage."""
        estimator = GenerationCostEstimator(tmp_path / "test.db")
        cost = estimator.record_page_tokens(
            run_id="gen-test",
            doc_slug="00-overview",
            provider="openai",
            model="gpt-4o-mini",
            prompt_tokens=1000,
            completion_tokens=500,
        )
        assert cost > 0

        # Record again - should accumulate in DB
        estimator.record_page_tokens(
            run_id="gen-test",
            doc_slug="00-overview",
            provider="openai",
            model="gpt-4o-mini",
            prompt_tokens=1000,
            completion_tokens=500,
        )

        # Verify accumulated cost in database
        total_cost, total_prompt, total_completion = estimator.get_run_total_cost("gen-test")
        assert total_prompt == 2000  # 1000 + 1000
        assert total_completion == 1000  # 500 + 500

    def test_get_run_total_cost(self, tmp_path):
        """Test getting run total cost."""
        estimator = GenerationCostEstimator(tmp_path / "test.db")
        estimator.record_page_tokens(
            run_id="gen-test",
            doc_slug="00-overview",
            provider="openai",
            model="gpt-4o-mini",
            prompt_tokens=1000,
            completion_tokens=500,
        )

        total_cost, prompt_tokens, completion_tokens = estimator.get_run_total_cost("gen-test")
        assert total_cost > 0
        assert prompt_tokens == 1000
        assert completion_tokens == 500

    def test_get_run_total_cost_nonexistent(self, tmp_path):
        """Test getting cost for nonexistent run."""
        estimator = GenerationCostEstimator(tmp_path / "test.db")
        total_cost, prompt_tokens, completion_tokens = estimator.get_run_total_cost("nonexistent")
        assert total_cost == 0.0
        assert prompt_tokens == 0
        assert completion_tokens == 0


class TestBudgetGate:
    """Tests for BudgetGate."""

    def test_check_run_budget_allowed(self, tmp_path):
        """Test budget check when within budget."""
        estimator = GenerationCostEstimator(tmp_path / "test.db", default_budget_usd=10.0)
        gate = BudgetGate(estimator, default_budget_usd=10.0)

        allowed, estimate = gate.check_run_budget(
            run_id="gen-test",
            provider="openai",
            model="gpt-4o-mini",
            estimated_prompt_tokens=10000,
            estimated_completion_tokens=5000,
        )

        assert allowed is True
        assert estimate.within_budget is True

    def test_check_run_budget_blocked(self, tmp_path):
        """Test budget check when over budget."""
        estimator = GenerationCostEstimator(tmp_path / "test.db", default_budget_usd=0.001)
        gate = BudgetGate(estimator, default_budget_usd=0.001, allow_override=True)

        allowed, estimate = gate.check_run_budget(
            run_id="gen-test",
            provider="openai",
            model="gpt-4o",
            estimated_prompt_tokens=1000000,
            estimated_completion_tokens=500000,
        )

        assert allowed is False
        assert estimate.within_budget is False

    def test_check_run_budget_with_override(self, tmp_path):
        """Test budget override allows over-budget run."""
        estimator = GenerationCostEstimator(tmp_path / "test.db", default_budget_usd=0.001)
        gate = BudgetGate(estimator, default_budget_usd=0.001, allow_override=True)

        # gpt-4o with 1M prompt + 500k completion = ~$12.5
        # With default budget of $0.001, this is way over
        allowed, estimate = gate.check_run_budget(
            run_id="gen-test",
            provider="openai",
            model="gpt-4o",
            estimated_prompt_tokens=1000000,
            estimated_completion_tokens=500000,
            budget_override=100.0,  # Allow up to $100
        )

        assert allowed is True
        # With $100 budget, cost ~$12.5 is within budget
        assert estimate.within_budget is True
        assert estimate.budget_limit_usd == 100.0

    def test_check_page_budget(self, tmp_path):
        """Test page budget check."""
        estimator = GenerationCostEstimator(tmp_path / "test.db", default_budget_usd=10.0)
        gate = BudgetGate(estimator, default_budget_usd=10.0)

        page_estimate = PageCostEstimate(
            run_id="gen-test",
            doc_slug="00-overview",
            provider="openai",
            model="gpt-4o-mini",
            prompt_tokens=1000,
            estimated_cost_usd=0.001,
            within_page_budget=True,
        )

        assert gate.check_page_budget(page_estimate) is True

    def test_check_page_budget_custom_page_budget(self, tmp_path):
        """Test page budget with custom override."""
        estimator = GenerationCostEstimator(tmp_path / "test.db", default_budget_usd=10.0)
        gate = BudgetGate(estimator, default_budget_usd=10.0)

        page_estimate = PageCostEstimate(
            run_id="gen-test",
            doc_slug="00-overview",
            provider="openai",
            model="gpt-4o-mini",
            prompt_tokens=1000,
            estimated_cost_usd=5.0,  # High cost
            within_page_budget=False,
        )

        # With default page budget (10% of run = $1), should fail
        assert gate.check_page_budget(page_estimate) is False

        # With higher page budget override
        assert gate.check_page_budget(page_estimate, page_budget_override=10.0) is True


class TestBudgetExceeded:
    """Tests for BudgetExceeded exception."""

    def test_budget_exceeded_exception(self, tmp_path):
        """Test BudgetExceeded exception."""
        estimator = GenerationCostEstimator(tmp_path / "test.db", default_budget_usd=0.001)
        estimate = estimator.estimate_run_cost(
            run_id="gen-test",
            provider="openai",
            model="gpt-4o",
            total_prompt_tokens=1000000,
            total_completion_tokens=500000,
        )

        exc = BudgetExceeded(
            message="Budget exceeded",
            reason_code="BUDGET_EXCEEDED",
            estimate=estimate,
        )

        assert exc.reason_code == "BUDGET_EXCEEDED"
        assert exc.estimate == estimate
        assert str(exc) == "Budget exceeded"


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_cost_estimator(self, tmp_path):
        """Test create_cost_estimator factory."""
        estimator = create_cost_estimator(tmp_path, default_budget_usd=5.0)
        assert isinstance(estimator, GenerationCostEstimator)
        expected_path = tmp_path / ".repo-wiki" / "index" / "generation_costs.sqlite3"
        assert estimator.db_path == expected_path

    def test_create_budget_gate(self, tmp_path):
        """Test create_budget_gate factory."""
        gate = create_budget_gate(tmp_path, default_budget_usd=5.0)
        assert isinstance(gate, BudgetGate)
        assert gate.default_budget_usd == 5.0
        assert gate.allow_override is True
