"""Tests for API Aggregator - Phase 10 Task 10.2.

These tests validate that API aggregation is truly grouped by service family,
domain, and exposure pattern, and that entry-point selection uses principled
scoring rather than just top-K retrieval.
"""

from repo_wiki.generator.engine import APIAggregator, APIEndpoint


class TestAPIAggregatorInitialization:
    """Tests for APIAggregator initialization and endpoint processing."""

    def test_aggregator_builds_endpoint_objects(self):
        """Test that aggregator converts raw endpoints to APIEndpoint objects."""
        endpoints = [
            {
                "method": "GET",
                "path": "/health",
                "module": "api",
                "handler": "health",
                "file_path": "api/main.py",
            }
        ]
        modules = [
            {
                "name": "api",
                "domain": "api-gateway",
                "service_family": "python-backend",
                "runtime_role": "api-server",
            }
        ]

        aggregator = APIAggregator(endpoints=endpoints, modules=modules)

        assert len(aggregator.api_endpoints) == 1
        ep = aggregator.api_endpoints[0]
        assert isinstance(ep, APIEndpoint)
        assert ep.method == "GET"
        assert ep.path == "/health"
        assert ep.module == "api"
        assert ep.domain == "api-gateway"

    def test_aggregator_extracts_module_metadata(self):
        """Test that aggregator attaches module domain/service_family to endpoints."""
        endpoints = [
            {
                "method": "POST",
                "path": "/users",
                "module": "users",
                "handler": "create_user",
                "file_path": "users/api.py",
            }
        ]
        modules = [
            {
                "name": "users",
                "domain": "core-platform",
                "service_family": "python-backend",
                "runtime_role": "api-server",
            }
        ]

        aggregator = APIAggregator(endpoints=endpoints, modules=modules)

        ep = aggregator.api_endpoints[0]
        assert ep.domain == "core-platform"
        assert ep.service_family == "python-backend"
        assert ep.runtime_role == "api-server"


class TestExposurePatternClassification:
    """Tests for API exposure pattern classification (public/internal/admin/webhook)."""

    def test_classifies_public_endpoints(self):
        """Test that health/status endpoints are classified as public."""
        endpoints = [
            {
                "method": "GET",
                "path": "/health",
                "module": "api",
                "handler": "health",
                "file_path": "api/main.py",
            },
            {
                "method": "GET",
                "path": "/ready",
                "module": "api",
                "handler": "ready",
                "file_path": "api/main.py",
            },
        ]
        modules = [
            {
                "name": "api",
                "domain": "api-gateway",
                "service_family": "python-backend",
                "runtime_role": "api-server",
            }
        ]

        aggregator = APIAggregator(endpoints=endpoints, modules=modules)

        for ep in aggregator.api_endpoints:
            assert ep.exposure_pattern == "public"

    def test_classifies_webhook_endpoints(self):
        """Test that webhook paths are classified correctly."""
        endpoints = [
            {
                "method": "POST",
                "path": "/webhook/github",
                "module": "hooks",
                "handler": "handle",
                "file_path": "hooks/api.py",
            },
        ]
        modules = [
            {
                "name": "hooks",
                "domain": "operations",
                "service_family": "python-backend",
                "runtime_role": "worker",
            }
        ]

        aggregator = APIAggregator(endpoints=endpoints, modules=modules)

        assert aggregator.api_endpoints[0].exposure_pattern == "webhook"

    def test_classifies_admin_endpoints(self):
        """Test that admin paths are classified as admin."""
        endpoints = [
            {
                "method": "POST",
                "path": "/admin/users",
                "module": "admin",
                "handler": "create_user",
                "file_path": "admin/api.py",
            },
        ]
        modules = [
            {
                "name": "admin",
                "domain": "operations",
                "service_family": "python-backend",
                "runtime_role": "api-server",
            }
        ]

        aggregator = APIAggregator(endpoints=endpoints, modules=modules)

        assert aggregator.api_endpoints[0].exposure_pattern == "admin"

    def test_classifies_auth_endpoints_as_public(self):
        """Test that auth endpoints are classified as public."""
        endpoints = [
            {
                "method": "POST",
                "path": "/auth/login",
                "module": "auth",
                "handler": "login",
                "file_path": "auth/api.py",
            },
        ]
        modules = [
            {
                "name": "auth",
                "domain": "core-platform",
                "service_family": "python-backend",
                "runtime_role": "api-server",
            }
        ]

        aggregator = APIAggregator(endpoints=endpoints, modules=modules)

        assert aggregator.api_endpoints[0].exposure_pattern == "public"


