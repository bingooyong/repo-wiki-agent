# External Baseline Registry — Code Spec

> Executable contract for consuming read-only Qoder reference baselines that live in **other** repositories.
> Implemented by `repo_wiki/verifier/external_baseline_registry.py` + `scripts/verify_baseline_registry.py`.
> Reference data contract: `docs/specs/qoder-knowledge-card-baseline-contract.md`.

---

## Scenario: Freeze and verify an external Qoder baseline

### 1. Scope / Trigger

Code-spec depth is mandatory here because this is infra + cross-layer contract work:
a new on-disk registry format, a new CLI script signature, and a fingerprint algorithm
shared with the existing canonical baseline guard.

Two distinct registries exist — do not confuse them:

| Module | Baseline location | Purpose |
|--------|-------------------|---------|
| `qoder_baseline_registry.py` | `<target repo>/.qoder/repowiki/zh` (canonical, in-repo) | Gates `repo-wiki compare`; rejects `.repo-agent-eval/*` as baseline |
| `external_baseline_registry.py` | Any path in **another** repo, described by `ai/baselines/registry.json` | Gap analysis only; never a compare gate |

### 2. Signatures

```python
# repo_wiki/verifier/external_baseline_registry.py
REGISTRY_SCHEMA_VERSION = 1
HASH_ALGORITHM = "sha256(relpath_posix + NUL + file_bytes + NUL), files sorted by relpath"

def load_registry(path: Path) -> dict[str, Any]
def resolve_entry_root(entry: dict, overrides: dict[str, Path] | None = None) -> Path
def collect_knowledge_stats(root: Path) -> dict[str, Any]
def collect_longform_stats(root: Path) -> dict[str, Any]
def collect_stats(kind: str, root: Path) -> dict[str, Any]      # kind: knowledge_cards | long_form_wiki
def refresh_entry(entry: dict, root: Path) -> dict[str, Any]    # writes content_hash/file_count/stats
def verify_entry(entry: dict, root: Path) -> dict[str, Any]
def verify_registry(registry_path: Path, overrides: dict[str, Path] | None = None) -> dict[str, Any]

# reused, NOT reimplemented
from repo_wiki.verifier.qoder_baseline_registry import compute_baseline_fingerprint
def compute_baseline_fingerprint(root: Path) -> tuple[str, int]  # (sha256 hexdigest, file_count)
```

```bash
python scripts/verify_baseline_registry.py [--registry PATH] [--baseline-root ID=PATH ...] [--update] [--json PATH]
# default registry: <repo>/ai/baselines/registry.json
# exit 0 = PASS, exit 1 = FAIL (also 1 when --update cannot find a baseline root)
```

### 3. Contracts

Registry file (`ai/baselines/registry.json`):

| Field | Type | Constraint |
|-------|------|------------|
| `schema_version` | int | Must equal `1`, else `ValueError` |
| `baselines` | list | Non-empty, else `ValueError` |
| `baselines[].id` | str | Unique; used as `--baseline-root` override key |
| `baselines[].kind` | str | `knowledge_cards` or `long_form_wiki`; anything else raises `ValueError` |
| `baselines[].source_repo_root` | str | Absolute local hint, machine-specific |
| `baselines[].source_path` | str | Path relative to `source_repo_root` |
| `baselines[].content_hash` | str | sha256 hexdigest, **written by `--update`, never hand-typed** |
| `baselines[].file_count` | int | Must equal fingerprint's count |
| `baselines[].stats` | object | Must equal `collect_stats(kind, root)` exactly |
| `baselines[].compare_support` | object | `{repo_wiki_compare: bool, reason: str}` — honest capability record |

Fingerprint algorithm (order matters, must stay byte-identical to the canonical guard):

```python
h = hashlib.sha256()
for path in sorted(p for p in root.rglob("*") if p.is_file()):
    h.update(path.relative_to(root).as_posix().encode("utf-8"))
    h.update(b"\0")
    h.update(path.read_bytes())
    h.update(b"\0")
```

No mtime, no absolute paths, no directory entries → reproducible across machines and checkouts.

Knowledge-card metrics (consumed by later tasks):
`module_count`, `module_card_counts`, `repo_card_counts`, `relation_counts{depends_on,related_to,version_of}`,
`relation_reason_coverage` = non-empty reasons / (`related_to` + `version_of`),
`evidence.refs_per_1k_chars`, `missing_module_yaml[]`, `missing_card_files[]`.

Long-form metrics:
`page_count`, `catalog_count`, `root_catalog_count`, `knowledge_relation_count`, `progress_status`,
`mermaid_coverage`, `cite_block_coverage`, `line_anchor_coverage`, `page_chars{min,median,max,total}`.

### 4. Validation & Error Matrix

