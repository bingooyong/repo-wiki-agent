---
name: repo-wiki-generate
description: Generate or improve a verified Repo Wiki candidate with an explicit safe run ID.
---

Resolve `<plugin_dir>` as this installed plugin's root and `<repo-root>` as the active repository. Run `python "<plugin_dir>/scripts/workflow.py" generate --run-id <id> --cwd "<repo-root>"` or replace `generate` with `improve`. The runner resolves configuration, reserves `.repo-agent-eval/runs/<id>`, runs config, then generation and exact-run verification. Report the returned candidate path and run ID. A verified candidate is not publishable until independent G005 evidence exists.
