# Handbook Wiki Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `repo-wiki verify --profile qoder-like` all-green on the FastAPI RealWorld sample mean a readable handbook (identity, how to run, which file to edit), without relaxing existing HARD/SOFT gates or the 95% citation floor.

**Architecture:** Keep `scan → plan → evidence → compose → write → verify`. Change three places only: onboarding evidence ranking and page contracts, compose rejection plus fallback copy, and qoder-like HARD checks (four handbook codes plus isolated `--output` ignored by dirty-worktree). Fallback stays DEGRADED. No new generator, no new taxonomy.

**Tech Stack:** Existing Python CLI (`repo_wiki`), pytest, ruff, qoder-like verifier, compact LLM prompts. Sample checkout: nsidnev/fastapi-realworld-example-app.

**Spec:** `docs/superpowers/specs/2026-08-18-handbook-wiki-design.md` (PR #92). This plan is the companion for spec §11.

## Global Constraints

- Do not relax any existing HARD or SOFT gate. Do not remove codes from `STRICT_HARD_CODES`.
- Do not lower `QODER_CITATION_FACT_COVERAGE_LOW` below 95% (`ratio < 0.95` in `_check_qoder_claim_citation_coverage`).
- Do not treat fallback pages as PASS. `QODER_PAGE_QUALITY_STATE_DEGRADED` stays HARD.
- Do not merge PRs #71–#90. Do not start a generate in Tasks 1–7.
- Branch product work from current `main`. Locally merge `origin/cursor/fix-fallback-onboarding-wiki-8442` (PR #91, commit `23e2957`) into the product branch. Do not `gh pr merge`.
- Keep real API keys out of settings, YAML, command strings, logs, docs, and commits.
- Sample-repo acceptance (Task 8) is a later eval run, not part of the product PR.
- Target SHA stack for eval, if needed: only SHAs already on `main` plus locally merged #91. List any extra SHA in Task 8; do not silently land unreviewed product PRs.

---

## File Map

- Locally merge (product branch only): PR #91 fallback rewrite in `repo_wiki/orchestration/service.py` and `tests/test_fallback_onboarding_markdown.py`.
- Create: `repo_wiki/verifier/handbook.py`
  - Phrase list, `contains_generator_meta`, page matchers, identity/install/API predicates, `GENERATOR_META_REJECTION`.
- Create: `tests/test_handbook.py`
  - Three `contains_generator_meta` tests plus ten verifier HARD tests.
- Create: `tests/test_composer_handbook_meta.py`
  - Composer reject + orchestration does not circuit-break on handbook meta.
- Create: `tests/test_onboarding_evidence_ranking.py`
  - Three ranking tests for overview / installation / security.
- Create: `tests/test_dirty_output_ignored.py`
  - Isolated `--output` ignored; extra dirty source still FAIL.
- Modify: `repo_wiki/generator/composer.py`
  - `_validate_output` rejects generator meta after insufficient-prose check.
  - `_build_compact_prompt` adds handbook cite contracts for overview/install/API.
- Modify: `repo_wiki/orchestration/service.py`
  - Treat `GENERATOR_META_REJECTION` like `"Insufficient prose content"` (page-local fallback, not circuit-break).
- Modify: `repo_wiki/evidence/ranking.py`
  - Boost README/settings/`main.py` for overview/installation; boost `authentication.py` over README for security. Do not globally boost README on API pages.
- Modify: `repo_wiki/verifier/qoder_strict_verifier.py`
  - Add four handbook codes to `STRICT_HARD_CODES`.
  - Register four checks in `verify()`.
  - `_git_dirty` ignores isolated output dir (and `runs/`).
- Modify: `repo_wiki/cli.py`
  - Thread isolated `--output` from `verify_command` into `verify_qoder_like`.
- Modify: `repo_wiki/prompts/fragments.py`
  - Same-line/next-line `<cite>` for README spans on overview/install; API pages require a cite to `app/api/routes/` when that evidence exists.
- Modify only if a snapshot asserts the old code set: `tests/test_qoder_like_verifier.py` (add the four new HARD codes; do not drop existing asserts).
- Do not edit sample-repo business code. Do not add `.gitignore` in the sample as a pass-line trick.

---

### Task 1: Confirm PR #91 fallback (still DEGRADED)

**Files:**
- Locally merge: `origin/cursor/fix-fallback-onboarding-wiki-8442` @ `23e2957`
- Test: `tests/test_fallback_onboarding_markdown.py`
- Do not change product code unless a spec gap remains after the merge

**Interfaces:**
- Consumes: `RepoWikiService._fallback_markdown_for_failed_page(page, binding) -> str`
- Produces: fallback Markdown with no generator meta, README substance + `<cite>`, empty binding invents no routes; quality state remains DEGRADED

- [ ] **Step 1: Locally merge #91 into the product working branch**

```bash
git fetch origin cursor/fix-fallback-onboarding-wiki-8442
git merge --no-ff 23e2957 -m "merge: fallback onboarding wiki from #91"
```

Expected: merge completes. Do not `gh pr merge`. Do not merge #71–#90.

- [ ] **Step 2: Run the fallback tests**

```bash
pytest tests/test_fallback_onboarding_markdown.py -v
```

Expected: PASS. Confirm by reading assertions and/or failing a local experiment that:

- Markdown has none of `fallback composer` / `repo-agent` / `该页面对应` / `evidence ranking` / bare reader-facing `page_id`
- Overview/install use README Quickstart substance (`PostgreSQL`, `docker`, `DATABASE_URL`) and `<cite>README.rst:`
- Empty binding invents no `README.rst` / `app/core/security.py` paths and has no `<cite>`
- Existing `QODER_PAGE_QUALITY_STATE_DEGRADED` still HARD (do not change `STRICT_HARD_CODES` here)

- [ ] **Step 3: Patch only if a spec gap remains**

If #91 still emits any spec §4.2 / §5.1 phrase, strip it in `_fallback_markdown_for_failed_page` and keep DEGRADED. Do not make fallback a PASS path.

- [ ] **Step 4: Commit if the merge or a spec-gap patch landed**

```bash
git add repo_wiki/orchestration/service.py tests/test_fallback_onboarding_markdown.py
git commit -m "fix: keep fallback pages readable without generator meta"
```

---

### Task 2: Reject generator meta at compose time

**Files:**
- Create: `repo_wiki/verifier/handbook.py`
- Create: `tests/test_handbook.py` (the three `contains_generator_meta` tests)
- Create: `tests/test_composer_handbook_meta.py`
- Modify: `repo_wiki/generator/composer.py` (`_validate_output` after insufficient prose)
- Modify: `repo_wiki/orchestration/service.py` (`record_compose_result`)

**Interfaces:**
- Consumes: composed Markdown string
- Produces:
  - `HANDBOOK_META_PHRASES: tuple[str, ...] = ("fallback composer", "repo-agent", "该页面对应", "evidence ranking")`
  - `contains_generator_meta(markdown: str) -> bool`
  - `GENERATOR_META_REJECTION = "Handbook generator meta content"`
  - Composer sets `rejection_reason = GENERATOR_META_REJECTION` and `rejected = True`
  - Orchestration treats that reason like `"Insufficient prose content"` (no `note_provider_failure()`)

- [ ] **Step 1: Write the three failing `contains_generator_meta` tests**

In `tests/test_handbook.py`:

```python
from repo_wiki.verifier.handbook import contains_generator_meta


def test_contains_generator_meta_detects_fallback_composer() -> None:
    assert contains_generator_meta("本页由 fallback composer 生成。") is True


def test_contains_generator_meta_detects_chinese_page_id_boilerplate() -> None:
    assert contains_generator_meta("该页面对应 `project-overview`，由 repo-agent 写出。") is True


def test_contains_generator_meta_ignores_page_id_in_code_fence() -> None:
    markdown = (
        "项目概述。\n\n"
        "```text\n"
        "page_id=project-overview\n"
        "```\n"
    )
    assert contains_generator_meta(markdown) is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_handbook.py::test_contains_generator_meta_detects_fallback_composer \
  tests/test_handbook.py::test_contains_generator_meta_detects_chinese_page_id_boilerplate \
  tests/test_handbook.py::test_contains_generator_meta_ignores_page_id_in_code_fence -v
```

Expected: FAIL with `ModuleNotFoundError` or `ImportError` for `repo_wiki.verifier.handbook`.

- [ ] **Step 3: Write `repo_wiki/verifier/handbook.py`**

```python
from __future__ import annotations

import re

HANDBOOK_META_PHRASES: tuple[str, ...] = (
    "fallback composer",
    "repo-agent",
    "该页面对应",
    "evidence ranking",
)

GENERATOR_META_REJECTION = "Handbook generator meta content"

_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)


