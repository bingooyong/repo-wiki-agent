---
agent: Agent_PlatformCore
task_ref: Task 30.2
status: Completed
ad_hoc_delegation: false
compatibility_issues: false
important_findings: false
---

# Task Log: Task 30.2 - Installation and VS Code extension workflow

## Summary
Documented end-to-end CLI and VS Code extension workflows (install, qoder-like generate, view, update, verify with profile/ci); corrected outdated docs; added CLI packaging smoke tests; validated `uv pip install -e .` in a clean temporary venv.

## Details
- Added canonical user docs:
  - `docs/getting-started.md` — ordered workflows, VSIX build/install, qoder-like generate/update/verify (including `--output` for qoder-like verify), viewing via extension/Markdown preview (no `repo-wiki open`), rebuild/reinstall steps.
  - `docs/installation.md` — short entry with links to getting-started and detailed operations doc.
- Updated `docs/operations/installation-and-vscode-extension.md`:
  - Linked to getting-started; removed incorrect `repo-wiki open` workflow; aligned verify examples with `--profile qoder-like --ci --output`; refreshed extension command titles; replaced stale static `--help` snippet with pointer to live CLI.
- Packaging smoke tests in `tests/test_cli_packaging_smoke.py` (Typer `--help` + `python -m repo_wiki.main --help`).
- Evidence: ran `uv venv` + `uv pip install -e .` in a fresh temp directory and confirmed `repo-wiki --help` exits 0.

## Output
- New: `docs/getting-started.md`, `docs/installation.md`, `tests/test_cli_packaging_smoke.py`
- Modified: `docs/operations/installation-and-vscode-extension.md`

## Issues
None

## Next Steps
None
