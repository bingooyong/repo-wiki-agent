# Docs Generation Purity — Code Spec

> Executable contracts for the `docs/0*.md` generation chain: template integrity, curated-content protection, and core-entity scoring.
> Implemented in `repo_wiki/generator/{templates,contracts,engine}.py`, `repo_wiki/scanner/{repository_scanner,artifacts}.py`, `repo_wiki/verifier/service.py`.
> Tests: `tests/test_source_truth_purity.py`.

---

## Scenario: Regenerate overview docs without destroying facts or human content

### 1. Scope / Trigger

Code-spec depth required: this changes a cross-layer contract (fact YAML → template context → rendered docs → verifier gate) and the generation cache key.

Chain: `repo-wiki generate` (DEFAULT profile) → `RepoWikiService.generate` → `write_source_of_truth` → `GenerationEngine.generate_full` → `CORE_DOCUMENT_CONTRACTS` → `docs/0*.md`.
The `qoder-like` profile takes a different branch (`_generate_isolated_eval`) and writes `.repo-agent-eval/`, **not** `docs/`.

### 2. Signatures

```python
# repo_wiki/generator/templates.py
class TemplateRenderer:
    def render(self, template_path: str, context: dict[str, Any]) -> str
    # raises ValueError listing every unresolved ${key} after safe_substitute

# repo_wiki/generator/engine.py
class GenerationEngine:
    def _render_with_cache(
        self, cache_key_prefix: str, template_path: str,
        context: dict[str, Any], required_keys: tuple[str, ...] = ()
    ) -> tuple[str, bool]
    # raises ValueError("missing required context keys: ...") — also on cache-hit paths
    # cache key = stable_hash({"k": prefix, "tpl": path, "tpl_sha256": sha256(template bytes), "ctx": context})

    def _write_doc(self, target: Path, rel_path: str, content: str) -> bool
    # False = preserved existing human-authored doc; True = written

# repo_wiki/scanner/docs_scanner.py
def is_init_generated_doc(rel: str, text: str) -> bool   # reuse this, do not reinvent

# repo_wiki/scanner/artifacts.py
_CURATED_FACT_FILES = {"repo-map.yaml","module-index.yaml","api-index.yaml","data-models.yaml","task-catalog.yaml"}
def write_source_of_truth(root: Path, snapshot) -> dict[str, Path]
```

### 3. Contracts

**Template ↔ context keys**: every `${var}` in a template must exist in the context built by `_build_core_context`, and `DocumentContract.required_keys` must be a subset of that context. Audit all CORE contracts in tests, not just the one you edited.

**Two template copies exist**: `templates/docs/*.j2` (repo, used by default `template_root = root/"templates"`) and `repo_wiki/templates/docs/*.j2` (packaged). A fix applied to only one copy silently fails in the other runtime.

**Curated fact files are read-only for BOTH writers**: the scanner guard (`_CURATED_FACT_FILES`) and every `DocumentContract.output_path`. Generated variants use a `.generated.` infix, e.g. `ai/source-of-truth/task-catalog.generated.yaml` / `.generated.json`.

**Curated signal**: `repo-map.yaml → repository.source_of_truth_status` starting with `curated`. While curated, scanner conclusions must not overwrite curated values; disagreements are emitted as diagnostics.

**Diagnostic record** (`ai/source-of-truth/classification-diagnostics.json`):
```json
{"source_conflicts": [{"label": "source-conflict", "field": "repository.framework",
  "curated_value": "typer-cli", "scanned_value": "typer", "resolution": "kept-curated"}]}
```

**Detection priority (GEN-001)**: package config (`pyproject.toml` / `go.mod` / `package.json` + `tsconfig.json`) > extension counting > README > `repo-wiki.yaml` > historical docs. Framework signals must be matched against the manifest of the detected primary language only; fixture manifests under `tests/` are not product manifests.

**Core-entity scoring** (`DataModelAggregator._identify_core_entities`):
- symbol match uses word boundaries, never `name.lower() in handler.lower()`;
- each reason appears at most once (ordered dedup);
- models sourced from dependency dirs (`node_modules`, `.venv`, `dist`, `build`) or `tests/`/fixtures are ineligible for core, tagged `dependency` / `test-harness`;
- names shorter than 3 chars cannot become core via the API signal alone;
- core threshold stays `3.0` — do not tune it to make output look better.

### 4. Validation & Error Matrix

| Condition | Behavior |
|-----------|----------|
| Template references a key absent from context | `render` raises `ValueError` naming the placeholders |
| `required_keys` missing from context (fresh or cached render) | `_render_with_cache` raises `ValueError("missing required context keys: …")` |
| Template file bytes changed | cache key changes → re-render (old cache must not survive a template fix) |
| New content is init-stub-like AND existing doc is not | `_write_doc` returns False, existing bytes preserved |
| Existing doc is itself a stub | overwrite allowed |
| New content is real (non-stub) | overwrite allowed, even over a previously curated-looking doc |
| Contract `output_path` basename ∈ `_CURATED_FACT_FILES` | contract test fails |
| Fact layer curated and scanner disagrees | keep curated bytes, append `source-conflict` diagnostic |
| Generated doc contains `${...}` outside code fences | verifier `unresolved-placeholders` HARD FAIL, reason `CONTENT_UNRESOLVED_PLACEHOLDER`, details carry path/line/placeholder |
| `${HOME}` inside a fenced code block | ignored (shell samples are legitimate) |

