---
name: repo-wiki
description: Inspect a repository and select the next safe Repo Wiki lifecycle action.
---

Resolve `<plugin_dir>` as this installed plugin's root and `<repo-root>` as the active repository. Use `python "<plugin_dir>/scripts/workflow.py" doctor --cwd "<repo-root>"` to check compatibility. Read-only `repo-wiki search` and `repo-wiki graph` may run after root resolution. Route lifecycle writes through the same absolute runner path with `--cwd "<repo-root>"`; never build shell command strings from configuration or secrets.

Treat `init`, `index`, `update`, `sync`, `generate`, and `improve` as write actions. State the repository and output target before invoking them. Never request, store, print, or place an API key in a command, file, or prompt.
