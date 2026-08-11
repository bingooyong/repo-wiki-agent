---
name: repo-wiki
description: Inspect a repository and select the next safe Repo Wiki lifecycle action.
---

Resolve the active repository before acting. Use `python scripts/workflow.py doctor` to check compatibility. Read-only `repo-wiki search` and `repo-wiki graph` may run after root resolution. Route generation, verification, and publishing through `scripts/workflow.py`; never build shell command strings from configuration or secrets.

Treat `init`, `index`, `update`, `sync`, `generate`, and `improve` as write actions. State the repository and output target before invoking them. Never request, store, print, or place an API key in a command, file, or prompt.
