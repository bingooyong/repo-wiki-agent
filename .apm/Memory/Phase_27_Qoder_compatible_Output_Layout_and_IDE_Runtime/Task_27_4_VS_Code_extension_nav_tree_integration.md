---
task_ref: "Task 27.4 - VS Code extension nav-tree integration"
status: "completed"
important_findings:
  - "Extension now reads only .repo-agent-eval/**/manifest.json navigation_tree for sidebar navigation"
  - "Implemented run discovery + latest run selection with manual run selector in sidebar"
  - "Removed docs/ fallback and docs/sections path guessing from extension navigation pipeline"
compatibility_issue: false
compatibility_issues: false
---

## Implementation

- Updated `extensions/repo-wiki-browser/src/extension.ts`
  - Added manifest run discovery (`.repo-agent-eval/**/manifest.json`)
  - Added `runSelect` UI with latest-by-generated_at/mtime default
  - Navigation tree rendering now uses `manifest.navigation_tree` only
  - File open mapping uses canonical page key from manifest path/absolutePath
  - Sidebar no longer scans workspace `docs/`

## Validation

- `npm --prefix extensions/repo-wiki-browser run compile`: passed
