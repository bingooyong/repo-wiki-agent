---
task_ref: "Task 27.5 - Markdown preview and stale wiki UX"
status: "completed"
important_findings:
  - "Stale prompt now compares current git commit against manifest wiki_git_commit/target_git_commit"
  - "Tree node click opens Markdown preview through manifest-resolved absolute paths"
  - "Added no-manifest guidance UI and explicit update/sync actions"
compatibility_issue: false
compatibility_issues: false
---

## Implementation

- Updated `extensions/repo-wiki-browser/src/extension.ts`
  - Git drift logic now relies on manifest commit metadata (`wiki_git_commit`, `target_git_commit`)
  - Added no-run state panel when no valid manifest/navigation_tree is found
  - Kept Markdown preview open flow via `markdown.showPreview`
  - Added better page labels: fallback to markdown H1 for generic labels (`index`, `overview`, etc.)

## Validation

- `npm --prefix extensions/repo-wiki-browser run compile`: passed
- `npx --yes @vscode/vsce package --out repo-wiki-browser-0.1.0.vsix`: passed