def contains_generator_meta(markdown: str) -> bool:
    """True if reader-facing generator meta appears outside fenced code."""
    body = _FENCE_RE.sub("", markdown)
    lowered = body.lower()
    for phrase in HANDBOOK_META_PHRASES:
        if phrase.lower() in lowered:
            return True
    return False
```

Match the four phrases as whole substrings (spec §5.1). Do not FAIL solely because a fenced identifier contains `page_id`. Do not add a fifth public phrase unless tests require it.

- [ ] **Step 4: Re-run the three tests**

```bash
pytest tests/test_handbook.py::test_contains_generator_meta_detects_fallback_composer \
  tests/test_handbook.py::test_contains_generator_meta_detects_chinese_page_id_boilerplate \
  tests/test_handbook.py::test_contains_generator_meta_ignores_page_id_in_code_fence -v
```

Expected: PASS.

- [ ] **Step 5: Write failing composer + orchestration tests**

In `tests/test_composer_handbook_meta.py`, follow existing `tests/test_llm_page_composer.py` / `tests/test_compose_circuit_break.py` fixtures.

Minimum cases:

```python
def test_validate_output_rejects_generator_meta(composer, handbook_input) -> None:
    content = "# 项目概述\n\n该页面对应 `project-overview`，由 fallback composer 生成。\n"
    result = composer._validate_output(content, handbook_input)
    assert result.rejected is True
    assert result.rejection_reason == "Handbook generator meta content"