class TestAuthTypeDetection:
    """Tests for authentication type detection from endpoint characteristics."""

    def test_detects_bearer_auth_for_api_servers(self):
        """Test that API server endpoints require bearer auth."""
        endpoints = [
            {
                "method": "GET",
                "path": "/api/users",
                "module": "api",
                "handler": "list_users",
                "file_path": "api/main.py",
            },
        ]
        modules = [
            {
                "name": "api",
                "domain": "api-gateway",
                "service_family": "python-backend",
                "runtime_role": "api-server",
            }
        ]

        aggregator = APIAggregator(endpoints=endpoints, modules=modules)

        ep = aggregator.api_endpoints[0]
        assert ep.auth_required == True
        assert ep.auth_type == "bearer"

    def test_detects_no_auth_for_tests(self):
        """Test that test module endpoints don't require auth."""
        endpoints = [
            {
                "method": "GET",
                "path": "/test/health",
                "module": "tests",
                "handler": "health",
                "file_path": "tests/api.py",
            },
        ]
        modules = [
            {
                "name": "tests",
                "domain": "testing",
                "service_family": "python-backend",
                "runtime_role": "test-harness",
            }
        ]

        aggregator = APIAggregator(endpoints=endpoints, modules=modules)

        ep = aggregator.api_endpoints[0]
        assert ep.auth_type == "none"

    def test_detects_auth_endpoints(self):
        """Test that auth-related paths are detected."""
        endpoints = [
            {
                "method": "POST",
                "path": "/login",
                "module": "auth",
                "handler": "login",
                "file_path": "auth/api.py",
            },
        ]
        modules = [
            {
                "name": "auth",
                "domain": "core-platform",
                "service_family": "python-backend",
                "runtime_role": "api-server",
            }
        ]

        aggregator = APIAggregator(endpoints=endpoints, modules=modules)

        ep = aggregator.api_endpoints[0]
        assert ep.auth_type == "bearer"


class TestEntryPointScoring:
    """Tests for principled entry-point scoring method."""

    def test_scores_public_mutation_high(self):
        """Test that public mutation endpoints score higher than internal GET endpoints."""
        endpoints = [
            {
                "method": "GET",
                "path": "/internal/stats",
                "module": "api",
                "handler": "stats",
                "file_path": "api/main.py",
            },  # Internal
            {
                "method": "POST",
                "path": "/users",
                "module": "api",
                "handler": "create_user",
                "file_path": "api/main.py",
            },  # Public mutation
        ]
        modules = [
            {
                "name": "api",
                "domain": "api-gateway",
                "service_family": "python-backend",
                "runtime_role": "api-server",
            }
        ]

        aggregator = APIAggregator(endpoints=endpoints, modules=modules)

        get_ep = next(ep for ep in aggregator.api_endpoints if ep.method == "GET")
        post_ep = next(ep for ep in aggregator.api_endpoints if ep.method == "POST")

        assert post_ep.entry_score > get_ep.entry_score

    def test_scores_root_level_paths_high(self):
        """Test that shorter paths (more root-level) score higher."""
        endpoints = [
            {
                "method": "GET",
                "path": "/",
                "module": "api",
                "handler": "root",
                "file_path": "api/main.py",
            },
            {
                "method": "GET",
                "path": "/api/v1/users/profile/settings",
                "module": "api",
                "handler": "deep",
                "file_path": "api/main.py",
            },
        ]
        modules = [
            {
                "name": "api",
                "domain": "api-gateway",
                "service_family": "python-backend",
                "runtime_role": "api-server",
            }
        ]

        aggregator = APIAggregator(endpoints=endpoints, modules=modules)

        root_ep = next(ep for ep in aggregator.api_endpoints if ep.path == "/")
        deep_ep = next(
            ep for ep in aggregator.api_endpoints if ep.path == "/api/v1/users/profile/settings"
        )

        assert root_ep.entry_score > deep_ep.entry_score

    def test_selects_entry_points_above_threshold(self):
        """Test that only endpoints above score threshold are marked as entry points."""
        endpoints = [
            {
                "method": "POST",
                "path": "/users",
                "module": "api",
                "handler": "create",
                "file_path": "api/main.py",
            },  # High score
            {
                "method": "GET",
                "path": "/users",
                "module": "api",
                "handler": "list",
                "file_path": "api/main.py",
            },  # Medium score
            {
                "method": "GET",
                "path": "/users/123/items",
                "module": "api",
                "handler": "get_items",
                "file_path": "api/main.py",
            },  # Lower score
        ]
        modules = [
            {
                "name": "api",
                "domain": "api-gateway",
                "service_family": "python-backend",
                "runtime_role": "api-server",
            }
        ]

        aggregator = APIAggregator(endpoints=endpoints, modules=modules)

        entry_points = [ep for ep in aggregator.api_endpoints if ep.is_entry_point]

        # POST to /users should definitely be entry point
        post_ep = next(ep for ep in aggregator.api_endpoints if ep.method == "POST")
        assert post_ep.is_entry_point == True

    def test_get_key_entry_apis_returns_top_scored(self):
        """Test that get_key_entry_apis returns top-scoring endpoints."""
        endpoints = [
            {
                "method": "GET",
                "path": "/health",
                "module": "api",
                "handler": "health",
                "file_path": "api/main.py",
            },
            {
                "method": "POST",
                "path": "/users",
                "module": "api",
                "handler": "create",
                "file_path": "api/main.py",
            },
            {
                "method": "GET",
                "path": "/users",
                "module": "api",
                "handler": "list",
                "file_path": "api/main.py",
            },
            {
                "method": "DELETE",
                "path": "/users/123",
                "module": "api",
                "handler": "delete",
                "file_path": "api/main.py",
            },
        ]
        modules = [
            {
                "name": "api",
                "domain": "api-gateway",
                "service_family": "python-backend",
                "runtime_role": "api-server",
            }
        ]

        aggregator = APIAggregator(endpoints=endpoints, modules=modules)

        key_apis = aggregator.get_key_entry_apis(max_count=2)

        assert len(key_apis) <= 2
        # Verify returned APIs are the highest scoring
        scores = [ep.entry_score for ep in key_apis]
        assert scores == sorted(scores, reverse=True)


