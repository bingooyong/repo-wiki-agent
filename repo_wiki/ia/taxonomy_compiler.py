from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DirectorySpec:
    path: str
    label: str
    enabled: bool
    record_families: list[str] = field(default_factory=list)
    evidence_threshold: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class TaxonomyProfile:
    directories: list[DirectorySpec]
    directory_coverage: dict[str, str]
    disabled_directories: dict[str, str]


class TaxonomyProfileCompiler:
    """Compile repository IA directory profile from Knowledge Model v3."""

    _ORDERED_DIRECTORY_DEFS: tuple[tuple[str, str], ...] = (
        ("项目概述/", "项目概述"),
        ("架构设计/", "架构设计"),
        ("服务与模块/", "服务与模块"),
        ("核心服务/", "核心服务"),
        ("Python服务/", "Python服务"),
        ("API参考/", "API参考"),
        ("数据模型/", "数据模型"),
        ("前端应用/", "前端应用"),
        ("开发指南/", "开发指南"),
        ("运行与部署/", "运行与部署"),
        ("安全与合规/", "安全与合规"),
        ("测试与质量/", "测试与质量"),
        ("故障排除与维护/", "故障排除与维护"),
    )

    def compile(self, knowledge_model: dict[str, Any]) -> TaxonomyProfile:
        summary = self._summary(knowledge_model)
        records = self._records(knowledge_model)

        service_count = self._count(summary, "service_count")
        api_count = self._count(summary, "api_surface_count")
        model_count = self._count(summary, "data_model_count")
        frontend_count = self._count(summary, "frontend_consumer_count")
        ops_count = self._count(summary, "operation_asset_count")
        conflict_count = self._count(summary, "conflict_count")

        has_core_runtime = self._has_service_runtime(records, {"java-spring", "go_main"})
        has_python_runtime = self._has_service_runtime(
            records, {"python", "python-fastapi", "python-flask"}
        )
        has_ci_or_docker = self._has_ci_or_docker_evidence(records)
        has_tests = self._has_tests(records)

        rules: dict[str, tuple[bool, list[str], dict[str, int], str, str]] = {
            "项目概述/": (
                True,
                ["repository"],
                {"repository_count": 1},
                "仓库事实是 IA 编译根上下文，目录固定启用。",
                "无；目录为固定入口。",
            ),
            "架构设计/": (
                service_count > 1 or ops_count > 0,
                ["services", "operation_assets"],
                {"service_count": 2, "operation_asset_count": 1},
                "检测到多服务或运行资产，需呈现架构边界与部署视图。",
                "服务数量不足且无运行资产，不生成架构层目录。",
            ),
            "服务与模块/": (
                service_count > 0,
                ["services"],
                {"service_count": 1},
                f"已识别 {service_count} 个服务记录，满足服务分层编排。",
                "无服务记录，目录不启用。",
            ),
            "核心服务/": (
                has_core_runtime,
                ["services"],
                {"service_count": 1},
                "服务运行时包含 java-spring 或 go_main，归入核心服务目录。",
                "未识别 java-spring/go_main 运行时，目录不启用。",
            ),
            "Python服务/": (
                has_python_runtime and not has_core_runtime,
                ["services"],
                {"service_count": 1},
                "服务为 Python 运行时且未触发核心服务运行时，启用 Python服务目录。",
                "未满足 Python-only 运行时分组条件，目录不启用。",
            ),
            "API参考/": (
                api_count > 0,
                ["api_surfaces"],
                {"api_surface_count": 1},
                f"已识别 {api_count} 个 API surface 记录，启用 API 参考目录。",
                "无 API surface 记录，目录不启用。",
            ),
            "数据模型/": (
                model_count > 0,
                ["data_models"],
                {"data_model_count": 1},
                f"已识别 {model_count} 个数据模型记录，启用数据模型目录。",
                "无数据模型记录，目录不启用。",
            ),
            "前端应用/": (
                frontend_count > 0,
                ["frontend_consumers"],
                {"frontend_consumer_count": 1},
                f"检测到 {frontend_count} 个前端消费者记录，启用前端应用目录。",
                "无前端消费者记录，目录不启用。",
            ),
            "开发指南/": (
                True,
                ["repository", "doc_artifacts"],
                {"repository_count": 1},
                "开发指南是固定读者入口目录，保持始终可达。",
                "无；目录为固定入口。",
            ),
            "运行与部署/": (
                ops_count > 0,
                ["operation_assets"],
                {"operation_asset_count": 1},
                f"检测到 {ops_count} 个运行资产，启用运行与部署目录。",
                "无运行资产记录，目录不启用。",
            ),
            "安全与合规/": (
                has_ci_or_docker,
                ["operation_assets"],
                {"operation_asset_count": 1},
                "运行资产含 CI workflow 或 Dockerfile 证据，启用安全与合规目录。",
                "未检测到 CI workflow/Dockerfile 证据，目录不启用。",
            ),
            "测试与质量/": (
                has_tests,
                ["operation_assets", "doc_artifacts"],
                {"test_record_count": 1},
                "检测到测试记录或测试相关资产，启用测试与质量目录。",
                "未检测到测试记录，目录不启用。",
            ),
            "故障排除与维护/": (
                conflict_count > 0 or ops_count > 0,
                ["conflicts", "operation_assets"],
                {"conflict_count": 1, "operation_asset_count": 1},
                "存在冲突或运行资产，需提供故障排除与维护路径。",
                "无冲突且无运行资产，目录不启用。",
            ),
        }

        enabled: list[DirectorySpec] = []
        coverage: dict[str, str] = {}
        disabled: dict[str, str] = {}

        for path, label in self._ORDERED_DIRECTORY_DEFS:
            is_enabled, families, threshold, yes_reason, no_reason = rules[path]
            spec = DirectorySpec(
                path=path,
                label=label,
                enabled=is_enabled,
                record_families=families,
                evidence_threshold=threshold,
            )
            if is_enabled:
                enabled.append(spec)
                coverage[path] = yes_reason
            else:
                disabled[path] = no_reason

        return TaxonomyProfile(
            directories=enabled,
            directory_coverage=coverage,
            disabled_directories=disabled,
        )

    def compile_from_loaded(self, repo_root: str | None = None) -> TaxonomyProfile:
        """Convenience loader for .repo-wiki/cache/knowledge_model_v3.json."""
        from pathlib import Path

        from repo_wiki.scanner import load_knowledge_model_v3

        root = Path(repo_root).resolve() if repo_root else Path.cwd()
        model = load_knowledge_model_v3(root)
        if not isinstance(model, dict):
            model = {"summary": {}, "records": {}}
        return self.compile(model)

    @staticmethod
    def _summary(knowledge_model: dict[str, Any]) -> dict[str, Any]:
        data = knowledge_model.get("summary", {})
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _records(knowledge_model: dict[str, Any]) -> dict[str, Any]:
        data = knowledge_model.get("records", {})
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _count(summary: dict[str, Any], key: str) -> int:
        value = summary.get(key, 0)
        return value if isinstance(value, int) and value >= 0 else 0

    @staticmethod
    def _has_service_runtime(records: dict[str, Any], runtimes: set[str]) -> bool:
        services = records.get("services", [])
        if not isinstance(services, list):
            return False
        for item in services:
            if not isinstance(item, dict):
                continue
            runtime = str(item.get("runtime", "")).strip().lower()
            if runtime in runtimes:
                return True
        return False

    @staticmethod
    def _has_ci_or_docker_evidence(records: dict[str, Any]) -> bool:
        assets = records.get("operation_assets", [])
        if not isinstance(assets, list):
            return False
        for item in assets:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path", "")).lower()
            asset_type = str(item.get("asset_type", "")).lower()
            if ".github/workflows/" in path or "dockerfile" in path:
                return True
            if "workflow" in asset_type or "dockerfile" in asset_type:
                return True
        return False

    @staticmethod
    def _has_tests(records: dict[str, Any]) -> bool:
        explicit_tests = records.get("tests")
        if isinstance(explicit_tests, list) and len(explicit_tests) > 0:
            return True

        assets = records.get("operation_assets", [])
        if isinstance(assets, list):
            for item in assets:
                if not isinstance(item, dict):
                    continue
                path = str(item.get("path", "")).lower()
                asset_type = str(item.get("asset_type", "")).lower()
                if "/test" in path or "/tests" in path or "pytest" in path:
                    return True
                if "test" in asset_type or "quality" in asset_type:
                    return True

        docs = records.get("doc_artifacts", [])
        if isinstance(docs, list):
            for item in docs:
                if not isinstance(item, dict):
                    continue
                path = str(item.get("path", "")).lower()
                doc_type = str(item.get("doc_type", "")).lower()
                if "test" in path or "qa" in path:
                    return True
                if "test" in doc_type or "qa" in doc_type:
                    return True
        return False
