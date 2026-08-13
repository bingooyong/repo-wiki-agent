# Flask round-1 eval notes (2026-08-13)

Target: [pallets/flask](https://github.com/pallets/flask) at SHA `2a8a38b`.
Generator: `repo-wiki` installed with `uv tool install` of this package.
Model: MiniMax-M3 (reasoning). No API keys recorded here.

## Failures

1. **`repo-wiki init` missing packaged templates.** The installed wheel did not ship `templates/`. `_template_root()` fell back to `Path(__file__).parents[2] / "templates"` (`site-packages/templates`), which does not exist. Result: `ValueError: Missing templates: docs/00-overview.md.j2, ...`.

2. **`generate --profile qoder-like` crashed after composing 83 pages.** `write_generation_conflict_artifacts` → `docs_scanner.py` raised `OSError: [Errno 36] File name too long` because `_extract_claims` treated a long CHANGES.rst backtick span (prose containing `.` and `/`) as a filesystem path and called `(repo_root / p).exists()`.

3. **Page compose timeout capped at 20s.** `repo-wiki.yaml` had `llm.timeout: 180`, but `_resolve_llm_page_timeout` did `min(configured_timeout, 20.0)`. MiniMax-M3 often exceeded 20s, so pages fell back.

4. **`verify --profile qoder-like --ci`:** FAIL with 11 HARD findings on the partial run. Verifier HARD/SOFT thresholds were not changed in this follow-up.

## Follow-up

Round-2 Flask generate should run after the hardening fixes land (packaged templates, safe path claims, honor `llm.timeout` with a 300s ceiling). Round-2 notes: `docs/eval/2026-08-13-flask-round2.md`.