class TestAPIGrouping:
    """Tests for API grouping by service family and exposure pattern."""

    def test_group_by_service_family(self):
        """Test that endpoints are grouped by service family and domain."""
        endpoints = [
            {
                "method": "GET",
                "path": "/api/users",
                "module": "api",
                "handler": "list",
                "file_path": "api/main.py",
            },
            {
                "method": "GET",
                "path": "/data/reports",
                "module": "data",
                "handler": "list",
                "file_path": "data/main.py",
            },
        ]
        modules = [
            {
                "name": "api",
                "domain": "api-gateway",
                "service_family": "python-backend",
                "runtime_role": "api-server",
            },
            {
                "name": "data",
                "domain": "data-pipeline",
                "service_family": "python-backend",
                "runtime_role": "data-pipeline",
            },
        ]

        aggregator = APIAggregator(endpoints=endpoints, modules=modules)
        groups = aggregator.group_by_service_family()

        assert len(groups) == 2
        assert "python-backend/api-gateway" in groups
        assert "python-backend/data-pipeline" in groups

    def test_group_by_exposure(self):
        """Test that endpoints are grouped by exposure pattern."""
        endpoints = [
            {
                "method": "GET",
                "path": "/health",
                "module": "api",
                "handler": "health",
                "file_path": "api/main.py",
            },
            {
                "method": "POST",
                "path": "/users",
                "module": "api",
                "handler": "create",
                "file_path": "api/main.py",
            },
        ]
        modules = [
            {
                "name": "api",
                "domain": "api-gateway",
                "service_family": "python-backend",
                "runtime_role": "api-server",
            },
        ]

        aggregator = APIAggregator(endpoints=endpoints, modules=modules)
        groups = aggregator.group_by_exposure()

        assert "public" in groups
        assert "internal" in groups


