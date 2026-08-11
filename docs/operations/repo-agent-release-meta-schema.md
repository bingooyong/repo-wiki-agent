# Repo-agent release meta schema (Phase 41.2)

This document specifies machine-readable artifacts under:

```text
.repo-agent-eval/repowiki/zh/
├── manifest.json              # EvalManifest / release overlay (existing)
├── content/                   # Qoder-compatible reader tree
└── meta/
    ├── repowiki-metadata.json       # Qoder-required blob (+ optional extras)
    ├── navigation.json               # Viewer navigation tree
    ├── page-registry.json            # Page inventory & taxonomy binding
    ├── source-inventory.json         # Source-code references
    ├── docs-inventory.json           # Non-code documentation references
    ├── service-registry.json          # Runnable services / libraries
    ├── api-inventory.json             # HTTP/RPC/API surface rows
    ├── data-model-inventory.json      # Entities, DTOs, migrations
    ├── evidence-index.json           # Citations ↔ source spans
    ├── diagram-index.json             # Mermaid diagrams by page
    ├── quality-report.json           # Verification / parity summary
    └── release.json                  # Publisher release record
```

Normative validators live in `repo_wiki/orchestration/release_meta_schema.py`.

## Versioning rules

| Rule | Detail |
|------|--------|
| Qoder compat | `repowiki-metadata.json` does **not** require `schema_version`; validators enforce Task 41.1 required keys and permit unknown keys. |
| Repo-agent sidecars | Each file MUST set `schema_version` to `repo_agent.<artifact>/<major>.<minor>` (regex enforced). |
| Patch bump | Optional fields only. |
| Minor bump | May add required fields for **new** writers; readers SHOULD tolerate absence until adoption. |
| Major bump | Breaking rename/removal — requires migration notes. |

## Canonical `schema_version` literals

Defined as constants in `release_meta_schema.py`:

| File | Constant | Value |
|------|----------|-------|
| `navigation.json` | `SCHEMA_VERSION_NAVIGATION` | `repo_agent.navigation/1.0` |
| `page-registry.json` | `SCHEMA_VERSION_PAGE_REGISTRY` | `repo_agent.page_registry/1.0` |
| `source-inventory.json` | `SCHEMA_VERSION_SOURCE_INVENTORY` | `repo_agent.source_inventory/1.0` |
| `docs-inventory.json` | `SCHEMA_VERSION_DOCS_INVENTORY` | `repo_agent.docs_inventory/1.0` |
| `service-registry.json` | `SCHEMA_VERSION_SERVICE_REGISTRY` | `repo_agent.service_registry/1.0` |
| `api-inventory.json` | `SCHEMA_VERSION_API_INVENTORY` | `repo_agent.api_inventory/1.0` |
| `data-model-inventory.json` | `SCHEMA_VERSION_DATA_MODEL_INVENTORY` | `repo_agent.data_model_inventory/1.0` |
| `evidence-index.json` | `SCHEMA_VERSION_EVIDENCE_INDEX` | `repo_agent.evidence_index/1.0` |
| `diagram-index.json` | `SCHEMA_VERSION_DIAGRAM_INDEX` | `repo_agent.diagram_index/1.0` |
| `quality-report.json` | `SCHEMA_VERSION_QUALITY_REPORT` | `repo_agent.quality_report/1.0` |
| `release.json` | `SCHEMA_VERSION_META_RELEASE` | `repo_agent.meta_release/1.0` |

## Field contracts (summary)

### `meta/repowiki-metadata.json` (Qoder)

**Required keys** (from `tests/fixtures/qoder_release_interface_invariants.json`):

- `wiki_catalogs`, `wiki_items`, `code_snippets`, `source_files`, `knowledge_relations` — arrays or objects (non-null).
- `wiki_overview`, `wiki_readme`, `wiki_repo` — JSON objects.

Optional: `schema_version` (string) if a future tooling layer tags the blob.

### `meta/navigation.json`

| Field | Req | Type | Notes |
|-------|-----|------|-------|
| `schema_version` | yes | string | `repo_agent.navigation/1.0` |
| `generated_at` | yes | string | ISO-8601 timestamp |
| `navigation_tree` | yes | array | Compatible with viewer / manifest tree nodes |

Optional: `taxonomy_version` (string).

### `meta/page-registry.json`

| Field | Req | Type |
|-------|-----|------|
| `schema_version` | yes | string |
| `generated_at` | yes | string |
| `pages` | yes | array of objects |

**Per-page required:** `page_id`, `relative_path`, `category`, `page_type`.

### `meta/source-inventory.json`

| Field | Req | Type |
|-------|-----|------|
| `schema_version` | yes | string |
| `generated_at` | yes | string |
| `repository_root` | yes | string |
| `files` | yes | array |

**Per-file required:** `path`.

### `meta/docs-inventory.json`

| Field | Req | Type |
|-------|-----|------|
| `schema_version` | yes | string |
| `generated_at` | yes | string |
| `documents` | yes | array |

**Per-document required:** `path`.

### `meta/service-registry.json`

| Field | Req | Type |
|-------|-----|------|
| `schema_version` | yes | string |
| `generated_at` | yes | string |
| `services` | yes | array |

