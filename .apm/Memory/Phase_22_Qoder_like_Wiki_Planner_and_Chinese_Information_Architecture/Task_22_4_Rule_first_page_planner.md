# Task 22.4 - Rule-first page planner

## Status: COMPLETED

## Objective
Generate a stable Qoder-like page plan without calling an LLM.

## Deliverables
- **Rule-first planner** (`repo_wiki/planner/rule_first.py`)
  - `RuleFirstPlanner`: generates deterministic page plans
  - `plan_pages_from_snapshot(identity, snapshot) -> WikiPlanManifest`
  - Produces stable page IDs, paths, parent links, and order
  - All pages use `GenerationMode.RULE_FIRST`

- **Planner tests** (`tests/test_rule_first_planner.py`)
  - 13 tests including AI_API_Atlas 80+ pages assertion

## Self-Test Results
```
uv run pytest tests/test_rule_first_planner.py tests/test_wiki_taxonomy.py  # PASSED (13 tests)
```

## Key Implementation Details
- Uses repository identity, modules, APIs, data models, and runtime roles
- Page generation by category:
  - Project Overview (6+ pages): overview, readme, changelog, installation, features, quickstart
  - Architecture Design (7+ pages): overview, components, relationships, data-flow, gateway, mesh, events, microservices
  - Core Services (10+ pages): index pages + per-module pages + API sub-pages + data model sub-pages
  - API Reference (10+ pages): overview + per-module indexes + per-endpoint pages
  - Data Models (10+ pages): overview + per-module indexes + per-model pages
  - Deployment Operations (10+ pages): overview, config, env, monitoring, logging, containers, k8s, cicd, backup, scaling
  - Development Guide (11+ pages): overview, local-setup, testing, code-style, contribution, debug, perf, ide, git, api-dev, db-migration
  - Security Compliance (10+ pages): overview, auth, authz, data-protection, encryption, api-security, audit, compliance, best-practices, vulnerability
  - Troubleshooting (14+ pages): overview, common-issues, error-codes, performance, network, database, auth, api, build, deployment, memory, disk, debug-tools, health-check

## AI_API_Atlas Target Achievement
- Rule-only plan: 80+ pages (actual: 81 pages)
