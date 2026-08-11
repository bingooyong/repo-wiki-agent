# Qoder directory and metadata interface inventory (Phase 41.1)

**Fixture path (read-only):** `<repo>/.qoder/repowiki/zh`
**Reference host:** `reference-repo` (local path via `REFERENCE_REPO_ROOT`; default in tests matches common dev layout)
**Policy:** This path is **immutable** for repo-agent tasks; inventory and tests MUST NOT write to it.

---

## 1. Purpose

Freeze the **published Qoder interface** that repo-agent release output should remain compatible with:

- Stable `content/` root for Markdown wiki pages.
- Stable `meta/` root for machine-readable sidecars.
- Evidence and diagram conventions discoverable from structure, not from copying baseline prose.

---

## 2. Directory interface

| Path (under `repowiki/zh`) | Role |
|----------------------------|------|
| `content/` | All reader-facing Markdown; mixed top-level `.md` stubs and Chinese topical directories. |
| `meta/repowiki-metadata.json` | Canonical Qoder metadata blob (catalogs, items, snippets, relations). |

**Reference observation (non-normative counts):** ~180 Markdown pages; max relative depth under `content/` observed at 4 segments; `API参考/` subtree contains dedicated service API pages plus nested groupings.

Machine-readable invariants (no prose excerpts) live in:

`tests/fixtures/qoder_release_interface_invariants.json`

Automated read-only checks:

`tests/test_qoder_reference_release_interface_fixture.py`

---

## 3. Content patterns (structural)

Validated on the fixture without quoting Qoder text:

| Signal | Meaning |
|--------|---------|
| Opening `<cite>...</cite>` blocks | Declared evidence scope per page. |
| `## 目录` section | In-page outline / navigation contract. |
| Fenced ` ```mermaid` blocks | Structural diagrams (flowchart, sequence, ER, etc.). |

On the Reference snapshot, structural presence of all three held for spot-checked pages including under `API参考/`.

---

## 4. Metadata interface (`repowiki-metadata.json`)

**Required top-level keys** (empty/missing → fixture invalid for comparison):

- `wiki_catalogs`, `wiki_items` — catalog/item graph for navigation and page binding.
- `code_snippets`, `source_files` — code span and file inventory.
- `knowledge_relations` — cross-links / relations.
- `wiki_overview`, `wiki_readme`, `wiki_repo` — repository and overview records (object-shaped).

Tests assert key presence, non-null values, and minimal collection population; they do **not** embed Qoder content strings.

---

## 5. Compatibility vs repo-agent release

| Aspect | Qoder (this fixture) | repo-agent target (per product plan) |
|--------|---------------------|----------------------------------------|
| Manifest | Embedded in Qoder meta / external tooling | `manifest.json` at release root |
| Content root | `repowiki/zh/content` | Same under `.repo-agent-eval/repowiki/zh` |
| Meta | `repowiki-metadata.json` | Extended meta + `navigation.json` etc. |

Phase 41.1 only **documents and tests** Qoder’s side; extending repo-agent meta is out of scope here.

---

## 6. Read-only verification

- No task step opens files for write under `.qoder/repowiki/zh`.
- Automated test `test_metadata_not_mutated_after_reads` asserts mtime/size unchanged after read-only ingest.

---

## 7. Evidence index

| Artifact | Path |
|----------|------|
| Fixture invariants (JSON) | `tests/fixtures/qoder_release_interface_invariants.json` |
| Read-only tests | `tests/test_qoder_reference_release_interface_fixture.py` |
| Product context | `docs/wiki-source-code-and-docs-intelligence-plan.md`, `docs/wiki-systematic-construction-master-plan.md` |
