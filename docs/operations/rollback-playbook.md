# Rollback Playbook

## Scope

This playbook covers Stage 0 `repo-wiki release-publish` rollback for the fixed reader tree:

```text
.repo-agent-eval/repowiki/zh/
```

The supported release path is:

```bash
repo-wiki generate --profile qoder-like --output .repo-agent-eval
repo-wiki verify --profile qoder-like --ci --output .repo-agent-eval
repo-wiki release-publish --output .repo-agent-eval --run <run_id>
```

Do not publish a run that has not passed strict verify. Do not manually copy a generated run over `.repo-agent-eval/repowiki/zh/`.

## Automatic rollback during publish

`release-publish` performs rollback automatically if replacement fails after an existing READY tree has been moved aside:

1. It stages the selected run in a temporary directory.
2. It moves the existing READY tree to `.repo-agent-eval/repowiki/zh.__backup__`.
3. It moves the staged tree to `.repo-agent-eval/repowiki/zh/`.
4. It appends `.repo-agent-eval/release-history.json` atomically.
5. It deletes `zh.__backup__` only after READY and history are committed.

If step 2 succeeds but a later step fails, the publisher restores the old READY tree from `zh.__backup__`. If there was no previous READY tree, it removes the failed new READY tree. Stage 0 does not add a separate user rollback command.

## Failure semantics

| Failure point | READY result | `release-history.json` result | Operator action |
|---|---|---|---|
| Candidate is not READY | Existing READY remains | No new entry | Fix generation or verify errors, then publish a new run. |
| Strict verify report missing or not `PASS` | Existing READY remains | No new entry | Run strict verify and publish only after PASS. |
| Candidate roots invalid or contain symlinks | Existing READY remains | No new entry | Regenerate or fix the run artifact. |
| Meta sidecar validation fails | Existing READY remains | No new entry | Fix sidecar writer or regenerate. |
| Filesystem swap fails after backup move | Previous READY is restored | No new entry | Inspect disk/permission errors and retry after cleanup. |
| History append fails | Previous READY is restored | Prior history bytes remain | Inspect disk/permission errors and retry. |
| Existing history is invalid JSON or not an array | Previous READY is restored | Invalid history bytes remain untouched | Repair or archive the invalid history after investigation, then retry. |

## Verification after a failed publish

Run these checks before retrying:

```bash
# Reader-facing READY tree still exists when there was a previous release
test -f .repo-agent-eval/repowiki/zh/manifest.json

# Confirm the source run did not change unexpectedly
python - <<'PY'
import json
from pathlib import Path
manifest = json.loads(Path('.repo-agent-eval/repowiki/zh/manifest.json').read_text())
print(manifest.get('source_run_id'), manifest.get('release_status'))
PY

# Confirm no temporary backup remains from a completed/rolled-back transaction
test ! -e .repo-agent-eval/repowiki/zh.__backup__
```

A failed publish should not add a successful release entry. Check the last history row only after confirming the command exited successfully:

```bash
python - <<'PY'
import json
from pathlib import Path
history = json.loads(Path('.repo-agent-eval/release-history.json').read_text())
print(history[-1]['release_id'], history[-1]['source_run_id'], history[-1]['release_status'])
PY
```

## Manual recovery for interrupted operator actions

Manual recovery is only for out-of-band interruption or hand edits. Prefer rerunning `release-publish` when possible.

```bash
# If an interrupted transaction left the backup and no READY tree, restore it.
if [ ! -e .repo-agent-eval/repowiki/zh ] && [ -e .repo-agent-eval/repowiki/zh.__backup__ ]; then
  mv .repo-agent-eval/repowiki/zh.__backup__ .repo-agent-eval/repowiki/zh
fi

# If both exist, do not overwrite blindly. Inspect first.
find .repo-agent-eval/repowiki -maxdepth 2 -type f -name manifest.json -print
```

After manual recovery, run strict verification on a fresh generated run and publish that run normally.
