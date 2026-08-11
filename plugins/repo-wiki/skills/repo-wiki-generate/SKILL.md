---
name: repo-wiki-generate
description: Generate or improve a verified Repo Wiki candidate with an explicit safe run ID.
---

Run `python scripts/workflow.py generate --run-id <id>` or `improve --run-id <id>`. The runner resolves the repository and configuration, reserves `.repo-agent-eval/runs/<id>`, runs config, then generation and exact-run verification. Report the returned candidate path and run ID. A verified candidate is not publishable until independent G005 evidence exists.
