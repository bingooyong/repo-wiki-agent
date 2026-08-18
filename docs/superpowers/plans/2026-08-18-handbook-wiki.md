# Handbook Wiki Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `repo-wiki verify --profile qoder-like` all-green on the FastAPI RealWorld sample mean a readable handbook (what this is, how to run, which file to edit) without relaxing HARD/SOFT gates or the 95% citation floor.

**Architecture:** Keep `scan → plan → evidence → compose → write → verify`. Change three places: onboarding evidence + page contracts, compose rejection plus fallback copy, and qoder-like HARD checks (four handbook codes; isolated `--output` ignored by dirty-worktree). Fallback stays DEGRADED. No new generator. No new taxonomy.

**Tech Stack:** Existing Python CLI (`repo_wiki`), pytest, ruff, qoder-like verifier, compact LLM prompts. Sample: nsidnev/fastapi-realworld-example-app.

**Spec:** `docs/superpowers/specs/2026-08-18-handbook-wiki-design.md` (PR #92).

## Global Constraints

- Do not relax existing HARD or SOFT. Do not remove codes from `STRICT_HARD_CODES`.
- Do not lower `QODER_CITATION_FACT_COVERAGE_LOW` (`ratio < 0.95`).
- Do not treat fallback as PASS. `QODER_PAGE_QUALITY_STATE_DEGRADED` stays HARD.
- Do not merge PRs #71–#90. Do not generate in Tasks 1–7.
- Product branch from current `main`. Locally merge `origin/cursor/fix-fallback-onboarding-wiki-8442` (PR #91, `23e2957`). Do not `gh pr merge`.
- Keep API keys out of settings, YAML, commands, logs, docs, and commits.
- Task 8 (sample generate+verify) is a later eval, not the product PR.
- SHA stack: `main` plus locally merged #91 only, unless Task 8 lists extra reviewed SHAs.

---

## File map

- Merge (product branch only): PR #91 `repo_wiki/orchestration/service.py`, `tests/test_fallback_onboarding_markdown.py`
- Create: `repo_wiki/verifier/handbook.py` — `HANDBOOK_META_PHRASES`, `contains_generator_meta`, `GENERATOR_META_REJECTION`, page matchers
- Create: `tests/test_handbook.py` — three `contains_generator_meta` tests and ten HARD tests
- Create: `tests/test_composer_handbook_meta.py`
- Create: `tests/test_onboarding_evidence_ranking.py` — three required ranking tests
- Create: `tests/test_dirty_output_ignored.py` — output-only PASS; extra `app/secret.py` FAIL
- Modify: `repo_wiki/generator/composer.py` — `_validate_output` after insufficient prose; `_build_compact_prompt` handbook cites
- Modify: `repo_wiki/orchestration/service.py` — treat `GENERATOR_META_REJECTION` like `"Insufficient prose content"`
- Modify: `repo_wiki/evidence/ranking.py` — README/settings/`main.py` for overview/install; `authentication.py` outranks README for security; no global README boost on API pages
- Modify: `repo_wiki/verifier/qoder_strict_verifier.py` — four HARD codes, four checks, `_git_dirty` ignores isolated output
- Modify: `repo_wiki/cli.py` — thread `--output` into `verify_qoder_like`
- Modify: `repo_wiki/prompts/fragments.py` — same-line/next-line README cites; API `app/api/routes/` cite when evidence exists
- Touch `tests/test_qoder_like_verifier.py` only if it snapshots the old HARD set
- Do not edit sample-repo business code. Do not gitignore output as the pass line.

---

### Task 1: PR #91 fallback (still DEGRADED)

**Files:**
- Merge: `origin/cursor/fix-fallback-onboarding-wiki-8442` @ `23e2957`
- Test: `tests/test_fallback_onboarding_markdown.py`

**Interfaces:**
- Consumes: `RepoWikiService._fallback_markdown_for_failed_page(page, binding) -> str`
- Produces: readable fallback; no generator meta; still DEGRADED

- [ ] **Step 1: Locally merge #91**

```bash
git fetch origin cursor/fix-fallback-onboarding-wiki-8442
git merge --no-ff 23e2957 -m "merge: fallback onboarding wiki from #91"
```

Do not `gh pr merge`. Do not merge #71–#90.

- [ ] **Step 2: Run fallback tests**

```bash
pytest tests/test_fallback_onboarding_markdown.py -v
```

Expected: PASS. Confirm:

- no `fallback composer` / `repo-agent` / `该页面对应` / `evidence ranking`
- README substance + `<cite>`
- empty binding invents no routes
- still DEGRADED (`QODER_PAGE_QUALITY_STATE_DEGRADED` remains HARD)

- [ ] **Step 3: Patch only on spec gap**

If #91 still emits §4.2 / §5.1 phrases, strip them. Do not make fallback PASS.

- [ ] **Step 4: Commit if a spec-gap patch landed**

```bash
git add repo_wiki/orchestration/service.py tests/test_fallback_onboarding_markdown.py
git commit -m "fix: keep fallback pages readable without generator meta"
```

---

### Task 2: Reject generator meta at compose time

**Files:**
- Create: `repo_wiki/verifier/handbook.py`
- Create: `tests/test_handbook.py`
- Create: `tests/test_composer_handbook_meta.py`
- Modify: `repo_wiki/generator/composer.py`
- Modify: `repo_wiki/orchestration/service.py`

**Interfaces:**
- `HANDBOOK_META_PHRASES = ("fallback composer", "repo-agent", "该页面对应", "evidence ranking")`
- `contains_generator_meta(markdown: str) -> bool`
- `GENERATOR_META_REJECTION = "Handbook generator meta content"`
- Composer reject is page-local (not circuit-break), same as `"Insufficient prose content"`

- [ ] **Step 1: Write the three failing tests**

```python
from repo_wiki.verifier.handbook import contains_generator_meta


def test_contains_generator_meta_detects_fallback_composer() -> None:
    assert contains_generator_meta("本页由 fallback composer 生成。") is True


def test_contains_generator_meta_detects_chinese_page_id_template() -> None:
    assert contains_generator_meta("该页面对应 `project-overview`，由 repo-agent 写出。") is True


def test_contains_generator_meta_ignores_innocent_readme() -> None:
    assert contains_generator_meta("按 README.rst Quickstart 安装 PostgreSQL。") is False
```

- [ ] **Step 2: Run to verify fail**

```bash
pytest tests/test_handbook.py::test_contains_generator_meta_detects_fallback_composer \
  tests/test_handbook.py::test_contains_generator_meta_detects_chinese_page_id_template \
  tests/test_handbook.py::test_contains_generator_meta_ignores_innocent_readme -v
```

Expected: FAIL (`ImportError` for `repo_wiki.verifier.handbook`).

- [ ] **Step 3: Minimal `handbook.py`**

```python
from __future__ import annotations

HANDBOOK_META_PHRASES: tuple[str, ...] = (
    "fallback composer",
    "repo-agent",
    "该页面对应",
    "evidence ranking",
)
GENERATOR_META_REJECTION = "Handbook generator meta content"


def contains_generator_meta(markdown: str) -> bool:
    lowered = markdown.lower()
    return any(phrase.lower() in lowered for phrase in HANDBOOK_META_PHRASES)
```

- [ ] **Step 4: Re-run the three tests — expected PASS**

- [ ] **Step 5: Write failing composer tests in `tests/test_composer_handbook_meta.py`**

```python
def test_validate_output_rejects_generator_meta_after_sufficient_prose(...) -> None:
    result = composer._validate_output(meta_markdown, handbook_input)
    assert result.rejected is True
    assert result.rejection_reason == "Handbook generator meta content"


def test_validate_output_accepts_handbook_prose_without_meta(...) -> None:
    result = composer._validate_output(clean_markdown, handbook_input)
    assert result.rejection_reason != "Handbook generator meta content"


def test_generator_meta_rejection_is_page_local_like_insufficient_prose(...) -> None:
    # Mirror test_insufficient_prose_rejects_do_not_trip_circuit_breaker
    assert result["llm"]["provider_disabled_after_failures"] is False
```

- [ ] **Step 6: Run `pytest tests/test_composer_handbook_meta.py -v` — expected FAIL**

- [ ] **Step 7: Composer — after insufficient-prose check in `_validate_output`**

```python
from repo_wiki.verifier.handbook import GENERATOR_META_REJECTION, contains_generator_meta

if not result.rejection_reason and contains_generator_meta(content):
    result.rejection_reason = GENERATOR_META_REJECTION
```

- [ ] **Step 8: Orchestration — page-local rejection set**

```python
from repo_wiki.verifier.handbook import GENERATOR_META_REJECTION

_PAGE_LOCAL_QUALITY_REJECTIONS = frozenset(
    {"Insufficient prose content", GENERATOR_META_REJECTION}
)
if output.rejection_reason not in _PAGE_LOCAL_QUALITY_REJECTIONS:
    note_provider_failure()
```

- [ ] **Step 9: Run**

```bash
pytest tests/test_handbook.py tests/test_composer_handbook_meta.py \
  tests/test_compose_circuit_break.py tests/test_fallback_onboarding_markdown.py -v
```

Expected: PASS. 529/timeout still trip the breaker.

- [ ] **Step 10: Commit**

```bash
git add repo_wiki/verifier/handbook.py repo_wiki/generator/composer.py \
  repo_wiki/orchestration/service.py tests/test_handbook.py \
  tests/test_composer_handbook_meta.py
git commit -m "feat: reject handbook generator-meta in compose"
```

---

### Task 3: Onboarding evidence ranking

**Files:**
- Modify: `repo_wiki/evidence/ranking.py` (`score_evidence_for_page`)
- Create: `tests/test_onboarding_evidence_ranking.py`
- Keep passing: `tests/test_evidence_ranking.py`

**Interfaces:**
- Overview/install: README, settings, `app/main.py` rank high
- Security: `app/api/dependencies/authentication.py` outranks README
- API pages: do not globally boost README

- [ ] **Step 1: Write the three required failing tests**

```python
def test_overview_ranks_readme_settings_and_main() -> None:
    ...


def test_installation_ranks_readme_and_main() -> None:
    ...


def test_security_ranks_authentication_over_readme() -> None:
    ...
```

`test_overview_ranks_readme_settings_and_main`: `page_id="project-overview"`. `README.rst`, `app/core/settings.py`, `app/main.py` each score above `app/models/article.py`.

`test_installation_ranks_readme_and_main`: `page_id="installation"`. README and `app/main.py` score above unrelated `tests/test_unrelated.py`.

`test_security_ranks_authentication_over_readme`: `page_id="security-overview"`, `SECURITY_COMPLIANCE`. `authentication.py` score > README Quickstart.

- [ ] **Step 2: `pytest tests/test_onboarding_evidence_ranking.py -v` — expected FAIL**

- [ ] **Step 3: Page-local boosts in `score_evidence_for_page`**

Onboarding page ids: `project-overview`, `installation`, `quick-start`. Security: `SECURITY_COMPLIANCE` / `security-overview`. Do not apply onboarding README boost on `API_REFERENCE` / `core-service-apis`. Do not change the scanner.

- [ ] **Step 4: `pytest tests/test_onboarding_evidence_ranking.py tests/test_evidence_ranking.py -v` — PASS**

- [ ] **Step 5: Commit**

```bash
git add repo_wiki/evidence/ranking.py tests/test_onboarding_evidence_ranking.py
git commit -m "feat: rank onboarding evidence for handbook pages"
```

---

### Task 4: Four handbook HARD codes

**Files:**
- Modify: `repo_wiki/verifier/handbook.py`
- Modify: `repo_wiki/verifier/qoder_strict_verifier.py`
- Modify: `tests/test_handbook.py`

**Codes (add, do not remove):**
`QODER_HANDBOOK_GENERATOR_META`, `QODER_HANDBOOK_OVERVIEW_IDENTITY`, `QODER_HANDBOOK_INSTALL_RUN`, `QODER_HANDBOOK_API_ROUTE_FILE`

Skip if page absent. FAIL if page exists and violates. Meta runs if any markdown exists. Coverage and DEGRADED stay HARD.

- [ ] **Step 1: Write the ten failing tests in `tests/test_handbook.py`**

Use `tmp_path` fake Wiki + fake README identity (no sample checkout).

1. `test_handbook_hard_codes_are_registered_strict`
2. `test_generator_meta_fails_when_phrase_present`
3. `test_generator_meta_passes_clean_markdown`
4. `test_overview_identity_skips_when_absent`
5. `test_overview_identity_fails_without_identity`
6. `test_overview_identity_passes_with_identity`
7. `test_install_run_fails_without_run_clues`
8. `test_install_run_passes_with_run_clues`
9. `test_api_route_file_requires_routes_cite`
10. `test_api_route_file_passes_with_routes_cite`

Identity: sample tokens `Conduit` or `RealWorld` plus `FastAPI`; else inventory/README identity substring. Install: at least two of `docker` / `docker-compose` / `DATABASE_URL` / `POSTGRES` (case-insensitive) and a `<cite>` to the real README path. API: at least one `<cite>` under `app/api/routes/` (models/tests-only fails).

- [ ] **Step 2: `pytest tests/test_handbook.py -v`**

Expected: three meta helper tests PASS; ten HARD tests FAIL.

- [ ] **Step 3: Register checks**

Add the four codes to `STRICT_HARD_CODES`. In `verify()` append:

```python
self._check_handbook_generator_meta(),
self._check_handbook_overview_identity(),
self._check_handbook_install_run(),
self._check_handbook_api_route_file(),
```

`CheckResult(..., gate_type=GateType.HARD)`. Skip via `_skip_check` when the page is missing.

- [ ] **Step 4: Run**

```bash
pytest tests/test_handbook.py tests/test_qoder_like_verifier.py \
  tests/test_release_gate_policy.py tests/test_qoder_page_contract_truthfulness.py -v
```

Expected: PASS. Billing-auth / `POST /ghost` / trailing `{slug}` still FAIL.

- [ ] **Step 5: Commit**

```bash
git add repo_wiki/verifier/handbook.py repo_wiki/verifier/qoder_strict_verifier.py \
  tests/test_handbook.py
git commit -m "feat: add handbook HARD gates without relaxing existing codes"
```

---

### Task 5: Ignore isolated `--output` in dirty-worktree

**Files:**
- Modify: `repo_wiki/verifier/qoder_strict_verifier.py`
- Modify: `repo_wiki/cli.py`
- Create: `tests/test_dirty_output_ignored.py`

Do not disable the dirty gate. Do not gitignore the sample repo as the pass line.

- [ ] **Step 1: Write failing tests**

```python
def test_output_only_dirty_passes(tmp_path) -> None:
    # git init; commit README; untracked .repo-agent-eval/content/x.md
    # isolated_output=.repo-agent-eval → QODER_DIRTY_WORKTREE absent


def test_extra_app_secret_still_fails(tmp_path) -> None:
    # plus untracked app/secret.py → FAIL QODER_DIRTY_WORKTREE
```

- [ ] **Step 2: `pytest tests/test_dirty_output_ignored.py -v` — expected FAIL**

- [ ] **Step 3: Thread `isolated_output`**

`QoderLikeVerifierService.__init__(..., isolated_output: Path | None = None)`. `verify_qoder_like(..., isolated_output=...)`. `verify_command` passes resolved `--output` (default `.repo-agent-eval` including `runs/`). `_git_dirty` skips porcelain paths under that directory; any other dirty path still HARD.

- [ ] **Step 4: `pytest tests/test_dirty_output_ignored.py tests/test_qoder_like_verifier.py -k dirty -v` — PASS**

- [ ] **Step 5: Commit**

```bash
git add repo_wiki/verifier/qoder_strict_verifier.py repo_wiki/cli.py \
  tests/test_dirty_output_ignored.py
git commit -m "fix: ignore isolated verify output in dirty worktree check"
```

---

### Task 6: Prompt cites (95% floor unchanged)

**Files:**
- Modify: `repo_wiki/generator/composer.py` (`_build_compact_prompt`)
- Modify: `repo_wiki/prompts/fragments.py`
- Test: `tests/test_page_prompts.py` and/or `tests/test_composer_handbook_meta.py`

Do not change `citation_fact_coverage` 95% window.

- [ ] **Step 1: Write failing tests**

```python
def test_overview_compact_prompt_requires_readme_same_line_cite(...) -> None:
    prompt = composer._build_compact_prompt(overview_input, context)
    assert "README" in prompt and "<cite>" in prompt
    assert "同行" in prompt or "同一行" in prompt or "下一行" in prompt


def test_api_compact_prompt_requires_routes_cite_when_routes_evidence_exists(...) -> None:
    prompt = composer._build_compact_prompt(api_input_with_routes, context)
    assert "app/api/routes" in prompt
```

- [ ] **Step 2: Run prompt tests — expected FAIL**

- [ ] **Step 3: Compact prompt rules**

Overview/install: identity from README/pyproject; executable Docker/`DATABASE_URL` steps; each README claim gets same-line or next-line `<cite>`; no generator meta. API (`WikiTaxonomyCategory.API_REFERENCE` value `"API参考"`, `core-service-apis`): if evidence has `app/api/routes/`, require a cite to that file. Mirror in fragments. Do not edit `citation_fact_coverage.py`.

- [ ] **Step 4: Re-run prompt tests — PASS**

- [ ] **Step 5: Commit**

```bash
git add repo_wiki/generator/composer.py repo_wiki/prompts/fragments.py \
  tests/test_page_prompts.py tests/test_composer_handbook_meta.py
git commit -m "feat: require handbook cite contracts in compose prompts"
```

---

### Task 7: Pytest bundle, ruff, product PR (no generate)

- [ ] **Step 1: Pytest bundle**

```bash
pytest \
  tests/test_fallback_onboarding_markdown.py \
  tests/test_handbook.py \
  tests/test_composer_handbook_meta.py \
  tests/test_onboarding_evidence_ranking.py \
  tests/test_evidence_ranking.py \
  tests/test_dirty_output_ignored.py \
  tests/test_compose_circuit_break.py \
  tests/test_qoder_like_verifier.py \
  tests/test_qoder_page_contract_truthfulness.py \
  tests/test_page_prompts.py \
  tests/test_release_gate_policy.py \
  -q
```

Expected: PASS. False-fact tests still assert FAIL.

- [ ] **Step 2: Ruff on touched Python**

```bash
ruff check repo_wiki/verifier/handbook.py repo_wiki/verifier/qoder_strict_verifier.py \
  repo_wiki/generator/composer.py repo_wiki/orchestration/service.py \
  repo_wiki/evidence/ranking.py repo_wiki/cli.py repo_wiki/prompts/fragments.py \
  tests/test_handbook.py tests/test_composer_handbook_meta.py \
  tests/test_onboarding_evidence_ranking.py tests/test_dirty_output_ignored.py
ruff format --check repo_wiki/verifier/handbook.py repo_wiki/verifier/qoder_strict_verifier.py \
  repo_wiki/generator/composer.py repo_wiki/orchestration/service.py \
  repo_wiki/evidence/ranking.py repo_wiki/cli.py repo_wiki/prompts/fragments.py \
  tests/test_handbook.py tests/test_composer_handbook_meta.py \
  tests/test_onboarding_evidence_ranking.py tests/test_dirty_output_ignored.py
```

- [ ] **Step 3: One product PR against `main`**

Title: `feat: handbook wiki checks and onboarding compose`

Body: implements spec `docs/superpowers/specs/2026-08-18-handbook-wiki-design.md`; includes #91 fallback; gates not relaxed; 95% floor unchanged; DEGRADED still HARD; does not merge #71–#90; no generate.

Do not merge.

---

### Task 8: Sample cold generate + verify (later eval)

Not in the product PR. Cold cache, real model, sample SHA pinned.

- [ ] **Step 1: Pin sample SHA. Stack `main` + #91 only unless extra SHAs are listed here.**

- [ ] **Step 2: Generate then verify**

```bash
repo-wiki generate --profile qoder-like --output .repo-agent-eval
repo-wiki verify --profile qoder-like --ci --output .repo-agent-eval
```

- [ ] **Step 3: Pass line**

Exit 0. HARD 0. No new SOFT. Four handbook checks PASS. No DEGRADED pages. Citation ≥ 95%. If red: fix generator/verifier; do not lower gates; do not edit sample business code; do not gitignore output as the pass line.

---

## Spec coverage

| Item | Tasks |
|---|---|
| Fallback readable, no generator meta | Task 1 |
| Compose rejects meta; page-local like insufficient prose | Task 2 |
| Onboarding evidence ranking | Task 3 |
| Four handbook HARD codes | Task 4 |
| Dirty ignores isolated `--output` | Task 5 |
| Prompt same-line/next-line cites; 95% floor unchanged | Task 6 |
| Product PR; no generate; no merge #71–#90 | Task 7 |
| Sample cold generate + verify | Task 8 |
| DEGRADED stays HARD | Tasks 1, 4, 7 |