**Per-service required:** `service_id`, `display_name`, `runtime_family`.

### `meta/api-inventory.json`

| Field | Req | Type |
|-------|-----|------|
| `schema_version` | yes | string |
| `generated_at` | yes | string |
| `endpoints` | yes | array |

**Per-endpoint required:** `service_id`, `method`, `path`.

### `meta/data-model-inventory.json`

| Field | Req | Type |
|-------|-----|------|
| `schema_version` | yes | string |
| `generated_at` | yes | string |
| `models` | yes | array |

**Per-model required:** `model_id`, `kind`, `service_id`.

### `meta/evidence-index.json`

| Field | Req | Type |
|-------|-----|------|
| `schema_version` | yes | string |
| `generated_at` | yes | string |
| `spans` | yes | array |

**Per-span required:** `span_id`, `page_relative_path`, `source_path`.
Optional integer line numbers: `start_line`, `end_line`.

### `meta/diagram-index.json`

| Field | Req | Type |
|-------|-----|------|
| `schema_version` | yes | string |
| `generated_at` | yes | string |
| `diagrams` | yes | array |

**Per-diagram required:** `diagram_id`, `page_relative_path`, `kind` (e.g. `mermaid`).

### `meta/quality-report.json`

| Field | Req | Type |
|-------|-----|------|
| `schema_version` | yes | string |
| `summary` | yes | object |

**`summary` required:** `profile`, `grade`.
Optional: `strict_mode` (bool).
Optional top-level: `metrics` (object), `parity_summary` (object).

### `meta/release.json` (publisher)

Written by `repo_wiki/orchestration/release_publisher.py` when a run is published.

| Field | Req | Type |
|-------|-----|------|
| `schema_version` | yes | `repo_agent.meta_release/1.0` |
| `release_status` | yes | `READY` \| `NOT_READY` \| `REVOKED` |
| `release_id` | yes | string |
| `source_run_id` | yes | string |
| `published_at` | yes | string |
| `target_git_commit` | no | `null` or 7–40 hex commit |
| `manifest_path` | no | string path to release `manifest.json` |

## Validation API

```python
from repo_wiki.orchestration.release_meta_schema import validate_meta_file

errors = validate_meta_file("navigation.json", payload)
assert not errors
```

## Tests & fixtures

- Fixtures: `tests/fixtures/release_meta/*.json`
- Tests: `tests/test_release_meta_schema.py`

## Cross-references

- Qoder interface inventory: `docs/operations/qoder-directory-metadata-interface-inventory.md`
- Product plan: `docs/wiki-source-code-and-docs-intelligence-plan.md`

## Stage 0 READY publish contract

The only canonical path from a generated run to the reader-facing READY tree is:

```bash
repo-wiki generate --profile qoder-like --output .repo-agent-eval
repo-wiki verify --profile qoder-like --ci --output .repo-agent-eval
repo-wiki release-publish --output .repo-agent-eval --run <run_id>
```

`release-publish` is intentionally narrow. It does not repair, regenerate, or select an unverified tree. The selected run must provide:

- `readiness_state: READY` or `ready: true`.
- `target_dirty: false`.
- `git_fresh` absent or `true`.
- a strict verify report in `report_paths` whose JSON body has `grade: "PASS"`.
- canonical candidate roots under `<run>/repowiki/zh/content` and `<run>/repowiki/zh/meta`.
- candidate content and meta trees with no symlinks.
- valid top-level `meta/*.json` sidecars.

The publisher writes the fixed reader path `.repo-agent-eval/repowiki/zh/` only after all checks pass.

## Atomic READY replacement and rollback boundary

READY replacement is a single local transaction:

1. Stage the selected run under a temporary directory inside `.repo-agent-eval/`.
2. Write the release overlay `manifest.json` and `meta/release.json` into the staging tree.
3. Move any existing `.repo-agent-eval/repowiki/zh/` to `.repo-agent-eval/repowiki/zh.__backup__`.
4. Move the staged tree into `.repo-agent-eval/repowiki/zh/`.
5. Atomically append the same release record to `.repo-agent-eval/release-history.json`.
6. Remove `zh.__backup__` after READY and history are both committed.

If any step from the backup move through the history append fails, the publisher restores the previous READY tree from `zh.__backup__`. If there was no previous READY tree, the failed new tree is removed. No user-facing rollback command is required for this Stage 0 contract; rollback is the publisher's failure path.

## `release-history.json` semantics

`release-history.json` is an audit log of successful READY publishes only. A rejected candidate, failed strict verify gate, invalid sidecar, failed filesystem swap, or failed history append MUST NOT add an entry. The history file is written through a temporary file and atomic replace so a write failure leaves the prior history bytes intact.

An existing history file that is unreadable, invalid JSON, not an array, or contains non-object entries blocks publication. The publisher restores the previous READY tree and leaves the invalid history bytes untouched for operator investigation.

If the history append cannot be committed after a new READY tree has been staged, the publish is considered failed and the previous READY tree is restored. This keeps `.repo-agent-eval/repowiki/zh/`, `meta/release.json`, and `release-history.json` coherent.
