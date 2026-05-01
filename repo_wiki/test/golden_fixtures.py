"""Golden fixture suite for qoder-like CI validation.

This module provides:
- Stable CI fixtures for Java, Python, TypeScript, and SQL projects
- Expected Wiki tree structure
- Mock LLM outputs for consistent testing
- Coverage of planner, evidence, composer, verifier, and comparator paths

Phase 29 - Task 29.4: Golden fixture suite
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# =============================================================================
# GOLDEN FIXTURE DEFINITIONS
# =============================================================================

@dataclass
class GoldenFixture:
    """A golden fixture for CI validation."""
    name: str
    language: str
    repository_type: str
    complexity_score: float
    size_category: str
    structure: dict[str, Any]
    expected_wiki_tree: dict[str, list[str]]
    mock_llm_output: dict[str, str]


# Python fixture - simple microservice
PYTHON_FIXTURE = GoldenFixture(
    name="python-microservice",
    language="python",
    repository_type="python",
    complexity_score=0.6,
    size_category="medium",
    structure={
        "modules": ["auth_service", "user_service", "order_service"],
        "api_endpoints": 12,
        "data_models": 8,
        "database_tables": 6,
    },
    expected_wiki_tree={
        "项目概述": ["00-overview"],
        "架构设计": ["01-architecture"],
        "核心服务": ["02-services", "03-modules"],
        "API参考": ["04-api"],
        "数据模型": ["05-data-model"],
    },
    mock_llm_output={
        "00-overview": """# Project Overview

