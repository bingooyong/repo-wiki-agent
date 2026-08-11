from __future__ import annotations

from repo_wiki.ia import TaxonomyProfileCompiler


def _base_model() -> dict:
    return {
        "schema_version": "repo_agent.knowledge_model_v3/1.0",
        "input_fingerprints": {},
        "records": {
            "repository": [{"repository_id": "r1"}],
            "services": [],
            "api_surfaces": [],
            "data_models": [],
            "frontend_consumers": [],
            "operation_assets": [],
            "doc_artifacts": [],
            "evidence_spans": [],
            "conflicts": [],
        },
        "summary": {
            "repository_count": 1,
            "service_count": 0,
            "api_surface_count": 0,
            "data_model_count": 0,
            "frontend_consumer_count": 0,
            "operation_asset_count": 0,
            "doc_artifact_count": 0,
            "evidence_span_count": 0,
            "conflict_count": 0,
        },
    }


def test_minimal_model_enables_only_overview_and_dev_guide():
    compiler = TaxonomyProfileCompiler()
    profile = compiler.compile(_base_model())
    enabled_paths = [d.path for d in profile.directories]
    assert enabled_paths == ["项目概述/", "开发指南/"]
    assert "API参考/" in profile.disabled_directories


def test_full_model_enables_all_directories():
    compiler = TaxonomyProfileCompiler()
    model = _base_model()
    model["records"]["services"] = [{"service_id": "s1", "runtime": "java-spring"}]
    model["records"]["api_surfaces"] = [{"api_id": "a1"}]
    model["records"]["data_models"] = [{"model_id": "m1"}]
    model["records"]["frontend_consumers"] = [{"consumer_id": "f1"}]
    model["records"]["operation_assets"] = [
        {"asset_id": "o1", "asset_type": "workflow", "path": ".github/workflows/ci.yml"},
        {"asset_id": "o2", "asset_type": "dockerfile", "path": "Dockerfile"},
        {"asset_id": "o3", "asset_type": "test_suite", "path": "tests/test_main.py"},
    ]
    model["records"]["doc_artifacts"] = [{"doc_id": "d1", "doc_type": "qa", "path": "docs/qa.md"}]
    model["records"]["conflicts"] = [{"conflict_id": "c1"}]
    model["summary"].update(
        {
            "service_count": 2,
            "api_surface_count": 3,
            "data_model_count": 2,
            "frontend_consumer_count": 1,
            "operation_asset_count": 3,
            "doc_artifact_count": 1,
            "conflict_count": 1,
        }
    )
    profile = compiler.compile(model)
    enabled_paths = [d.path for d in profile.directories]
    assert enabled_paths == [
        "项目概述/",
        "架构设计/",
        "服务与模块/",
        "核心服务/",
        "API参考/",
        "数据模型/",
        "前端应用/",
        "开发指南/",
        "运行与部署/",
        "安全与合规/",
        "测试与质量/",
        "故障排除与维护/",
    ]


def test_python_only_service_enables_python_services_not_core():
    compiler = TaxonomyProfileCompiler()
    model = _base_model()
    model["records"]["services"] = [{"service_id": "s1", "runtime": "python-fastapi"}]
    model["summary"]["service_count"] = 1
    profile = compiler.compile(model)
    enabled_paths = [d.path for d in profile.directories]
    assert "Python服务/" in enabled_paths
    assert "核心服务/" not in enabled_paths


def test_java_services_enable_core_services():
    compiler = TaxonomyProfileCompiler()
    model = _base_model()
    model["records"]["services"] = [{"service_id": "s1", "runtime": "java-spring"}]
    model["summary"]["service_count"] = 1
    profile = compiler.compile(model)
    enabled_paths = [d.path for d in profile.directories]
    assert "核心服务/" in enabled_paths
    assert "Python服务/" not in enabled_paths


def test_directory_order_is_stable_for_same_input():
    compiler = TaxonomyProfileCompiler()
    model = _base_model()
    model["records"]["services"] = [{"service_id": "s1", "runtime": "java-spring"}]
    model["records"]["api_surfaces"] = [{"api_id": "a1"}]
    model["summary"]["service_count"] = 1
    model["summary"]["api_surface_count"] = 1
    profile1 = compiler.compile(model)
    profile2 = compiler.compile(model)
    assert [d.path for d in profile1.directories] == [d.path for d in profile2.directories]


def test_enabled_directory_coverage_reason_non_empty():
    compiler = TaxonomyProfileCompiler()
    model = _base_model()
    model["records"]["services"] = [{"service_id": "s1", "runtime": "go_main"}]
    model["summary"]["service_count"] = 1
    profile = compiler.compile(model)

    for path in [d.path for d in profile.directories]:
        reason = profile.directory_coverage.get(path, "")
        assert isinstance(reason, str)
        assert reason.strip() != ""
