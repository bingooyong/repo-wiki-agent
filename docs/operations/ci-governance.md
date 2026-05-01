# CI Governance and Packaging

## Local Commands
- `make ai-init`
- `make ai-index`
- `make ai-update`
- `make ai-sync`
- `make ai-verify`
- `make ai-cost`

## CI Contract
- CI must run `repo-wiki verify --ci`.
- Non-zero exit code indicates FAIL grade.
- CI artifacts should include generated verify JSON output.

## Safe Hook Guidance
Optional post-commit reminder hook:
```bash
#!/usr/bin/env bash
echo "[repo-wiki] Reminder: run 'repo-wiki verify --ci' before pushing."
```

Do not auto-modify files inside hooks; keep reminders non-destructive.

## Troubleshooting
- If verify fails due to missing docs, run `repo-wiki init` first.
- If adapter path validation fails, run `repo-wiki sync`.
- If stale-doc warnings persist, run `repo-wiki update` and re-run verify.
