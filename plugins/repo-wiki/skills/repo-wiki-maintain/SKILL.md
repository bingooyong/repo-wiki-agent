---
name: repo-wiki-maintain
description: Maintain an existing Repo Wiki using runner-backed lifecycle workflows.
---

Use `scripts/workflow.py doctor` before write workflows. Use the existing CLI only with the resolved repository as cwd. For a stable release, first use `scripts/workflow.py publish --run-id <id>` to inspect an explicit G005-gated run; after the user explicitly confirms the local replacement, repeat with `--confirm-run-id <id>`. Never publish latest implicitly.