| Condition | Behavior |
|-----------|----------|
| `schema_version != 1` | `load_registry` raises `ValueError` |
| `baselines` empty / not a list | `load_registry` raises `ValueError` |
| Unknown `kind` | `collect_stats` raises `ValueError` |
| Baseline root missing | `verify_entry` → `status=FAIL`, mismatch `baseline root missing: <path>`; `--update` prints FAIL and returns 1 |
| Hash differs from registry | `status=FAIL`, mismatch `content_hash mismatch: registry=… actual=…` |
| `file_count` differs | `status=FAIL`, mismatch `file_count mismatch: …` |
| Stats differ | `status=FAIL`, mismatch `stats mismatch against registry` |
| Two consecutive fingerprints differ | `status=FAIL`, `hash_reproducible=false` (baseline being mutated concurrently) |
| `--baseline-root` without `=` | `SystemExit` with usage message |
| Any entry FAIL | `verify_registry` → `status=FAIL`, `failed_entries=[ids]`, script exit 1 |

### 5. Good / Base / Bad Cases

- **Good**: registry refreshed by `--update`, verify run twice → identical hashes, `REGISTRY PASS`, exit 0.
- **Base**: baseline checked out at a different path → pass `--baseline-root ai-testing-knowledge-zh=/new/path/knowledge/zh`; no registry edit needed.
- **Bad**: hand-editing `content_hash`, or pointing `source_path` at a `.repo-agent-eval` run and calling it a baseline. Runs are process artifacts, never baselines.

### 6. Tests Required

`tests/test_external_baseline_registry.py` (synthetic fixtures; real-baseline case skips when absent):

| Test | Assertion points |
|------|------------------|
| knowledge stats | `module_count`, per-type card counts, `relation_reason_coverage == 0.5` when one reason is empty |
| missing card file | deleting `概述.md` yields `missing_card_files == ["root/概述.md"]` |
| long-form stats | coverage ratios are `0.5` with one of two pages carrying mermaid/cite/`#L` |
| hash reproducibility + tamper | `verify_entry` PASS before edit; FAIL with `content_hash mismatch` after edit |
| missing root | FAIL with `baseline root missing` |
| registry load/override | bad schema raises; override resolves; missing root FAIL vs override PASS |
| real baseline | `verify_registry` PASS, `module_count == 15`, `relation_reason_coverage == 1.0` |

Commands:

```bash
.venv/bin/python scripts/verify_baseline_registry.py
.venv/bin/python -m pytest tests/test_external_baseline_registry.py -q
.venv/bin/python -m pytest tests -q -k "baseline or comparator or parity"
```

### 7. Wrong vs Correct

#### Wrong — trusting planning text about artifact existence

```text
PRD: "long-form wiki is screenshots only, 61/70, not on disk" → record long_form_available: false
PRD: "ai/source-of-truth is polluted by node_modules" → plan a scanner cleanup
```

Both premises were false on disk: the long-form wiki was complete (70 pages, `progress_status=completed`),
and `ai/source-of-truth/` was already clean (41 models, 0 polluted entries). The pollution survived only
in generated `docs/01/03/05`.

#### Correct — measure first, then write the contract

```bash
find <baseline>/zh/content -name '*.md' | wc -l
python -c "import json;print(json.load(open('<baseline>/zh/meta/repowiki-metadata.json'))['wiki_repo']['progress_status'])"
```

Record measured numbers, cite file:line for every claimed defect, and correct the PRD when evidence contradicts it.

#### Wrong — loosening a gate to make a comparison pass

```python
# editing _compare_readiness_failures thresholds (0.80 / 0.70) to accept 8 pages vs 70
```

#### Correct — record the unsupported capability honestly

```json
"compare_support": {
  "repo_wiki_compare": false,
  "reason": "register_single_qoder_baseline forces baseline == <target repo>/.qoder/repowiki/zh; cross-repo baseline cannot be consumed without writing into the baseline repo (forbidden)."
}
```

---

## Common Mistakes

### Mistake: treating `compare` as a cross-repo comparator

**Symptom**: `repo-wiki compare --baseline /other/repo/.qoder/repowiki/zh` fails with `Baseline must be canonical …`.
**Cause**: `cli.py:734` → `qoder_baseline_registry.py:65-81` resolves the canonical path from the **target's** repo root and rejects any other path.
**Fix**: Use `external_baseline_registry` for cross-repo gap analysis; leave `compare` semantics untouched.
**Prevention**: Check `compare_support` in the registry before promising a comparison in a plan.

### Mistake: inventing module dependencies to look complete

**Symptom**: exported cards carry `depends_on` edges the baseline does not have.
**Cause**: assuming a richer graph is better. The ai-testing baseline has `depends_on: 0`, `related_to: 6`, `version_of: 1`, and every reason names a real file plus a call/import.
**Fix**: emit a relation only with file+symbol evidence; otherwise leave it empty.
**Prevention**: gate on `relation_reason_coverage`, not on relation count.

### Mistake: assuming baseline artifacts are versioned in their own repo

**Symptom**: citing the baseline `commit` as proof of a frozen baseline.
**Cause**: ai-testing's `.qoder/` is **untracked**; `commit` only records the source repo HEAD at export time.
**Fix**: freeze via this registry's `content_hash` and re-verify before each acceptance run.