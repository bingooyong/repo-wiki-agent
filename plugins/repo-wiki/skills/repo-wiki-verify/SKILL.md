---
name: repo-wiki-verify
description: Verify an exact Repo Wiki run and explain failures without exposing secrets.
---

Resolve `<plugin_dir>` as this installed plugin's root and `<repo-root>` as the active repository. Use `python "<plugin_dir>/scripts/workflow.py" verify --run-id <id> --cwd "<repo-root>"` for a complete `.repo-agent-eval/runs/<id>` path. Report the redacted JSON result, including the canonical repository, output root, run ID, and report path. Stop on a failed grade, mismatched manifest identity, or malformed output; do not publish after any failure.
