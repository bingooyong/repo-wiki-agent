# Knowledge Plan Core Specification

## Purpose

The knowledge plan is a first-class, version-managed YAML contract that sits between repository scanning/IA compilation and later wiki generation orchestration. It is intentionally human-editable and protects generated sections from silent overwrite.

## Location and Version

- Default path: `.repo-wiki/knowledge-plan.yaml`
- Schema version: `repo_agent.knowledge_plan/1.0`
- Python package: `repo_wiki.knowledge_plan`

## YAML Shape

Top-level fields:

- `schema_version`: required schema version string.
- `generated_at`: UTC timestamp for the generated plan.
- `model`: Knowledge Model v3 provenance, summary, input fingerprints, and deterministic model fingerprint.
- `include`: enabled repository-relative IA directory paths to include.
- `exclude`: repository-relative paths intentionally excluded from planning.
- `docs.allowlist`: repository-relative documentation artifacts allowed as source material, derived from `doc_artifacts`.
- `directories`: IA roots from `TaxonomyProfileCompiler`, each with record families, evidence thresholds, and template references.
- `page_templates`: explicit template definitions with ids, titles, and source contracts.
- `business_domains`: deterministic domain groups derived from service runtime and evidence paths.
- `manual_sections`: operator-owned notes or overrides that are not part of the managed fingerprint.
- `overwrite_policy`: declares manual-edit protection behavior.
- `generated.fingerprint`: SHA-256 fingerprint of the managed/generated portion.

## Manual Edit Protection

The managed fingerprint covers generated fields only. `manual_sections` and `generated` metadata are excluded. Writers recompute the current managed fingerprint before replacing an existing plan. If the existing managed content differs from its stored fingerprint, default writes raise `ManualEditConflictError`. For existing managed plans whose generated content is clean, default writes preserve `manual_sections` while refreshing generated fields. Callers must choose an explicit force overwrite (`overwrite=True`) to replace manual sections and generated content.

## Validation

`validate_plan(plan)` returns structured issues with:

- `severity`
- `path`
- `message`
- `code`

Current validation checks schema version, unsafe path-like values for include/exclude/docs allowlist/directory/domain directory fields, duplicate directory paths, docs allowlist shape, template id shape and references, business-domain directory mappings, overwrite-policy shape, generated managed key metadata, and managed fingerprint integrity for current-schema/generated plans. The overwrite policy cannot disable generated metadata or fingerprint integrity validation. Path-like fields must be repository-relative and must not use absolute paths, `..`, home expansion, environment expansion, or NUL bytes.

## Docs Scanner Consumption

When docs inventory scanning is called without an explicit `docs_filter`, the scanner loads `.repo-wiki/knowledge-plan.yaml` if it exists and validates successfully. The plan's include/exclude/docs allowlist then bounds documentation discovery. Explicit `docs_filter` arguments take precedence. Filter expansion resolves candidates under the repository root and ignores traversal or absolute patterns before reading or globbing.

## Incremental Impact

`analyze_impact(...)` compares old/new plans and optionally old/new Knowledge Model v3 payloads. It reports impacted directories, pages, templates, domains, docs, and deterministic reasons. The algorithm is intentionally conservative: it maps changed Knowledge Model record families back to directories by `record_families`, and include/exclude scope changes back to affected directories, pages, templates, and docs when possible.

## Public APIs

Import from `repo_wiki.knowledge_plan`:

- `generate_plan(knowledge_model, taxonomy_profile=None)`
- `validate_plan(plan)`
- `dump_plan_yaml(plan)` / `load_plan_yaml(text)`
- `load_plan(path=DEFAULT_PLAN_PATH)` / `write_plan(plan, path=DEFAULT_PLAN_PATH, overwrite=False, merge=False)`
- `analyze_impact(old_plan=None, new_plan=None, old_model=None, new_model=None)`
- `compute_managed_fingerprint(plan)` / `has_manual_managed_edits(plan)`
- `ManualEditConflictError`
