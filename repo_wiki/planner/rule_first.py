"""Rule-first page planner.

Generates a stable Qoder-like page plan without calling an LLM.
Uses repository identity, modules, APIs, data models, and runtime roles.

Output: deterministic page IDs, paths, parent links, and order.
"""

from __future__ import annotations

from repo_wiki.core.contracts import Module, RepositorySnapshot
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

# Category ordering for navigation
_CATEGORY_ORDER = {
    WikiTaxonomyCategory.PROJECT_OVERVIEW: 0,
    WikiTaxonomyCategory.ARCHITECTURE_DESIGN: 1,
    WikiTaxonomyCategory.CORE_SERVICES: 2,
    WikiTaxonomyCategory.PYTHON_SERVICES: 3,
    WikiTaxonomyCategory.FRONTEND_APPLICATIONS: 4,
    WikiTaxonomyCategory.DATA_MODELS: 5,
    WikiTaxonomyCategory.API_REFERENCE: 6,
    WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS: 7,
    WikiTaxonomyCategory.DEVELOPMENT_GUIDE: 8,
    WikiTaxonomyCategory.SECURITY_COMPLIANCE: 9,
    WikiTaxonomyCategory.TROUBLESHOOTING: 10,
}


class RuleFirstPlanner:
    """Deterministic rule-first page planner.

    Generates a complete wiki page plan based on repository structure
    without using any LLM calls. Page IDs and paths are stable and
    reproducible.
    """

    def __init__(
        self,
        identity: RepositoryIdentity,
        snapshot: RepositorySnapshot,
    ) -> None:
        self.identity = identity
        self.snapshot = snapshot
        self.pages: list[WikiPagePlan] = []
        self._page_id_set: set[str] = set()

    def generate(self) -> WikiPlanManifest:
        """Generate a complete page plan.

        Returns:
            WikiPlanManifest with all planned pages
        """
        self.pages = []
        self._page_id_set = set()

        # Generate overview pages (project overview, architecture, etc.)
        self._generate_overview_pages()

        # Generate module pages
        self._generate_module_pages()

        # Generate API reference pages
        self._generate_api_pages()

        # Generate data model pages
        self._generate_data_model_pages()

        # Generate deployment/ops pages
        self._generate_ops_pages()

        # Generate development guide pages
        self._generate_dev_guide_pages()

        # Generate security/compliance pages
        self._generate_security_pages()

        # Generate troubleshooting pages
        self._generate_troubleshooting_pages()

        # Sort pages by category order then by sort_order
        self.pages.sort(key=lambda p: (_CATEGORY_ORDER.get(p.category, 999), p.sort_order))

        # Build navigation tree
        nav_tree = self._build_navigation_tree()

        manifest = WikiPlanManifest(
            version=current_schema_version(),
            profile="qoder-chinese",
            repository_identity=self.identity,
            pages=self.pages,
            navigation_tree=nav_tree,
        )

        return manifest

    def _make_page_id(self, base: str, category: WikiTaxonomyCategory) -> str:
        """Create a unique page ID, handling duplicates."""
        slug = base.lower().replace(" ", "-").replace("_", "-")
        # Remove multiple consecutive dashes
        slug = re.sub(r"-+", "-", slug)
        # Remove leading/trailing dashes
        slug = slug.strip("-")

        original = slug
        counter = 1
        while slug in self._page_id_set:
            slug = f"{original}-{counter}"
            counter += 1

        self._page_id_set.add(slug)
        return slug

    def _make_output_path(self, page_id: str, category: WikiTaxonomyCategory) -> str:
        """Create output path based on category."""
        category_paths = {
            WikiTaxonomyCategory.PROJECT_OVERVIEW: "docs/pages/overview",
            WikiTaxonomyCategory.ARCHITECTURE_DESIGN: "docs/pages/architecture",
            WikiTaxonomyCategory.CORE_SERVICES: "docs/pages/services",
            WikiTaxonomyCategory.PYTHON_SERVICES: "docs/pages/python-services",
            WikiTaxonomyCategory.FRONTEND_APPLICATIONS: "docs/pages/frontend",
            WikiTaxonomyCategory.DATA_MODELS: "docs/pages/data-models",
            WikiTaxonomyCategory.API_REFERENCE: "docs/pages/api",
            WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS: "docs/pages/deployment",
            WikiTaxonomyCategory.DEVELOPMENT_GUIDE: "docs/pages/development",
            WikiTaxonomyCategory.SECURITY_COMPLIANCE: "docs/pages/security",
            WikiTaxonomyCategory.TROUBLESHOOTING: "docs/pages/troubleshooting",
        }
        base = category_paths.get(category, "docs/pages")
        return f"{base}/{page_id}.md"

    def _module_by_name(self, module_name: str) -> Module | None:
        for module in self.snapshot.modules:
            if module.name == module_name:
                return module
        return None

    def _module_domain(self, module_name: str) -> str:
        module = self._module_by_name(module_name)
        return module.domain if module else "unknown"

    def _module_runtime(self, module_name: str) -> str:
        module = self._module_by_name(module_name)
        runtime_role = module.runtime_role if module else ""
        service_family = module.service_family if module else ""
        combined = f"{runtime_role} {service_family}".lower()
        if "python" in combined or "fastapi" in combined:
            return "python"
        return combined or "unknown"

    def _humanize_service_title(self, name: str) -> str:
        known = {
            "api-atlas-agent": "API采集Agent",
            "api-gateway": "API网关",
            "doc-parser-service": "文档解析服务",
            "tcsl-generator-service": "TCSL生成服务",
            "nl-to-dsl-service": "自然语言转DSL服务",
            "scenario-orchestrator-service": "场景编排服务",
            "contract-service": "契约管理服务",
            "diff-service": "差异分析服务",
            "execution-service": "执行引擎服务",
            "gate-service": "质量门禁服务",
            "inventory-service": "API台账服务",
            "knowledge-graph-service": "知识图谱服务",
            "prd-reviewer": "PRD评审服务",
            "script-generator-service": "脚本生成服务",
            "security-audit-service": "安全审计服务",
            "security-scan-mcp-service": "安全扫描MCP服务",
            "test-data-factory-service": "测试数据工厂服务",
            "zentao-mcp-service": "禅道MCP服务",
            "jenkins-mcp-service": "Jenkins MCP服务",
            "gitlab-mcp-service": "GitLab MCP服务",
            "frontend": "前端应用",
        }
        if name in known:
            return known[name]
        words = [part for part in re.split(r"[-_]+", name) if part]
        return " ".join(
            part.upper() if part.lower() in {"api", "mcp", "ai"} else part.capitalize()
            for part in words
        )

    def _include_endpoint_pages(self) -> bool:
        import os

        return os.environ.get("REPO_WIKI_INCLUDE_ENDPOINT_PAGES", "").strip().lower() in {
            "1",
            "true",
            "yes",
        }

    def _include_raw_model_pages(self) -> bool:
        import os

        return os.environ.get("REPO_WIKI_INCLUDE_RAW_MODEL_PAGES", "").strip().lower() in {
            "1",
            "true",
            "yes",
        }

    def _add_page(
        self,
        page_id: str,
        title: str,
        category: WikiTaxonomyCategory,
        parent: str | None = None,
        source_requirements: SourceRequirement | None = None,
        sort_order: int = 0,
        tags: list[str] | None = None,
    ) -> WikiPagePlan:
        """Add a page to the plan."""
        page = WikiPagePlan(
            page_id=page_id,
            title=title,
            category=category,
            parent=parent,
            output_path=self._make_output_path(page_id, category),
            source_requirements=source_requirements or SourceRequirement(),
            generation_mode=GenerationMode.RULE_FIRST,
            sort_order=sort_order,
            tags=tags or [],
        )
        self.pages.append(page)
        return page

    def _generate_overview_pages(self) -> None:
        """Generate overview category pages."""
        # Project overview index
        self._add_page(
            page_id=self._make_page_id("project-overview", WikiTaxonomyCategory.PROJECT_OVERVIEW),
            title="项目概述",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            parent=None,
            source_requirements=SourceRequirement(
                modules=[m.name for m in self.snapshot.modules],
                commands=["start", "build", "test"],
            ),
            sort_order=0,
            tags=["overview", "index"],
        )

        # README summary
        self._add_page(
            page_id=self._make_page_id("readme", WikiTaxonomyCategory.PROJECT_OVERVIEW),
            title="自述文件",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            parent="project-overview",
            source_requirements=SourceRequirement(files=["README.md"]),
            sort_order=1,
            tags=["readme", "introduction"],
        )

        # Project changelog
        self._add_page(
            page_id=self._make_page_id("changelog", WikiTaxonomyCategory.PROJECT_OVERVIEW),
            title="更新日志",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            parent="project-overview",
            sort_order=5,
            tags=["changelog", "history"],
        )

        # Quick start guide
        self._add_page(
            page_id=self._make_page_id("quick-start", WikiTaxonomyCategory.PROJECT_OVERVIEW),
            title="快速开始",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            parent="project-overview",
            source_requirements=SourceRequirement(commands=["start"]),
            sort_order=2,
            tags=["quickstart", "getting-started"],
        )

        # Installation guide
        self._add_page(
            page_id=self._make_page_id("installation", WikiTaxonomyCategory.PROJECT_OVERVIEW),
            title="安装指南",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            parent="project-overview",
            sort_order=3,
            tags=["installation", "setup"],
        )

        # Key features
        self._add_page(
            page_id=self._make_page_id("key-features", WikiTaxonomyCategory.PROJECT_OVERVIEW),
            title="核心特性",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            parent="project-overview",
            sort_order=4,
            tags=["features", "capabilities"],
        )

        # Architecture overview
        self._add_page(
            page_id=self._make_page_id(
                "architecture-overview", WikiTaxonomyCategory.ARCHITECTURE_DESIGN
            ),
            title="架构设计",
            category=WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
            parent=None,
            source_requirements=SourceRequirement(
                modules=[
                    m.name
                    for m in self.snapshot.modules
                    if m.domain in ("core-platform", "ai-services")
                ]
            ),
            sort_order=0,
            tags=["architecture", "design"],
        )

        # System components
        self._add_page(
            page_id=self._make_page_id(
                "system-components", WikiTaxonomyCategory.ARCHITECTURE_DESIGN
            ),
            title="系统组件",
            category=WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
            parent="architecture-overview",
            source_requirements=SourceRequirement(modules=[m.name for m in self.snapshot.modules]),
            sort_order=1,
            tags=["components", "modules"],
        )

        # Module relationships
        self._add_page(
            page_id=self._make_page_id(
                "module-relationships", WikiTaxonomyCategory.ARCHITECTURE_DESIGN
            ),
            title="模块关系",
            category=WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
            parent="architecture-overview",
            source_requirements=SourceRequirement(
                modules=[m.name for m in self.snapshot.modules if m.depends_on]
            ),
            sort_order=2,
            tags=["dependencies", "relationships"],
        )

        # Data flow
        self._add_page(
            page_id=self._make_page_id("data-flow", WikiTaxonomyCategory.ARCHITECTURE_DESIGN),
            title="数据流",
            category=WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
            parent="architecture-overview",
            source_requirements=SourceRequirement(
                modules=[m.name for m in self.snapshot.modules if m.data_models]
            ),
            sort_order=3,
            tags=["data-flow", "pipeline"],
        )

        # API gateway
        self._add_page(
            page_id=self._make_page_id("api-gateway", WikiTaxonomyCategory.ARCHITECTURE_DESIGN),
            title="API网关",
            category=WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
            parent="architecture-overview",
            sort_order=4,
            tags=["api-gateway", "router"],
        )

        # Service mesh
        self._add_page(
            page_id=self._make_page_id("service-mesh", WikiTaxonomyCategory.ARCHITECTURE_DESIGN),
            title="服务网格",
            category=WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
            parent="architecture-overview",
            sort_order=5,
            tags=["mesh", "microservices"],
        )

        # Event driven architecture
        self._add_page(
            page_id=self._make_page_id(
                "event-architecture", WikiTaxonomyCategory.ARCHITECTURE_DESIGN
            ),
            title="事件驱动架构",
            category=WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
            parent="architecture-overview",
            sort_order=6,
            tags=["events", "messaging"],
        )

        # Microservices pattern
        self._add_page(
            page_id=self._make_page_id(
                "microservices-pattern", WikiTaxonomyCategory.ARCHITECTURE_DESIGN
            ),
            title="微服务模式",
            category=WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
            parent="architecture-overview",
            sort_order=7,
            tags=["microservices", "patterns"],
        )

    def _generate_module_pages(self) -> None:
        """Generate module category pages."""
        # Group modules by domain
        modules_by_domain: dict[str, list[Module]] = {}
        for module in self.snapshot.modules:
            domain = module.domain or "unknown"
            if domain not in modules_by_domain:
                modules_by_domain[domain] = []
            modules_by_domain[domain].append(module)

        # Core services index
        self._add_page(
            page_id=self._make_page_id("core-services-index", WikiTaxonomyCategory.CORE_SERVICES),
            title="核心服务",
            category=WikiTaxonomyCategory.CORE_SERVICES,
            parent=None,
            source_requirements=SourceRequirement(
                modules=[m.name for m in self.snapshot.modules if m.domain == "core-platform"]
            ),
            sort_order=0,
            tags=["index", "services"],
        )

        # AI services index
        ai_modules = [m for m in self.snapshot.modules if m.domain == "ai-services"]
        if ai_modules:
            self._add_page(
                page_id=self._make_page_id("ai-services-index", WikiTaxonomyCategory.CORE_SERVICES),
                title="AI服务",
                category=WikiTaxonomyCategory.CORE_SERVICES,
                parent="core-services-index",
                source_requirements=SourceRequirement(modules=[m.name for m in ai_modules]),
                sort_order=1,
                tags=["ai", "machine-learning"],
            )

        # Individual module pages
        for idx, module in enumerate(sorted(self.snapshot.modules, key=lambda m: m.path)):
            module_page_id = self._make_page_id(module.name, WikiTaxonomyCategory.CORE_SERVICES)
            self._add_page(
                page_id=module_page_id,
                title=self._humanize_service_title(module.name),
                category=WikiTaxonomyCategory.CORE_SERVICES,
                parent="core-services-index"
                if module.domain == "core-platform"
                else "ai-services-index",
                source_requirements=SourceRequirement(
                    modules=[module.name],
                    files=[module.doc_path] if module.doc_path else [],
                ),
                sort_order=10 + idx,
                tags=[module.domain, module.service_family],
            )

            # Module data models sub-page
            if module.data_models:
                self._add_page(
                    page_id=self._make_page_id(
                        f"{module.name}-models", WikiTaxonomyCategory.DATA_MODELS
                    ),
                    title=f"{self._humanize_service_title(module.name)} 数据模型",
                    category=WikiTaxonomyCategory.DATA_MODELS,
                    parent=module_page_id,
                    source_requirements=SourceRequirement(data_models=module.data_models),
                    sort_order=30 + idx,
                    tags=["models", "schemas"],
                )

    def _generate_api_pages(self) -> None:
        """Generate Qoder-like API reference pages without endpoint dumps."""
        self._add_page(
            page_id=self._make_page_id("api-overview", WikiTaxonomyCategory.API_REFERENCE),
            title="API参考",
            category=WikiTaxonomyCategory.API_REFERENCE,
            parent=None,
            source_requirements=SourceRequirement(
                endpoints=[f"{e.method} {e.path}" for e in self.snapshot.endpoints]
            ),
            sort_order=0,
            tags=["api", "reference"],
        )

        by_module: dict[str, list] = {}
        for ep in self.snapshot.endpoints:
            if ep.module not in by_module:
                by_module[ep.module] = []
            by_module[ep.module].append(ep)

        service_groups = [
            (
                "core-service-apis",
                "核心服务API",
                lambda module_name, endpoints: any(
                    getattr(e, "domain", "") == "core-platform"
                    or self._module_domain(module_name) == "core-platform"
                    for e in endpoints
                ),
            ),
            (
                "python-service-apis",
                "Python服务API",
                lambda module_name, endpoints: any(
                    "python" in getattr(e, "service_family", "")
                    or self._module_runtime(module_name) in {"python", "fastapi"}
                    for e in endpoints
                ),
            ),
            (
                "api-gateway-api",
                "API网关API",
                lambda module_name, endpoints: "gateway" in module_name.lower(),
            ),
            (
                "agent-proxy-api",
                "Agent代理API",
                lambda module_name, endpoints: "agent" in module_name.lower()
                or any("agent" in e.path.lower() for e in endpoints),
            ),
            (
                "frontend-application-api",
                "前端应用API",
                lambda module_name, endpoints: self._module_domain(module_name) == "frontend",
            ),
        ]

        for sort_offset, (page_id_base, title, predicate) in enumerate(service_groups, start=1):
            grouped_modules: list[str] = []
            grouped_endpoints: list[str] = []
            for module_name, endpoints in by_module.items():
                if predicate(module_name, endpoints):
                    grouped_modules.append(module_name)
                    grouped_endpoints.extend(f"{e.method} {e.path}" for e in endpoints)
            if not grouped_modules and page_id_base not in {
                "api-gateway-api",
                "agent-proxy-api",
                "frontend-application-api",
            }:
                continue
            self._add_page(
                page_id=self._make_page_id(page_id_base, WikiTaxonomyCategory.API_REFERENCE),
                title=title,
                category=WikiTaxonomyCategory.API_REFERENCE,
                parent="api-overview",
                source_requirements=SourceRequirement(
                    modules=sorted(set(grouped_modules)),
                    endpoints=sorted(set(grouped_endpoints)),
                ),
                sort_order=10 + sort_offset,
                tags=["api", "service-family"],
            )

        auth_endpoints = [
            f"{e.method} {e.path}"
            for e in self.snapshot.endpoints
            if getattr(e, "auth_required", False)
            or getattr(e, "auth_type", "unknown") not in {"unknown", "none"}
        ]
        self._add_page(
            page_id=self._make_page_id(
                "authentication-authorization-api", WikiTaxonomyCategory.API_REFERENCE
            ),
            title="认证授权API",
            category=WikiTaxonomyCategory.API_REFERENCE,
            parent="api-overview",
            source_requirements=SourceRequirement(endpoints=auth_endpoints),
            sort_order=20,
            tags=["api", "auth", "security"],
        )
        self._add_page(
            page_id=self._make_page_id(
                "error-handling-status-codes", WikiTaxonomyCategory.API_REFERENCE
            ),
            title="错误处理与状态码",
            category=WikiTaxonomyCategory.API_REFERENCE,
            parent="api-overview",
            source_requirements=SourceRequirement(
                endpoints=[
                    f"{e.method} {e.path}"
                    for e in self.snapshot.endpoints
                    if getattr(e, "error_codes", [])
                ]
            ),
            sort_order=21,
            tags=["api", "errors", "status-codes"],
        )

        # Per-service API articles are useful, but individual endpoint pages are not.
        for idx, (module_name, endpoints) in enumerate(sorted(by_module.items())):
            if not endpoints:
                continue
            self._add_page(
                page_id=self._make_page_id(
                    f"{module_name}-api-reference", WikiTaxonomyCategory.API_REFERENCE
                ),
                title=f"{self._humanize_service_title(module_name)} API",
                category=WikiTaxonomyCategory.API_REFERENCE,
                parent="api-overview",
                source_requirements=SourceRequirement(
                    modules=[module_name],
                    endpoints=[f"{e.method} {e.path}" for e in endpoints],
                ),
                sort_order=100 + idx,
                tags=["api", "service-api", module_name],
            )

        if self._include_endpoint_pages():
            for module_name, endpoints in sorted(by_module.items()):
                module_api_id = self._make_page_id(
                    f"{module_name}-endpoints", WikiTaxonomyCategory.API_REFERENCE
                )
                self._add_page(
                    page_id=module_api_id,
                    title=f"{self._humanize_service_title(module_name)} 接口清单",
                    category=WikiTaxonomyCategory.API_REFERENCE,
                    parent="api-overview",
                    source_requirements=SourceRequirement(
                        modules=[module_name],
                        endpoints=[f"{e.method} {e.path}" for e in endpoints],
                    ),
                    sort_order=1000 + len(self.pages),
                    tags=["api", "endpoint-index"],
                )

    def _generate_data_model_pages(self) -> None:
        """Generate Qoder-like data model pages without raw DTO/entity dumps."""
        self._add_page(
            page_id=self._make_page_id("data-models-overview", WikiTaxonomyCategory.DATA_MODELS),
            title="数据模型",
            category=WikiTaxonomyCategory.DATA_MODELS,
            parent=None,
            source_requirements=SourceRequirement(
                data_models=[dm.name for dm in self.snapshot.data_models]
            ),
            sort_order=0,
            tags=["models", "schemas"],
        )

        by_module: dict[str, list] = {}
        for dm in self.snapshot.data_models:
            if dm.module not in by_module:
                by_module[dm.module] = []
            by_module[dm.module].append(dm)

        core_names = [
            model.name
            for model in self.snapshot.data_models
            if any(
                token in model.name.lower()
                for token in ["entity", "apiatom", "contract", "workflow", "audit", "execution"]
            )
        ]
        self._add_page(
            page_id=self._make_page_id("core-data-models", WikiTaxonomyCategory.DATA_MODELS),
            title="核心数据模型",
            category=WikiTaxonomyCategory.DATA_MODELS,
            parent="data-models-overview",
            source_requirements=SourceRequirement(data_models=sorted(set(core_names))[:120]),
            sort_order=10,
            tags=["models", "core-entities"],
        )
        self._add_page(
            page_id=self._make_page_id("service-data-models", WikiTaxonomyCategory.DATA_MODELS),
            title="服务数据模型",
            category=WikiTaxonomyCategory.DATA_MODELS,
            parent="data-models-overview",
            source_requirements=SourceRequirement(
                data_models=[dm.name for dm in self.snapshot.data_models]
            ),
            sort_order=11,
            tags=["models", "service-models"],
        )
        self._add_page(
            page_id=self._make_page_id("database-architecture", WikiTaxonomyCategory.DATA_MODELS),
            title="数据库架构",
            category=WikiTaxonomyCategory.DATA_MODELS,
            parent="data-models-overview",
            source_requirements=SourceRequirement(files=["db", "sql", "migrations"]),
            sort_order=12,
            tags=["database", "schema"],
        )
        self._add_page(
            page_id=self._make_page_id(
                "database-migration-strategy", WikiTaxonomyCategory.DATA_MODELS
            ),
            title="数据迁移策略",
            category=WikiTaxonomyCategory.DATA_MODELS,
            parent="database-architecture",
            source_requirements=SourceRequirement(files=["migration", "migrations", "sql"]),
            sort_order=13,
            tags=["database", "migration"],
        )

        for idx, (module_name, models) in enumerate(sorted(by_module.items())):
            module_models_id = self._make_page_id(
                f"{module_name}-data-models", WikiTaxonomyCategory.DATA_MODELS
            )
            self._add_page(
                page_id=module_models_id,
                title=f"{self._humanize_service_title(module_name)} 数据模型",
                category=WikiTaxonomyCategory.DATA_MODELS,
                parent="service-data-models",
                source_requirements=SourceRequirement(data_models=[m.name for m in models]),
                sort_order=100 + idx,
                tags=["models", "service-model", module_name],
            )

            if not self._include_raw_model_pages():
                continue
            for model_idx, model in enumerate(sorted(models, key=lambda m: m.name)):
                model_id = self._make_page_id(
                    f"{module_name}-{model.name}", WikiTaxonomyCategory.DATA_MODELS
                )
                self._add_page(
                    page_id=model_id,
                    title=model.name,
                    category=WikiTaxonomyCategory.DATA_MODELS,
                    parent=module_models_id,
                    source_requirements=SourceRequirement(
                        data_models=[model.name],
                        files=[model.file_path],
                    ),
                    sort_order=200 + model_idx,
                    tags=["raw-model", model.type],
                )

    def _generate_ops_pages(self) -> None:
        """Generate deployment and operations pages."""
        # Deployment overview
        self._add_page(
            page_id=self._make_page_id(
                "deployment-overview", WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS
            ),
            title="部署运维概览",
            category=WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS,
            parent=None,
            source_requirements=SourceRequirement(commands=["start", "build", "test"]),
            sort_order=0,
            tags=["deployment", "operations"],
        )

        # Configuration guide
        self._add_page(
            page_id=self._make_page_id("configuration", WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS),
            title="配置指南",
            category=WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS,
            parent="deployment-overview",
            source_requirements=SourceRequirement(files=["repo-wiki.yaml", ".repo-wiki.yaml"]),
            sort_order=1,
            tags=["config", "settings"],
        )

        # Environment setup
        self._add_page(
            page_id=self._make_page_id(
                "environment-setup", WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS
            ),
            title="环境配置",
            category=WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS,
            parent="deployment-overview",
            sort_order=2,
            tags=["environment", "setup"],
        )

        # Monitoring
        self._add_page(
            page_id=self._make_page_id("monitoring", WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS),
            title="监控告警",
            category=WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS,
            parent="deployment-overview",
            sort_order=3,
            tags=["monitoring", "alerts"],
        )

        # Logging
        self._add_page(
            page_id=self._make_page_id("logging", WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS),
            title="日志管理",
            category=WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS,
            parent="deployment-overview",
            sort_order=4,
            tags=["logging", "observability"],
        )

        # Container deployment
        self._add_page(
            page_id=self._make_page_id(
                "container-deployment", WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS
            ),
            title="容器化部署",
            category=WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS,
            parent="deployment-overview",
            sort_order=5,
            tags=["docker", "containers"],
        )

        # Kubernetes deployment
        self._add_page(
            page_id=self._make_page_id(
                "kubernetes-deployment", WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS
            ),
            title="Kubernetes部署",
            category=WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS,
            parent="deployment-overview",
            sort_order=6,
            tags=["kubernetes", "k8s"],
        )

        # CI/CD pipeline
        self._add_page(
            page_id=self._make_page_id("cicd-pipeline", WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS),
            title="CI/CD流水线",
            category=WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS,
            parent="deployment-overview",
            sort_order=7,
            tags=["cicd", "automation"],
        )

        # Backup and recovery
        self._add_page(
            page_id=self._make_page_id(
                "backup-recovery", WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS
            ),
            title="备份恢复",
            category=WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS,
            parent="deployment-overview",
            sort_order=8,
            tags=["backup", "disaster-recovery"],
        )

        # Scaling
        self._add_page(
            page_id=self._make_page_id("scaling", WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS),
            title="扩缩容",
            category=WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS,
            parent="deployment-overview",
            sort_order=9,
            tags=["scaling", "performance"],
        )

    def _generate_dev_guide_pages(self) -> None:
        """Generate development guide pages."""
        # Development guide overview
        self._add_page(
            page_id=self._make_page_id("development-guide", WikiTaxonomyCategory.DEVELOPMENT_GUIDE),
            title="开发指南",
            category=WikiTaxonomyCategory.DEVELOPMENT_GUIDE,
            parent=None,
            sort_order=0,
            tags=["development", "guide"],
        )

        # Local setup
        self._add_page(
            page_id=self._make_page_id("local-setup", WikiTaxonomyCategory.DEVELOPMENT_GUIDE),
            title="本地开发环境",
            category=WikiTaxonomyCategory.DEVELOPMENT_GUIDE,
            parent="development-guide",
            sort_order=1,
            tags=["setup", "local"],
        )

        # Testing guide
        self._add_page(
            page_id=self._make_page_id("testing-guide", WikiTaxonomyCategory.DEVELOPMENT_GUIDE),
            title="测试指南",
            category=WikiTaxonomyCategory.DEVELOPMENT_GUIDE,
            parent="development-guide",
            source_requirements=SourceRequirement(commands=["test"]),
            sort_order=2,
            tags=["testing", "tests"],
        )

        # Code style
        self._add_page(
            page_id=self._make_page_id("code-style", WikiTaxonomyCategory.DEVELOPMENT_GUIDE),
            title="代码规范",
            category=WikiTaxonomyCategory.DEVELOPMENT_GUIDE,
            parent="development-guide",
            sort_order=3,
            tags=["style", "linting"],
        )

        # Contribution guide
        self._add_page(
            page_id=self._make_page_id("contribution", WikiTaxonomyCategory.DEVELOPMENT_GUIDE),
            title="贡献指南",
            category=WikiTaxonomyCategory.DEVELOPMENT_GUIDE,
            parent="development-guide",
            sort_order=4,
            tags=["contribution", "pull-request"],
        )

        # Debug guide
        self._add_page(
            page_id=self._make_page_id("debug-guide", WikiTaxonomyCategory.DEVELOPMENT_GUIDE),
            title="调试指南",
            category=WikiTaxonomyCategory.DEVELOPMENT_GUIDE,
            parent="development-guide",
            sort_order=5,
            tags=["debug", "troubleshooting"],
        )

        # Performance optimization
        self._add_page(
            page_id=self._make_page_id(
                "performance-optimization", WikiTaxonomyCategory.DEVELOPMENT_GUIDE
            ),
            title="性能优化",
            category=WikiTaxonomyCategory.DEVELOPMENT_GUIDE,
            parent="development-guide",
            sort_order=6,
            tags=["performance", "optimization"],
        )

        # IDE setup
        self._add_page(
            page_id=self._make_page_id("ide-setup", WikiTaxonomyCategory.DEVELOPMENT_GUIDE),
            title="IDE配置",
            category=WikiTaxonomyCategory.DEVELOPMENT_GUIDE,
            parent="development-guide",
            sort_order=7,
            tags=["ide", "editor"],
        )

        # Git workflow
        self._add_page(
            page_id=self._make_page_id("git-workflow", WikiTaxonomyCategory.DEVELOPMENT_GUIDE),
            title="Git工作流",
            category=WikiTaxonomyCategory.DEVELOPMENT_GUIDE,
            parent="development-guide",
            sort_order=8,
            tags=["git", "workflow"],
        )

        # API development
        self._add_page(
            page_id=self._make_page_id("api-development", WikiTaxonomyCategory.DEVELOPMENT_GUIDE),
            title="API开发指南",
            category=WikiTaxonomyCategory.DEVELOPMENT_GUIDE,
            parent="development-guide",
            sort_order=9,
            tags=["api", "rest"],
        )

        # Database migration
        self._add_page(
            page_id=self._make_page_id(
                "database-migration", WikiTaxonomyCategory.DEVELOPMENT_GUIDE
            ),
            title="数据库迁移",
            category=WikiTaxonomyCategory.DEVELOPMENT_GUIDE,
            parent="development-guide",
            sort_order=10,
            tags=["database", "migration"],
        )

    def _generate_security_pages(self) -> None:
        """Generate security and compliance pages."""
        # Security overview
        self._add_page(
            page_id=self._make_page_id(
                "security-overview", WikiTaxonomyCategory.SECURITY_COMPLIANCE
            ),
            title="安全合规概览",
            category=WikiTaxonomyCategory.SECURITY_COMPLIANCE,
            parent=None,
            sort_order=0,
            tags=["security", "compliance"],
        )

        # Authentication
        self._add_page(
            page_id=self._make_page_id("authentication", WikiTaxonomyCategory.SECURITY_COMPLIANCE),
            title="身份认证",
            category=WikiTaxonomyCategory.SECURITY_COMPLIANCE,
            parent="security-overview",
            sort_order=1,
            tags=["auth", "authentication"],
        )

        # Authorization
        self._add_page(
            page_id=self._make_page_id("authorization", WikiTaxonomyCategory.SECURITY_COMPLIANCE),
            title="权限管理",
            category=WikiTaxonomyCategory.SECURITY_COMPLIANCE,
            parent="security-overview",
            sort_order=2,
            tags=["authz", "authorization"],
        )

        # Data protection
        self._add_page(
            page_id=self._make_page_id("data-protection", WikiTaxonomyCategory.SECURITY_COMPLIANCE),
            title="数据保护",
            category=WikiTaxonomyCategory.SECURITY_COMPLIANCE,
            parent="security-overview",
            sort_order=3,
            tags=["data", "protection"],
        )

        # Encryption
        self._add_page(
            page_id=self._make_page_id("encryption", WikiTaxonomyCategory.SECURITY_COMPLIANCE),
            title="加密策略",
            category=WikiTaxonomyCategory.SECURITY_COMPLIANCE,
            parent="security-overview",
            sort_order=4,
            tags=["encryption", "security"],
        )

        # API security
        self._add_page(
            page_id=self._make_page_id("api-security", WikiTaxonomyCategory.SECURITY_COMPLIANCE),
            title="API安全",
            category=WikiTaxonomyCategory.SECURITY_COMPLIANCE,
            parent="security-overview",
            sort_order=5,
            tags=["api", "security"],
        )

        # Audit logging
        self._add_page(
            page_id=self._make_page_id("audit-logging", WikiTaxonomyCategory.SECURITY_COMPLIANCE),
            title="审计日志",
            category=WikiTaxonomyCategory.SECURITY_COMPLIANCE,
            parent="security-overview",
            sort_order=6,
            tags=["audit", "logging"],
        )

        # Compliance frameworks
        self._add_page(
            page_id=self._make_page_id(
                "compliance-frameworks", WikiTaxonomyCategory.SECURITY_COMPLIANCE
            ),
            title="合规框架",
            category=WikiTaxonomyCategory.SECURITY_COMPLIANCE,
            parent="security-overview",
            sort_order=7,
            tags=["compliance", "standards"],
        )

        # Security best practices
        self._add_page(
            page_id=self._make_page_id(
                "security-best-practices", WikiTaxonomyCategory.SECURITY_COMPLIANCE
            ),
            title="安全最佳实践",
            category=WikiTaxonomyCategory.SECURITY_COMPLIANCE,
            parent="security-overview",
            sort_order=8,
            tags=["best-practices", "security"],
        )

        # Vulnerability management
        self._add_page(
            page_id=self._make_page_id(
                "vulnerability-management", WikiTaxonomyCategory.SECURITY_COMPLIANCE
            ),
            title="漏洞管理",
            category=WikiTaxonomyCategory.SECURITY_COMPLIANCE,
            parent="security-overview",
            sort_order=9,
            tags=["vulnerability", "security"],
        )

    def _generate_troubleshooting_pages(self) -> None:
        """Generate troubleshooting pages."""
        # Troubleshooting overview
        self._add_page(
            page_id=self._make_page_id(
                "troubleshooting-overview", WikiTaxonomyCategory.TROUBLESHOOTING
            ),
            title="故障排除概览",
            category=WikiTaxonomyCategory.TROUBLESHOOTING,
            parent=None,
            sort_order=0,
            tags=["troubleshooting", "debugging"],
        )

        # Common issues
        self._add_page(
            page_id=self._make_page_id("common-issues", WikiTaxonomyCategory.TROUBLESHOOTING),
            title="常见问题",
            category=WikiTaxonomyCategory.TROUBLESHOOTING,
            parent="troubleshooting-overview",
            sort_order=1,
            tags=["faq", "issues"],
        )

        # Error codes
        self._add_page(
            page_id=self._make_page_id("error-codes", WikiTaxonomyCategory.TROUBLESHOOTING),
            title="错误码参考",
            category=WikiTaxonomyCategory.TROUBLESHOOTING,
            parent="troubleshooting-overview",
            sort_order=2,
            tags=["errors", "codes"],
        )

        # Performance issues
        self._add_page(
            page_id=self._make_page_id("performance-issues", WikiTaxonomyCategory.TROUBLESHOOTING),
            title="性能问题",
            category=WikiTaxonomyCategory.TROUBLESHOOTING,
            parent="troubleshooting-overview",
            sort_order=3,
            tags=["performance", "optimization"],
        )

        # Network issues
        self._add_page(
            page_id=self._make_page_id("network-issues", WikiTaxonomyCategory.TROUBLESHOOTING),
            title="网络问题",
            category=WikiTaxonomyCategory.TROUBLESHOOTING,
            parent="troubleshooting-overview",
            sort_order=4,
            tags=["network", "connectivity"],
        )

        # Database issues
        self._add_page(
            page_id=self._make_page_id("database-issues", WikiTaxonomyCategory.TROUBLESHOOTING),
            title="数据库问题",
            category=WikiTaxonomyCategory.TROUBLESHOOTING,
            parent="troubleshooting-overview",
            sort_order=5,
            tags=["database", "sql"],
        )

        # Authentication issues
        self._add_page(
            page_id=self._make_page_id("auth-issues", WikiTaxonomyCategory.TROUBLESHOOTING),
            title="认证问题",
            category=WikiTaxonomyCategory.TROUBLESHOOTING,
            parent="troubleshooting-overview",
            sort_order=6,
            tags=["auth", "login"],
        )

        # API issues
        self._add_page(
            page_id=self._make_page_id("api-issues", WikiTaxonomyCategory.TROUBLESHOOTING),
            title="API问题",
            category=WikiTaxonomyCategory.TROUBLESHOOTING,
            parent="troubleshooting-overview",
            sort_order=7,
            tags=["api", "errors"],
        )

        # Build failures
        self._add_page(
            page_id=self._make_page_id("build-failures", WikiTaxonomyCategory.TROUBLESHOOTING),
            title="构建失败",
            category=WikiTaxonomyCategory.TROUBLESHOOTING,
            parent="troubleshooting-overview",
            sort_order=8,
            tags=["build", "compile"],
        )

        # Deployment issues
        self._add_page(
            page_id=self._make_page_id("deployment-issues", WikiTaxonomyCategory.TROUBLESHOOTING),
            title="部署问题",
            category=WikiTaxonomyCategory.TROUBLESHOOTING,
            parent="troubleshooting-overview",
            sort_order=9,
            tags=["deployment", "rollback"],
        )

        # Memory issues
        self._add_page(
            page_id=self._make_page_id("memory-issues", WikiTaxonomyCategory.TROUBLESHOOTING),
            title="内存问题",
            category=WikiTaxonomyCategory.TROUBLESHOOTING,
            parent="troubleshooting-overview",
            sort_order=10,
            tags=["memory", "oom"],
        )

        # Disk space issues
        self._add_page(
            page_id=self._make_page_id("disk-issues", WikiTaxonomyCategory.TROUBLESHOOTING),
            title="磁盘问题",
            category=WikiTaxonomyCategory.TROUBLESHOOTING,
            parent="troubleshooting-overview",
            sort_order=11,
            tags=["disk", "space"],
        )

        # Debug tools
        self._add_page(
            page_id=self._make_page_id("debug-tools", WikiTaxonomyCategory.TROUBLESHOOTING),
            title="调试工具",
            category=WikiTaxonomyCategory.TROUBLESHOOTING,
            parent="troubleshooting-overview",
            sort_order=12,
            tags=["debug", "tools"],
        )

        # Health check guide
        self._add_page(
            page_id=self._make_page_id("health-check", WikiTaxonomyCategory.TROUBLESHOOTING),
            title="健康检查",
            category=WikiTaxonomyCategory.TROUBLESHOOTING,
            parent="troubleshooting-overview",
            sort_order=13,
            tags=["health", "monitoring"],
        )

    def _build_navigation_tree(self) -> list[NavNode]:
        """Build navigation tree from page plan."""
        # Create root category nodes
        category_nodes: dict[WikiTaxonomyCategory, NavNode] = {}
        for category in DEFAULT_CHINESE_TAXONOMY:
            node = NavNode(
                node_id=f"cat-{category.value}",
                label=category.value,
                node_type="category",
                sort_order=_CATEGORY_ORDER.get(category, 999),
            )
            category_nodes[category] = node

        # Add pages under categories
        for page in self.pages:
            cat_node = category_nodes.get(page.category)
            if not cat_node:
                continue

            page_node = NavNode(
                node_id=f"page-{page.page_id}",
                label=page.title,
                node_type="page",
                path=page.output_path,
                sort_order=page.sort_order,
            )

            # Find parent page node
            if page.parent:
                parent_node = self._find_nav_node(cat_node, f"page-{page.parent}")
                if parent_node:
                    parent_node.children.append(page_node)
                else:
                    cat_node.children.append(page_node)
            else:
                cat_node.children.append(page_node)

        # Sort children at each level
        def sort_children(node: NavNode) -> None:
            node.children.sort(key=lambda c: (c.sort_order, c.label))
            for child in node.children:
                sort_children(child)

        for node in category_nodes.values():
            sort_children(node)

        # Return sorted category nodes
        return sorted(category_nodes.values(), key=lambda n: n.sort_order)

    def _find_nav_node(self, parent: NavNode, node_id: str) -> NavNode | None:
        """Find a navigation node by ID within parent subtree."""
        for child in parent.children:
            if child.node_id == node_id:
                return child
            found = self._find_nav_node(child, node_id)
            if found:
                return found
        return None


import re


def plan_pages_from_snapshot(
    identity: RepositoryIdentity,
    snapshot: RepositorySnapshot,
) -> WikiPlanManifest:
    """Generate a rule-first page plan from repository snapshot.

    This is the main entry point for deterministic page planning.

    Args:
        identity: Repository identity
        snapshot: Repository scan snapshot

    Returns:
        WikiPlanManifest with planned pages
    """
    planner = RuleFirstPlanner(identity, snapshot)
    return planner.generate()
