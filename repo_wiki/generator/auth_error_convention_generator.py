"""Auth and error convention generator for API reference pages.

This generator creates authentication, authorization, error code, and status code
topic pages based on enriched API metadata from repository scanning.

Phase 25 - Task 25.4: Auth and error convention generator

Key features:
- Documents auth patterns (bearer token, API key, OAuth)
- Covers error handling conventions from actual endpoint error_codes
- Documents status code conventions
- Cites configuration, middleware, controller files
- Documents missing-evidence behavior (no invented conventions)

Integration with existing pipeline:
- Uses ServiceFamilyAPIComposer for endpoint data
- Composes with LLMPageComposer for LLM-based generation
- Reuses ComposerContext and ComposerInput builders
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from repo_wiki.core.contracts import Endpoint, RepositorySnapshot
from repo_wiki.generator.composer import (
    ComposerContext,
    ComposerInput,
    ComposerOutput,
    build_composer_input,
    create_composer,
)
from repo_wiki.llm.providers import MockLLMProvider
from repo_wiki.planner.schema import WikiPagePlan

# =============================================================================
# AUTH AND ERROR CONVENTION GENERATOR
# =============================================================================


class AuthErrorConventionGenerator:
    """Generator for auth and error convention API pages.

    This generator creates API reference pages that document:
    - Authentication patterns (bearer token, API key, OAuth)
    - Authorization and permissions
    - Error code conventions
    - Status code conventions
    - Common failure modes

    It analyzes enriched endpoint metadata to extract:
    - auth_type and auth_required from each endpoint
    - error_codes from each endpoint
    - Handler file paths for citations

    Key principle: Document existing behavior, don't invent conventions.
    If evidence is missing, the page notes this rather than guessing.
    """

    # Common auth types seen in enriched endpoints
    AUTH_TYPE_PATTERNS = {
        "bearer": "Bearer token (JWT) authentication",
        "api-key": "API key authentication",
        "oauth": "OAuth 2.0 flow",
        "none": "No authentication required",
        "unknown": "Authentication type not specified",
    }

    # HTTP status code categories
    STATUS_CODE_CATEGORIES = {
        400: ("Bad Request", "Client error - malformed request syntax"),
        401: ("Unauthorized", "Authentication required or failed"),
        403: ("Forbidden", "Authenticated but lacks permission"),
        404: ("Not Found", "Resource does not exist"),
        409: ("Conflict", "Resource state conflict"),
        422: ("Unprocessable", "Request format valid but semantic content is invalid"),
        429: ("Too Many Requests", "Rate limit exceeded"),
        500: ("Internal Server Error", "Server-side error"),
        502: ("Bad Gateway", "Upstream server error"),
        503: ("Service Unavailable", "Service temporarily unavailable"),
    }

    def __init__(
        self,
        snapshot: RepositorySnapshot,
        llm_provider: MockLLMProvider | None = None,
        workspace_root: str | Path | None = None,
    ) -> None:
        """Initialize the auth/error convention generator.

        Args:
            snapshot: Repository snapshot with enriched endpoints
            llm_provider: Optional LLM provider (uses mock if not provided)
            workspace_root: Optional workspace root for path resolution
        """
        self.snapshot = snapshot
        self.workspace_root = Path(workspace_root) if workspace_root else None
        self._llm_composer = create_composer(
            provider=llm_provider,
            workspace_root=workspace_root,
        )

    # =========================================================================
    # AUTH PATTERN ANALYSIS
    # =========================================================================

    def analyze_auth_patterns(self) -> dict[str, Any]:
        """Analyze authentication patterns across all endpoints.

        Returns:
            Dict with auth pattern analysis:
            - auth_types: unique auth types found
            - authenticated_endpoints: count
            - unauthenticated_endpoints: count
            - auth_modules: modules handling auth
            - auth_files: file paths for auth handlers
        """
        auth_endpoints: list[Endpoint] = []
        unauth_endpoints: list[Endpoint] = []
        auth_types: set[str] = set()
        auth_modules: set[str] = set()
        auth_files: set[str] = set()

        for ep in self.snapshot.endpoints:
            if ep.auth_required or ep.auth_type not in ("none", "unknown"):
                auth_endpoints.append(ep)
                auth_types.add(ep.auth_type)
                auth_modules.add(ep.module)
                auth_files.add(ep.file_path)
            else:
                unauth_endpoints.append(ep)

        return {
            "auth_types": sorted(auth_types),
            "authenticated_endpoint_count": len(auth_endpoints),
            "unauthenticated_endpoint_count": len(unauth_endpoints),
            "auth_modules": sorted(auth_modules),
            "auth_files": sorted(auth_files),
            "total_endpoints": len(self.snapshot.endpoints),
        }

    def get_auth_endpoints(self) -> list[Endpoint]:
        """Get all endpoints that require authentication."""
        return [
            ep
            for ep in self.snapshot.endpoints
            if ep.auth_required or ep.auth_type in ("bearer", "oauth", "api-key")
        ]

    def get_unauth_endpoints(self) -> list[Endpoint]:
        """Get all endpoints that don't require authentication."""
        return [
            ep
            for ep in self.snapshot.endpoints
            if not ep.auth_required and ep.auth_type in ("none", "unknown")
        ]

    # =========================================================================
    # ERROR CODE ANALYSIS
    # =========================================================================

    def analyze_error_codes(self) -> dict[str, Any]:
        """Analyze error codes across all endpoints.

        Returns:
            Dict with error code analysis:
            - error_codes: unique error codes found
            - error_codes_by_category: grouped by category
            - endpoints_by_error_code: which endpoints return each code
            - most_common_errors: codes appearing in 3+ endpoints
        """
        error_codes: set[int] = set()
        endpoints_by_code: dict[int, list[Endpoint]] = {}

        for ep in self.snapshot.endpoints:
            for code in ep.error_codes:
                error_codes.add(code)
                if code not in endpoints_by_code:
                    endpoints_by_code[code] = []
                endpoints_by_code[code].append(ep)

        # Categorize error codes
        by_category: dict[str, list[int]] = {
            "client_error": [],
            "server_error": [],
            "auth_error": [],
            "validation_error": [],
            "not_found": [],
        }

        for code in error_codes:
            if code == 401 or code == 403:
                by_category["auth_error"].append(code)
            elif code == 400 or code == 422:
                by_category["validation_error"].append(code)
            elif code == 404:
                by_category["not_found"].append(code)
            elif 400 <= code < 500:
                by_category["client_error"].append(code)
            elif code >= 500:
                by_category["server_error"].append(code)

        # Find most common errors (appearing in 3+ endpoints)
        most_common = [
            (code, len(endpoints))
            for code, endpoints in endpoints_by_code.items()
            if len(endpoints) >= 3
        ]
        most_common.sort(key=lambda x: (-x[1], x[0]))

        return {
            "error_codes": sorted(error_codes),
            "endpoints_by_error_code": {
                code: [f"{ep.method} {ep.path}" for ep in eps]
                for code, eps in endpoints_by_code.items()
            },
            "error_codes_by_category": by_category,
            "most_common_errors": most_common[:10],
        }

    # =========================================================================
    # STATUS CODE DOCUMENTATION
    # =========================================================================

    def document_status_code_conventions(self) -> str:
        """Document status code conventions based on actual endpoint error_codes.

        Returns:
            Markdown string documenting status code conventions
        """
        analysis = self.analyze_error_codes()
        lines = ["## 状态码约定", ""]

        if not analysis["error_codes"]:
            lines.append(
                "**注意**: 当前仓库端点未提供错误码信息，此部分基于约定俗成的HTTP状态码规范。"
            )
            lines.append("")
            lines.append("### 通用状态码")
            lines.append("")
            lines.append(self._format_generic_status_codes())
            return "\n".join(lines)

        lines.append("以下状态码约定基于实际端点返回的错误码整理：")
        lines.append("")

        # Document by category
        for category, codes in analysis["error_codes_by_category"].items():
            if codes:
                lines.append(f"### {self._category_label(category)}")
                lines.append("")
                lines.append(self._format_status_code_table(codes))
                lines.append("")

        return "\n".join(lines)

    def _category_label(self, category: str) -> str:
        """Get human-readable category label."""
        labels = {
            "client_error": "客户端错误 (4xx)",
            "server_error": "服务端错误 (5xx)",
            "auth_error": "认证授权错误 (401/403)",
            "validation_error": "验证错误 (400/422)",
            "not_found": "未找到资源 (404)",
        }
        return labels.get(category, category.replace("_", " ").title())

    def _format_status_code_table(self, codes: list[int]) -> str:
        """Format status codes as a table."""
        lines = ["| 状态码 | 名称 | 说明 |", "|--------|------|------|"]
        for code in sorted(codes):
            if code in self.STATUS_CODE_CATEGORIES:
                name, desc = self.STATUS_CODE_CATEGORIES[code]
                lines.append(f"| {code} | {name} | {desc} |")
            else:
                lines.append(f"| {code} | - | - |")
        return "\n".join(lines)

    def _format_generic_status_codes(self) -> str:
        """Format generic HTTP status code table."""
        lines = ["| 状态码 | 名称 | 说明 |", "|--------|------|------|"]
        for code, (name, desc) in sorted(self.STATUS_CODE_CATEGORIES.items()):
            lines.append(f"| {code} | {name} | {desc} |")
        return "\n".join(lines)

    # =========================================================================
    # AUTH CONVENTION DOCUMENTATION
    # =========================================================================

    def document_auth_conventions(self) -> str:
        """Document authentication conventions based on actual endpoint metadata.

        Returns:
            Markdown string documenting auth conventions
        """
        analysis = self.analyze_auth_patterns()
        lines = ["## 认证授权约定", ""]

        if analysis["authenticated_endpoint_count"] == 0:
            lines.append("**注意**: 当前仓库端点未标记认证信息，文档基于无认证场景。")
            lines.append("")
            lines.append(self._format_no_auth_content())
            return "\n".join(lines)

        lines.append(
            f"当前仓库共有 **{analysis['authenticated_endpoint_count']}** 个需认证端点，"
            f"**{analysis['unauthenticated_endpoint_count']}** 个公开端点。"
        )
        lines.append("")

        # Document auth types
        if analysis["auth_types"]:
            lines.append("### 认证方式")
            lines.append("")
            lines.append(self._format_auth_type_table(analysis["auth_types"]))
            lines.append("")

        # Document auth modules if available
        if analysis["auth_modules"]:
            lines.append("### 认证处理模块")
            lines.append("")
            lines.append("以下模块涉及认证处理：")
            lines.append("")
            for module in analysis["auth_modules"]:
                lines.append(f"- `{module}`")
            lines.append("")

        # Document auth files with citations
        if analysis["auth_files"]:
            lines.append("### 认证相关文件")
            lines.append("")
            for fpath in analysis["auth_files"]:
                lines.append(f"- <cite>{fpath}</cite>")
            lines.append("")

        return "\n".join(lines)

    def _format_auth_type_table(self, auth_types: list[str]) -> str:
        """Format auth types as a table."""
        lines = ["| 认证类型 | 说明 |", "|----------|------|"]
        for auth_type in auth_types:
            desc = self.AUTH_TYPE_PATTERNS.get(auth_type, "Unknown auth type")
            lines.append(f"| `{auth_type}` | {desc} |")
        return "\n".join(lines)

    def _format_no_auth_content(self) -> str:
        """Format content for no auth scenario."""
        return """### 公开端点

当前仓库端点均不需要认证即可访问。

| 端点 | 说明 |
|------|------|
"""

    # =========================================================================
    # ERROR HANDLING DOCUMENTATION
    # =========================================================================

    def document_error_handling_conventions(self) -> str:
        """Document error handling conventions based on actual error codes.

        Returns:
            Markdown string documenting error handling
        """
        analysis = self.analyze_error_codes()
        lines = ["## 错误处理约定", ""]

        if not analysis["error_codes"]:
            lines.append("**注意**: 当前仓库端点未提供错误码信息。")
            lines.append("")
            lines.append("错误处理遵循标准HTTP语义，具体错误码含义请参考上方状态码约定。")
            return "\n".join(lines)

        lines.append(f"当前仓库端点共涉及 **{len(analysis['error_codes'])}** 种错误码。")
        lines.append("")

        # Document most common errors
        if analysis["most_common_errors"]:
            lines.append("### 常见错误码")
            lines.append("")
            lines.append("以下错误码在多个端点中出现：")
            lines.append("")
            lines.append("| 错误码 | 出现次数 | 影响端点 |")
            lines.append("|--------|----------|----------|")
            for code, count in analysis["most_common_errors"]:
                endpoints = analysis["endpoints_by_error_code"][code]
                endpoint_str = ", ".join(endpoints[:3])
                if len(endpoints) > 3:
                    endpoint_str += f" (+{len(endpoints) - 3} more)"
                lines.append(f"| {code} | {count} | {endpoint_str} |")
            lines.append("")

        # Document missing-evidence behavior
        lines.append("### 缺失证据处理")
        lines.append("")
        lines.append("**重要**: 本文档档错误码信息来源于代码静态分析。")
        lines.append("如发现错误码缺失或不准确，请以实际运行时响应为准。")
        lines.append("")

        return "\n".join(lines)

    # =========================================================================
    # PAGE COMPOSITION
    # =========================================================================

    def compose_auth_page(self, page_plan: WikiPagePlan) -> ComposerOutput:
        """Compose authentication convention page.

        Args:
            page_plan: WikiPagePlan for this page

        Returns:
            ComposerOutput with generated content
        """
        # Build context
        context = self._build_composer_context()

        # Build composer input
        composer_input = build_composer_input(
            page_plan=page_plan,
            evidence_binding=None,
            context=context,
        )

        # Delegate to LLM composer (sync wrapper)
        return self._compose_with_llm(composer_input)

    def compose_error_codes_page(self, page_plan: WikiPagePlan) -> ComposerOutput:
        """Compose error codes reference page.

        Args:
            page_plan: WikiPagePlan for this page

        Returns:
            ComposerOutput with generated content
        """
        # Build context
        context = self._build_composer_context()

        # Build composer input
        composer_input = build_composer_input(
            page_plan=page_plan,
            evidence_binding=None,
            context=context,
        )

        # Delegate to LLM composer (sync wrapper)
        return self._compose_with_llm(composer_input)

    def _compose_with_llm(self, composer_input: ComposerInput) -> ComposerOutput:
        """Generate content using LLM composer.

        This is a synchronous wrapper that uses the underlying async method.
        """
        import asyncio

        return asyncio.run(self._llm_composer.compose_page(composer_input))

    def _build_composer_context(self) -> ComposerContext:
        """Build ComposerContext for auth/error pages.

        Returns:
            ComposerContext with repository and endpoint info
        """
        auth_analysis = self.analyze_auth_patterns()
        error_analysis = self.analyze_error_codes()

        # Collect all endpoints info
        all_endpoints = []
        for ep in self.snapshot.endpoints:
            all_endpoints.append(
                {
                    "path": ep.path,
                    "method": ep.method,
                    "auth_required": ep.auth_required,
                    "auth_type": ep.auth_type,
                    "error_codes": ep.error_codes,
                }
            )

        return ComposerContext(
            repository_name=self.snapshot.repository.name,
            primary_language=self.snapshot.repository.language,
            framework=self.snapshot.repository.framework,
            repository_root=str(self.workspace_root) if self.workspace_root else ".",
            endpoints=all_endpoints,
            modules=[{"name": m.name, "path": m.path} for m in self.snapshot.modules],
        )

    # =========================================================================
    # STATIC CONTENT GENERATION (no LLM)
    # =========================================================================

    def generate_auth_conventions_static(self) -> str:
        """Generate auth conventions content without LLM.

        Returns:
            Markdown string with auth conventions
        """
        return self.document_auth_conventions()

    def generate_error_conventions_static(self) -> str:
        """Generate error conventions content without LLM.

        Returns:
            Markdown string with error conventions
        """
        return self.document_error_handling_conventions()

    def generate_status_codes_static(self) -> str:
        """Generate status codes content without LLM.

        Returns:
            Markdown string with status code conventions
        """
        return self.document_status_code_conventions()


