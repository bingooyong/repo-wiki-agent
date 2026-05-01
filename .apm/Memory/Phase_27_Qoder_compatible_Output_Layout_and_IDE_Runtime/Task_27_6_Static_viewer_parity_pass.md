---
task_ref: "Task 27.6 - Static viewer parity pass"
status: "completed"
important_findings:
  - "Static viewer navigation contract aligned to manifest navigation_tree (canonical source)"
  - "Plugin and static viewer now share manifest-first navigation contract semantics"
compatibility_issue: false
compatibility_issues: false
---

## Implementation

- Updated `repo_wiki/viewer/static_viewer.py`
  - `build_nav_tree_from_manifest()` now treats `navigation_tree` as canonical contract
  - Removed legacy fallback from `files` for this path; returns empty nav when navigation_tree is absent

## Validation

- Extension compile/package checks completed in this task batch:
  - `npm --prefix extensions/repo-wiki-browser run compile`
  - `npx --yes @vscode/vsce package --out repo-wiki-browser-0.1.0.vsix`