### 5. Good / Base / Bad Cases

- **Good**: `generate` refreshes `docs/01/03/05`, leaves `docs/00-overview.md` and all five curated fact YAMLs byte-identical, tech stack reads Python / typer-cli.
- **Base**: a target repo with no curated marker → scanner writes fact files normally, `source_conflicts == []`.
- **Bad**: pointing a contract at `ai/source-of-truth/task-catalog.yaml`, or letting the `00-overview` stub replace a hand-written overview with a name-disambiguation table.

### 6. Tests Required

`tests/test_source_truth_purity.py`:

| Group | Assertion points |
|-------|------------------|
| Template/context audit | for every CORE contract: no unknown `${}`; `required_keys ⊆ context` |
| Placeholder guard | missing key raises; unresolved `${foo}` never reaches disk |
| required_keys + cache | raises on fresh and cached paths; template edit forces `cached=False` |
| Core entity purity | `in`/`instanceof` (node_modules) and `dm_sales_facts` (tests) not core; one `"API 参数类型"` reason across many endpoints |
| Detection | pyproject.toml forces python; express devDependency in package.json must not label a Python repo |
| Pruning | `node_modules` never scanned |
| Curated conflicts | curated bytes preserved; diagnostics labelled `source-conflict` / `kept-curated` |
| Curated output protection | no contract targets a curated fact file; `generate_full` keeps curated bytes |
| Stub protection | curated overview preserved; stub-over-stub and real-over-curated both write |
| Verifier gate | injected `${foo}` → HARD FAIL with path/line; code-fence sample → PASS |

```bash
.venv/bin/python -m pytest tests/test_source_truth_purity.py -q
.venv/bin/python -m pytest tests -q -k "generator or scanner or contract or verifier or template"
.venv/bin/python -m repo_wiki.main generate && .venv/bin/python -m repo_wiki.main verify --ci
```

### 7. Wrong vs Correct

#### Wrong — silent placeholder substitution

```python
return Template(raw).safe_substitute(materialized)   # ${incremental_governance} ships to readers
```

#### Correct — fail fast and fix the key name

```python
rendered = Template(raw).safe_substitute(materialized)
leftover = sorted(set(re.findall(r"\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}", rendered)))
if leftover:
    raise ValueError(f"unresolved template placeholders: {', '.join(leftover)}")
```

#### Wrong — cache keyed by template path only

```python
key = stable_hash({"k": prefix, "tpl": template_path, "ctx": context})
```

Template edits then appear to have no effect, and the "fix" gets reverted in frustration.

#### Correct — include template bytes

```python
template_digest = hashlib.sha256((self.template_root / template_path).read_bytes()).hexdigest()
key = stable_hash({"k": prefix, "tpl": template_path,
                   "tpl_sha256": template_digest, "ctx": context})
```

#### Wrong — substring symbol matching in scoring

```python
if model.name.lower() in ep_handler:   # a model named "in" matches everything
    score += 1.0
    reasons.append("API 参数类型")      # appended once per endpoint → score stacking
```

#### Correct — boundary match, dedup, source eligibility

```python
if re.search(rf"\b{re.escape(model.name)}\b", ep_handler, re.IGNORECASE):
    score += 1.0
    reason = "API 参数类型"
    if reason not in reasons:
        reasons.append(reason)
```

---

## Common Mistakes

### Mistake: assuming polluted docs mean a polluted scanner

**Symptom**: `docs/05-data-model.md` lists `node_modules` entities, so the plan says "clean the scanner".
**Cause**: the fact YAMLs were already clean; the docs were stale output plus a real scoring defect.
**Fix**: measure `ai/source-of-truth/` first, then separate "stale artifact" from "live defect".
**Prevention**: see the baseline thinking triggers in `../guides/index.md`.

### Mistake: protecting curated files in one writer only

**Symptom**: `task-catalog.yaml` gets clobbered even though `_CURATED_FACT_FILES` lists it.
**Cause**: the guard lived in `write_source_of_truth`, but `TASK_CATALOG_CONTRACT.output_path` wrote the same path from the generator.
**Fix**: assert across ALL contracts that no `output_path` basename is a curated fact file.

### Mistake: trusting `verify --profile qoder-like --ci` as a local purity gate

**Symptom**: NOT_READY with `QODER_META_ROOT_MISSING` after a clean purity fix.
**Cause**: no READY release exists yet; that gate needs `release-publish` output, which is a different task's deliverable.
**Fix**: use default `verify --ci` (zero hard failures) for purity work, and prove any qoder-like failure pre-exists on the base commit before blaming your diff.