def test_handbook_meta_reject_does_not_trip_circuit_breaker(...) -> None:
    # Three consecutive GENERATOR_META_REJECTION pages must not call note_provider_failure
    # or set provider_disabled_after_failures. Mirror
    # test_insufficient_prose_rejects_do_not_trip_circuit_breaker.
    ...
```

Use a page whose Markdown is long enough that the insufficient-prose check does not fire first, or include enough prose plus a meta phrase.

- [ ] **Step 6: Run composer tests to verify they fail**

```bash
pytest tests/test_composer_handbook_meta.py -v
```

Expected: FAIL because `_validate_output` never sets `GENERATOR_META_REJECTION`.

- [ ] **Step 7: Implement composer rejection**

In `repo_wiki/generator/composer.py`, inside `_validate_output`, immediately after the insufficient-prose assignment (`result.rejection_reason = "Insufficient prose content"`), add:

```python
from repo_wiki.verifier.handbook import (
    GENERATOR_META_REJECTION,
    contains_generator_meta,
)

if not result.rejection_reason and contains_generator_meta(content):
    result.rejection_reason = GENERATOR_META_REJECTION
```

Keep inventory-primary-evidence rejection after this. Meta reject is a compose failure (same family as insufficient prose): quality state DEGRADED via existing fallback write.

- [ ] **Step 8: Implement orchestration exemption**

In `repo_wiki/orchestration/service.py` `record_compose_result`, change the circuit-break skip from equality on `"Insufficient prose content"` to a helper:

```python
from repo_wiki.verifier.handbook import GENERATOR_META_REJECTION

_PAGE_LOCAL_REJECTIONS = frozenset(
    {"Insufficient prose content", GENERATOR_META_REJECTION}
)

if output.rejection_reason not in _PAGE_LOCAL_REJECTIONS:
    note_provider_failure()
```

- [ ] **Step 9: Run tests**

```bash
pytest tests/test_handbook.py tests/test_composer_handbook_meta.py \
  tests/test_compose_circuit_break.py tests/test_fallback_onboarding_markdown.py -v
```

Expected: PASS. Existing 529/timeout circuit-break tests still FAIL the provider as before.

- [ ] **Step 10: Commit**

```bash
git add repo_wiki/verifier/handbook.py repo_wiki/generator/composer.py \
  repo_wiki/orchestration/service.py tests/test_handbook.py \
  tests/test_composer_handbook_meta.py
