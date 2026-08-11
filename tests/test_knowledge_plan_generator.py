from repo_wiki.ia.taxonomy_compiler import TaxonomyProfileCompiler
from repo_wiki.knowledge_plan import SCHEMA_VERSION, generate_plan, validate_plan


def _knowledge_model() -> dict:
    return {
        "schema_version": "repo_agent.knowledge_model_v3/1.0",
        "input_fingerprints": {"source_inventory": "srcfp", "docs_inventory": "docsfp"},
        "summary": {
            "repository_count": 1,
            "service_count": 2,
            "api_surface_count": 1,
            "data_model_count": 1,
            "operation_asset_count": 1,
            "conflict_count": 0,
        },
        "records": {
            "repository": [{"repository_id": "repo1"}],
            "services": [
                {
                    "service_id": "service:billing",
                    "runtime": "python-fastapi",
                    "evidence_path": "src/billing/app.py",
                },
                {
                    "service_id": "service:orders",
                    "runtime": "go_main",
                    "evidence_path": "cmd/orders/main.go",
                },
            ],
            "api_surfaces": [
                {
                    "api_id": "api:get:/orders",
                    "path": "/orders",
                    "evidence_path": "cmd/orders/api.go",
                }
            ],
            "data_models": [
                {"model_id": "model:Order", "name": "Order", "evidence_path": "cmd/orders/model.go"}
            ],
            "operation_assets": [
                {"asset_id": "ops:docker", "asset_type": "dockerfile", "path": "Dockerfile"}
            ],
            "doc_artifacts": [
                {
                    "doc_id": "doc:readme",
                    "path": "README.md",
                    "doc_type": "overview",
                    "authority": "primary",
                    "content_sha256": "abc123",
                }
            ],
            "conflicts": [],
        },
    }


def test_generate_plan_contains_required_sections_and_validates() -> None:
    plan = generate_plan(_knowledge_model())

    assert plan["schema_version"] == SCHEMA_VERSION
    assert plan["generated"]["fingerprint"]
    assert "服务与模块/" in plan["include"]
    assert plan["exclude"] == []
    assert plan["docs"]["allowlist"] == [
        {
            "path": "README.md",
            "doc_id": "doc:readme",
            "doc_type": "overview",
            "authority": "primary",
            "content_sha256": "abc123",
        }
    ]

    directory_by_path = {directory["path"]: directory for directory in plan["directories"]}
    assert directory_by_path["API参考/"]["templates"] == [
        {"id": "api.reference", "contracts": ["api_surfaces"]}
    ]
    assert directory_by_path["数据模型/"]["templates"] == [
        {"id": "data.model", "contracts": ["data_models"]}
    ]
    assert {template["id"] for template in plan["page_templates"]} >= {
        "api.reference",
        "data.model",
        "service.module",
    }

    domains = {domain["id"]: domain for domain in plan["business_domains"]}
    assert domains["python-fastapi"]["services"] == ["service:billing"]
    assert domains["python-fastapi"]["evidence_paths"] == ["src/billing/app.py"]
    assert domains["go-main"]["directories"] == ["核心服务/"]

    assert validate_plan(plan) == []


def test_generate_plan_accepts_compiler_output() -> None:
    model = _knowledge_model()
    profile = TaxonomyProfileCompiler().compile(model)
    plan = generate_plan(model, profile)

    assert [directory.path for directory in profile.directories] == plan["include"]
    assert plan["model"]["schema_version"] == "repo_agent.knowledge_model_v3/1.0"
    assert plan["model"]["fingerprint"]