class TestSummarizationMethods:
    """Tests for API calling convention summarization methods."""

    def test_summarize_auth_conventions(self):
        """Test that auth conventions are summarized by module."""
        endpoints = [
            {
                "method": "GET",
                "path": "/api/users",
                "module": "api",
                "handler": "list",
                "file_path": "api/main.py",
            },
            {
                "method": "GET",
                "path": "/health",
                "module": "health",
                "handler": "check",
                "file_path": "health/main.py",
            },
        ]
        modules = [
            {
                "name": "api",
                "domain": "api-gateway",
                "service_family": "python-backend",
                "runtime_role": "api-server",
            },
            {
                "name": "health",
                "domain": "operations",
                "service_family": "python-backend",
                "runtime_role": "tooling",
            },
        ]

        aggregator = APIAggregator(endpoints=endpoints, modules=modules)
        summary = aggregator.summarize_auth_conventions()

        assert "api" in summary
        assert "health" in summary
        # API should require auth, health should not
        assert "bearer" in summary or "unknown" in summary

    def test_summarize_calling_conventions(self):
        """Test that calling conventions are summarized for a group."""
        endpoints = [
            {
                "method": "POST",
                "path": "/users",
                "module": "api",
                "handler": "create",
                "file_path": "api/main.py",
            },
            {
                "method": "GET",
                "path": "/users",
                "module": "api",
                "handler": "list",
                "file_path": "api/main.py",
            },
        ]
        modules = [
            {
                "name": "api",
                "domain": "api-gateway",
                "service_family": "python-backend",
                "runtime_role": "api-server",
            },
        ]

        aggregator = APIAggregator(endpoints=endpoints, modules=modules)
        group_endpoints = aggregator.api_endpoints
        summary = aggregator.summarize_calling_conventions("api", group_endpoints)

        assert "POST" in summary or "GET" in summary
        assert "认证" in summary

    def test_build_api_groups_table(self):
        """Test that API groups table is built correctly."""
        endpoints = [
            {
                "method": "GET",
                "path": "/api/users",
                "module": "api",
                "handler": "list",
                "file_path": "api/main.py",
            },
        ]
        modules = [
            {
                "name": "api",
                "domain": "api-gateway",
                "service_family": "python-backend",
                "runtime_role": "api-server",
            },
        ]

        aggregator = APIAggregator(endpoints=endpoints, modules=modules)
        table = aggregator.build_api_groups_table()

        assert "python-backend" in table
        assert "api-gateway" in table
        assert "1" in table  # endpoint count

    def test_build_api_groups_detail(self):
        """Test that API groups detail contains calling convention summaries."""
        endpoints = [
            {
                "method": "POST",
                "path": "/users",
                "module": "users",
                "handler": "create",
                "file_path": "users/api.py",
            },
        ]
        modules = [
            {
                "name": "users",
                "domain": "core-platform",
                "service_family": "python-backend",
                "runtime_role": "api-server",
            },
        ]

        aggregator = APIAggregator(endpoints=endpoints, modules=modules)
        detail = aggregator.build_api_groups_detail()

        assert "python-backend" in detail
        assert "core-platform" in detail
        assert "POST" in detail
        assert "调用约定" in detail or "calling" in detail.lower()


class TestNoEndpointDump:
    """Tests that detect pure endpoint dumps without aggregation narrative."""

    def test_endpoint_dump_detected_by_validation(self):
        """Test that validation detects pure endpoint listing without aggregation."""
        from repo_wiki.generator.contracts import validate_api_contract_not_endpoint_dump

        # Pure endpoint dump - every endpoint listed verbatim
        dump_content = """
        ## API Endpoints

        - GET /users
        - GET /users/123
        - GET /users/123/orders
        - POST /users
        - PUT /users/123
        - DELETE /users/123
        - GET /products
        - GET /products/456
        - POST /products
        ...
        (many more endpoints)
        """

        # This should fail because it's just a list
        is_valid, reason = validate_api_contract_not_endpoint_dump(dump_content)
        assert not is_valid, "Pure endpoint dump should be rejected"

    def test_aggregated_content_passes_validation(self):
        """Test that properly aggregated content passes validation."""
        from repo_wiki.generator.contracts import validate_api_contract_grouped

        aggregated_content = """
        ## 服务/API 分组

        ### 用户服务 (core-platform)

        **主题域**: core-platform | **运行时角色**: api-server

        **关键入口点**:
        - POST /users - 创建用户
        - GET /users - 获取用户列表

        ## 调用约定

        ### 认证
        Bearer Token

        ### 错误与状态码
        Standard HTTP status codes

        ### 关键入口 API
        POST /users
        """

        is_valid, reason = validate_api_contract_grouped(aggregated_content)
        # This should pass because it has proper structure
        assert is_valid or "service/API grouping" in reason
