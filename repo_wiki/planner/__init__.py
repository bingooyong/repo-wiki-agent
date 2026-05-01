"""Wiki page planner module.

This module provides:
- WikiPlanManifest and WikiPagePlan schema definitions
- Chinese taxonomy baseline (DEFAULT_CHINESE_TAXONOMY)
- Repository identity resolver
- Rule-first page planner
- LLM-assisted page planner extension
- Planner persistence into SQLite and manifest
"""
from __future__ import annotations

from repo_wiki.planner.identity import resolve_repository_identity, detect_language_and_framework, detect_package_manager
from repo_wiki.planner.rule_first import RuleFirstPlanner, plan_pages_from_snapshot
from repo_wiki.planner.api_topic_planner import APITopicPlanner, plan_api_topics
from repo_wiki.planner.data_model_topic_planner import DataModelTopicPlanner, plan_data_model_topics
from repo_wiki.planner.llm_planner import LLMAssistedPlanner, MockLLMProvider, enhance_plan_with_llm
from repo_wiki.planner.persistence import persist_plan, load_plan_from_sqlite
from repo_wiki.planner.rule_first import RuleFirstPlanner, plan_pages_from_snapshot
from repo_wiki.planner.schema import (
    GenerationMode,
    NavNode,
    RepositoryIdentity,
    SourceRequirement,
    WikiPagePlan,
    WikiPlanManifest,
    WikiTaxonomyCategory,
    DEFAULT_CHINESE_TAXONOMY,
    current_schema_version,
)

__all__ = [
    # Schema
    "GenerationMode",
    "NavNode",
    "RepositoryIdentity",
    "SourceRequirement",
    "WikiPagePlan",
    "WikiPlanManifest",
    "WikiTaxonomyCategory",
    "DEFAULT_CHINESE_TAXONOMY",
    "current_schema_version",
    # Identity
    "resolve_repository_identity",
    "detect_language_and_framework",
    "detect_package_manager",
    # Rule-first planner
    "RuleFirstPlanner",
    "plan_pages_from_snapshot",
    # API topic planner
    "APITopicPlanner",
    "plan_api_topics",
    # Data model topic planner
    "DataModelTopicPlanner",
    "plan_data_model_topics",
    # LLM-assisted planner
    "LLMAssistedPlanner",
    "MockLLMProvider",
    "enhance_plan_with_llm",
    # Persistence
    "persist_plan",
    "load_plan_from_sqlite",
]