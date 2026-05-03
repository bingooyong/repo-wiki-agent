---
task_ref: "Task 32.2 - Service subtopic planner"
status: "completed"
date: "2026-05-03"
agent: "Agent_DocGen"
---

# Task 32.2: Service Subtopic Planner Report

## Objective
Generate service subtopic plans instead of one page per service, based on Qoder baseline patterns discovered in Task 32.1.

## Deliverables

### 1. Service Subtopic Planner (`repo_wiki/planner/service_subtopic_planner.py`)

Created a new planner that generates multi-page service documentation following Qoder Chinese wiki patterns:

**Key Features**:
- Generates 5 subtopic pages per Python service:
  - `服务概述` (Overview)
  - `架构设计` (Architecture Design)
  - `API接口文档` (API Documentation)
  - `部署配置` (Deployment Configuration)
  - `核心组件` (Core Components)
- Creates business subdomain pages for core services
- Preserves stable slugs and manifest navigation ordering
- Maintains compatibility with existing WikiPlanManifest structure

**Architecture**:
- `ServiceSubtopicPlanner` class with `generate()` method
- `plan_service_subtopics()` convenience function
- `ServiceSubtopicCategory` enum-like class for subtopic types

### 2. Module Export (`repo_wiki/planner/__init__.py`)

Added export for the new planner:
```python
from repo_wiki.planner.service_subtopic_planner import ServiceSubtopicPlanner, plan_service_subtopics
```

### 3. Planner Tests (`tests/test_service_subtopic_planner.py`)

Created comprehensive test suite with 13 tests:
- `TestServiceSubtopicPlanner`: 9 tests for planner functionality
- `TestServiceSubtopicCategory`: 2 tests for subtopic constants
- `TestManifestNavigationIntegration`: 3 tests for manifest compatibility

**Test Coverage**:
- Planner initialization
- Python service subtopic generation
- Business subdomain page generation
- Subtopic structure validation
- All 5 subtopic templates per service
- Navigation tree integration
- Endpoint grouping by service
- Manifest compatibility

## Self-Test Verification

**Command**: `uv run repo-wiki --help`
**Result**: PASS - repo-wiki commands available

**Command**: `uv run pytest tests/test_manifest_navigation.py tests/test_service_subtopic_planner.py -v`
**Result**: PASS - 28 tests passed

**Extended Test**: `uv run pytest tests/test_qoder_like_verifier.py tests/test_qoder_like_profile.py tests/test_manifest_navigation.py tests/test_service_subtopic_planner.py -v`
**Result**: PASS - 47 tests passed

## Navigation Ordering

Service subtopic pages are sorted by category order, following the established taxonomy:
- `PYTHON_SERVICES`: order 3
- `CORE_SERVICES`: order 2

Within each category, pages are sorted by `sort_order` field.

## Stable Slugs

Page IDs are generated using the service name and subtopic type:
- Format: `{service-name}-{subtopic}`
- Example: `tcsl-generator-service-overview`, `tcsl-generator-service-architecture`

Slugs are deduplicated using a counter suffix if collisions occur.

---
**Status**: COMPLETED
**Agent**: Agent_DocGen
**Completed**: 2026-05-03
**Next Task**: Task 32.3 - Data model entity topic planner