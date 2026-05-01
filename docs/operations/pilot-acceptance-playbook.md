# Repo-Wiki MVP Pilot Acceptance Playbook

## Pilot Qualification
- Repository size: 30 to 300 modules.
- Contains backend API routes and data model definitions.
- Supports at least one of Python, TypeScript/JavaScript, or Go.
- Can execute `repo-wiki init`, `repo-wiki update`, and `repo-wiki verify --ci`.

## Acceptance Scenarios
1. `init`: Full pipeline bootstrap with source-of-truth + docs + adapters.
2. `search`: Validate Top-3 results for representative queries.
3. `graph`: Validate upstream/downstream chain for key modules.
4. `update`: Modify sample files, verify impacted module regeneration.
5. `verify`: Confirm PASS/WARN/FAIL behavior and CI exit code contract.

## Metric Capture
- Module identification accuracy.
- REST extraction accuracy.
- Module doc coverage ratio.
- Search Top-3 hit rate.
- Impact-chain reasonableness.
- Init success rate.

Use:
```bash
python scripts/pilot_acceptance.py --target /path/to/repo --out .repo-wiki/pilot
```

## Evidence Pack
- `.repo-wiki/pilot/acceptance-report.json`
- `.repo-wiki/pilot/metrics.json`
- `.repo-wiki/pilot/scenario-logs/*.json`

## Pass/Fail Template
- PASS: all mandatory scenarios succeed and no FAIL checks in `verify --ci`.
- WARN: scenarios pass but quality metrics below target thresholds.
- FAIL: init/update/verify contracts fail or artifacts are incomplete.