git commit -m "feat: reject handbook generator meta at compose time"
```

---

### Task 3: Onboarding evidence ranking

**Files:**
- Modify: `repo_wiki/evidence/ranking.py` (`score_evidence_for_page`)
- Create: `tests/test_onboarding_evidence_ranking.py`
- Must keep: `tests/test_evidence_ranking.py` passing

**Interfaces:**
- Consumes: `WikiPagePlan`, `EvidenceSpanRecord`
- Produces: higher scores for README / settings / `app/main.py` on overview and installation pages; `app/api/dependencies/authentication.py` outranks README on security pages; API pages do not get a global README boost

- [ ] **Step 1: Write the three required failing tests**

In `tests/test_onboarding_evidence_ranking.py` use the same `WikiPagePlan` / `EvidenceSpanRecord` construction as `tests/test_evidence_ranking.py`.

Required names:

```python
def test_overview_ranks_readme_above_unrelated_module() -> None:
    ...


def test_installation_ranks_readme_and_settings() -> None:
    ...


def test_security_ranks_authentication_above_readme() -> None:
    ...
```

`test_overview_ranks_readme_above_unrelated_module`: page `page_id="project-overview"`, category `PROJECT_OVERVIEW`. Spans: `README.rst` (Quickstart text) vs `app/models/article.py`. Assert `score_evidence_for_page` for README > article model.

`test_installation_ranks_readme_and_settings`: page `page_id="installation"`. Spans: `README.rst`, `app/core/settings.py` (`database_url` / `DATABASE_URL`), `app/main.py`. Assert all three score above an unrelated `tests/test_unrelated.py` span. README and settings must both be > 0.

`test_security_ranks_authentication_above_readme`: page `page_id="security-overview"`, category `SECURITY_COMPLIANCE`. Spans: `app/api/dependencies/authentication.py` (`RWAPIKeyHeader`) vs `README.rst` Quickstart. Assert authentication score > README score.

Also add (same file, not one of the three required names) `test_api_page_does_not_get_global_readme_boost`: page `page_id="core-service-apis"`, category `API_REFERENCE`. README must not outrank `app/api/routes/authentication.py` solely from the onboarding boost.

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_onboarding_evidence_ranking.py -v
```

Expected: FAIL because overview/install/security use generic keyword/proximity scores only.

- [ ] **Step 3: Implement ranking boosts**

In `score_evidence_for_page`, after existing signals, add an onboarding boost. Keep it page-local:

```python
ONBOARDING_PAGE_IDS = frozenset({"project-overview", "installation", "quick-start"})
SECURITY_PAGE_IDS = frozenset({"security-overview", "security-compliance"})
WEIGHT_ONBOARDING_README = 3.0
WEIGHT_ONBOARDING_ENTRY = 2.4
WEIGHT_SECURITY_AUTH = 3.2

def _is_onboarding_page(page: WikiPagePlan) -> bool:
    if page.page_id in ONBOARDING_PAGE_IDS:
        return True
    if page.category == WikiTaxonomyCategory.PROJECT_OVERVIEW and page.page_id in {
        "project-overview",
        "installation",
        "quick-start",
    }:
        return True
    blob = f"{page.page_id} {page.title} {' '.join(page.tags)}".lower()
    return any(token in blob for token in ("install", "安装", "quickstart", "快速开始"))


def _is_security_page(page: WikiPagePlan) -> bool:
    return page.category == WikiTaxonomyCategory.SECURITY_COMPLIANCE or page.page_id in SECURITY_PAGE_IDS
```

Scoring rules:

- Onboarding: `README` / `README.rst` / `README.md` → `WEIGHT_ONBOARDING_README`, signal `onboarding_readme`
- Onboarding: path contains `settings` or file is `app/main.py` or `main.py` at repo root → `WEIGHT_ONBOARDING_ENTRY`, signal `onboarding_entry`
- Security: path endswith `authentication.py` or contains `api/dependencies/authentication` → `WEIGHT_SECURITY_AUTH`, signal `security_auth`
- Security: README spans get **no** onboarding README boost (so auth can outrank README)
- API_REFERENCE / `core-service-apis`: do not apply onboarding README boost

Do not change the scanner. Do not globally boost README for every page.

- [ ] **Step 4: Run ranking tests**

