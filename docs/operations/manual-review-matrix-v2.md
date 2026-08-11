# Manual Review Matrix v2

`Manual review matrix v2` is the readiness review contract used after strict verify and baseline compare.

## Thresholds

- Reviewed pages: at least `30`
- Accepted pages: at least `24`
- Mandatory rows: must include `API台账服务 API`
- Mandatory P0 policy: mandatory rows must have `0` P0 failures
- Category coverage: must include all of:
  - `overview`
  - `architecture`
  - `services`
  - `api`
  - `data-models`
  - `operations`
  - `security`
  - `troubleshooting`

## Artifact Placement

Store manual review artifacts in at least one audited location:

- Selected eval run reports, e.g. `.repo-agent-eval/runs/<run-id>/reports/manual-review-matrix-v2.{json,md}`
- Operations evidence, e.g. `docs/operations/evidence/manual-review-matrix-v2.{json,md}`

## Failure Semantics

The gate fails when any of the following is true:

- `MANUAL_REVIEW_REVIEWED_PAGES_LOW`
- `MANUAL_REVIEW_ACCEPTED_PAGES_LOW`
- `MANUAL_REVIEW_MANDATORY_ROW_MISSING`
- `MANUAL_REVIEW_MANDATORY_P0_FAILURE`
- `MANUAL_REVIEW_CATEGORY_COVERAGE_LOW`
