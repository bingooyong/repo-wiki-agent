from copy import deepcopy

from repo_wiki.knowledge_plan import (
    SCHEMA_VERSION,
    attach_fingerprint,
    generate_plan,
    has_manual_managed_edits,
    validate_plan,
)


def _valid_plan() -> dict:
    return attach_fingerprint(
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": "2026-07-14T00:00:00Z",
            "model": {"schema_version": "repo_agent.knowledge_model_v3/1.0"},
            "include": ["服务与模块/"],
            "exclude": ["tmp/"],
            "docs": {"allowlist": [{"path": "README.md", "doc_id": "doc:readme"}]},
            "directories": [
                {
                    "path": "服务与模块/",
                    "label": "服务与模块",
                    "enabled": True,
                    "record_families": ["services"],
                    "templates": [{"id": "service.module", "contracts": ["services"]}],
                }
            ],
            "page_templates": [
                {"id": "service.module", "title": "服务与模块", "contracts": ["services"]}
            ],
            "business_domains": [
                {
                    "id": "python-fastapi",
                    "label": "python-fastapi services",
                    "runtimes": ["python-fastapi"],
                    "services": ["service:web"],
                    "evidence_paths": ["src/app.py"],
                    "directories": ["服务与模块/"],
                }
            ],
            "manual_sections": [],
            "overwrite_policy": {"mode": "protect_manual_edits"},
        }
    )


def test_validate_plan_accepts_valid_shape() -> None:
    assert validate_plan(_valid_plan()) == []


def test_validate_plan_reports_structured_issues() -> None:
    plan = _valid_plan()
    plan["schema_version"] = "repo_agent.knowledge_plan/9.9"
    plan["include"] = ["${SECRET_PATH}"]
    plan["directories"].append(deepcopy(plan["directories"][0]))
    plan["docs"] = {"allowlist": ["README.md"]}
    plan["page_templates"][0]["id"] = "Invalid Template Id"
    plan["business_domains"][0]["directories"] = ["missing/"]

    issues = validate_plan(plan)
    codes = {issue.code for issue in issues}

    assert "schema_version.unsupported" in codes
    assert "include.unsafe_path" in codes
    assert "directory.duplicate_path" in codes
    assert "docs.allowlist.not_mapping" in codes
    assert "template.invalid_id" in codes
    assert "domain.directory_unknown" in codes
    assert all(issue.severity == "error" for issue in issues)
    assert all(issue.path and issue.message and issue.code for issue in issues)


def test_manual_edit_detection_ignores_manual_sections_but_flags_managed_changes() -> None:
    plan = _valid_plan()
    clean = deepcopy(plan)
    clean["manual_sections"].append({"id": "operator-note", "body": "Reviewed locally."})
    assert not has_manual_managed_edits(clean)

    dirty = deepcopy(plan)
    dirty["include"].append("API参考/")
    assert has_manual_managed_edits(dirty)


def test_validate_plan_rejects_unsafe_path_like_fields() -> None:
    plan = _valid_plan()
    plan["include"] = ["/absolute"]
    plan["exclude"] = ["../outside.md"]
    plan["docs"]["allowlist"] = [
        {"path": "~/secret.md"},
        {"path": "$DOC_PATH"},
        {"path": "bad\x00name.md"},
    ]
    plan["directories"][0]["path"] = "docs/../escape/"
    plan["business_domains"][0]["directories"] = ["../escape/"]

    codes = {issue.code for issue in validate_plan(plan)}

    assert "include.unsafe_path" in codes
    assert "exclude.unsafe_path" in codes
    assert "docs.allowlist.unsafe_path" in codes
    assert "directory.unsafe_path" in codes
    assert "domain.directory_unsafe_path" in codes


def test_validate_plan_requires_valid_generated_fingerprint_when_policy_requires_it() -> None:
    plan = _valid_plan()
    del plan["generated"]["fingerprint"]
    codes = {issue.code for issue in validate_plan(plan)}
    assert "generated.fingerprint.invalid" in codes

    plan = _valid_plan()
    plan["generated"]["managed_keys"] = ["schema_version"]
    codes = {issue.code for issue in validate_plan(plan)}
    assert "generated.managed_keys.mismatch" in codes

    plan = _valid_plan()
    plan["include"].append("API参考/")
    codes = {issue.code for issue in validate_plan(plan)}
    assert "generated.fingerprint.mismatch" in codes


def test_validate_plan_generated_fingerprint_cannot_be_disabled_by_policy_tampering() -> None:
    plan = generate_plan({"records": {}})
    plan["include"].append("API参考/")
    plan["overwrite_policy"] = {}

    codes = {issue.code for issue in validate_plan(plan)}

    assert "generated.fingerprint.mismatch" in codes
    assert "overwrite_policy.mode_required" in codes
