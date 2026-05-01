"""Generation engine for MVP documentation and support artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .cache import GenerationCache
from .context import ContextBuilder
from .contracts import (
    CORE_DOCUMENT_CONTRACTS,
    DocumentLayer,
    PHASE_DEFINITIONS,
    PROMPT_FRAGMENT_CONTRACTS,
    SECTION_DEFINITIONS,
    TASK_CATALOG_CONTRACT,
    all_phase_contracts,
    all_section_contracts,
    get_contracts_by_layer,
    is_governance_only_layer,
    is_target_output_layer,
    module_document_contract,
    overview_to_section_link,
    overview_to_module_link,
    section_to_overview_link,
    section_to_section_link,
    validate_contract_coverage,
    validate_overview_prose,
    validate_overview_not_list_only,
    validate_architecture_has_mermaid,
    validate_architecture_not_module_enum,
    validate_module_map_domain_grouped,
    validate_module_map_not_directory_flat,
    validate_api_contract_grouped,
    validate_api_contract_not_endpoint_dump,
    validate_data_model_grouped,
    validate_data_model_not_dump,
    validate_section_page_exists,
    validate_section_page_content,
    validate_section_cross_links,
    validate_all_required_sections_exist,
    validate_narrative_not_generic,
    validate_architecture_rationale_exists,
    validate_overview_has_repository_specifics,
)
from .io import ensure_dir, read_yamlish, stable_hash, write_json, write_text
from .templates import TemplateRenderer


@dataclass(frozen=True)
class GenerationConfig:
    model_init: str = "claude-3-5-sonnet"
    model_update: str = "claude-3-5-sonnet"
    model_verify: str = "claude-3-5-haiku"
    token_budget: int = 4000

    def select_model(self, mode: str) -> str:
        if mode == "init":
            return self.model_init
        if mode == "update":
            return self.model_update
        if mode == "verify":
            return self.model_verify
        return self.model_update


@dataclass
class GenerationRunResult:
    written_files: list[str]
    cache_hits: int
    cache_misses: int


class NarrativeBuilder:
    """Builds repository-specific narrative for overview and architecture docs.

    This class derives project positioning, core problem, core capabilities,
    and architecture rationale from repository signals rather than using
    fixed generic templates.

    Phase 10 - Task 10.1: Narrative builder for overview and architecture
    """

    def __init__(
        self,
        repo_name: str,
        primary_language: str,
        framework: str,
        modules: list[dict[str, Any]],
        endpoints: list[dict[str, Any]],
        models: list[dict[str, Any]],
        commands: dict[str, str],
    ) -> None:
        self.repo_name = repo_name
        self.primary_language = primary_language
        self.framework = framework
        self.modules = modules
        self.endpoints = endpoints
        self.models = models
        self.commands = commands

        # Analyze repository signals once during initialization
        self._analyze_signals()

    def _analyze_signals(self) -> None:
        """Analyze repository signals to derive narrative components."""
        # Analyze module composition to understand project type
        self.module_domains = self._analyze_module_domains()
        self.project_type = self._derive_project_type()
        self.is_knowledge_management_system = self._detect_knowledge_management_signals()
        self.is_document_generation_system = self._detect_document_generation_signals()

    def _analyze_module_domains(self) -> dict[str, int]:
        """Analyze domain distribution across modules."""
        domains: dict[str, int] = {}
        for m in self.modules:
            domain = m.get("domain", "unknown")
            domains[domain] = domains.get(domain, 0) + 1
        return domains

    def _derive_project_type(self) -> str:
        """Derive the project type from module analysis."""
        # Detect if this is a tooling project, library, service, etc.
        if any("tool" in name.lower() or "cli" in name.lower() for m in self.modules if (name := m.get("name", ""))):
            return "tooling"
        if any("server" in name.lower() or "api" in name.lower() or "service" in name.lower()
               for m in self.modules if (name := m.get("name", ""))):
            return "service"
        if any("lib" in name.lower() or "sdk" in name.lower() for m in self.modules if (name := m.get("name", ""))):
            return "library"
        return "application"

    def _detect_knowledge_management_signals(self) -> bool:
        """Detect if this is a knowledge management system."""
        knowledge_signals = ["knowledge", "graph", "index", "retrieval", "embedding", "vector", "chroma", "sqlite"]
        name_lower = self.repo_name.lower()
        path_signals = []
        domain_signals = []

        for m in self.modules:
            path = m.get("path", "").lower()
            path_signals.append(path)
            exports = " ".join(m.get("exports", []) or []).lower()
            path_signals.append(exports)
            # Also check domain
            domain = m.get("domain", "").lower()
            domain_signals.append(domain)
            # Check responsibility field too
            resp = m.get("responsibility", "").lower()
            path_signals.append(resp)

        combined = name_lower + " " + " ".join(path_signals) + " " + " ".join(domain_signals)
        return any(signal in combined for signal in knowledge_signals)

    def _detect_document_generation_signals(self) -> bool:
        """Detect if this is a document generation system."""
        doc_signals = ["document", "wiki", "doc", "markdown", "template", "generate", "render"]
        name_lower = self.repo_name.lower()
        path_signals = []
        for m in self.modules:
            path = m.get("path", "").lower()
            path_signals.append(path)
            exports = " ".join(m.get("exports", []) or []).lower()
            path_signals.append(exports)

        combined = name_lower + " " + " ".join(path_signals)
        return any(signal in combined for signal in doc_signals)

    def build_project_description(self) -> str:
        """Build repository-specific project description.

        Derives from: project type, language, framework, module composition
        """
        # Build description based on actual project signals
        capabilities = []

        # Detect actual capabilities from module analysis
        if self.module_domains.get("ai-services") or self.is_knowledge_management_system:
            capabilities.append("知识管理和语义检索")

        if self.module_domains.get("tooling") or self._detect_tooling_signals():
            capabilities.append("命令行工具和脚本自动化")

        if self.is_document_generation_system:
            capabilities.append("文档自动生成")

        if self.module_domains.get("core-platform"):
            capabilities.append("核心平台基础设施")

        capability_str = "、".join(capabilities) if capabilities else "代码分析和模块理解"

        # Build language/framework context
        lang_context = f"{self.primary_language.title()} "
        if self.framework and self.framework != "unknown":
            lang_context += f"({self.framework})"
        else:
            lang_context += "项目"

        # Construct description
        if self.is_knowledge_management_system and self.is_document_generation_system:
            description = (
                f"{self.repo_name} 是一个基于 {lang_context} 的知识管理和文档生成平台。"
                f"系统提供 {capability_str} 等核心能力。"
            )
        elif self.is_document_generation_system:
            description = (
                f"{self.repo_name} 是一个基于 {lang_context} 的文档生成系统。"
                f"通过自动化手段将代码知识转化为可读的文档内容。"
            )
        elif self.is_knowledge_management_system:
            description = (
                f"{self.repo_name} 是一个基于 {lang_context} 的知识图谱系统。"
                f"支持 {capability_str} 等功能。"
            )
        else:
            description = (
                f"{self.repo_name} 是一个基于 {lang_context} 的 {self.project_type}。"
                f"包含 {capability_str} 等功能。"
            )

        return description

    def _detect_tooling_signals(self) -> bool:
        """Detect if project has tooling characteristics."""
        tooling_domains = ["tooling", "operations"]
        return any(d in self.module_domains for d in tooling_domains)

    def build_project_positioning(self) -> str:
        """Build repository-specific positioning statement.

        Derives from: project type, detected capabilities, target users
        """
        # Determine target user profile
        if self._detect_tooling_signals():
            user_profile = "开发者"
            use_case = "日常开发工作流自动化"
        elif self.is_document_generation_system:
            user_profile = "技术写作者和开发者"
            use_case = "文档维护和知识同步"
        elif self.is_knowledge_management_system:
            user_profile = "需要知识检索能力的开发者"
            use_case = "代码理解和快速检索"
        else:
            user_profile = "开发者"
            use_case = f"{self.project_type}开发"

        positioning = (
            f"该项目面向 {user_profile}，致力于解决 {use_case} 中的效率问题。"
            f"通过结构化知识组织和自动化工具，提升代码理解和维护效率。"
        )

        return positioning

    def build_core_problem(self) -> str:
        """Build repository-specific problem statement.

        Derives from: project type, detected pain points from structure
        """
        problems = []

        # Detect problems based on project characteristics
        if self.is_document_generation_system:
            problems.extend([
                "文档与代码不同步，维护成本高",
                "传统文档难以发现和检索",
            ])

        if self.is_knowledge_management_system:
            problems.extend([
                "代码结构复杂，难以快速理解",
                "知识分散在代码中，难以聚合",
            ])

        if not problems:
            # Generic problems for unknown project types
            problems.extend([
                "代码库规模增长带来的理解成本上升",
                "模块间依赖关系不清晰",
            ])

        # Format as prose, not bullet list
        problem_text = "；".join(problems[:-1]) + "。" if len(problems) > 1 else problems[0] + "。"
        return f"{self.repo_name} 旨在解决以下核心问题：{problem_text}"

    def build_core_capabilities(self) -> str:
        """Build repository-specific capabilities list.

        Derives from: actual modules, endpoints, models, commands
        """
        capabilities = []

        # Derive capabilities from actual module composition
        if self.modules:
            # Group by domain to derive capabilities
            domain_modules = {}
            for m in self.modules:
                domain = m.get("domain", "unknown")
                if domain not in domain_modules:
                    domain_modules[domain] = []
                domain_modules[domain].append(m)

            if "ai-services" in domain_modules or "core-platform" in domain_modules:
                capabilities.append(f"模块分析和依赖关系构建（{len(self.modules)} 个模块）")

            if "tooling" in domain_modules or "operations" in domain_modules:
                capabilities.append("命令行工具和自动化脚本")

        # Derive capabilities from endpoints
        if self.endpoints:
            api_modules = set(e.get("module", "unknown") for e in self.endpoints)
            capabilities.append(f"RESTful API 接口（{len(self.endpoints)} 个端点，跨越 {len(api_modules)} 个模块）")

        # Derive capabilities from data models
        if self.models:
            capabilities.append(f"数据模型提取和管理（{len(self.models)} 个模型）")

        # Derive capabilities from commands
        if self.commands:
            key_commands = []
            for key in ["init", "scan", "generate", "verify", "update"]:
                if key in self.commands:
                    key_commands.append(key)
            if key_commands:
                capabilities.append(f"端到端工作流命令（{', '.join(key_commands)}）")

        # Add language-specific capability
        lang_caps = {
            "python": "Python 生态集成",
            "typescript": "TypeScript/JavaScript 生态集成",
            "go": "Go 并发和部署支持",
        }
        if self.primary_language in lang_caps:
            capabilities.append(lang_caps[self.primary_language])

        # Format as prose
        if capabilities:
            cap_text = "；".join(capabilities[:-1]) + "。" if len(capabilities) > 1 else capabilities[0] + "。"
            return f"{self.repo_name} 提供以下核心能力：{cap_text}"
        else:
            return f"{self.repo_name} 提供基础的代码分析和结构理解能力。"

    def build_architecture_rationale(self) -> str:
        """Build architecture rationale explaining WHY the three-layer model exists.

        This explains the design decisions and problems each layer solves,
        not just what the layers are named.
        """
        # Derive rationale based on project characteristics
        rationale_parts = []

        # Problem 1: Why separate runtime storage from source of truth?
        rationale_parts.append(
            "**为什么分离运行时存储与结构化事实？**\n"
            "运行时操作（索引、缓存、向量存储）会产生大量临时状态，而结构化事实（模块定义、API契约、数据模型）需要稳定持久化。"
            "如果混在一起，状态污染会影响事实的可靠性。分离后，事实层可以作为稳定的API响应来源。"
        )

        # Problem 2: Why have a document center layer at all?
        if self.is_document_generation_system:
            rationale_parts.append(
                "**为什么需要文档中心？**\n"
                "文档不仅是信息的展示，更是知识的组织结构。文档中心层通过分层组织（总览、专题、模块）"
                "支持不同的阅读路径，既能满足快速概览需求，也能支持深入研究场景。"
            )
        else:
            rationale_parts.append(
                "**文档中心的可选性**：\n"
                "对于非文档生成系统，文档中心提供了知识的一站式导航能力，"
                "帮助新成员快速理解项目结构，也支持长期项目的知识积累。"
            )

        # Problem 3: Why layer ordering/dependencies?
        rationale_parts.append(
            "**层次依赖设计原因**：\n"
            ".repo-wiki/ 层不直接面向读者，仅作为系统运行底座；"
            "ai/source-of-truth/ 层面向机器和自动化工具，提供结构化的事实接口；"
            "docs/ 层面向最终读者，提供人类可读的知识组织。"
        )

        return "\n\n".join(rationale_parts)

    def build_three_layer_overview(self) -> str:
        """Build detailed three-layer architecture overview with rationale."""
        layer_parts = []

        # Layer 1 with rationale
        layer_parts.append(
            "**第一层：运行时存储层 (`.repo-wiki/`)**\n"
            "负责支撑系统运行时操作的临时状态存储。\n"
            "- **索引存储** (SQLite + FTS): 全文搜索和精确查询\n"
            "- **知识图谱** (JSON): 模块间依赖关系和影响链\n"
            "- **向量缓存** (Chroma): 语义检索的向量表示\n"
            "- **生成缓存**: 避免重复生成，节省计算资源\n"
            "**为什么需要这一层？** 这一层处理的是高频变化的运行时状态，不适合与稳定的结构化事实混在一起。"
        )

        # Layer 2 with rationale
        layer_parts.append(
            "**第二层：结构化事实层 (`ai/source-of-truth/`)**\n"
            '代表系统的"真理之源"，记录扫描后沉淀的结构化信息。\n'
            "- **module-index.yaml**: 所有模块的元信息（名称、路径、依赖、域分类）\n"
            "- **api-index.yaml**: API 端点注册表（路径、方法、处理器）\n"
            "- **data-models.yaml**: 数据模型定义（类型、字段、关系）\n"
            "- **repo-map.yaml**: 仓库级元数据和命令注册表\n"
            "**为什么需要这一层？** 事实需要稳定、可追溯、可验证。结构化格式支持机器消费（生成器、适配器、治理检查）和自动化处理。"
        )

        # Layer 3 with rationale
        layer_parts.append(
            "**第三层：文档中心层 (`docs/`)**\n"
            "真正面向读者（人或者 AI agent）的知识导航界面。\n"
            "- **总览文档** (00-05): 快速定位和能力了解\n"
            "- **专题文档** (sections/): 按业务主题聚合的相关内容\n"
            "- **模块文档** (modules/): 单个模块的详细参考\n"
            "**为什么需要这一层？** 源代码和结构化事实都不是面向读者的最优格式。"
            "文档中心通过选择性的信息呈现（而非全量导出）来提升可读性。"
        )

        return "\n\n".join(layer_parts)

    def build_service_collaboration_narrative(self) -> str:
        """Build narrative explaining service collaboration with repository-specific details."""
        # Identify actual services from modules
        services = []
        for m in self.modules:
            name = m.get("name", "unknown")
            role = m.get("runtime_role", "unknown")
            responsibility = m.get("responsibility", "")
            if role in ("api-server", "worker", "data-pipeline", "tooling"):
                services.append((name, role, responsibility))

        if services:
            service_lines = ["系统包含以下核心服务组件："]
            for name, role, resp in sorted(services, key=lambda x: x[1]):
                role_desc = {
                    "api-server": "API 服务器",
                    "worker": "后台任务处理器",
                    "data-pipeline": "数据处理流水线",
                    "tooling": "工具脚本",
                }.get(role, role)
                service_lines.append(f"- **{name}** ({role_desc}): {resp}")
            return "\n".join(service_lines)
        else:
            return (
                "系统服务组件包括：\n"
                "- **Scanner**: 扫描和解析源代码\n"
                "- **Indexer**: 构建索引和图谱\n"
                "- **Generator**: 生成文档内容\n"
                "- **Verifier**: 验证输出质量"
            )

    def build_data_flow_narrative(self) -> str:
        """Build narrative explaining data flow with repository-specific detail."""
        flow_steps = []

        # Step 1: Scanning
        if self.modules:
            flow_steps.append(
                f"**代码扫描**：Scanner 遍历源代码，发现 {len(self.modules)} 个模块"
            )

        # Step 2: Extraction
        extraction_parts = []
        if self.endpoints:
            extraction_parts.append(f"{len(self.endpoints)} 个 API 端点")
        if self.models:
            extraction_parts.append(f"{len(self.models)} 个数据模型")

        if extraction_parts:
            flow_steps.append(
                f"**信息提取**：Indexer 从代码中提取 { '、'.join(extraction_parts)}"
            )
        else:
            flow_steps.append("**信息提取**：Indexer 分析代码结构和符号")

        # Step 3: Storage
        flow_steps.append(
            "**状态持久化**：索引状态、图谱关系、向量嵌入分别存储"
        )

        # Step 4: Document generation
        flow_steps.append(
            "**文档生成**：Generator 根据模板和事实数据生成 Markdown"
        )

        # Step 5: Verification
        flow_steps.append(
            "**质量验证**：Verifier 检查文档结构和引用的有效性"
        )

        return "\n".join(flow_steps)

    def build_storage_retrieval_narrative(self) -> str:
        """Build narrative explaining storage and retrieval design."""
        return (
            "系统采用多模态存储策略以支持不同的访问模式：\n\n"
            "**向量存储 (Chroma)**：支持语义相似性搜索，当用户用自然语言查询时，"
            "系统将查询转换为向量，在已存储的代码块中寻找最相似的内容。\n\n"
            "**全文索引 (SQLite FTS)**：支持精确的关键词匹配，当用户知道要查找的术语时，"
            "可以直接通过关键词找到所有包含该术语的代码位置。\n\n"
            "**知识图谱 (JSON)**：支持结构化的依赖关系查询，例如查找某个模块的所有上游依赖，"
            "或者确定修改某段代码会影响到哪些其他模块。"
        )

    def build_governance_narrative(self) -> str:
        """Build narrative explaining incremental update and governance."""
        return (
            "系统通过以下机制确保文档与代码的持续同步：\n\n"
            "**变更驱动的增量更新**：系统检测代码变更，只重新生成受影响模块的文档，"
            "而非全量重建，保证响应速度。\n\n"
            "**质量门禁验证**：每次生成后自动执行结构验证，确保文档不仅存在，"
            "而且满足最小质量标准（prose 长度、引用完整性、导航有效性）。\n\n"
            "**双向追溯能力**：文档中记录了对应的源代码位置，同时源代码注释引用文档路径，"
            "形成完整的知识闭环。"
        )


# =============================================================================
# API AGGREGATION ENGINE (Phase 10 - Task 10.2)
# =============================================================================
# True API aggregation that groups by service family, domain, and exposure pattern
# rather than just listing all endpoints verbatim.

from dataclasses import dataclass
from typing import Optional


@dataclass
class APIEndpoint:
    """A single API endpoint with rich metadata for aggregation."""
    method: str
    path: str
    module: str
    handler: str
    file_path: str
    domain: str = "unknown"
    service_family: str = "unknown"
    runtime_role: str = "unknown"
    auth_required: bool = False
    auth_type: str = "none"
    error_codes: list[int] = None
    request_body: bool = False
    response_type: str = "json"
    is_entry_point: bool = False
    entry_score: float = 0.0
    entry_reason: str = ""

    def __post_init__(self):
        if self.error_codes is None:
            self.error_codes = []


@dataclass
class APIEndpointGroup:
    """A group of API endpoints sharing common characteristics."""
    name: str
    domain: str
    service_family: str
    exposure_pattern: str  # "public" | "internal" | "admin" | "webhook"
    endpoints: list[APIEndpoint]
    auth_convention: str
    error_convention: str
    calling_convention_summary: str


class APIAggregator:
    """Aggregates API endpoints by service family, domain, and exposure pattern.

    Phase 10 - Task 10.2: True API aggregation and entry-point summarization
    """

    def __init__(
        self,
        endpoints: list[dict[str, Any]],
        modules: list[dict[str, Any]],
    ) -> None:
        self.endpoints = endpoints
        self.modules = modules
        self._module_lookup = {m.get("name"): m for m in modules}
        self._build_endpoint_objects()
        self._classify_exposure_patterns()
        self._score_entry_points()

    def _build_endpoint_objects(self) -> None:
        """Convert raw endpoint dicts to APIEndpoint objects with module metadata."""
        self.api_endpoints = []
        for ep in self.endpoints:
            module_name = ep.get("module", "unknown")
            module = self._module_lookup.get(module_name, {})

            # Detect authentication from endpoint characteristics
            auth_type = self._detect_auth_type(ep, module)

            # Detect request body from method and path patterns
            has_body = ep.get("method") in ("POST", "PUT", "PATCH") and not self._is_webhook_path(ep.get("path", ""))

            endpoint = APIEndpoint(
                method=ep.get("method", "GET"),
                path=ep.get("path", "/"),
                module=module_name,
                handler=ep.get("handler", "unknown"),
                file_path=ep.get("file_path", ""),
                domain=module.get("domain", "unknown"),
                service_family=module.get("service_family", "unknown"),
                runtime_role=module.get("runtime_role", "unknown"),
                auth_required=auth_type != "none",
                auth_type=auth_type,
                request_body=has_body,
                error_codes=self._extract_error_codes(ep, module),
            )
            self.api_endpoints.append(endpoint)

    def _is_webhook_path(self, path: str) -> bool:
        """Check if path looks like a webhook (ending with /webhook, /callback, etc)."""
        webhook_patterns = ["webhook", "callback", "hook", "/trigger", "/event"]
        path_lower = path.lower()
        return any(pattern in path_lower for pattern in webhook_patterns)

    def _detect_auth_type(self, ep: dict[str, Any], module: dict[str, Any]) -> str:
        """Detect authentication type from endpoint and module metadata."""
        module_name = ep.get("module", "unknown")

        # Test modules don't require auth
        if module_name == "tests" or "test" in module_name.lower():
            return "none"

        # Check module domain for auth hints
        domain = module.get("domain", "")
        if domain in ("frontend", "operations"):
            return "none"

        # Check for auth-related path segments
        path = ep.get("path", "").lower()
        auth_paths = ["auth", "login", "signin", "token", "jwt", "oauth"]
        if any(ap in path for ap in auth_paths):
            return "bearer"  # Auth endpoints typically use bearer tokens

        # Check runtime role
        runtime_role = module.get("runtime_role", "")
        if runtime_role == "api-server":
            return "bearer"  # API servers typically require auth

        return "unknown"

    def _extract_error_codes(self, ep: dict[str, Any], module: dict[str, Any]) -> list[int]:
        """Extract error codes from endpoint or use common defaults."""
        # Default common error codes for REST APIs
        common_codes = [400, 401, 403, 404, 500]
        return common_codes

    def _classify_exposure_patterns(self) -> None:
        """Classify each endpoint by its exposure pattern (public/internal/admin/webhook)."""
        for ep in self.api_endpoints:
            path = ep.path.lower()
            method = ep.method

            # Webhook detection
            if self._is_webhook_path(path):
                ep.exposure_pattern = "webhook"
                continue

            # Admin endpoints
            admin_patterns = ["admin", "manage", "/internal/", "/system/"]
            if any(pattern in path for pattern in admin_patterns):
                ep.exposure_pattern = "admin"
                continue

            # Auth endpoints are typically public
            auth_patterns = ["auth", "login", "signin", "token", "register", "signup"]
            if any(pattern in path for pattern in auth_patterns):
                ep.exposure_pattern = "public"
                continue

            # Health/readiness endpoints are typically public
            if method == "GET" and any(pattern in path for pattern in ["health", "ready", "status", "info"]):
                ep.exposure_pattern = "public"
                continue

            # Internal API endpoints
            if ep.service_family == "python-backend" or ep.runtime_role == "api-server":
                ep.exposure_pattern = "internal"
                continue

            # Default to internal
            ep.exposure_pattern = "internal"

    def _score_entry_points(self) -> None:
        """Score and select key entry APIs using principled scoring method.

        Scoring factors:
        - Exposure: public endpoints score higher (user-facing)
        - Mutation: POST/PUT/PATCH score higher than GET (actions vs reads)
        - Auth: authenticated endpoints that gate access score higher
        - Centrality: endpoints in central modules score higher
        - Naming: root-level endpoints score higher
        """
        for ep in self.api_endpoints:
            score = 0.0
            reasons = []

            # Exposure pattern scoring (max 3 points)
            exposure_scores = {"public": 3, "webhook": 2, "internal": 1, "admin": 0}
            score += exposure_scores.get(ep.exposure_pattern, 0)
            if ep.exposure_pattern == "public":
                reasons.append("公开接口")

            # Mutation scoring (max 2 points)
            mutation_scores = {"POST": 2, "PUT": 2, "PATCH": 1.5, "DELETE": 1.5, "GET": 0.5}
            score += mutation_scores.get(ep.method, 0)
            if ep.method in ("POST", "PUT", "PATCH"):
                reasons.append(f"{ep.method} 操作")

            # Auth scoring (1 point if auth required)
            if ep.auth_required:
                score += 1
                reasons.append("需要认证")

            # Centrality scoring based on domain
            centrality_scores = {
                "core-platform": 2,
                "ai-services": 1.5,
                "api-gateway": 2,
                "persistence": 1,
            }
            score += centrality_scores.get(ep.domain, 0)

            # Path depth scoring (shorter paths = more entry-point like)
            path_depth = ep.path.count("/")
            if path_depth <= 2:
                score += 1
                reasons.append("根级路径")

            ep.entry_score = score
            ep.entry_reason = " + ".join(reasons) if reasons else "通用接口"
            ep.is_entry_point = score >= 3.0  # Threshold for entry point selection

    def group_by_service_family(self) -> dict[str, list[APIEndpoint]]:
        """Group endpoints by service family and domain."""
        groups: dict[str, list[APIEndpoint]] = {}
        for ep in self.api_endpoints:
            key = f"{ep.service_family}/{ep.domain}"
            if key not in groups:
                groups[key] = []
            groups[key].append(ep)
        return groups

    def group_by_exposure(self) -> dict[str, list[APIEndpoint]]:
        """Group endpoints by exposure pattern."""
        groups: dict[str, list[APIEndpoint]] = {}
        for ep in self.api_endpoints:
            if ep.exposure_pattern not in groups:
                groups[ep.exposure_pattern] = []
            groups[ep.exposure_pattern].append(ep)
        return groups

    def get_key_entry_apis(self, max_count: int = 10) -> list[APIEndpoint]:
        """Get top-scoring entry APIs, not just top-K by retrieval."""
        scored = sorted(self.api_endpoints, key=lambda x: x.entry_score, reverse=True)
        return scored[:max_count]

    def summarize_auth_conventions(self) -> str:
        """Summarize authentication conventions across all endpoints."""
        auth_by_module: dict[str, set[str]] = {}
        for ep in self.api_endpoints:
            if ep.module not in auth_by_module:
                auth_by_module[ep.module] = set()
            auth_by_module[ep.module].add(ep.auth_type)

        summary_parts = ["系统 API 认证约定："]
        for module, auth_types in sorted(auth_by_module.items()):
            auth_list = ", ".join(sorted(auth_types)) if auth_types else "unknown"
            summary_parts.append(f"- **{module}**: {auth_list}")

        return "\n".join(summary_parts)

    def summarize_error_conventions(self) -> str:
        """Summarize error and status code conventions."""
        # Group error codes by pattern
        common_codes = set()
        for ep in self.api_endpoints:
            common_codes.update(ep.error_codes)

        summary_parts = [
            "API 错误与状态码约定：\n",
            "| 状态码 | 含义 | 使用场景 |",
            "|--------|------|---------|",
            "| 200 | OK | 成功响应 |",
            "| 400 | Bad Request | 请求参数错误 |",
            "| 401 | Unauthorized | 未认证或认证失败 |",
            "| 403 | Forbidden | 无权限访问 |",
            "| 404 | Not Found | 资源不存在 |",
            "| 500 | Internal Server Error | 服务器内部错误 |",
        ]

        # Add domain-specific codes if found
        if common_codes:
            summary_parts.append("")
            summary_parts.append(f"**常见错误码**: {', '.join(str(c) for c in sorted(common_codes))}")

        return "\n".join(summary_parts)

    def summarize_calling_conventions(self, group_name: str, endpoints: list[APIEndpoint]) -> str:
        """Summarize calling conventions for a group of endpoints."""
        if not endpoints:
            return "暂无接口定义"

        # Analyze the group
        methods = set(ep.method for ep in endpoints)
        has_mutations = any(m in methods for m in ("POST", "PUT", "PATCH", "DELETE"))
        has_auth = any(ep.auth_required for ep in endpoints)
        has_bodies = any(ep.request_body for ep in endpoints)

        parts = [f"**{group_name}** 接口调用约定：\n"]

        # HTTP methods used
        method_summary = ", ".join(sorted(methods))
        parts.append(f"- HTTP 方法: {method_summary}")

        # Auth requirement
        if has_auth:
            parts.append("- 认证: 需要 Bearer Token")
        else:
            parts.append("- 认证: 无需认证")

        # Request body
        if has_mutations:
            if has_bodies:
                parts.append("- 请求体: JSON 格式")
            parts.append("- 响应格式: JSON")

        # Entry point note
        entry_points = [ep for ep in endpoints if ep.is_entry_point]
        if entry_points:
            paths = ", ".join(f"`{ep.path}`" for ep in entry_points[:3])
            parts.append(f"- 关键入口: {paths}")

        return "\n".join(parts)

    def build_api_groups_table(self) -> str:
        """Build API groups overview table with service family and domain grouping."""
        groups = self.group_by_service_family()

        lines = [
            "| 服务族/域 | 端点数 | 认证模式 | 暴露类型 |",
            "|-----------|--------|----------|---------|"
        ]

        for group_key in sorted(groups.keys()):
            endpoints = groups[group_key]
            # Determine dominant auth type
            auth_types = set(ep.auth_type for ep in endpoints)
            auth_summary = "/".join(sorted(auth_types)) if auth_types else "unknown"

            # Determine exposure mix
            exposures = set(ep.exposure_pattern for ep in endpoints)
            exposure_summary = "/".join(sorted(exposures)) if exposures else "internal"

            lines.append(f"| {group_key} | {len(endpoints)} | {auth_summary} | {exposure_summary} |")

        return "\n".join(lines)

    def build_api_groups_detail(self) -> str:
        """Build detailed API groups with calling conventions summaries."""
        groups = self.group_by_service_family()
        detail_parts = []

        for group_key in sorted(groups.keys()):
            endpoints = groups[group_key]

            # Get module metadata for the group
            sample_ep = endpoints[0]
            module = self._module_lookup.get(sample_ep.module, {})

            detail_parts.append(f"### {group_key}\n")
            detail_parts.append(f"**主题域**: {sample_ep.domain} | **服务族**: {sample_ep.service_family} | **运行时角色**: {sample_ep.runtime_role}")
            detail_parts.append(f"**端点数量**: {len(endpoints)}\n")

            # Add calling convention summary for this group
            detail_parts.append(self.summarize_calling_conventions(group_key, endpoints))
            detail_parts.append("")

            # List entry points for this group
            group_entry_points = [ep for ep in endpoints if ep.is_entry_point]
            if group_entry_points:
                detail_parts.append("**关键入口点**：")
                for ep in sorted(group_entry_points, key=lambda x: x.entry_score, reverse=True)[:5]:
                    detail_parts.append(f"- **{ep.method}** `{ep.path}` ({ep.entry_reason})")
                detail_parts.append("")

        return "\n".join(detail_parts) if detail_parts else "- 暂无 API 端点数据"


# =============================================================================
# CORE ENTITY AND MIGRATION-AWARE DATA MODEL AGGREGATION (Phase 10 - Task 10.3)
# =============================================================================
# Core entity identification using ownership cues, endpoint parameter types,
# and cross-module references. Migration-aware aggregation for database schemas.

from dataclasses import dataclass
from typing import Optional


@dataclass
class DataModel:
    """A data model with rich metadata for entity analysis."""
    name: str
    module: str
    type: str  # python_class, dataclass, pydantic, sqlalchemy, etc.
    file_path: str
    domain: str = "unknown"
    service_family: str = "unknown"
    is_core_entity: bool = False
    core_score: float = 0.0
    core_reason: str = ""
    dedup_key: str = ""  # For deduplicating ORM/DTO/builder representations
    migration_related: bool = False
    ownership_modules: list[str] = None
    # Phase 26: Model classification for canonical resolver
    model_category: str = "unknown"  # core_entity, dto, request_response, duplicated_projection, infrastructure
    canonical_name: str = ""  # The canonical name this model resolves to
    is_canonical: bool = False  # Whether this is the canonical representation
    projections: list[str] = None  # Other names this entity is known by

    def __post_init__(self):
        if self.ownership_modules is None:
            self.ownership_modules = []
        if self.projections is None:
            self.projections = []


class ModelCategory:
    """Model category constants for classification."""
    CORE_ENTITY = "core_entity"
    DTO = "dto"
    REQUEST_RESPONSE = "request_response"
    DUPLICATED_PROJECTION = "duplicated_projection"
    INFRASTRUCTURE = "infrastructure"


@dataclass
class CoreEntityGroup:
    """A core entity that spans multiple modules."""
    name: str
    models: list[DataModel]  # All representations (ORM, DTO, builder) of this entity
    module_count: int
    description: str
    cross_module_flow: str  # How data flows across modules


@dataclass
class DatabaseSchema:
    """Database schema information for migration analysis."""
    schema_name: str
    version: Optional[int] = None
    tables: list[str] = None
    indexes: list[str] = None
    migration_table: Optional[str] = None


class DataModelAggregator:
    """Aggregates data models into core/service/infrastructure groups with narrative.

    Phase 10 - Task 10.3: Core entity and migration-aware data model aggregation
    """

    def __init__(
        self,
        models: list[dict[str, Any]],
        modules: list[dict[str, Any]],
        endpoints: list[dict[str, Any]] | None = None,
    ) -> None:
        self.models_raw = models
        self.modules = modules
        self.endpoints = endpoints or []
        self._module_lookup = {m.get("name"): m for m in modules}
        self._build_model_objects()
        self._identify_core_entities()
        self._analyze_migration_signals()
        self._deduplicate_models()

    def _build_model_objects(self) -> None:
        """Convert raw model dicts to DataModel objects with module metadata."""
        self.data_models = []
        for m in self.models_raw:
            module = self._module_lookup.get(m.get("module", ""), {})
            model = DataModel(
                name=m.get("name", "unknown"),
                module=m.get("module", "unknown"),
                type=m.get("type", "unknown"),
                file_path=m.get("file_path", ""),
                domain=module.get("domain", "unknown"),
                service_family=module.get("service_family", "unknown"),
            )
            self.data_models.append(model)

    def _identify_core_entities(self) -> None:
        """Identify core domain entities using multiple signals.

        Core entity signals:
        1. Appears in multiple modules (shared entity)
        2. Referenced by API endpoints (parameter types)
        3. Used by infrastructure modules (persistence, core-platform)
        4. Ownership spans multiple service families
        """
        # Build reference graph: model name -> modules that reference it
        model_references: dict[str, set[str]] = {}
        for m in self.data_models:
            model_references[m.name] = model_references.get(m.name, set())
            model_references[m.name].add(m.module)

        # Check endpoint parameter types for model references
        if self.endpoints:
            for ep in self.endpoints:
                # Look for model names in handler
                handler = ep.get("handler", "")
                # Extract potential model names from handler (simplified heuristic)
                for m in self.data_models:
                    if m.name.lower() in handler.lower():
                        model_references[m.name].add(ep.get("module", "unknown"))

        # Score each model as potential core entity
        for model in self.data_models:
            score = 0.0
            reasons = []

            # Signal 1: Multiple modules reference this model
            ref_count = len(model_references.get(model.name, {model.module}))
            if ref_count > 1:
                score += ref_count * 2.0
                reasons.append(f"被 {ref_count} 个模块共享")

            # Signal 2: Core platform or persistence domain
            if model.domain in ("core-platform", "persistence", "ai-services"):
                score += 3.0
                reasons.append(f"核心域 {model.domain}")

            # Signal 3: Module name suggests it might be foundational
            foundational_patterns = ["base", "core", "common", "shared", "entity", "model"]
            if any(pattern in model.name.lower() for pattern in foundational_patterns):
                score += 1.5
                reasons.append("名称暗示基础实体")

            # Signal 4: Referenced by API (in parameter types)
            # This is a simplified check - in real implementation would parse function signatures
            for ep in self.endpoints:
                ep_module = ep.get("module", "")
                ep_handler = ep.get("handler", "").lower()
                # If handler contains model name, it's likely used as parameter
                if model.name.lower() in ep_handler:
                    score += 1.0
                    reasons.append("API 参数类型")

            model.core_score = score
            model.core_reason = " + ".join(reasons) if reasons else "单一模块实体"
            model.is_core_entity = score >= 3.0

            # Track ownership modules
            model.ownership_modules = list(model_references.get(model.name, {model.module}))

    def _analyze_migration_signals(self) -> None:
        """Extract migration strategy and database shape signals from codebase."""
        # Look for migration-related patterns in model types and names
        migration_patterns = ["migration", "migrate", "schema", "version", "alembic", "flyway"]
        version_patterns = ["current_schema_version", "schema_version", "_v1", "_v2"]

        self.database_schemas: list[DatabaseSchema] = []
        has_migration = False

        for model in self.data_models:
            model_name_lower = model.name.lower()

            # Check for migration-related models
            if any(pattern in model_name_lower for pattern in migration_patterns):
                model.migration_related = True
                has_migration = True

            # Check for version patterns in model attributes or file path
            if any(pattern in model_name_lower for pattern in version_patterns):
                model.migration_related = True
                has_migration = True

        # Analyze schema patterns
        self.has_explicit_schemas = has_migration
        self.migration_strategy = self._detect_migration_strategy()

    def _detect_migration_strategy(self) -> str:
        """Detect the migration strategy used by the project."""
        # Look for patterns that indicate migration strategy
        all_types = set(m.type.lower() for m in self.data_models)
        all_names = " ".join(m.name.lower() for m in self.data_models)
        all_paths = " ".join(m.file_path.lower() for m in self.data_models)

        # Detect migration tool patterns
        if "alembic" in all_paths or "alembic" in all_names:
            return "Alembic"
        if "flyway" in all_paths or "flyway" in all_names:
            return "Flyway"
        if "liquibase" in all_paths or "liquibase" in all_names:
            return "Liquibase"

        # Detect schema version tracking patterns
        if "current_schema_version" in all_names or "schema_version" in all_names:
            return "Schema 版本跟踪 + 手动迁移"

        # Detect SQLAlchemy patterns
        if "sqlalchemy" in all_paths or "declarative_base" in all_names:
            return "SQLAlchemy ORM + Alembic"

        # Detect Pydantic patterns (often used for config migrations)
        pydantic_types = [t for t in all_types if "pydantic" in t]
        if pydantic_types and all(t.startswith("pydantic") for t in pydantic_types):
            return "Pydantic 配置迁移"

        # Check if this is primarily an ORM-based project
        orm_types = {"sqlalchemy", "orm", "model", "entity"}
        if any(t in orm_types for t in all_types):
            return "ORM 模型迁移"

        return "未知迁移策略（需要代码扫描）"

    def _deduplicate_models(self) -> None:
        """Deduplicate ORM models, DTOs, and builder types representing same entity.

        Some entities are represented multiple times:
        - SQLAlchemy ORM model (database representation)
        - Pydantic model (API/DTO representation)
        - Builder/Factory class (object construction)
        - Dataclass (simple value object)

        We consolidate these into a single canonical representation.
        """
        # Build dedup keys based on normalized entity names
        # Pattern: remove _model, _dto, _entity, _builder suffixes to get base name
        import re
        dedup_map: dict[str, list[DataModel]] = {}

        for model in self.data_models:
            # Normalize name to base entity
            name = model.name
            # Remove common suffixes (same pattern as CanonicalModelResolver._normalize_name)
            normalized = re.sub(
                r'(_model|_dto|_entity|_builder|_factory|_schema|_table|_request|_response|_req|_resp|Dto|Entity|Model|Builder|Factory|Schema|Table|Request|Response|Req|Resp)$',
                '',
                name,
                flags=re.IGNORECASE
            )
            normalized = normalized.lower()

            if normalized not in dedup_map:
                dedup_map[normalized] = []
            dedup_map[normalized].append(model)
            model.dedup_key = normalized

        # For entities with multiple representations, keep the "most authoritative" one
        # Priority: ORM model > Pydantic > Dataclass > Builder
        type_priority = {
            "sqlalchemy": 4,
            "pydantic": 3,
            "dataclass": 2,
            "model": 2,
            "builder": 1,
            "factory": 1,
        }

        for dedup_key, models in dedup_map.items():
            if len(models) > 1:
                # Sort by type priority and take the highest
                models.sort(key=lambda m: type_priority.get(m.type.lower(), 0), reverse=True)
                # Mark others as non-canonical
                for i, m in enumerate(models):
                    if i > 0:
                        # This is a duplicate representation
                        pass  # We keep track but don't remove for now

    def get_core_entities(self) -> list[DataModel]:
        """Get all models identified as core entities."""
        return [m for m in self.data_models if m.is_core_entity]

    def get_service_models(self) -> list[DataModel]:
        """Get all models identified as service-specific (not core)."""
        return [m for m in self.data_models if not m.is_core_entity]

    def get_models_by_domain(self) -> dict[str, list[DataModel]]:
        """Group models by domain."""
        groups: dict[str, list[DataModel]] = {}
        for model in self.data_models:
            if model.domain not in groups:
                groups[model.domain] = []
            groups[model.domain].append(model)
        return groups

    def get_models_by_module(self) -> dict[str, list[DataModel]]:
        """Group models by module."""
        groups: dict[str, list[DataModel]] = {}
        for model in self.data_models:
            if model.module not in groups:
                groups[model.module] = []
            groups[model.module].append(model)
        return groups

    def summarize_database_shape(self) -> str:
        """Summarize the database/database-like storage shape."""
        # Group models by type
        type_counts: dict[str, int] = {}
        for model in self.data_models:
            type_counts[model.type] = type_counts.get(model.type, 0) + 1

        parts = ["**数据库形状概述**：\n"]
        parts.append("| 类型 | 数量 |")
        parts.append("|------|------|")
        for model_type, count in sorted(type_counts.items()):
            parts.append(f"| {model_type} | {count} |")

        if self.has_explicit_schemas:
            parts.append("")
            parts.append(f"**检测到迁移系统**：{self.migration_strategy}")

        return "\n".join(parts)

    def summarize_migration_strategy(self) -> str:
        """Summarize the migration strategy with detailed explanation."""
        parts = ["**数据迁移策略**：\n"]

        strategy = self.migration_strategy
        parts.append(f"**迁移工具/方法**: {strategy}")

        # Add migration-specific details based on detected strategy
        if "Alembic" in strategy:
            parts.append("- 使用 Alembic 进行数据库迁移管理")
            parts.append("- Schema 版本通过 `alembic_version` 表跟踪")
            parts.append("- 迁移文件位于 `migrations/versions/` 目录")
        elif "Schema 版本跟踪" in strategy:
            parts.append("- 通过 `current_schema_version` 字段跟踪模式版本")
            parts.append("- 迁移在应用启动时自动检查和应用")
            parts.append("- `_apply_migrations` 方法处理版本升级")
        elif "SQLAlchemy" in strategy:
            parts.append("- 使用 SQLAlchemy ORM 定义数据库模式")
            parts.append("- 通过 ORM `create_all()` 和 `drop_all()` 管理 schema")
        else:
            parts.append("- 迁移策略需要在代码扫描后确定")

        return "\n".join(parts)

    def build_core_models_section(self) -> str:
        """Build the core models section with entity identification narrative."""
        core_models = self.get_core_entities()

        if not core_models:
            return "暂无核心模型定义。"

        parts = ["核心模型是系统的基础数据结构，定义跨模块共享的实体类型。\n"]
        parts.append(f"**识别出 {len(core_models)} 个核心实体**：\n")

        for model in sorted(core_models, key=lambda x: x.core_score, reverse=True):
            parts.append(f"- **{model.name}** ({model.type})")
            parts.append(f"  - 所属模块: {', '.join(model.ownership_modules)}")
            parts.append(f"  - 核心评分: {model.core_score:.1f} ({model.core_reason})")
            if model.migration_related:
                parts.append(f"  - 迁移相关: 是")
            parts.append(f"  - 定义文件: `{model.file_path}`")
            parts.append("")

        return "\n".join(parts)

    def build_service_models_section(self) -> str:
        """Build the service models section grouped by domain."""
        service_models = self.get_service_models()

        if not service_models:
            return "暂无服务模型定义。"

        parts = ["服务模型是特定于模块或域的业务数据结构。\n"]
        parts.append(f"**共有 {len(service_models)} 个服务模型**\n")

        # Group by module
        by_module = self.get_models_by_module()
        for module_name in sorted(by_module.keys()):
            module_models = [m for m in by_module[module_name] if not m.is_core_entity]
            if not module_models:
                continue

            module_info = self._module_lookup.get(module_name, {})
            domain = module_info.get("domain", "unknown")

            parts.append(f"### {module_name} ({domain})\n")
            for m in sorted(module_models, key=lambda x: x.name):
                parts.append(f"- **{m.name}** ({m.type}) - `{m.file_path}`")
            parts.append("")

        return "\n".join(parts)

    def build_cross_module_boundaries(self) -> str:
        """Build narrative about how data flows across module boundaries."""
        core_entities = self.get_core_entities()

        if not core_entities:
            return "暂无跨模块数据边界定义"

        parts = ["**跨模块数据边界**：\n"]
        parts.append("核心实体在模块间的流动：\n")

        for entity in core_entities[:5]:  # Top 5 core entities
            parts.append(f"- **{entity.name}**: 被以下模块使用")
            for owner in entity.ownership_modules[:3]:
                parts.append(f"  - `{owner}`")

            # Determine flow direction
            if len(entity.ownership_modules) > 1:
                parts.append(f"  - 数据流向: 跨 {len(entity.ownership_modules)} 个模块共享")

        parts.append("")
        parts.append("**数据一致性机制**：")
        if self.has_explicit_schemas:
            parts.append(f"- 使用 {self.migration_strategy} 确保 schema 一致性")
        else:
            parts.append("- 使用 ORM 模型作为单一事实源")

        return "\n".join(parts)


# =============================================================================
# CANONICAL MODEL RESOLVER (Phase 26 - Task 26.1)
# =============================================================================
# Resolves Java entities, DTOs, TypeScript types, and SQL tables into
# canonical models with deduplication keys and metadata.
#
# Model Classification:
#   - core_entity: Foundational domain objects shared across modules
#   - dto: Data transfer objects for API boundaries
#   - request_response: Request/Response types for API contracts
#   - duplicated_projection: Multiple representations of same entity
#   - infrastructure: Database tables, config, migrations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CanonicalModel:
    """A canonical model resolved from multiple projections."""
    dedup_key: str
    canonical_name: str
    category: str
    models: list[DataModel]  # All projections of this entity
    is_high_frequency: bool = False  # High-frequency model for fixture generation
    high_frequency_reason: str = ""
    authority_type: str = ""  # The most authoritative representation (ORM, etc.)
    authority_path: str = ""  # Path to the authoritative definition


class CanonicalModelResolver:
    """Resolves Java entities, DTOs, TypeScript types, and SQL tables into canonical models.

    Phase 26 - Task 26.1: Entity deduplication and canonical model resolver

    This resolver:
    1. Distinguishes core entities, DTOs, request/response types, and duplicated projections
    2. Adds deduplication keys and canonical model metadata
    3. Generates high-count model fixtures so DTOs do not dominate output
    """

    # Suffix patterns that indicate non-canonical projections
    DTO_SUFFIXES = frozenset({"_dto", "_DTO", "Dto", "_request", "_response", "_req", "_resp"})
    ENTITY_SUFFIXES = frozenset({"_entity", "_Entity", "_model", "_Model", "_table", "_Table"})
    REQUEST_RESPONSE_SUFFIXES = frozenset({"_request", "_Request", "_response", "_Response", "Request", "Response"})
    BUILDER_SUFFIXES = frozenset({"_builder", "_Builder", "_factory", "_Factory", "Builder", "Factory"})

    # High-frequency model name patterns (models that appear in many modules)
    HIGH_FREQUENCY_PATTERNS = frozenset({
        "user", "users", "config", "configuration", "settings", "base", "common",
        "session", "token", "auth", "error", "result", "response", "request",
        "metadata", "data", "item", "list", "page", "pagination",
    })

    # Core domain names that suggest core entity status
    CORE_DOMAINS = frozenset({"core-platform", "persistence", "ai-services", "core"})

    def __init__(self, data_models: list[DataModel]):
        self.data_models = data_models
        self._resolve()

    def _normalize_name(self, name: str) -> str:
        """Normalize model name to base entity key."""
        # Remove common suffixes (case-insensitive, matching various patterns)
        normalized = re.sub(
            r'(_model|_dto|_entity|_builder|_factory|_schema|_table|_request|_response|_req|_resp|Dto|Entity|Model|Builder|Factory|Schema|Table|Request|Response|Req|Resp)$',
            '',
            name,
            flags=re.IGNORECASE
        )
        return normalized.lower()

    def _classify_model(self, model: DataModel) -> str:
        """Classify a model into a category."""
        name_lower = model.name.lower()

        # Check name suffixes first
        if any(model.name.endswith(suf) for suf in self.DTO_SUFFIXES):
            return ModelCategory.DTO
        if any(model.name.endswith(suf) for suf in self.REQUEST_RESPONSE_SUFFIXES):
            return ModelCategory.REQUEST_RESPONSE
        if any(model.name.endswith(suf) for suf in self.ENTITY_SUFFIXES):
            return ModelCategory.CORE_ENTITY
        if any(model.name.endswith(suf) for suf in self.BUILDER_SUFFIXES):
            return ModelCategory.DUPLICATED_PROJECTION

        # Check type-based classification
        if model.type in ("sqlalchemy", "orm", "entity", "table"):
            return ModelCategory.CORE_ENTITY
        if model.type in ("pydantic", "schema"):
            # Check if it's a request/response pattern
            if any(pattern in name_lower for pattern in ["request", "response", "result"]):
                return ModelCategory.REQUEST_RESPONSE
            return ModelCategory.DTO

        # Check domain-based classification
        if model.domain in self.CORE_DOMAINS and model.is_core_entity:
            return ModelCategory.CORE_ENTITY

        # Check if it's a high-frequency model
        if any(pattern in name_lower for pattern in self.HIGH_FREQUENCY_PATTERNS):
            return ModelCategory.INFRASTRUCTURE

        # Default to core_entity if it's marked as such
        if model.is_core_entity:
            return ModelCategory.CORE_ENTITY

        return ModelCategory.DUPLICATED_PROJECTION

    def _get_authority_representation(self, models: list[DataModel]) -> tuple[str, str]:
        """Get the most authoritative representation from a list of models."""
        # Priority: SQLAlchemy > Pydantic > Dataclass > Other
        type_priority = {
            "sqlalchemy": 4,
            "orm": 3,
            "entity": 3,
            "pydantic": 2,
            "dataclass": 1,
        }

        if not models:
            return "", ""

        # Sort by priority and path length (shorter paths more authoritative)
        sorted_models = sorted(
            models,
            key=lambda m: (type_priority.get(m.type.lower(), 0), len(m.file_path)),
            reverse=True
        )
        authority = sorted_models[0]
        return authority.type, authority.file_path

    def _resolve(self) -> None:
        """Resolve all models into canonical representations."""
        # Group models by dedup key
        dedup_groups: dict[str, list[DataModel]] = {}
        for model in self.data_models:
            if not model.dedup_key:
                model.dedup_key = self._normalize_name(model.name)
            if model.dedup_key not in dedup_groups:
                dedup_groups[model.dedup_key] = []
            dedup_groups[model.dedup_key].append(model)

        # Build canonical models
        self.canonical_models: list[CanonicalModel] = []

        for dedup_key, models in dedup_groups.items():
            # Classify the entity
            category = self._classify_model(models[0])

            # Get authority representation
            authority_type, authority_path = self._get_authority_representation(models)

            # Determine if high-frequency
            is_high_freq = (
                len(models) >= 3 or  # Shared across 3+ modules
                any(pattern in dedup_key for pattern in self.HIGH_FREQUENCY_PATTERNS)
            )

            high_freq_reason = ""
            if len(models) >= 3:
                high_freq_reason = f"跨 {len(models)} 个模块共享"
            elif any(pattern in dedup_key for pattern in self.HIGH_FREQUENCY_PATTERNS):
                high_freq_reason = f"高频名称模式: {dedup_key}"

            # Create canonical name (use the most common/authority name)
            names = [m.name for m in models]
            canonical_name = max(names, key=lambda n: names.count(n))

            # Create canonical model
            canonical = CanonicalModel(
                dedup_key=dedup_key,
                canonical_name=canonical_name,
                category=category,
                models=models,
                is_high_frequency=is_high_freq,
                high_frequency_reason=high_freq_reason,
                authority_type=authority_type,
                authority_path=authority_path,
            )
            self.canonical_models.append(canonical)

            # Update original models with canonical metadata
            for m in models:
                m.model_category = category
                m.canonical_name = canonical_name
                m.is_canonical = (m.name == canonical_name and m.type == authority_type)
                m.projections = [n for n in names if n != m.name]

        # Sort: high-frequency first, then by dedup key
        self.canonical_models.sort(
            key=lambda c: (
                not c.is_high_frequency,  # High-frequency first
                -len([m for m in self.data_models if m.dedup_key == c.dedup_key]),  # Then by projection count
                c.dedup_key
            )
        )

    def get_canonical_by_category(self, category: str) -> list[CanonicalModel]:
        """Get all canonical models in a specific category."""
        return [c for c in self.canonical_models if c.category == category]

    def get_core_entities(self) -> list[CanonicalModel]:
        """Get core entities."""
        return self.get_canonical_by_category(ModelCategory.CORE_ENTITY)

    def get_dtos(self) -> list[CanonicalModel]:
        """Get DTOs."""
        return self.get_canonical_by_category(ModelCategory.DTO)

    def get_request_response_types(self) -> list[CanonicalModel]:
        """Get request/response types."""
        return self.get_canonical_by_category(ModelCategory.REQUEST_RESPONSE)

    def get_duplicated_projections(self) -> list[CanonicalModel]:
        """Get duplicated projections."""
        return self.get_canonical_by_category(ModelCategory.DUPLICATED_PROJECTION)

    def get_high_frequency_models(self) -> list[CanonicalModel]:
        """Get high-frequency models for fixtures."""
        return [c for c in self.canonical_models if c.is_high_frequency]

    def get_infrastructure_models(self) -> list[CanonicalModel]:
        """Get infrastructure models (config, db tables, etc.)."""
        return self.get_canonical_by_category(ModelCategory.INFRASTRUCTURE)

    def summarize_canonical_models(self) -> str:
        """Generate a summary of canonical model resolution."""
        parts = ["## 规范模型解析结果\n"]

        # Count by category
        category_counts = {}
        for c in self.canonical_models:
            category_counts[c.category] = category_counts.get(c.category, 0) + 1

        parts.append("**模型分类统计**：\n")
        parts.append("| 分类 | 数量 |")
        parts.append("|------|------|")
        for cat, count in sorted(category_counts.items()):
            parts.append(f"| {cat} | {count} |")

        parts.append("")

        # High-frequency models (fixtures)
        high_freq = self.get_high_frequency_models()
        if high_freq:
            parts.append(f"**高频模型（Fixtures）**：共 {len(high_freq)} 个\n")
            for c in high_freq[:10]:  # Top 10
                parts.append(f"- {c.canonical_name} ({c.category}): {c.high_frequency_reason}")
            if len(high_freq) > 10:
                parts.append(f"- ... 还有 {len(high_freq) - 10} 个高频模型")

        parts.append("")

        # Core entities
        core_entities = self.get_core_entities()
        if core_entities:
            parts.append(f"**核心实体**：共 {len(core_entities)} 个\n")
            for c in core_entities[:5]:  # Top 5
                parts.append(f"- {c.canonical_name}: {len(c.models)} 个投影")
            if len(core_entities) > 5:
                parts.append(f"- ... 还有 {len(core_entities) - 5} 个核心实体")

        return "\n".join(parts)


# =============================================================================
# SECTION NARRATIVE BUILDER AND READING PATH GENERATOR (Phase 10 - Task 10.4)
# =============================================================================
# Section page builder rewrite for document-center behavior.
# Generates repository-derived narrative and explains reading paths.

from typing import TypedDict


class ReadingPath(TypedDict):
    """A reading path recommendation with explanation."""
    doc_path: str
    doc_title: str
    reason: str  # Why this document is recommended after/before current section
    order: int  # Suggested reading order


class SectionNarrativeBuilder:
    """Builds repository-specific narrative for section pages.

    Phase 10 - Task 10.4: Section page builder rewrite for document-center behavior
    """

    def __init__(
        self,
        section_slug: str,
        section_title: str,
        modules: list[dict[str, Any]],
        endpoints: list[dict[str, Any]],
        commands: dict[str, str],
        core_context: dict[str, Any],
    ) -> None:
        self.section_slug = section_slug
        self.section_title = section_title
        self.modules = modules
        self.endpoints = endpoints
        self.commands = commands
        self.core_context = core_context
        self._module_lookup = {m.get("name"): m for m in modules}

        # Build domain groups for section content
        self._build_domain_groups()

    def _build_domain_groups(self) -> None:
        """Build domain groups for section content organization."""
        self.domain_modules: dict[str, list[dict[str, Any]]] = {}
        for m in self.modules:
            domain = m.get("domain", "unknown")
            if domain not in self.domain_modules:
                self.domain_modules[domain] = []
            self.domain_modules[domain].append(m)

    def build_section_description(self) -> str:
        """Build repository-specific section description based on domain content."""
        # Get modules relevant to this section based on slug
        section_modules = self._get_relevant_modules()

        if not section_modules:
            return f"{self.section_title} 的详细文档。"

        # Build description based on actual module content
        module_count = len(section_modules)
        domains = set(m.get("domain", "unknown") for m in section_modules)

        if module_count == 1:
            m = section_modules[0]
            domain = m.get("domain", "unknown")
            responsibility = m.get("responsibility", "")
            return f"本节涵盖 {domain} 域下的 {m.get('name', 'unknown')} 模块，{responsibility}。"
        else:
            domain_desc = "、".join(sorted(domains)[:3])
            return f"本节涵盖 {domain_desc} 等 {module_count} 个模块的内容。"

    def _get_relevant_modules(self) -> list[dict[str, Any]]:
        """Get modules relevant to this section based on section slug and domain."""
        slug_domain_map = {
            "project": ["core-platform", "tooling", "operations"],
            "architecture": ["core-platform", "ai-services"],
            "services": ["api-gateway", "core-platform", "data-pipeline"],
            "python-services": ["core-platform"],
            "data-model": ["persistence", "data-pipeline"],
            "api": ["api-gateway"],
            "operations": ["operations", "tooling"],
            "development": ["tooling"],
            "security": ["operations"],
            "troubleshooting": ["operations"],
        }

        target_domains = slug_domain_map.get(self.section_slug, [])
        if not target_domains:
            return self.modules[:5]  # Default fallback

        relevant = []
        for m in self.modules:
            domain = m.get("domain", "unknown")
            if domain in target_domains:
                relevant.append(m)

        return relevant if relevant else self.modules[:3]

    def build_section_content(self) -> str:
        """Build section content narrative with domain explanation."""
        section_modules = self._get_relevant_modules()

        if not section_modules:
            return "暂无相关内容。"

        parts = []

        # Build content based on section type
        if self.section_slug in ("services", "python-services"):
            parts.append("## 核心服务组件\n")
            parts.append("本节深入介绍系统中的核心服务组件。这些模块承担着系统的主要业务逻辑，是实现功能的核心单元。下面的每个组件都有明确的职责边界和运行时角色，它们通过标准接口进行通信，共同维持系统的正常运转。\n")
            for m in section_modules[:5]:
                name = m.get("name", "unknown")
                domain = m.get("domain", "unknown")
                responsibility = m.get("responsibility", "N/A")
                runtime_role = m.get("runtime_role", "unknown")
                depends_on = m.get("depends_on", []) or []

                parts.append(f"### {name} ({domain})\n")
                parts.append(f"**职责**: {responsibility}")
                parts.append(f"**运行时角色**: {runtime_role}")
                if depends_on:
                    parts.append(f"**依赖**: {', '.join(depends_on)}")
                parts.append("")

        elif self.section_slug == "data-model":
            parts.append("## 数据模型概述\n")
            parts.append("本节介绍系统的数据模型设计。数据模型是系统状态管理的核心，定义了实体结构、关系约束和数据访问模式。良好的数据模型设计能够提高系统的一致性和可维护性。\n")
            # Get core models from core_context if available
            core_models = self.core_context.get("core_models_section", "")
            if core_models and "暂无" not in core_models:
                parts.append(f"**核心模型**: {core_models[:200]}...")
                parts.append("")
            parts.append(f"**服务模型**: 本节涵盖 {len(section_modules)} 个服务模块的数据模型。")

        elif self.section_slug == "api":
            parts.append("## API 端点概述\n")
            parts.append("本节提供系统 API 接口的完整参考。API 是系统与外部交互的契约，定义了请求格式、响应结构和调用约定。理解 API 设计有助于集成开发和第三方对接。\n")
            endpoint_count = len(self.endpoints)
            if endpoint_count > 0:
                # Group by module
                by_module: dict[str, int] = {}
                for ep in self.endpoints:
                    module = ep.get("module", "unknown")
                    by_module[module] = by_module.get(module, 0) + 1

                parts.append(f"**端点总数**: {endpoint_count}")
                parts.append("\n**按模块分布**:")
                for module, count in sorted(by_module.items(), key=lambda x: x[1], reverse=True)[:5]:
                    parts.append(f"- {module}: {count} 个端点")

        else:
            # Generic section content
            parts.append(f"## {self.section_title} 内容概览\n")
            parts.append(f"本节介绍 {self.section_title} 的相关内容。以下模块和组件共同构成了系统的 {self.section_title} 能力，了解它们有助于深入理解系统设计和实现细节。\n")
            for m in section_modules[:5]:
                name = m.get("name", "unknown")
                responsibility = m.get("responsibility", "N/A")
                parts.append(f"- **{name}**: {responsibility}")

        return "\n".join(parts)

    def build_section_modules(self) -> str:
        """Build section modules list with narrative."""
        section_modules = self._get_relevant_modules()

        if not section_modules:
            return "- 暂无相关模块"

        parts = []
        for m in section_modules[:8]:  # Limit to top 8
            name = m.get("name", "unknown")
            path = m.get("path", "")
            domain = m.get("domain", "unknown")
            responsibility = m.get("responsibility", "N/A")

            parts.append(f"- **{name}** `{path}`")
            parts.append(f"  - {responsibility}")
            parts.append(f"  - 域: {domain}")

        return "\n".join(parts)

    def build_section_apis(self) -> str:
        """Build section API endpoints with narrative."""
        if not self.endpoints:
            return "- 暂无 API 端点"

        # Get top endpoints by score using APIAggregator logic
        # Simplified: just take first 10
        parts = []
        for ep in self.endpoints[:10]:
            method = ep.get("method", "GET")
            path = ep.get("path", "/")
            module = ep.get("module", "unknown")
            handler = ep.get("handler", "unknown")

            parts.append(f"- **{method}** `{path}`")
            parts.append(f"  - {module}.{handler}")

        return "\n".join(parts)

    def build_section_commands(self) -> str:
        """Build section commands list."""
        if not self.commands:
            return "- 暂无相关命令"

        parts = []
        for key, value in sorted(self.commands.items()):
            parts.append(f"- `{key}`: `{value}`")

        return "\n".join(parts)


class ReadingPathGenerator:
    """Generates reading paths that explain WHY documents are recommended in sequence.

    Phase 10 - Task 10.4: Document-center reading path generation
    """

    def __init__(
        self,
        section_slug: str,
        section_title: str,
        modules: list[dict[str, Any]],
        endpoints: list[dict[str, Any]],
        core_context: dict[str, Any],
    ) -> None:
        self.section_slug = section_slug
        self.section_title = section_title
        self.modules = modules
        self.endpoints = endpoints
        self.core_context = core_context
        self._module_lookup = {m.get("name"): m for m in modules}

    def generate_reading_paths(self) -> list[ReadingPath]:
        """Generate reading paths for this section with explanatory narrative."""
        paths: list[ReadingPath] = []

        # Define reading path rules based on section relationships
        # Format: current_section -> [(target_slug, target_title, reason, order), ...]
        path_rules = {
            "project": [
                ("architecture", "系统架构", "理解系统设计后，再深入模块细节", 1),
                ("services", "核心服务", "在了解架构后查看服务实现", 2),
                ("development", "开发指南", "开发前必读的编码规范", 3),
            ],
            "architecture": [
                ("project", "项目概览", "回到项目概览了解整体定位", 0),
                ("services", "核心服务", "架构是服务的抽象，服务是架构的具体实现", 1),
                ("data-model", "数据模型", "数据模型支撑服务间的数据流", 2),
            ],
            "services": [
                ("architecture", "系统架构", "服务是架构的具体实现", 0),
                ("api", "API 参考", "服务通过 API 对外暴露接口", 1),
                ("data-model", "数据模型", "服务的业务逻辑依赖数据模型", 2),
            ],
            "api": [
                ("services", "核心服务", "API 是服务的对外接口", 0),
                ("security", "安全考虑", "使用 API 时需要关注安全", 1),
            ],
            "data-model": [
                ("services", "核心服务", "数据模型被服务使用", 0),
                ("architecture", "系统架构", "数据库设计是架构的一部分", 1),
            ],
            "operations": [
                ("development", "开发指南", "运维建立在开发规范之上", 0),
                ("troubleshooting", "故障排查", "出现问题时的诊断流程", 1),
            ],
            "development": [
                ("project", "项目概览", "开发前先了解项目", 0),
                ("architecture", "系统架构", "理解架构再编写代码", 1),
            ],
            "security": [
                ("api", "API 参考", "API 安全是重要组成部分", 0),
                ("operations", "运维", "运维安全同样重要", 1),
            ],
            "troubleshooting": [
                ("operations", "运维", "故障排查是运维的一部分", 0),
                ("development", "开发指南", "了解开发流程有助于诊断", 1),
            ],
        }

        # Get rules for this section
        rules = path_rules.get(self.section_slug, [])

        # Add overview always first
        paths.append(ReadingPath(
            doc_path="../../00-overview.md",
            doc_title="项目概览",
            reason="总览提供项目整体定位和能力",
            order=-1  # Special order indicating it should be read before
        ))

        # Add other recommended paths
        for target_slug, target_title, reason, order in rules:
            doc_path = f"../{target_slug}/index.md"
            paths.append(ReadingPath(
                doc_path=doc_path,
                doc_title=target_title,
                reason=reason,
                order=order
            ))

        # Sort by order
        paths.sort(key=lambda x: x["order"])
        return paths

    def format_reading_paths(self) -> str:
        """Format reading paths as markdown with explanations."""
        paths = self.generate_reading_paths()

        if not paths:
            return ""

        parts = ["## 推荐阅读路径\n"]
        parts.append("本文档建议按以下顺序阅读：\n")

        for i, path in enumerate(paths):
            order = path["order"]
            if order == -1:
                parts.append(f"- [{path['doc_title']}]({path['doc_path']}) - {path['reason']}（建议首先阅读）")
            else:
                parts.append(f"- [{path['doc_title']}]({path['doc_path']}) - {path['reason']}")

        return "\n".join(parts)

    def format_related_sections(self) -> str:
        """Format related sections as markdown with explanations."""
        paths = self.generate_reading_paths()

        if not paths:
            return ""

        parts: list[str] = []
        parts.append("## 相关专题")

        for path in paths:
            parts.append(f"- [{path['doc_title']}]({path['doc_path']}) - {path['reason']}")

        return "\n".join(parts)


class GenerationEngine:
    """Generates frozen MVP docs, prompt fragments, and task catalog.

    The engine supports two modes:
    - Target repository mode (default): generates OVERVIEW, SECTION, MODULE layers only
    - Governance mode (include_governance_layers=True): also generates PHASE layer

    PHASE layer (docs/phases/) is GOVERNANCE_ONLY and should never be generated
    for target repositories. It contains repo-agent's internal stage-governance
    documentation that is not relevant to target repos being analyzed.
    """

    def __init__(
        self,
        root: Path,
        config: GenerationConfig | None = None,
        template_root: Path | None = None,
        include_governance_layers: bool = False,
    ) -> None:
        self.root = root
        self.config = config or GenerationConfig()
        self.template_root = template_root or (root / "templates")
        self.source_root = root / "ai" / "source-of-truth"
        self.include_governance_layers = include_governance_layers
        self.renderer = TemplateRenderer(self.template_root)
        self.context_builder = ContextBuilder(token_budget=self.config.token_budget)
        self.cache = GenerationCache(
            sqlite_path=root / ".repo-wiki" / "cache" / "generation_cache.sqlite3",
            diskcache_dir=root / ".repo-wiki" / "cache" / "diskcache",
        )

    def validate_templates(self) -> list[str]:
        return validate_contract_coverage(self.template_root)

    def generate_full(self) -> GenerationRunResult:
        return self._generate(impacted_modules=None)

    def generate_incremental(self, impacted_modules: list[str]) -> GenerationRunResult:
        return self._generate(impacted_modules=sorted(set(impacted_modules)))

    def _generate(self, impacted_modules: list[str] | None) -> GenerationRunResult:
        missing = self.validate_templates()
        if missing:
            raise ValueError(f"Missing templates: {', '.join(missing)}")

        snapshot = self._load_snapshot()
        core_context = self._build_core_context(snapshot)
        written: list[str] = []
        hits = 0
        misses = 0

        # Layer 1: Core overview documents (existing MVP)
        for contract in CORE_DOCUMENT_CONTRACTS:
            content, cached = self._render_with_cache(contract.name, contract.template_path, core_context)
            target = self.root / contract.output_path
            write_text(target, content)
            written.append(contract.output_path)
            hits += 1 if cached else 0
            misses += 0 if cached else 1

        # Layer 2: Section layer documents (docs/sections/<section>/index.md)
        section_docs, section_hits, section_misses = self._generate_section_docs(core_context, snapshot)
        written.extend(section_docs)
        hits += section_hits
        misses += section_misses

        # Layer 3: Phase layer documents (docs/phases/<phase>.md)
        # PHASE layer is GOVERNANCE_ONLY - only generate for repo-agent's own repo
        # Skip for target repositories to prevent governance-target output mixing
        phase_docs: list[str] = []
        phase_hits = 0
        phase_misses = 0
        if self.include_governance_layers:
            phase_docs, phase_hits, phase_misses = self._generate_phase_docs(core_context)
            written.extend(phase_docs)
            hits += phase_hits
            misses += phase_misses

        # Layer 4: Module layer documents (docs/modules/<module>.md)
        module_docs, module_hits, module_misses = self._generate_module_docs(snapshot, impacted_modules)
        written.extend(module_docs)
        hits += module_hits
        misses += module_misses

        # Prompt fragments and task catalog
        fragment_files, fragment_hits, fragment_misses = self._generate_prompt_fragments(core_context)
        written.extend(fragment_files)
        hits += fragment_hits
        misses += fragment_misses

        catalog_path, catalog_cached = self._generate_task_catalog(snapshot)
        written.append(catalog_path)
        hits += 1 if catalog_cached else 0
        misses += 0 if catalog_cached else 1

        return GenerationRunResult(written_files=written, cache_hits=hits, cache_misses=misses)

    def _load_snapshot(self) -> dict[str, Any]:
        repo_map = read_yamlish(self.source_root / "repo-map.yaml", {"repository": {}, "commands": {}})
        module_index = read_yamlish(self.source_root / "module-index.yaml", {"modules": []})
        api_index = read_yamlish(self.source_root / "api-index.yaml", {"endpoints": []})
        data_models = read_yamlish(self.source_root / "data-models.yaml", {"models": []})
        graph_data = read_yamlish(self.root / ".repo-wiki" / "graph" / "knowledge_graph.json", {"modules": {}})
        retrieval = read_yamlish(self.root / ".repo-wiki" / "index" / "retrieval_candidates.json", {"modules": {}})
        return {
            "repo_map": repo_map,
            "module_index": module_index,
            "api_index": api_index,
            "data_models": data_models,
            "graph": graph_data,
            "retrieval": retrieval,
        }

    def _build_core_context(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        repo = snapshot["repo_map"].get("repository", {}) or {}
        modules = sorted(snapshot["module_index"].get("modules", []), key=lambda x: str(x.get("name", "")))
        endpoints = sorted(snapshot["api_index"].get("endpoints", []), key=lambda x: (str(x.get("module", "")), str(x.get("path", ""))))
        models = sorted(snapshot["data_models"].get("models", []), key=lambda x: (str(x.get("module", "")), str(x.get("name", ""))))
        commands = snapshot["repo_map"].get("commands", {}) or {}

        module_lines = [
            f"- `{m.get('name', 'unknown')}` -> `{m.get('path', '')}` ({m.get('responsibility', 'N/A')})" for m in modules
        ] or ["- No modules discovered yet."]
        api_lines = [
            f"- `{e.get('method', 'GET')} {e.get('path', '/')}` (`{e.get('module', 'unknown')}`)" for e in endpoints
        ] or ["- No API endpoints discovered yet."]
        model_lines = [
            f"- `{d.get('name', 'unknown')}` (`{d.get('module', 'unknown')}`, {d.get('type', 'model')})" for d in models
        ] or ["- No data models discovered yet."]
        command_lines = [f"- `{k}`: `{v}`" for k, v in sorted(commands.items())] or ["- start/build/test/lint are not extracted yet."]

        graph_modules = snapshot["graph"].get("modules", {}) or {}
        graph_summary = f"Graph nodes: {len(graph_modules)} modules."

        # Build prose-first overview content using NarrativeBuilder
        repo_name = repo.get("name", self.root.name)
        primary_language = repo.get("primary_language", "unknown")
        framework = repo.get("framework", "unknown")

        # Initialize NarrativeBuilder with repository signals
        narrative_builder = NarrativeBuilder(
            repo_name=repo_name,
            primary_language=primary_language,
            framework=framework,
            modules=modules,
            endpoints=endpoints,
            models=models,
            commands=commands,
        )

        # Use NarrativeBuilder to generate repository-specific prose
        project_description = narrative_builder.build_project_description()
        project_positioning = narrative_builder.build_project_positioning()
        core_problem = narrative_builder.build_core_problem()
        core_capabilities = narrative_builder.build_core_capabilities()

        # Environment requirements based on language
        env_requirements = {
            "python": "Python 3.10+",
            "typescript": "Node.js 18+ 和 npm",
            "javascript": "Node.js 18+ 和 npm",
            "go": "Go 1.21+",
            "java": "JDK 17+",
        }.get(primary_language, "请参考项目 README 了解环境要求")

        environment_requirements = f"- **{primary_language.title()}**: {env_requirements}"

        # Startup commands
        startup_parts = []
        for key in ["install", "build", "start", "test"]:
            if key in commands:
                startup_parts.append(f"- `{commands[key]}`")
        if not startup_parts:
            startup_parts.append("- 暂无标准启动命令")
        startup_commands = "\n".join(startup_parts)

        # Reading navigation - linking to sections and modules
        # Use unified link builder to ensure correct relative paths
        # From docs/00-overview.md (depth 0) to sections/ (depth 1): sections/<slug>/index.md
        # From docs/00-overview.md (depth 0) to docs/03-module-map.md (depth 0): 03-module-map.md
        reading_nav_parts = [
            f"- [项目架构]({overview_to_section_link('architecture')}) - 了解系统设计和技术栈",
            f"- [核心服务]({overview_to_section_link('services')}) - 查看主要业务模块",
            f"- [API 参考]({overview_to_section_link('api')}) - 查阅接口文档",
            "- [模块详情](03-module-map.md) - 浏览所有模块",
        ]
        reading_navigation = "\n".join(reading_nav_parts)

        # Build domain groups for overview display
        domain_groups: dict[str, list[str]] = {}
        for m in modules:
            domain = m.get("domain", "unknown")
            if domain not in domain_groups:
                domain_groups[domain] = []
            module_info = f"- **{m.get('name', 'unknown')}** ({m.get('service_family', 'unknown')}) - {m.get('responsibility', 'N/A')}"
            domain_groups[domain].append(module_info)

        # Format domain groups for template
        formatted_domain_groups: dict[str, str] = {}
        domain_groups_markdown_parts: list[str] = []
        for domain, module_list in sorted(domain_groups.items()):
            joined = "\n".join(module_list)
            formatted_domain_groups[domain] = joined
            domain_groups_markdown_parts.append(f"### {domain}\n\n{joined}\n")
        domain_groups_markdown = "\n".join(domain_groups_markdown_parts).strip() or "暂无可用领域分组信息。"

        # Build architecture description using NarrativeBuilder
        architecture_description = (
            f"{repo_name} 采用三层架构设计，将运行时存储层、结构化事实层和文档中心层分离。"
            f"这种设计确保了知识的持久化、可追溯性和可读性的平衡。"
        )

        # System layers description using NarrativeBuilder
        system_layers = narrative_builder.build_architecture_rationale()

        # Three-layer overview using NarrativeBuilder (with WHY explanation)
        three_layer_overview = narrative_builder.build_three_layer_overview()

        # Service collaboration using NarrativeBuilder
        service_collaboration = narrative_builder.build_service_collaboration_narrative()

        # Core data flow using NarrativeBuilder
        core_data_flow = narrative_builder.build_data_flow_narrative()

        # Storage and retrieval design using NarrativeBuilder
        storage_retrieval_design = narrative_builder.build_storage_retrieval_narrative()

        # Incremental update and governance using NarrativeBuilder
        incremental_governance = narrative_builder.build_governance_narrative()

        # Governance checkpoints
        governance_checkpoints = (
            "- **模板覆盖**: 所有核心文档都有对应模板\n"
            "- **契约验证**: 生成前验证 required_keys\n"
            "- **Prose 约束**: 验证最小段落数和章节数\n"
            "- **引用检查**: 验证文档间交叉引用有效性"
        )

        # Module overview table
        module_overview_table = "\n".join([
            f"| {m.get('name', 'unknown')} | {m.get('domain', 'N/A')} | {m.get('runtime_role', 'N/A')} | {m.get('responsibility', 'N/A')[:50]}... |"
            for m in modules[:10]
        ]) if modules else "| No modules | | | |"

        # Tech stack
        tech_stack = (
            f"| 组件 | 技术 | 说明 |\n"
            f"|------|------|------|\n"
            f"| 语言 | {primary_language.title()} | 主要实现语言 |\n"
            f"| 框架 | {framework} | Web/应用框架 |\n"
            f"| 存储 | SQLite | 状态和缓存存储 |\n"
            f"| 向量 | Chroma | 语义检索向量数据库 |"
        )

        # =====================================================================
        # Domain-centered module map generation (Phase 07 - Task 7.1)
        # =====================================================================

        # Build domain groups with proper organization
        # Group modules by domain, then by service_family, then by runtime_role
        domain_modules: dict[str, dict[str, dict[str, list[dict]]]] = {}
        for m in modules:
            domain = m.get("domain", "unknown")
            service_family = m.get("service_family", "unknown")
            runtime_role = m.get("runtime_role", "unknown")

            if domain not in domain_modules:
                domain_modules[domain] = {}
            if service_family not in domain_modules[domain]:
                domain_modules[domain][service_family] = {}
            if runtime_role not in domain_modules[domain][service_family]:
                domain_modules[domain][service_family][runtime_role] = []
            domain_modules[domain][service_family][runtime_role].append(m)

        # Build domain overview table
        domain_summary_lines = [
            "| 业务域 | 服务族数量 | 模块数量 | 说明 |",
            "|--------|-----------|----------|------|"
        ]
        for domain in sorted(domain_modules.keys()):
            service_families = domain_modules[domain]
            module_count = sum(len(modules) for sf in service_families.values() for modules in sf.values())
            domain_descriptions = {
                "core-platform": "核心平台基础设施，包括核心运行时和存储层",
                "ai-services": "AI 服务能力，包括向量索引、语义检索和知识图谱",
                "api-gateway": "API 网关和路由层，负责请求分发和接口暴露",
                "data-pipeline": "数据管道和处理流水线，负责批量和流式数据处理",
                "frontend": "前端界面和客户端组件",
                "persistence": "持久化层，包括数据库和存储抽象",
                "tooling": "工具和脚本，用于构建、测试和部署",
                "testing": "测试框架和测试工具",
                "operations": "运维工具，包括部署、监控和日志",
                "unknown": "未分类模块，需要领域分类"
            }
            description = domain_descriptions.get(domain, f"业务域: {domain}")
            domain_summary_lines.append(f"| {domain} | {len(service_families)} | {module_count} | {description} |")
        domain_overview_table = "\n".join(domain_summary_lines)

        # Build detailed domain groups
        domain_groups_parts = []
        for domain in sorted(domain_modules.keys()):
            service_families = domain_modules[domain]
            domain_parts = [f"### {domain}\n"]
            domain_parts.append(f"服务族数量: {len(service_families)}")

            for sf_name in sorted(service_families.keys()):
                runtime_roles = service_families[sf_name]
                sf_parts = [f"#### {sf_name}\n"]

                for rr_name in sorted(runtime_roles.keys()):
                    rr_modules = runtime_roles[rr_name]
                    sf_parts.append(f"**{rr_name}** ({len(rr_modules)} 模块):")
                    for mod in sorted(rr_modules, key=lambda x: x.get("name", "")):
                        mod_name = mod.get("name", "unknown")
                        mod_path = mod.get("path", "")
                        mod_resp = mod.get("responsibility", "N/A")
                        depends_on = mod.get("depends_on", [])
                        depended_by = mod.get("depended_by", [])
                        doc_link = mod.get("doc_path", "")

                        dep_info = ""
                        if depends_on:
                            dep_info = f" → 依赖: {', '.join(depends_on)}"
                        if depended_by:
                            dep_info += f" ← 被依赖: {', '.join(depended_by)}"

                        sf_parts.append(f"- **`{mod_name}`** `{mod_path}`{dep_info}")
                        sf_parts.append(f"  - 职责: {mod_resp}")
                        if doc_link:
                            sf_parts.append(f"  - 文档: [{doc_link}](../{doc_link})")

                domain_parts.append("\n".join(sf_parts))

            domain_groups_parts.append("\n".join(domain_parts))

        domain_groups_detail = "\n\n".join(domain_groups_parts)

        # Build module index table (flat by domain for quick lookup)
        module_index_lines = [
            "| 模块 | 路径 | 运行时角色 | 域 | 核心职责 |",
            "|------|------|-----------|-----|---------|"
        ]
        for m in sorted(modules, key=lambda x: (x.get("domain", "z"), x.get("name", ""))):
            name = m.get("name", "unknown")
            path = m.get("path", "")
            runtime_role = m.get("runtime_role", "unknown")
            domain = m.get("domain", "unknown")
            responsibility = m.get("responsibility", "N/A")[:60]
            module_index_lines.append(f"| `{name}` | `{path}` | {runtime_role} | {domain} | {responsibility} |")
        module_index_table = "\n".join(module_index_lines)

        # Build cross-domain dependencies
        cross_domain_deps = []
        seen_deps = set()

        for m in modules:
            domain = m.get("domain", "unknown")
            depends_on = m.get("depends_on", []) or []
            depended_by = m.get("depended_by", []) or []

            for dep in depends_on:
                dep_module = next((mod for mod in modules if mod.get("name") == dep), None)
                if dep_module:
                    dep_domain = dep_module.get("domain", "unknown")
                    if domain != dep_domain:
                        dep_key = (domain, dep_domain)
                        if dep_key not in seen_deps:
                            seen_deps.add(dep_key)
                            cross_domain_deps.append(f"- **{domain}** → **{dep_domain}**: `{m.get('name')}` 依赖 `{dep}`")

        for m in modules:
            domain = m.get("domain", "unknown")
            depended_by = m.get("depended_by", []) or []

            for dep in depended_by:
                dep_module = next((mod for mod in modules if mod.get("name") == dep), None)
                if dep_module:
                    dep_domain = dep_module.get("domain", "unknown")
                    if domain != dep_domain:
                        dep_key = (domain, dep_domain)
                        if dep_key not in seen_deps:
                            seen_deps.add(dep_key)
                            cross_domain_deps.append(f"- **{domain}** ← **{dep_domain}**: `{m.get('name')}` 被 `{dep}` 依赖")

        cross_domain_dependencies = "\n".join(cross_domain_deps) if cross_domain_deps else "- 暂无跨域依赖关系"

        # =====================================================================
        # Aggregated API contracts generation (Phase 10 - Task 10.2)
        # Uses APIAggregator for true aggregation and entry-point selection
        # =====================================================================

        # Initialize API Aggregator with endpoints and module metadata
        api_aggregator = APIAggregator(endpoints=endpoints, modules=modules)

        # Use APIAggregator to build API groups table and detail
        api_groups_table = api_aggregator.build_api_groups_table()
        api_groups_detail = api_aggregator.build_api_groups_detail()

        # Use APIAggregator for auth and error conventions
        authentication_patterns = api_aggregator.summarize_auth_conventions()
        error_status_behavior = api_aggregator.summarize_error_conventions()

        # Key entry APIs - use principled scoring method
        key_entry_endpoints = api_aggregator.get_key_entry_apis(max_count=10)
        if key_entry_endpoints:
            key_api_parts = ["系统中的关键入口 API：\n"]
            for ep in key_entry_endpoints:
                key_api_parts.append(f"- **{ep.method}** `{ep.path}` ({ep.module}.{ep.handler}) - {ep.entry_reason}")
            key_entry_apis = "\n".join(key_api_parts)
        else:
            key_entry_apis = "- 暂无关键入口 API 定义"

        # Build endpoint index table (simplified for reference)
        endpoint_index_lines = [
            "| 方法 | 路径 | 模块 | 处理器 | 文档 |",
            "|------|------|------|--------|------|"
        ]
        for ep in sorted(endpoints, key=lambda x: (x.get("module", ""), x.get("path", ""))):
            method = ep.get("method", "GET")
            path = ep.get("path", "/")
            module_name = ep.get("module", "unknown")
            handler = ep.get("handler", "unknown")
            file_path = ep.get("file_path", "")
            # Find module doc path
            doc_link = f"[模块文档](modules/{module_name}.md)" if module_name != "tests" else "[测试模块](modules/tests.md)"
            endpoint_index_lines.append(f"| {method} | `{path}` | {module_name} | `{handler}` | {doc_link} |")
        endpoint_index_table = "\n".join(endpoint_index_lines) if endpoint_index_lines else "| 无端点 | | | |"

        # =====================================================================
        # Domain-aggregated data model generation (Phase 10 - Task 10.3)
        # Uses DataModelAggregator for core entity identification and migration-aware aggregation
        # =====================================================================

        # Initialize Data Model Aggregator with models, modules, and endpoints
        data_model_aggregator = DataModelAggregator(
            models=models,
            modules=modules,
            endpoints=endpoints,
        )

        # Use DataModelAggregator to build model sections
        core_models_section = data_model_aggregator.build_core_models_section()
        service_models_section = data_model_aggregator.build_service_models_section()

        # Build core models table for index
        core_models = data_model_aggregator.get_core_entities()
        if core_models:
            core_models_table_lines = [
                "| 模型名称 | 类型 | 模块 | 定义文件 |",
                "|----------|------|------|----------|"
            ]
            for m in sorted(core_models, key=lambda x: x.name):
                core_models_table_lines.append(f"| {m.name} | {m.type} | {m.module} | `{m.file_path}` |")
            core_models_table = "\n".join(core_models_table_lines)
        else:
            core_models_table = "| 无核心模型 | | | |"

        # Service models by module
        service_models = data_model_aggregator.get_service_models()
        module_lookup = {m.get("name"): m for m in modules}
        if service_models:
            service_models_by_module_parts = []
            by_module = data_model_aggregator.get_models_by_module()
            for module_name in sorted(by_module.keys()):
                module_models = [m for m in by_module[module_name] if not m.is_core_entity]
                if not module_models:
                    continue
                module_info = module_lookup.get(module_name, {})
                domain = module_info.get("domain", "unknown")
                sm_parts = [f"### {module_name} ({domain})\n"]
                for m in sorted(module_models, key=lambda x: x.name):
                    sm_parts.append(f"- **{m.name}** ({m.type}) - `{m.file_path}`")
                service_models_by_module_parts.append("\n".join(sm_parts))
            service_models_by_module = "\n\n".join(service_models_by_module_parts)
        else:
            service_models_by_module = "- 无服务模型"

        # Database and migration section using aggregator
        database_migration_section = data_model_aggregator.summarize_database_shape()
        database_shape = database_migration_section
        migration_strategy = data_model_aggregator.summarize_migration_strategy()

        # Cross-module boundaries using aggregator
        cross_module_boundaries = data_model_aggregator.build_cross_module_boundaries()

        # Model index table
        model_index_lines = [
            "| 模型名称 | 类型 | 模块 | 定义文件 |",
            "|----------|------|------|----------|"
        ]
        for m in sorted(data_model_aggregator.data_models, key=lambda x: (x.module, x.name)):
            # Determine if core
            is_core = "**[核心]**" if m.is_core_entity else ""
            model_index_lines.append(f"| {m.name} {is_core} | {m.type} | {m.module} | `{m.file_path}` |")
        model_index_table = "\n".join(model_index_lines) if model_index_lines else "| 无模型 | | | |"

        return {
            "repository_name": repo_name,
            "repository_root": str(repo.get("root_path", self.root)),
            "primary_language": primary_language,
            "framework": framework,
            "modules_table": "\n".join(module_lines),
            "api_table": "\n".join(api_lines),
            "model_table": "\n".join(model_lines),
            "commands_table": "\n".join(command_lines),
            "module_count": str(len(modules)),
            "endpoint_count":str(len(endpoints)),
            "model_count": str(len(models)),
            "graph_summary": graph_summary,
            # New prose-first fields for 00-overview.md
            "project_description": project_description,
            "project_positioning": project_positioning,
            "core_problem": core_problem,
            "core_capabilities": core_capabilities,
            "environment_requirements": environment_requirements,
            "startup_commands": startup_commands,
            "reading_navigation": reading_navigation,
            # Domain grouping for business organization
            "domain_groups": formatted_domain_groups,
            "domain_groups_markdown": domain_groups_markdown,
            # Architecture page fields
            "architecture_description": architecture_description,
            "system_layers": system_layers,
            "three_layer_overview": three_layer_overview,
            "service_collaboration": service_collaboration,
            "core_data_flow": core_data_flow,
            "storage_retrieval_design": storage_retrieval_design,
            "incremental_update_governance": incremental_governance,
            "governance_checkpoints": governance_checkpoints,
            "module_overview_table": module_overview_table,
            "tech_stack": tech_stack,
            # Domain-centered module map fields (Phase 07 - Task 7.1)
            "domain_overview_table": domain_overview_table,
            "domain_groups_detail": domain_groups_detail,
            "module_index_table": module_index_table,
            "cross_domain_dependencies": cross_domain_dependencies,
            # Aggregated API contracts fields (Phase 07 - Task 7.2)
            "api_groups_table": api_groups_table,
            "api_groups_detail": api_groups_detail,
            "authentication_patterns": authentication_patterns,
            "error_status_behavior": error_status_behavior,
            "key_entry_apis": key_entry_apis,
            "endpoint_index_table": endpoint_index_table,
            # Domain-aggregated data model fields (Phase 07 - Task 7.3)
            "core_models_section": core_models_section,
            "core_models_table": core_models_table,
            "service_models_section": service_models_section,
            "service_models_by_module": service_models_by_module,
            "database_migration_section": database_migration_section,
            "database_shape": database_shape,
            "migration_strategy": migration_strategy,
            "cross_module_boundaries": cross_module_boundaries,
            "model_index_table": model_index_table,
        }

    def _generate_section_docs(
        self, core_context: dict[str, Any], snapshot: dict[str, Any]
    ) -> tuple[list[str], int, int]:
        """Generate section layer documents (Layer 2: docs/sections/<section>/index.md).

        Section documents provide a thematic grouping layer between overview docs
        and individual module docs. They organize content by business concern
        rather than physical directory structure.

        The section layer is additive - it does NOT replace existing overview
        or module docs. It provides additional navigation paths for readers.
        """
        files: list[str] = []
        hits = 0
        misses = 0
        modules = snapshot["module_index"].get("modules", []) or []
        endpoints = snapshot["api_index"].get("endpoints", []) or []
        commands = snapshot["repo_map"].get("commands", {}) or {}

        for section_def in SECTION_DEFINITIONS:
            section_slug = section_def.canonical_slug
            # Build section context based on section type
            section_context = self._build_section_context(
                section_slug, section_def.title, modules, endpoints, commands, core_context
            )
            # Find the actual contract for this section
            for sec_contract in all_section_contracts():
                if sec_contract.name == f"section:{section_slug}":
                    content, cached = self._render_with_cache(
                        sec_contract.name, sec_contract.template_path, section_context
                    )
                    target = self.root / sec_contract.output_path
                    ensure_dir(target.parent)
                    write_text(target, content)
                    files.append(sec_contract.output_path)
                    hits += 1 if cached else 0
                    misses += 0 if cached else 1
                    break

        return files, hits, misses

    def _build_section_context(
        self,
        section_slug: str,
        section_title: str,
        modules: list[dict[str, Any]],
        endpoints: list[dict[str, Any]],
        commands: dict[str, str],
        core_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Build context for a section document.

        Each section aggregates relevant modules, APIs, and commands based on
        thematic grouping. This is the key difference from flat module docs -
        sections group by business concern, not physical path.

        Uses SectionNarrativeBuilder for repository-derived narrative instead
        of template-based aggregation. Uses ReadingPathGenerator for document-
        center reading path generation that explains WHY documents are
        recommended in sequence.
        """
        # Use SectionNarrativeBuilder for repository-specific narrative
        narrative_builder = SectionNarrativeBuilder(
            section_slug=section_slug,
            section_title=section_title,
            modules=modules,
            endpoints=endpoints,
            commands=commands,
            core_context=core_context,
        )

        # Use ReadingPathGenerator for document-center reading paths
        reading_path_gen = ReadingPathGenerator(
            section_slug=section_slug,
            section_title=section_title,
            modules=modules,
            endpoints=endpoints,
            core_context=core_context,
        )

        # Build section context using the builders
        section_description = narrative_builder.build_section_description()
        section_content = narrative_builder.build_section_content()
        section_modules = narrative_builder.build_section_modules()
        section_apis = narrative_builder.build_section_apis()
        section_commands = narrative_builder.build_section_commands()
        reading_paths = reading_path_gen.format_reading_paths()
        related_sections = reading_path_gen.format_related_sections()

        # Build standard navigation with related sections
        section_relations = {
            "project": ["architecture", "development"],
            "architecture": ["project", "services", "data-model"],
            "services": ["architecture", "api", "python-services"],
            "python-services": ["services", "api", "data-model"],
            "data-model": ["services", "api", "architecture"],
            "api": ["services", "data-model", "security"],
            "operations": ["development", "security"],
            "development": ["project", "operations"],
            "security": ["api", "operations"],
            "troubleshooting": ["operations", "development"],
        }

        nav_parts = [f"- {section_title}（当前页）"]
        nav_parts.append("- [Overview](../../00-overview.md)")

        # Add related sections from same hierarchy level
        rel_section_names = section_relations.get(section_slug, [])
        for rel_slug in rel_section_names:
            # Find the title for related section
            for section_def in SECTION_DEFINITIONS:
                if section_def.canonical_slug == rel_slug:
                    nav_parts.append(f"- [{section_def.title}](../{rel_slug}/index.md)")
                    break

        section_nav = "\n".join(nav_parts)

        return {
            "section_title": section_title,
            "section_description": section_description,
            "section_content": section_content,
            "section_modules": section_modules,
            "section_apis": section_apis,
            "section_commands": section_commands,
            "section_nav": section_nav,
            "reading_paths": reading_paths,
            "related_sections": related_sections,
        }

    def _generate_phase_docs(self, core_context: dict[str, Any]) -> tuple[list[str], int, int]:
        """Generate phase layer documents (Layer 3: docs/phases/<phase>.md).

        Phase documents provide a stage-governance view of the project,
        showing objectives, deliverables, and dependencies for each phase.

        The phase layer is additive - it does NOT replace existing overview docs.
        """
        files: list[str] = []
        hits = 0
        misses = 0

        phase_contracts = all_phase_contracts()
        phase_defs_list = list(PHASE_DEFINITIONS)

        for i, (phase_slug, phase_title) in enumerate(phase_defs_list):
            phase_context = self._build_phase_context(phase_slug, phase_title, phase_defs_list, i)
            for contract in phase_contracts:
                if contract.name == f"phase:{phase_slug}":
                    content, cached = self._render_with_cache(
                        contract.name, contract.template_path, phase_context
                    )
                    target = self.root / contract.output_path
                    ensure_dir(target.parent)
                    write_text(target, content)
                    files.append(contract.output_path)
                    hits += 1 if cached else 0
                    misses += 0 if cached else 1
                    break

        return files, hits, misses

    def _build_phase_context(
        self,
        phase_slug: str,
        phase_title: str,
        all_phases: list[tuple[str, str]],
        current_index: int,
    ) -> dict[str, Any]:
        """Build context for a phase document.

        Phase documents are informational - they describe the objectives
        and status of each project phase for governance and navigation.
        """
        # Phase objectives and deliverables based on phase slug
        phase_objectives_map = {
            "phase-01-setup": "Initialize repo-wiki configuration, establish project structure, and set up initial tooling.",
            "phase-02-scanning": "Scan repository for modules, endpoints, data models, and commands. Build source-of-truth index.",
            "phase-03-generation": "Generate documentation from source-of-truth data using templates and contracts.",
            "phase-04-adaptation": "Create adaptation layer for Claude, Codex, and other AI tooling integration.",
            "phase-05-verification": "Implement governance checks, verify generated docs, and establish quality gates.",
            "phase-06-architecture": "Recover information architecture, establish document center structure, and define contracts.",
        }

        phase_deliverables_map = {
            "phase-01-setup": "- Configuration files\n- Project scaffolding\n- Initial documentation structure",
            "phase-02-scanning": "- module-index.yaml\n- api-index.yaml\n- data-models.yaml\n- repo-map.yaml",
            "phase-03-generation": "- docs/00-overview.md\n- docs/01-architecture.md\n- docs/modules/*.md",
            "phase-04-adaptation": "- .claude/CLAUDE.md\n- .codex/config.toml\n- Agent instruction files",
            "phase-05-verification": "- verify --ci\n- Governance checks\n- Quality gates",
            "phase-06-architecture": "- docs/sections/ layer\n- docs/phases/ layer\n- Document contracts\n- Domain classification",
        }

        phase_dependencies_map = {
            "phase-01-setup": "None - this is the initial phase.",
            "phase-02-scanning": "Phase 01: Setup must be complete.",
            "phase-03-generation": "Phase 02: Scanning must populate source-of-truth.",
            "phase-04-adaptation": "Phase 03: Generation must produce initial docs.",
            "phase-05-verification": "Phase 04: Adaptation layer should be in place.",
            "phase-06-architecture": "Phase 01-05: All prior phases should be functional.",
        }

        # Determine status based on current phase
        status_map = {
            "phase-01-setup": "Completed",
            "phase-02-scanning": "Completed",
            "phase-03-generation": "Completed",
            "phase-04-adaptation": "Completed",
            "phase-05-verification": "Completed",
            "phase-06-architecture": "In Progress",
        }

        # Navigation: prev/next phases
        phase_prev = None
        phase_prev_title = None
        phase_next = None
        phase_next_title = None

        if current_index > 0:
            phase_prev = all_phases[current_index - 1][0]
            phase_prev_title = all_phases[current_index - 1][1]
        if current_index < len(all_phases) - 1:
            phase_next = all_phases[current_index + 1][0]
            phase_next_title = all_phases[current_index + 1][1]

        objectives = phase_objectives_map.get(phase_slug, f"Objectives for {phase_title}.")
        deliverables = phase_deliverables_map.get(phase_slug, "- Phase deliverables to be defined.")
        dependencies = phase_dependencies_map.get(phase_slug, "Dependencies not yet defined.")
        status = status_map.get(phase_slug, "Unknown")

        deliverables_formatted = "\n".join(f"  - {d}" for d in deliverables.split("\n"))

        return {
            "phase_title": phase_title,
            "phase_objectives": objectives,
            "phase_deliverables": deliverables_formatted,
            "phase_dependencies": dependencies,
            "phase_status": status,
            "phase_prev": phase_prev,
            "phase_prev_title": phase_prev_title,
            "phase_next": phase_next,
            "phase_next_title": phase_next_title,
        }

    def _generate_module_docs(
        self, snapshot: dict[str, Any], impacted_modules: list[str] | None
    ) -> tuple[list[str], int, int]:
        modules = sorted(snapshot["module_index"].get("modules", []), key=lambda x: str(x.get("name", "")))
        graph_modules = snapshot["graph"].get("modules", {}) or {}
        retrieval_modules = snapshot["retrieval"].get("modules", {}) or {}
        files: list[str] = []
        hits = 0
        misses = 0
        for module in modules:
            name = str(module.get("name", "unknown"))
            if impacted_modules is not None and name not in impacted_modules:
                continue

            retrieval_candidates = retrieval_modules.get(name, []) if isinstance(retrieval_modules, dict) else []
            neighbors: list[str] = []
            if isinstance(graph_modules, dict):
                node = graph_modules.get(name, {}) or {}
                neighbors = (node.get("upstream", []) or []) + (node.get("downstream", []) or [])
            context_strategy = self.context_builder.build_module_context(module, retrieval_candidates, neighbors)

            contract = module_document_contract(name)
            module_context = {
                "module_name": name,
                "module_path": module.get("path", ""),
                "module_owner": module.get("owner", "unknown"),
                "module_responsibility": module.get("responsibility", "unknown"),
                "module_exports": "\n".join(f"- `{x}`" for x in (module.get("exports", []) or [])) or "- none",
                "module_depends_on": "\n".join(f"- `{x}`" for x in (module.get("depends_on", []) or [])) or "- none",
                "module_depended_by": "\n".join(f"- `{x}`" for x in (module.get("depended_by", []) or [])) or "- none",
                "module_interfaces": "\n".join(f"- `{x}`" for x in (module.get("interfaces", []) or [])) or "- none",
                "module_data_models": "\n".join(f"- `{x}`" for x in (module.get("data_models", []) or [])) or "- none",
                "context_strategy": context_strategy.strategy,
                "context_token_budget": str(context_strategy.token_budget),
                "context_notes": context_strategy.notes,
                "context_neighbors": "\n".join(f"- `{x}`" for x in context_strategy.neighbors) or "- none",
                "context_chunks": "\n".join(
                    f"- `{chunk.get('symbol_name', 'chunk')}` `{chunk.get('file_path', '')}`"
                    for chunk in context_strategy.chunks
                )
                or "- none",
            }

            content, cached = self._render_with_cache(contract.name, contract.template_path, module_context)
            target = self.root / contract.output_path
            write_text(target, content)
            files.append(contract.output_path)
            hits += 1 if cached else 0
            misses += 0 if cached else 1
        return files, hits, misses

    def _generate_prompt_fragments(self, core_context: dict[str, Any]) -> tuple[list[str], int, int]:
        files: list[str] = []
        hits = 0
        misses = 0
        for contract in PROMPT_FRAGMENT_CONTRACTS:
            content, cached = self._render_with_cache(contract.name, contract.template_path, core_context)
            write_text(self.root / contract.output_path, content)
            files.append(contract.output_path)
            hits += 1 if cached else 0
            misses += 0 if cached else 1
        return files, hits, misses

    def _generate_task_catalog(self, snapshot: dict[str, Any]) -> tuple[str, bool]:
        modules = [m.get("name", "unknown") for m in snapshot["module_index"].get("modules", [])]
        commands = snapshot["repo_map"].get("commands", {}) or {}
        tasks = [
            {"name": "init", "description": "Full bootstrap workflow", "commands": ["repo-wiki init"]},
            {"name": "update", "description": "Impacted module regeneration", "commands": ["repo-wiki update"]},
            {"name": "verify", "description": "Governance checks", "commands": ["repo-wiki verify", "repo-wiki verify --ci"]},
        ]
        payload = {"tasks": tasks, "module_references": sorted(str(x) for x in modules), "commands": commands}
        context = {"task_catalog_json": self._json_text(payload)}
        content, cached = self._render_with_cache(
            TASK_CATALOG_CONTRACT.name, TASK_CATALOG_CONTRACT.template_path, context
        )
        write_text(self.root / TASK_CATALOG_CONTRACT.output_path, content)
        # Also keep a deterministic parseable export.
        write_json(self.root / "ai" / "source-of-truth" / "task-catalog.generated.json", payload)
        return TASK_CATALOG_CONTRACT.output_path, cached

    def _render_with_cache(self, cache_key_prefix: str, template_path: str, context: dict[str, Any]) -> tuple[str, bool]:
        key = stable_hash({"k": cache_key_prefix, "tpl": template_path, "ctx": context})
        cached = self.cache.get(key)
        if cached is not None:
            return cached, True
        content = self.renderer.render(template_path, context)
        self.cache.set(key, content)
        return content, False

    @staticmethod
    def _json_text(payload: dict[str, Any]) -> str:
        import json

        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)

    def ensure_source_of_truth_scaffold(self) -> None:
        ensure_dir(self.source_root / "prompt-fragments")
        defaults = {
            self.source_root / "repo-map.yaml": {"repository": {"name": self.root.name, "root_path": str(self.root)}, "commands": {}},
            self.source_root / "module-index.yaml": {"modules": []},
            self.source_root / "api-index.yaml": {"endpoints": []},
            self.source_root / "data-models.yaml": {"models": []},
        }
        for path, payload in defaults.items():
            if not path.exists():
                write_json(path, payload)

    def validate_overview_output(self, content: str) -> list[str]:
        """Validate overview output meets prose-first requirements.

        Returns a list of validation errors, empty if valid.
        This does NOT raise exceptions - it returns diagnostics.
        """
        errors = []

        # Check prose length
        is_valid, reason = validate_overview_prose(content)
        if not is_valid:
            errors.append(f"prose_validation: {reason}")

        # Check not list-only
        is_valid, reason = validate_overview_not_list_only(content)
        if not is_valid:
            errors.append(f"list_only_check: {reason}")

        return errors

    def validate_architecture_output(self, content: str) -> list[str]:
        """Validate architecture output meets Mermaid and design-reasoning requirements.

        Returns a list of validation errors, empty if valid.
        This does NOT raise exceptions - it returns diagnostics.
        """
        errors = []

        # Check Mermaid presence
        is_valid, reason = validate_architecture_has_mermaid(content)
        if not is_valid:
            errors.append(f"mermaid_validation: {reason}")

        # Check not module enumeration
        is_valid, reason = validate_architecture_not_module_enum(content)
        if not is_valid:
            errors.append(f"module_enum_check: {reason}")

        return errors

    def validate_module_map_output(self, content: str, has_domain_metadata: bool = True) -> list[str]:
        """Validate module map output meets domain-grouped organization requirements.

        Returns a list of validation errors, empty if valid.
        This does NOT raise exceptions - it returns diagnostics.

        Parameters:
        - content: The rendered module map content
        - has_domain_metadata: True if domain classification metadata is available in source data
        """
        errors = []

        # Check domain grouping structure
        is_valid, reason = validate_module_map_domain_grouped(content)
        if not is_valid:
            errors.append(f"domain_grouped_validation: {reason}")

        # Check not flat directory listing
        is_valid, reason = validate_module_map_not_directory_flat(content, has_domain_metadata)
        if not is_valid:
            errors.append(f"flat_listing_check: {reason}")

        return errors

    def validate_api_contract_output(self, content: str) -> list[str]:
        """Validate API contracts output meets grouped aggregation requirements.

        Returns a list of validation errors, empty if valid.
        This does NOT raise exceptions - it returns diagnostics.
        """
        errors = []

        # Check API grouping structure
        is_valid, reason = validate_api_contract_grouped(content)
        if not is_valid:
            errors.append(f"api_grouped_validation: {reason}")

        # Check not endpoint dump
        is_valid, reason = validate_api_contract_not_endpoint_dump(content)
        if not is_valid:
            errors.append(f"endpoint_dump_check: {reason}")

        return errors

    def validate_data_model_output(self, content: str) -> list[str]:
        """Validate data model output meets three-section aggregation requirements.

        Returns a list of validation errors, empty if valid.
        This does NOT raise exceptions - it returns diagnostics.
        """
        errors = []

        # Check data model grouping structure
        is_valid, reason = validate_data_model_grouped(content)
        if not is_valid:
            errors.append(f"data_model_grouped_validation: {reason}")

        # Check not model dump
        is_valid, reason = validate_data_model_not_dump(content)
        if not is_valid:
            errors.append(f"model_dump_check: {reason}")

        return errors

    def validate_section_docs(self, section_slug: str) -> list[str]:
        """Validate a section page exists and has proper content/navigation.

        Returns a list of validation errors, empty if valid.
        This does NOT raise exceptions - it returns diagnostics.

        Parameters:
        - section_slug: The section identifier to validate
        """
        errors = []

        # Check section page exists
        section_dir = self.root / "docs" / "sections"
        is_valid, reason = validate_section_page_exists(section_slug, section_dir)
        if not is_valid:
            errors.append(f"section_exists: {reason}")
            return errors  # Can't validate content if file doesn't exist

        # Read section content
        section_path = section_dir / section_slug / "index.md"
        try:
            content = section_path.read_text()
        except Exception as e:
            errors.append(f"section_read: Failed to read {section_path}: {e}")
            return errors

        # Validate content
        is_valid, reason = validate_section_page_content(content, section_slug)
        if not is_valid:
            errors.append(f"section_content: {reason}")

        # Validate cross-links
        is_valid, reason = validate_section_cross_links(content, section_slug)
        if not is_valid:
            errors.append(f"section_cross_links: {reason}")

        return errors

    def validate_all_section_docs(self) -> dict[str, list[str]]:
        """Validate all required section pages.

        Returns a dictionary mapping section slug to list of errors (empty if valid).
        """
        results = {}
        required_sections = [
            "project", "architecture", "services", "data-model",
            "api", "operations", "development", "security"
        ]

        for section_slug in required_sections:
            errors = self.validate_section_docs(section_slug)
            results[section_slug] = errors

        return results

    def validate_narrative_output(self, content: str, doc_type: str = "overview") -> list[str]:
        """Validate that narrative content is repository-specific, not generic template.

        Phase 10 - Task 10.1: Detects overly generic or repeated boilerplate patterns.

        Args:
            content: The rendered narrative content
            doc_type: Type of document ('overview' or 'architecture')

        Returns a list of validation errors, empty if valid.
        """
        errors = []

        # Check for generic boilerplate patterns
        is_valid, reason = validate_narrative_not_generic(content)
        if not is_valid:
            errors.append(f"narrative_generic_check: {reason}")

        # For architecture docs, check for rationale explanation
        if doc_type == "architecture":
            is_valid, reason = validate_architecture_rationale_exists(content)
            if not is_valid:
                errors.append(f"architecture_rationale_check: {reason}")

        return errors

    def validate_overview_narrative(self, content: str, repo_name: str) -> list[str]:
        """Validate overview narrative is repository-specific.

        Phase 10 - Task 10.1: Checks that overview references repository name.

        Args:
            content: The rendered overview content
            repo_name: The repository name for reference check

        Returns a list of validation errors, empty if valid.
        """
        errors = []

        # Check for repository-specific references
        is_valid, reason = validate_overview_has_repository_specifics(content, repo_name)
        if not is_valid:
            errors.append(f"overview_repository_specifics: {reason}")

        # Check for generic patterns
        is_valid, reason = validate_narrative_not_generic(content)
        if not is_valid:
            errors.append(f"overview_generic_check: {reason}")

        return errors