# =============================================================================
# COMPOSER FACTORY
# =============================================================================


def create_auth_error_convention_generator(
    snapshot: RepositorySnapshot,
    llm_provider: MockLLMProvider | None = None,
    workspace_root: str | Path | None = None,
) -> AuthErrorConventionGenerator:
    """Create an auth/error convention generator.

    Args:
        snapshot: Repository snapshot with enriched endpoints
        llm_provider: Optional LLM provider
        workspace_root: Optional workspace root

    Returns:
        AuthErrorConventionGenerator instance
    """
    return AuthErrorConventionGenerator(
        snapshot=snapshot,
        llm_provider=llm_provider,
        workspace_root=workspace_root,
    )


# =============================================================================
# STANDALONE COMPOSITION HELPERS
# =============================================================================


def compose_auth_convention_article(
    page_plan: WikiPagePlan,
    snapshot: RepositorySnapshot,
    llm_provider: MockLLMProvider | None = None,
    workspace_root: str | Path | None = None,
) -> ComposerOutput:
    """Convenience function to compose auth convention article.

    Args:
        page_plan: WikiPagePlan for the auth page
        snapshot: Repository snapshot with endpoints
        llm_provider: Optional LLM provider
        workspace_root: Optional workspace root

    Returns:
        ComposerOutput with generated content
    """
    generator = create_auth_error_convention_generator(
        snapshot=snapshot,
        llm_provider=llm_provider,
        workspace_root=workspace_root,
    )
    return generator.compose_auth_page(page_plan)


def compose_error_convention_article(
    page_plan: WikiPagePlan,
    snapshot: RepositorySnapshot,
    llm_provider: MockLLMProvider | None = None,
    workspace_root: str | Path | None = None,
) -> ComposerOutput:
    """Convenience function to compose error convention article.

    Args:
        page_plan: WikiPagePlan for the error page
        snapshot: Repository snapshot with endpoints
        llm_provider: Optional LLM provider
        workspace_root: Optional workspace root

    Returns:
        ComposerOutput with generated content
    """
    generator = create_auth_error_convention_generator(
        snapshot=snapshot,
        llm_provider=llm_provider,
        workspace_root=workspace_root,
    )
    return generator.compose_error_codes_page(page_plan)