```bash
pytest tests/test_onboarding_evidence_ranking.py tests/test_evidence_ranking.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add repo_wiki/evidence/ranking.py tests/test_onboarding_evidence_ranking.py
git commit -m "feat: rank onboarding evidence for handbook pages"
```

---

### Task 4: Four handbook HARD checks

**Files:**
- Modify: `repo_wiki/verifier/handbook.py` (page matchers + check helpers)
- Modify: `repo_wiki/verifier/qoder_strict_verifier.py` (`STRICT_HARD_CODES`, `verify()`, four `_check_*` methods)
- Modify: `tests/test_handbook.py` (ten verifier tests)
- Modify only if needed: `tests/test_qoder_like_verifier.py`

**Interfaces:**
- Consumes: wiki Markdown under the content dir; optional README identity string
- Produces: HARD `CheckResult`s with codes:
  - `QODER_HANDBOOK_GENERATOR_META`
  - `QODER_HANDBOOK_OVERVIEW_IDENTITY`
  - `QODER_HANDBOOK_INSTALL_RUN`
  - `QODER_HANDBOOK_API_ROUTE_FILE`
- Skip if the target page is absent. FAIL if the page exists and violates. Meta runs if any Markdown exists.
- `QODER_CITATION_FACT_COVERAGE_LOW` and `QODER_PAGE_QUALITY_STATE_DEGRADED` remain HARD.

- [ ] **Step 1: Write the ten failing verifier tests**

Append to `tests/test_handbook.py`. Use `tmp_path` wiki trees (no sample-repo checkout). Helper to write `content/*.md` and construct `QoderLikeVerifierService(tmp_path)`.

The ten tests:

1. `test_handbook_codes_are_strict_hard` — all four codes in `QoderLikeSeverityThreshold.STRICT_HARD_CODES`; `QODER_CITATION_FACT_COVERAGE_LOW` and `QODER_PAGE_QUALITY_STATE_DEGRADED` still present.
2. `test_generator_meta_hard_fails_on_fallback_composer` — any `.md` containing `fallback composer` → FAIL `QODER_HANDBOOK_GENERATOR_META`.
3. `test_generator_meta_passes_clean_page` — clean overview Markdown → that code absent from `hard_gate_codes`.
4. `test_overview_identity_fails_without_product_name` — `content/项目概述.md` (or `project-overview.md`) with FastAPI but neither Conduit nor RealWorld, identity=`Conduit RealWorld FastAPI` → FAIL `QODER_HANDBOOK_OVERVIEW_IDENTITY`.
5. `test_overview_identity_passes_with_conduit_and_fastapi` — body has `Conduit` and `FastAPI` → PASS.
6. `test_install_run_fails_without_docker_and_readme_cite` — install page with neither two run tokens nor a README cite → FAIL `QODER_HANDBOOK_INSTALL_RUN`.
7. `test_install_run_passes_with_docker_database_url_and_readme_cite` — `docker` + `DATABASE_URL` (case-insensitive) and `<cite>README.rst:10-20</cite>` → PASS.
8. `test_api_route_file_fails_with_only_model_cites` — core API page cites only `app/models/article.py` and `tests/test_api.py` → FAIL `QODER_HANDBOOK_API_ROUTE_FILE`.
9. `test_api_route_file_passes_with_routes_cite` — `<cite>app/api/routes/authentication.py:1-40</cite>` → PASS.
10. `test_handbook_checks_skip_when_page_absent` — wiki with only an unrelated page → overview/install/API checks PASS (skip); meta still runs on whatever Markdown exists.

Page matching (implement in `handbook.py`, used by tests and verifier):

```python
def is_overview_page(rel_path: str, title: str = "") -> bool:
    blob = f"{rel_path} {title}".lower()
    return "project-overview" in blob or "项目概述" in blob or rel_path.endswith("overview.md")


def is_install_page(rel_path: str, title: str = "") -> bool:
    blob = f"{rel_path} {title}".lower()
    return "installation" in blob or "安装" in blob


def is_core_api_page(rel_path: str, title: str = "") -> bool:
    blob = f"{rel_path} {title}".lower()
    return (
        "core-service-apis" in blob
        or "核心服务api" in blob
        or "核心服务API" in f"{rel_path} {title}"
    )
```

