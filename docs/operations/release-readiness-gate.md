# Repo-Wiki MVP Final Readiness Gate

## Evidence Summary
- Phase 1-4 pipeline implemented and command surface exposed.
- Governance check available through `repo-wiki verify --ci`.
- Pilot and CI packaging artifacts prepared under `docs/operations/`.

## Risk Register
- Optional dependencies (`chromadb`, `sentence-transformers`, `diskcache`) may fallback to deterministic local behavior.
- Search relevance depends on repository quality and extraction coverage.
- Non-git workspaces rely on hash-compare fallback for change detection.

## Rollback / Fallback
- If semantic stack is unavailable, fallback to SQLite FTS + deterministic embeddings.
- If docs generation quality regresses, rerun full `repo-wiki init` to rebuild all artifacts.
- If adapter files drift, run `repo-wiki sync`.

## Recommendation
- Gate status: **Ready with controlled risks**.
- Required follow-up after pilot:
  - Capture pilot metrics and compare with target thresholds.
  - Promote CI workflow from template to enforced branch protection after pilot sign-off.
