"""Tests for auth and error convention generator.

Tests the generator module (repo_wiki/generator/auth_error_convention_generator.py)
which provides:
- AuthErrorConventionGenerator: Generates auth/error convention pages
- analyze_auth_patterns: Analyzes authentication patterns
- analyze_error_codes: Analyzes error codes
- document_auth_conventions: Documents auth conventions
- document_error_handling_conventions: Documents error handling
- compose_auth_page: Composes auth convention page
- compose_error_codes_page: Composes error codes page

Phase 25 - Task 25.4: Auth and error convention generator

Test coverage:
- Auth pattern analysis
- Error code analysis
- Status code documentation
- Auth convention documentation
- Error handling convention documentation
- Page composition
- Missing evidence behavior
"""

from __future__ import annotations

import pytest

from repo_wiki.core.contracts import (
    Endpoint,
    Module,
    RepositoryInfo,
    RepositorySnapshot,
    RepositoryStats,
)
from repo_wiki.generator.auth_error_convention_generator import (
    AuthErrorConventionGenerator,
    compose_auth_convention_article,
    compose_error_convention_article,
    create_auth_error_convention_generator,
)
from repo_wiki.planner.schema import (
    GenerationMode,
    SourceRequirement,
    WikiPagePlan,
    WikiTaxonomyCategory,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def sample_snapshot() -> RepositorySnapshot:
    """Create a sample repository snapshot for testing."""
    repo_info = RepositoryInfo(
        name="test-repo",
        root_path="/test",
        language="python",
        framework="fastapi",
    )

    modules = [
        Module(
            name="auth",
            path="src/auth",
            responsibility="Authentication module",
            doc_path="docs/auth.md",
            service_family="python-backend",
            domain="core-platform",
            runtime_role="api-server",
        ),
        Module(
            name="api",
            path="src/api",
            responsibility="API endpoints",
            doc_path="docs/api.md",
            service_family="python-backend",
            domain="core-platform",
            runtime_role="api-server",
        ),
    ]

    endpoints = [
        Endpoint(
            method="GET",
            path="/health",
            module="api",
            handler="health_check",
            file_path="src/api/health.py",
            service_family="python-backend",
            domain="core-platform",
            runtime_role="api-server",
            auth_type="none",
            auth_required=False,
            error_codes=[],
        ),
        Endpoint(
            method="POST",
            path="/api/auth/login",
            module="auth",
            handler="login_handler",
            file_path="src/auth/handlers.py",
            service_family="python-backend",
            domain="core-platform",
            runtime_role="api-server",
            auth_type="bearer",
            auth_required=True,
            request_body=True,
            error_codes=[400, 401, 500],
        ),
        Endpoint(
            method="POST",
            path="/api/auth/logout",
            module="auth",
            handler="logout_handler",
            file_path="src/auth/handlers.py",
            service_family="python-backend",
            domain="core-platform",
            runtime_role="api-server",
            auth_type="bearer",
            auth_required=True,
            error_codes=[401, 500],
        ),
        Endpoint(
            method="GET",
            path="/api/users",
            module="api",
            handler="get_users",
            file_path="src/api/users.py",
            service_family="python-backend",
            domain="core-platform",
            runtime_role="api-server",
            auth_type="bearer",
            auth_required=True,
            error_codes=[401, 403, 500],
        ),
        Endpoint(
            method="GET",
            path="/api/users/{id}",
            module="api",
            handler="get_user",
            file_path="src/api/users.py",
            service_family="python-backend",
            domain="core-platform",
            runtime_role="api-server",
            auth_type="bearer",
            auth_required=True,
            error_codes=[401, 404, 500],
        ),
        Endpoint(
            method="POST",
            path="/api/data/upload",
            module="api",
            handler="upload_data",
            file_path="src/api/upload.py",
            service_family="python-backend",
            domain="core-platform",
            runtime_role="api-server",
            auth_type="api-key",
            auth_required=True,
            request_body=True,
            error_codes=[400, 413, 500],
        ),
    ]

    return RepositorySnapshot(
        repository=repo_info,
        modules=modules,
        endpoints=endpoints,
        commands={},
        stats=RepositoryStats(endpoint_count=6),
    )


@pytest.fixture
def auth_page_plan() -> WikiPagePlan:
    """Create an authentication API page plan."""
    return WikiPagePlan(
        page_id="api-authentication",
        title="认证授权API",
        category=WikiTaxonomyCategory.API_REFERENCE,
        output_path="docs/pages/api/api-authentication.md",
        source_requirements=SourceRequirement(
            endpoints=["POST /api/auth/login", "POST /api/auth/logout"],
            modules=["auth"],
        ),
        generation_mode=GenerationMode.RULE_FIRST,
        sort_order=10,
        tags=["api", "authentication"],
    )


@pytest.fixture
def error_codes_page_plan() -> WikiPagePlan:
    """Create an error codes API page plan."""
    return WikiPagePlan(
        page_id="api-error-codes",
        title="错误处理API",
        category=WikiTaxonomyCategory.API_REFERENCE,
        output_path="docs/pages/api/api-error-codes.md",
        source_requirements=SourceRequirement(
            endpoints=[
                "POST /api/auth/login",
                "GET /api/users",
                "POST /api/data/upload",
            ],
            modules=["auth", "api"],
        ),
        generation_mode=GenerationMode.RULE_FIRST,
        sort_order=20,
        tags=["api", "error-handling"],
    )


# =============================================================================
# TESTS FOR AUTH PATTERN ANALYSIS
# =============================================================================

class TestAuthPatternAnalysis:
    """Tests for authentication pattern analysis."""

    def test_analyze_auth_patterns_with_auth(self, sample_snapshot):
        """Test analyzing auth patterns when endpoints have auth."""
        generator = AuthErrorConventionGenerator(sample_snapshot)
        result = generator.analyze_auth_patterns()

        assert "bearer" in result["auth_types"]
        assert "api-key" in result["auth_types"]
        assert result["authenticated_endpoint_count"] == 5
        assert result["unauthenticated_endpoint_count"] == 1
        assert "auth" in result["auth_modules"]

    def test_analyze_auth_patterns_empty_snapshot(self):
        """Test analyzing auth patterns with empty snapshot."""
        empty_snapshot = RepositorySnapshot(
            repository=RepositoryInfo(name="empty", root_path="/test"),
            modules=[],
            endpoints=[],
            commands={},
            stats=RepositoryStats(),
        )
        generator = AuthErrorConventionGenerator(empty_snapshot)
        result = generator.analyze_auth_patterns()

        assert len(result["auth_types"]) == 0
        assert result["authenticated_endpoint_count"] == 0
        assert result["unauthenticated_endpoint_count"] == 0

    def test_get_auth_endpoints(self, sample_snapshot):
        """Test getting authenticated endpoints."""
        generator = AuthErrorConventionGenerator(sample_snapshot)
        endpoints = generator.get_auth_endpoints()

        assert len(endpoints) == 5
        assert all(ep.auth_required for ep in endpoints)

    def test_get_unauth_endpoints(self, sample_snapshot):
        """Test getting unauthenticated endpoints."""
        generator = AuthErrorConventionGenerator(sample_snapshot)
        endpoints = generator.get_unauth_endpoints()

        assert len(endpoints) == 1
        assert endpoints[0].path == "/health"

    def test_auth_files_collection(self, sample_snapshot):
        """Test that auth files are collected correctly."""
        generator = AuthErrorConventionGenerator(sample_snapshot)
        result = generator.analyze_auth_patterns()

        assert "src/auth/handlers.py" in result["auth_files"]
        assert "src/api/users.py" in result["auth_files"]


# =============================================================================
# TESTS FOR ERROR CODE ANALYSIS
# =============================================================================

class TestErrorCodeAnalysis:
    """Tests for error code analysis."""

    def test_analyze_error_codes(self, sample_snapshot):
        """Test analyzing error codes across endpoints."""
        generator = AuthErrorConventionGenerator(sample_snapshot)
        result = generator.analyze_error_codes()

        assert 400 in result["error_codes"]
        assert 401 in result["error_codes"]
        assert 403 in result["error_codes"]
        assert 404 in result["error_codes"]
        assert 500 in result["error_codes"]
        assert 413 in result["error_codes"]

    def test_error_codes_by_category(self, sample_snapshot):
        """Test error codes are categorized correctly."""
        generator = AuthErrorConventionGenerator(sample_snapshot)
        result = generator.analyze_error_codes()

        # 401 and 403 are auth errors
        assert 401 in result["error_codes_by_category"]["auth_error"]
        assert 403 in result["error_codes_by_category"]["auth_error"]

        # 400 is validation error
        assert 400 in result["error_codes_by_category"]["validation_error"]

        # 404 is not found
        assert 404 in result["error_codes_by_category"]["not_found"]

        # 500 is server error
        assert 500 in result["error_codes_by_category"]["server_error"]

    def test_endpoints_by_error_code(self, sample_snapshot):
        """Test endpoints are mapped to error codes correctly."""
        generator = AuthErrorConventionGenerator(sample_snapshot)
        result = generator.analyze_error_codes()

        assert 401 in result["endpoints_by_error_code"]
        # 401 appears in login, logout, get_users, get_user
        assert len(result["endpoints_by_error_code"][401]) == 4

    def test_most_common_errors(self, sample_snapshot):
        """Test most common errors are identified correctly."""
        generator = AuthErrorConventionGenerator(sample_snapshot)
        result = generator.analyze_error_codes()

        # 500 appears in 5 endpoints (login, logout, get_users, get_user, upload_data)
        most_common = dict(result["most_common_errors"])
        assert 500 in most_common
        assert most_common[500] == 5

    def test_analyze_error_codes_empty_snapshot(self):
        """Test analyzing error codes with empty snapshot."""
        empty_snapshot = RepositorySnapshot(
            repository=RepositoryInfo(name="empty", root_path="/test"),
            modules=[],
            endpoints=[],
            commands={},
            stats=RepositoryStats(),
        )
        generator = AuthErrorConventionGenerator(empty_snapshot)
        result = generator.analyze_error_codes()

        assert len(result["error_codes"]) == 0


# =============================================================================
# TESTS FOR STATUS CODE DOCUMENTATION
# =============================================================================

class TestStatusCodeDocumentation:
    """Tests for status code documentation generation."""

    def test_document_status_codes_with_evidence(self, sample_snapshot):
        """Test status code documentation with actual error codes."""
        generator = AuthErrorConventionGenerator(sample_snapshot)
        result = generator.document_status_code_conventions()

        assert "## 状态码约定" in result
        assert "以下状态码约定基于实际端点返回的错误码整理" in result

    def test_document_status_codes_without_evidence(self):
        """Test status code documentation without error codes."""
        empty_snapshot = RepositorySnapshot(
            repository=RepositoryInfo(name="empty", root_path="/test"),
            modules=[],
            endpoints=[],
            commands={},
            stats=RepositoryStats(),
        )
        generator = AuthErrorConventionGenerator(empty_snapshot)
        result = generator.document_status_code_conventions()

        assert "## 状态码约定" in result
        assert "当前仓库端点未提供错误码信息" in result

    def test_status_code_categories_shown(self, sample_snapshot):
        """Test that all status code categories are shown."""
        generator = AuthErrorConventionGenerator(sample_snapshot)
        result = generator.document_status_code_conventions()

        # Should have category sections
        assert "认证授权错误 (401/403)" in result
        assert "验证错误 (400/422)" in result

    def test_format_status_code_table(self, sample_snapshot):
        """Test status code table formatting."""
        generator = AuthErrorConventionGenerator(sample_snapshot)
        table = generator._format_status_code_table([400, 401, 500])

        assert "| 状态码 | 名称 | 说明 |" in table
        assert "| 400 | Bad Request |" in table
        assert "| 401 | Unauthorized |" in table


# =============================================================================
# TESTS FOR AUTH CONVENTION DOCUMENTATION
# =============================================================================

class TestAuthConventionDocumentation:
    """Tests for auth convention documentation generation."""

    def test_document_auth_conventions_with_auth(self, sample_snapshot):
        """Test auth convention documentation with actual auth data."""
        generator = AuthErrorConventionGenerator(sample_snapshot)
        result = generator.document_auth_conventions()

        assert "## 认证授权约定" in result
        assert "5" in result  # authenticated endpoint count
        assert "1" in result  # unauthenticated endpoint count

    def test_document_auth_conventions_without_auth(self):
        """Test auth convention documentation without auth data."""
        empty_snapshot = RepositorySnapshot(
            repository=RepositoryInfo(name="empty", root_path="/test"),
            modules=[],
            endpoints=[],
            commands={},
            stats=RepositoryStats(),
        )
        generator = AuthErrorConventionGenerator(empty_snapshot)
        result = generator.document_auth_conventions()

        assert "## 认证授权约定" in result
        assert "当前仓库端点未标记认证信息" in result

    def test_auth_type_table(self, sample_snapshot):
        """Test auth type table formatting."""
        generator = AuthErrorConventionGenerator(sample_snapshot)
        table = generator._format_auth_type_table(["bearer", "api-key"])

        assert "| 认证类型 | 说明 |" in table
        assert "`bearer`" in table
        assert "`api-key`" in table

    def test_auth_modules_documented(self, sample_snapshot):
        """Test that auth modules are documented."""
        generator = AuthErrorConventionGenerator(sample_snapshot)
        result = generator.document_auth_conventions()

        assert "### 认证处理模块" in result
        assert "`auth`" in result

    def test_auth_files_cited(self, sample_snapshot):
        """Test that auth files are cited."""
        generator = AuthErrorConventionGenerator(sample_snapshot)
        result = generator.document_auth_conventions()

        assert "### 认证相关文件" in result
        assert "<cite>" in result


# =============================================================================
# TESTS FOR ERROR HANDLING DOCUMENTATION
# =============================================================================

class TestErrorHandlingDocumentation:
    """Tests for error handling convention documentation."""

    def test_document_error_handling_with_codes(self, sample_snapshot):
        """Test error handling documentation with actual error codes."""
        generator = AuthErrorConventionGenerator(sample_snapshot)
        result = generator.document_error_handling_conventions()

        assert "## 错误处理约定" in result
        assert "6" in result  # error code count

    def test_document_error_handling_without_codes(self):
        """Test error handling documentation without error codes."""
        empty_snapshot = RepositorySnapshot(
            repository=RepositoryInfo(name="empty", root_path="/test"),
            modules=[],
            endpoints=[],
            commands={},
            stats=RepositoryStats(),
        )
        generator = AuthErrorConventionGenerator(empty_snapshot)
        result = generator.document_error_handling_conventions()

        assert "## 错误处理约定" in result
        assert "当前仓库端点未提供错误码信息" in result

    def test_most_common_errors_documented(self, sample_snapshot):
        """Test that most common errors are documented."""
        generator = AuthErrorConventionGenerator(sample_snapshot)
        result = generator.document_error_handling_conventions()

        assert "### 常见错误码" in result
        assert "| 错误码 | 出现次数 |" in result

    def test_missing_evidence_behavior(self, sample_snapshot):
        """Test that missing evidence behavior is documented."""
        generator = AuthErrorConventionGenerator(sample_snapshot)
        result = generator.document_error_handling_conventions()

        assert "### 缺失证据处理" in result
        assert "来源于代码静态分析" in result


# =============================================================================
# TESTS FOR STATIC CONTENT GENERATION
# =============================================================================

class TestStaticContentGeneration:
    """Tests for static content generation without LLM."""

    def test_generate_auth_conventions_static(self, sample_snapshot):
        """Test static auth conventions generation."""
        generator = AuthErrorConventionGenerator(sample_snapshot)
        result = generator.generate_auth_conventions_static()

        assert "## 认证授权约定" in result
        assert len(result) > 100

    def test_generate_error_conventions_static(self, sample_snapshot):
        """Test static error conventions generation."""
        generator = AuthErrorConventionGenerator(sample_snapshot)
        result = generator.generate_error_conventions_static()

        assert "## 错误处理约定" in result
        assert len(result) > 100

    def test_generate_status_codes_static(self, sample_snapshot):
        """Test static status codes generation."""
        generator = AuthErrorConventionGenerator(sample_snapshot)
        result = generator.generate_status_codes_static()

        assert "## 状态码约定" in result
        assert len(result) > 100


# =============================================================================
# TESTS FOR PAGE COMPOSITION
# =============================================================================

class TestPageComposition:
    """Tests for page composition with LLM composer."""

    def test_compose_auth_page(self, sample_snapshot, auth_page_plan):
        """Test composing auth page."""
        generator = AuthErrorConventionGenerator(sample_snapshot)
        output = generator.compose_auth_page(auth_page_plan)

        assert output is not None
        assert output.page_id == "api-authentication"

    def test_compose_error_codes_page(self, sample_snapshot, error_codes_page_plan):
        """Test composing error codes page."""
        generator = AuthErrorConventionGenerator(sample_snapshot)
        output = generator.compose_error_codes_page(error_codes_page_plan)

        assert output is not None
        assert output.page_id == "api-error-codes"

    def test_build_composer_context(self, sample_snapshot):
        """Test composer context building."""
        generator = AuthErrorConventionGenerator(sample_snapshot)
        context = generator._build_composer_context()

        assert context.repository_name == "test-repo"
        assert context.primary_language == "python"
        assert context.framework == "fastapi"
        assert len(context.endpoints) == 6


# =============================================================================
# TESTS FOR FACTORY FUNCTION
# =============================================================================

class TestFactoryFunction:
    """Tests for create_auth_error_convention_generator factory."""

    def test_create_generator(self, sample_snapshot):
        """Test creating a generator."""
        generator = create_auth_error_convention_generator(sample_snapshot)
        assert generator is not None
        assert isinstance(generator, AuthErrorConventionGenerator)

    def test_create_with_workspace_root(self, sample_snapshot):
        """Test creating generator with workspace root."""
        generator = create_auth_error_convention_generator(
            sample_snapshot,
            workspace_root="/test/workspace",
        )
        assert generator.workspace_root is not None


# =============================================================================
# TESTS FOR CONVENIENCE FUNCTIONS
# =============================================================================

class TestConvenienceFunctions:
    """Tests for compose_auth_convention_article and compose_error_convention_article."""

    def test_compose_auth_convention_article(self, sample_snapshot, auth_page_plan):
        """Test compose_auth_convention_article convenience function."""
        output = compose_auth_convention_article(
            page_plan=auth_page_plan,
            snapshot=sample_snapshot,
        )

        assert output is not None
        assert output.page_id == "api-authentication"

    def test_compose_error_convention_article(
        self, sample_snapshot, error_codes_page_plan
    ):
        """Test compose_error_convention_article convenience function."""
        output = compose_error_convention_article(
            page_plan=error_codes_page_plan,
            snapshot=sample_snapshot,
        )

        assert output is not None
        assert output.page_id == "api-error-codes"


# =============================================================================
# TESTS FOR EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_all_auth_types(self, sample_snapshot):
        """Test handling of various auth types."""
        generator = AuthErrorConventionGenerator(sample_snapshot)
        auth_endpoints = generator.get_auth_endpoints()

        # Should handle bearer and api-key
        auth_types = set(ep.auth_type for ep in auth_endpoints)
        assert "bearer" in auth_types
        assert "api-key" in auth_types

    def test_all_error_code_ranges(self):
        """Test handling of various error code ranges."""
        snapshot = RepositorySnapshot(
            repository=RepositoryInfo(name="test", root_path="/test"),
            modules=[],
            endpoints=[
                Endpoint(
                    method="GET",
                    path="/test",
                    module="api",
                    handler="test",
                    file_path="api/test.py",
                    error_codes=[400, 404, 500],
                ),
            ],
            commands={},
            stats=RepositoryStats(endpoint_count=1),
        )
        generator = AuthErrorConventionGenerator(snapshot)
        result = generator.analyze_error_codes()

        assert 400 in result["error_codes"]
        assert 404 in result["error_codes"]
        assert 500 in result["error_codes"]

    def test_missing_evidence_behavior_auth(self):
        """Test that missing auth evidence is handled properly."""
        empty_snapshot = RepositorySnapshot(
            repository=RepositoryInfo(name="empty", root_path="/test"),
            modules=[],
            endpoints=[],
            commands={},
            stats=RepositoryStats(),
        )
        generator = AuthErrorConventionGenerator(empty_snapshot)
        result = generator.document_auth_conventions()

        # Should document that no auth info is available
        assert "未标记认证信息" in result or "未提供" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])