Identity (spec §5.2): if the wiki/README identity string contains `Conduit` or `RealWorld`, require those sample tokens plus `FastAPI`. Otherwise require the inventory/README identity string (case-insensitive substring). Missing identity → FAIL when the overview page exists.

Install (spec §5.3): at least two of `docker`, `docker-compose`, `DATABASE_URL`, `POSTGRES` (case-insensitive) in body or cites, **and** at least one `<cite>` whose path is `README.rst` or the repo's actual README filename.

API (spec §5.4): at least one `<cite>` path under `app/api/routes/` (or inventory-equivalent route module if recorded). Cites only to `app/db`, `app/models`, `tests/` are not enough.

- [ ] **Step 2: Run the ten tests to verify they fail**

```bash
pytest tests/test_handbook.py -v
```

Expected: the three meta-helper tests still PASS; the ten verifier tests FAIL (codes missing / checks not registered).

- [ ] **Step 3: Add codes and checks**

In `QoderLikeSeverityThreshold.STRICT_HARD_CODES` add (do not remove any existing member):

```python
"QODER_HANDBOOK_GENERATOR_META",
"QODER_HANDBOOK_OVERVIEW_IDENTITY",
"QODER_HANDBOOK_INSTALL_RUN",
"QODER_HANDBOOK_API_ROUTE_FILE",
```

In `QoderLikeVerifierService.verify()`, append:

```python
self._check_handbook_generator_meta(),
self._check_handbook_overview_identity(),
self._check_handbook_install_run(),
self._check_handbook_api_route_file(),
```

Implement the four methods using `handbook.py` predicates and `_find_content_dir()`. Use existing `CheckResult(..., gate_type=GateType.HARD)`. Skip via `_skip_check` when the matched page is absent. Meta: if content dir has any `*.md` and `contains_generator_meta` is true on any page, FAIL.

For overview identity, read identity from (in order): verifier `self.root` README via `resolve_repository_identity` display/description if cheap; else default sample tokens `Conduit`/`RealWorld` + `FastAPI` when those strings appear in any README under `self.root`; else FAIL if overview exists and no identity string can be resolved.

- [ ] **Step 4: Run verifier tests**

```bash
pytest tests/test_handbook.py tests/test_qoder_like_verifier.py tests/test_release_gate_policy.py -v
```

Expected: PASS. Existing billing-auth / `POST /ghost` / trailing `{slug}` false-fact tests still FAIL as HARD.

- [ ] **Step 5: Commit**

```bash
git add repo_wiki/verifier/handbook.py repo_wiki/verifier/qoder_strict_verifier.py \
  tests/test_handbook.py tests/test_qoder_like_verifier.py
git commit -m "feat: add handbook HARD gates without relaxing existing codes"
```

---

### Task 5: Ignore isolated `--output` in dirty-worktree

**Files:**
- Modify: `repo_wiki/verifier/qoder_strict_verifier.py` (`__init__`, `_git_dirty`, `_check_qoder_dirty_worktree`)
- Modify: `repo_wiki/cli.py` (`verify_command` → `verify_qoder_like`)
- Create: `tests/test_dirty_output_ignored.py`

**Interfaces:**
- Consumes: isolated output path (CLI `--output`, default `.repo-agent-eval` including `runs/`)
- Produces: `QODER_DIRTY_WORKTREE` ignores those paths; any other uncommitted source still HARD
- Do not disable the dirty gate. Do not gitignore the sample repo as the pass line.

- [ ] **Step 1: Write failing tests**

In `tests/test_dirty_output_ignored.py`:

```python
def test_output_only_dirty_passes(tmp_path, monkeypatch) -> None:
    # git init repo; commit README; write untracked .repo-agent-eval/content/x.md
    # verify with isolated_output=.repo-agent-eval → QODER_DIRTY_WORKTREE not in hard_gate_codes


def test_extra_app_secret_still_fails(tmp_path) -> None:
    # same as above plus untracked app/secret.py
    # → FAIL QODER_DIRTY_WORKTREE
```

