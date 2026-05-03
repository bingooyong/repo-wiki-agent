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

from repo_wiki.planner.api_topic_planner import APITopicPlanner, plan_api_topics
from repo_wiki.planner.data_model_topic_planner import DataModelTopicPlanner, plan_data_model_topics
from repo_wiki.planner.identity import (
    detect_language_and_framework,
    detect_package_manager,
    resolve_repository_identity,
)
from repo_wiki.planner.llm_planner import LLMAssistedPlanner, MockLLMProvider, enhance_plan_with_llm
from repo_wiki.planner.persistence import load_plan_from_sqlite, persist_plan
from repo_wiki.planner.rule_first import RuleFirstPlanner, plan_pages_from_snapshot
from repo_wiki.planner.schema import (
    DEFAULT_CHINESE_TAXONOMY,
    GenerationMode,
    NavNode,
    RepositoryIdentity,
    SourceRequirement,
    WikiPagePlan,
    WikiPlanManifest,
    WikiTaxonomyCategory,
    current_schema_version,
)
from repo_wiki.planner.service_subtopic_planner import (
    ServiceSubtopicPlanner,
    plan_service_subtopics,
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
    # Service subtopic planner
    "ServiceSubtopicPlanner",
    "plan_service_subtopics",
    # Persistence
    "persist_plan",
    "load_plan_from_sqlite",
]