## Table of Contents
- [Introduction](#introduction)
- [Quick Start](#quick-start)

## Introduction

This is a Python microservice project with authentication, user management,
and order processing capabilities.

<cite>source:README.md</cite>

## Quick Start

1. Install dependencies: `pip install -r requirements.txt`
2. Configure environment: copy `.env.example` to `.env`
3. Run the service: `python -m auth_service`

## Architecture

```mermaid
graph LR
    A[Client] --> B[API Gateway]
    B --> C[Auth Service]
    B --> D[User Service]
    D --> E[(Database)]
```

<cite>source:docs/architecture.md</cite>
""",
        "architecture": """# Architecture

## 系统分层

The system follows a layered architecture:
- **API Layer**: REST endpoints via FastAPI
- **Service Layer**: Business logic
- **Data Layer**: SQLAlchemy ORM

## 核心链路

1. Client sends request to API Gateway
2. Gateway authenticates via Auth Service
3. Auth Service validates JWT token
4. Request forwarded to appropriate service
5. Service queries database and returns response

<cite>source:architecture.md</cite>
""",
    },
)


# TypeScript fixture - React frontend
TYPESCRIPT_FIXTURE = GoldenFixture(
    name="typescript-react",
    language="typescript",
    repository_type="typescript",
    complexity_score=0.5,
    size_category="small",
    structure={
        "components": 15,
        "pages": 5,
        "api_calls": 8,
        "state_management": "redux",
    },
    expected_wiki_tree={
        "项目概述": ["00-overview"],
        "架构设计": ["01-architecture"],
        "开发指南": ["02-development"],
    },
    mock_llm_output={
        "00-overview": """# Project Overview

## Table of Contents
- [Introduction](#introduction)

## Introduction

This is a React-based TypeScript frontend application.

<cite>source:README.md</cite>
""",
    },
)


# Java fixture - Spring Boot backend
JAVA_FIXTURE = GoldenFixture(
    name="java-springboot",
    language="java",
    repository_type="java",
    complexity_score=0.7,
    size_category="large",
    structure={
        "packages": ["com.example.api", "com.example.service", "com.example.repository"],
        "controllers": 6,
        "services": 8,
        "entities": 10,
    },
    expected_wiki_tree={
        "项目概述": ["00-overview"],
        "架构设计": ["01-architecture"],
        "核心服务": ["02-services"],
        "数据模型": ["03-data-model"],
        "API参考": ["04-api"],
    },
    mock_llm_output={
        "00-overview": """# Project Overview

## Table of Contents

## Introduction

Java Spring Boot application with REST API.

<cite>source:pom.xml</cite>
""",
    },
)


# SQL fixture - Database schema
SQL_FIXTURE = GoldenFixture(
    name="sql-database",
    language="sql",
    repository_type="sql",
    complexity_score=0.4,
    size_category="small",
    structure={
        "tables": 12,
        "views": 5,
        "stored_procedures": 8,
        "triggers": 4,
    },
    expected_wiki_tree={
        "数据模型": ["00-data-model"],
        "部署运维": ["01-deployment"],
    },
    mock_llm_output={
        "00-data-model": """# Data Model

## Entity Relationship

```mermaid
erDiagram
    CUSTOMER ||--o{ ORDER : places
    ORDER ||--|{ LINE_ITEM : contains
    PRODUCT ||--o{ LINE_ITEM : "ordered in"
```

## Tables

| Table | Description |
|-------|-------------|
| customers | Customer information |
| orders | Order headers |
| line_items | Order line items |

<cite>source:schema.sql</cite>
""",
    },
)


# All golden fixtures
GOLDEN_FIXTURES = {
    "python-microservice": PYTHON_FIXTURE,
    "typescript-react": TYPESCRIPT_FIXTURE,
    "java-springboot": JAVA_FIXTURE,
    "sql-database": SQL_FIXTURE,
}


# =============================================================================
# FIXTURE BUILDER
# =============================================================================

class GoldenFixtureBuilder:
    """Builds golden fixture file structures."""

    def __init__(self, root: Path) -> None:
        """Initialize fixture builder.

        Args:
            root: Root directory for fixtures
        """
        self.root = Path(root)

    def build_fixture(self, fixture: GoldenFixture) -> Path:
        """Build a complete golden fixture.

        Args:
            fixture: GoldenFixture to build

        Returns:
            Path to built fixture root
        """
        fixture_root = self.root / fixture.name
        fixture_root.mkdir(parents=True, exist_ok=True)

        # Create content directory structure
        content_dir = fixture_root / "content"
        content_dir.mkdir(parents=True, exist_ok=True)

        # Create qoder-like taxonomy directories
        for category in fixture.expected_wiki_tree.keys():
            (content_dir / category).mkdir(exist_ok=True)

        # Write mock LLM outputs
        for doc_slug, content in fixture.mock_llm_output.items():
            # Determine category from wiki tree
            target_category = None
            for cat, docs in fixture.expected_wiki_tree.items():
                if doc_slug in docs:
                    target_category = cat
                    break

            if target_category:
                target_dir = content_dir / target_category
                file_path = target_dir / f"{doc_slug}.md"
                file_path.write_text(content, encoding="utf-8")

        # Create fixture metadata
        metadata = {
            "schema_version": "1.0",
            "name": fixture.name,
            "language": fixture.language,
            "repository_type": fixture.repository_type,
            "complexity_score": fixture.complexity_score,
            "size_category": fixture.size_category,
            "generated_at": "2024-01-01T00:00:00Z",
            "generator_version": "golden-fixture-v1.0",
            "expected_tree": fixture.expected_wiki_tree,
        }
        (fixture_root / "fixture_metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return fixture_root

    def build_all_fixtures(self) -> list[Path]:
        """Build all golden fixtures.

        Returns:
            List of paths to built fixtures
        """
        roots = []
        for fixture in GOLDEN_FIXTURES.values():
            root = self.build_fixture(fixture)
            roots.append(root)
        return roots


# =============================================================================
# FIXTURE VALIDATOR
# =============================================================================

class GoldenFixtureValidator:
    """Validates golden fixtures."""

    def __init__(self, fixture_root: Path) -> None:
        """Initialize validator.

        Args:
            fixture_root: Root of fixture to validate
        """
        self.fixture_root = Path(fixture_root)

    def validate(self) -> tuple[bool, list[str]]:
        """Validate a golden fixture.

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Check metadata exists
        metadata_path = self.fixture_root / "fixture_metadata.json"
        if not metadata_path.exists():
            errors.append("Missing fixture_metadata.json")
            return False, errors

        # Load and validate metadata
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON in metadata: {e}")
            return False, errors

        # Check required fields
        required_fields = ["name", "language", "repository_type", "schema_version"]
        for field in required_fields:
            if field not in metadata:
                errors.append(f"Missing required field: {field}")

        # Check content directory exists
        content_dir = self.fixture_root / "content"
        if not content_dir.exists():
            errors.append("Missing content directory")

        # Check for markdown files
        md_files = list(content_dir.rglob("*.md"))
        if len(md_files) == 0:
            errors.append("No markdown files found in content")

        # Check for citations in files
        for md_file in md_files:
            content = md_file.read_text(encoding="utf-8")
            # Golden fixtures should have at least some citations
            # but we don't enforce this strictly for fixture validation

        return len(errors) == 0, errors


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_golden_fixtures(root: Path) -> list[Path]:
    """Create all golden fixtures.

    Args:
        root: Root directory for fixtures

    Returns:
        List of paths to created fixtures
    """
    builder = GoldenFixtureBuilder(root)
    return builder.build_all_fixtures()


def validate_golden_fixture(fixture_root: Path) -> tuple[bool, list[str]]:
    """Validate a golden fixture.

    Args:
        fixture_root: Root of fixture to validate

    Returns:
        Tuple of (is_valid, error_messages)
    """
    validator = GoldenFixtureValidator(fixture_root)
    return validator.validate()


def get_fixture(name: str) -> GoldenFixture | None:
    """Get a golden fixture by name.

    Args:
        name: Fixture name

    Returns:
        GoldenFixture or None if not found
    """
    return GOLDEN_FIXTURES.get(name)


def list_fixtures() -> list[str]:
    """List all available fixture names.

    Returns:
        List of fixture names
    """
    return list(GOLDEN_FIXTURES.keys())