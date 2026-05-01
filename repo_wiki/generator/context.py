"""Context strategy builder for document generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ContextStrategyResult:
    strategy: str
    token_budget: int
    chunks: list[dict[str, Any]]
    neighbors: list[str]
    notes: str


class ContextBuilder:
    """Implements A/B/C context strategy with deterministic thresholds."""

    def __init__(self, token_budget: int = 4000) -> None:
        self.token_budget = token_budget

    def choose_strategy(self, module: dict[str, Any]) -> str:
        size = int(module.get("line_count", 0))
        dep_count = len(module.get("depends_on", []) or [])
        if size <= 300 and dep_count <= 3:
            return "A"
        if size <= 1200 and dep_count <= 8:
            return "B"
        return "C"

    def build_module_context(
        self,
        module: dict[str, Any],
        retrieval_candidates: list[dict[str, Any]],
        graph_neighbors: list[str],
    ) -> ContextStrategyResult:
        strategy = self.choose_strategy(module)
        if strategy == "A":
            k = min(3, len(retrieval_candidates))
            note = "Small module summary from direct metadata and a compact chunk set."
            budget = min(self.token_budget, 1200)
        elif strategy == "B":
            k = min(6, len(retrieval_candidates))
            note = "Balanced context from module metadata, interfaces/models and Top-K chunks."
            budget = min(self.token_budget, 2400)
        else:
            k = min(10, len(retrieval_candidates))
            note = "Heavy context with graph neighbors, Top-K chunks and key config summaries."
            budget = self.token_budget

        return ContextStrategyResult(
            strategy=strategy,
            token_budget=budget,
            chunks=retrieval_candidates[:k],
            neighbors=sorted(set(graph_neighbors)),
            notes=note,
        )
