---
name: repo-wiki-verify
description: Verify an exact Repo Wiki run and explain failures without exposing secrets.
---

Use `python scripts/workflow.py verify --run-id <id>` for a complete `.repo-agent-eval/runs/<id>` path. Report the redacted JSON result, including the canonical repository, output root, run ID, and report path. Stop on a failed grade, mismatched manifest identity, or malformed output; do not publish after any failure.