Use a real `git init` + `git commit` in `tmp_path`. Point `QoderLikeVerifierService` at the repo (or content dir) with `isolated_output=tmp_path / ".repo-agent-eval"`.

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_dirty_output_ignored.py -v
```

Expected: FAIL because `_git_dirty` treats any porcelain line as dirty.

- [ ] **Step 3: Thread isolated output and filter porcelain**

`QoderLikeVerifierService.__init__`: add `isolated_output: Path | None = None`.

`create_qoder_like_verifier` / `verify_qoder_like`:

```python
def verify_qoder_like(
    root: Path,
    ci: bool = True,
    strict: bool = True,
    isolated_output: Path | None = None,
) -> dict[str, Any]:
    verifier = QoderLikeVerifierService(root, strict=strict, isolated_output=isolated_output)
    return verifier.verify(ci=ci)
```

`verify_command`: when `profile == "qoder-like"`, pass the resolved `--output` directory (if None, `project_root / ".repo-agent-eval"` when that is the generate output; otherwise None). Prefer the actual `--output` path the user passed, resolved against project root.

`_git_dirty`: parse `git status --porcelain`. For each path, if it is inside `isolated_output` (resolved) or inside `isolated_output / "runs"`, skip. If any remaining path exists, return True.

Also ignore the default `.repo-agent-eval` directory when it is a nested isolated output even if `isolated_output` was passed as a run dir under it (parent `.repo-agent-eval` and `runs/` both skipped).

- [ ] **Step 4: Run dirty + existing dirty tests**

```bash
pytest tests/test_dirty_output_ignored.py tests/test_qoder_like_verifier.py -k dirty -v
```

Expected: PASS. A dirty `app/secret.py` still FAIL.

- [ ] **Step 5: Commit**

```bash
git add repo_wiki/verifier/qoder_strict_verifier.py repo_wiki/cli.py \
  tests/test_dirty_output_ignored.py
git commit -m "fix: ignore isolated verify output in dirty worktree check"
```

---

### Task 6: Prompt contract for same-line cites (95% floor unchanged)

**Files:**
- Modify: `repo_wiki/generator/composer.py` (`_build_compact_prompt`)
- Modify: `repo_wiki/prompts/fragments.py` (`OVERVIEW_PROMPT_FRAGMENT`, `API_PROMPT_FRAGMENT`, development/install fragment if present)
- Test: extend `tests/test_page_prompts.py` and add compact-prompt assertions (new tests in `tests/test_composer_handbook_meta.py` or `tests/test_page_prompts.py`)

**Interfaces:**
- Consumes: page plan + evidence context already in the compact prompt
- Produces: overview/install prompts require same-line or next-line `<cite>` for README spans; API prompts require a cite to `app/api/routes/` (or inventory route module) when such evidence exists
- Do not change `citation_fact_coverage` window or the `ratio < 0.95` threshold

- [ ] **Step 1: Write failing prompt tests**

```python
def test_overview_compact_prompt_requires_readme_same_line_cite(composer, overview_input) -> None:
    prompt = composer._build_compact_prompt(overview_input, composer._build_context(overview_input))
    assert "同一行" in prompt or "same-line" in prompt.lower() or "同行" in prompt
    assert "<cite>" in prompt
    assert "README" in prompt


def test_api_compact_prompt_requires_routes_cite_when_routes_evidence_exists(
    composer, api_input_with_routes
) -> None:
    prompt = composer._build_compact_prompt(
        api_input_with_routes, composer._build_context(api_input_with_routes)
    )
    assert "app/api/routes" in prompt
```

Also assert `OVERVIEW_PROMPT_FRAGMENT` / `API_PROMPT_FRAGMENT` contain the same rules so the non-compact path matches.

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_page_prompts.py tests/test_composer_handbook_meta.py -k cite -v
```

Expected: FAIL; compact prompt lacks handbook cite contract.

- [ ] **Step 3: Implement prompt text**

In `_build_compact_prompt`, after `_root_readme_cite_rule()`, add:

```python
handbook_rules = ""
if page.page_id in {"project-overview", "installation", "quick-start"} or page.category.value == "项目概述":
    handbook_rules = (
        "\n手册页附加要求：\n"
        "- 产品身份必须写进简介（证据里的 README / pyproject 名称，禁止只写 slug）。\n"
        "- 安装/Quickstart 步骤必须可执行，并以证据中的 Docker / DATABASE_URL / 测试命令为准。\n"
        "- README 证据的每个论断必须在同一行或下一行给出 `<cite>实际README文件名:start-end</cite>`。\n"
        "- 禁止生成器元话语：fallback composer、repo-agent、该页面对应、evidence ranking。\n"
    )
if page.category.value == "API参考" or page.page_id in {"core-service-apis", "api-overview"}:
    handbook_rules += (
        "\n- 当证据含 `app/api/routes/`（或库存中的等价路由模块）时，"
        "正文必须至少有一条 `<cite>` 指向该路由文件；不要只用 models/tests。\n"
    )
```

Insert `{handbook_rules}` into the compact prompt. Key API rules off `WikiTaxonomyCategory.API_REFERENCE` (`"API参考"`), not the unused `"api_reference"` string.

Mirror the same sentences in `OVERVIEW_PROMPT_FRAGMENT` and `API_PROMPT_FRAGMENT`.

Do not edit `repo_wiki/verifier/citation_fact_coverage.py`. Unverifiable claims still do not count as covered.

- [ ] **Step 4: Run prompt tests**

```bash
pytest tests/test_page_prompts.py tests/test_composer_handbook_meta.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add repo_wiki/generator/composer.py repo_wiki/prompts/fragments.py \
  tests/test_page_prompts.py tests/test_composer_handbook_meta.py
git commit -m "feat: require handbook cite contracts in compose prompts"
```

---

### Task 7: Pytest bundle, ruff, product PR (no generate)

**Files:** none new beyond Tasks 1–6

- [ ] **Step 1: Run the pytest bundle**

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

Expected: all PASS. False-fact cases remain FAIL at the check level (tests that assert FAIL still assert FAIL).

- [ ] **Step 2: Lint touched Python**

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

Expected: clean.

- [ ] **Step 3: Open one product PR against `main`**

Title: `feat: handbook wiki checks and onboarding compose`

Body must state:

- Implements spec `docs/superpowers/specs/2026-08-18-handbook-wiki-design.md`
- Includes #91 fallback (local merge only)
- Gates not relaxed; 95% citation floor unchanged; DEGRADED still HARD
- Does not merge #71–#90
- Does not run sample generate (Task 8 is a later eval)

Do not merge that PR in this plan.

---

### Task 8: Sample-repo cold generate + verify (later eval, not Tasks 1–7)

**Files:** eval notes only, if a later docs/eval PR is opened. No product edits here.

**Not in the product PR.** Spec §8: cold cache, real model, sample SHA pinned.

- [ ] **Step 1: Pin sample SHA and list stacked SHAs**

Record the FastAPI RealWorld commit SHA. Stack only `main` plus locally merged #91 unless a later reviewed SHA is listed here explicitly.

- [ ] **Step 2: Generate then verify**

```bash
repo-wiki generate --profile qoder-like --output .repo-agent-eval
repo-wiki verify --profile qoder-like --ci --output .repo-agent-eval
```

- [ ] **Step 3: Pass line**

Exit code 0. HARD 0. No new SOFT. Four handbook checks PASS. No DEGRADED pages. Citation coverage ≥ 95%. Human-read follow-ups do not block this gate.

If verify is red, fix generator/verifier on a product branch; do not lower gates; do not edit sample business code; do not gitignore output as the pass line.

---

## Spec coverage

| Spec | Task |
|---|---|
| §4.2 / §11.1 Fallback readable, still DEGRADED | Task 1 (#91) |
| §4.1 / §5.1 / §11.2 Compose rejects meta | Task 2 |
| §4.3 / §11.3 Onboarding evidence + contracts | Tasks 3, 6 |
| §5.1–5.4 / §11.4 Four handbook HARD | Task 4 |
| §6 / §11.5 Dirty ignores isolated output | Task 5 |
| §7 / §11.6 Citation 95% via cites, not a lower floor | Task 6 (prompts); Task 4 (floor still HARD) |
| §8 / §9 / §11.7 Sample cold run | Task 8 (later) |
| §8.4 SHA stack listed, no silent merge of #71–#90 | Global Constraints, Task 7, Task 8 |
| §10 Non-goals | Global Constraints |

## Placeholder scan

No TBD/TODO. Test names, reason codes, file paths, and commands are spelled out. `GENERATOR_META_REJECTION` is the same string in handbook.py, composer, orchestration, and tests.
