# Secret sentinel artifact regression

This check scans generated repo-wiki artifacts for high-signal API key and token leaks before a run is published or attached to CI output.

## CI usage

Run the scanner against the artifact roots that may contain configuration snapshots, YAML, command logs, manifests, run folders, release folders, and generated Markdown:

```bash
python scripts/secret_sentinel_scan.py \
  .repo-agent-eval \
  repo-wiki.yaml \
  .repo-wiki.yaml \
  docs
```

Exit codes are CI-friendly:

- `0`: no findings
- `1`: one or more possible secret leaks found
- `2`: invalid input path

Finding output contains only path, line, column, rule name, length, and a short digest. It does not print the matched secret value.

## Scan boundaries

The scanner is deterministic and local. It recursively scans common text artifact types such as YAML, JSON, logs, shell commands, Markdown, config files, manifests, and generated docs. It skips binary files and common cache or dependency directories, including `.git`, virtualenvs, `node_modules`, Python caches, build, and dist folders.

The rules intentionally focus on high-signal leaks:

- explicit regression sentinel values used by tests
- OpenAI-compatible `sk-` key shape
- Bearer token headers
- labeled key/token/password assignments with long mixed values
- JWT-like tokens
- AWS access key IDs

Variable names such as `LLM_API_KEY_ENV`, environment variable references, redacted markers, and documentation placeholders are not findings.

## Rule maintenance

When adding a new provider or artifact channel, add a focused test fixture first in `tests/test_secret_sentinel_artifacts.py`, then update `scripts/secret_sentinel_scan.py` with the narrowest rule that catches the leak without matching variable names or placeholders. Prefer provider-specific prefixes, labels, or sentinel values over broad entropy-only detection.

Keep examples in documentation as placeholders or environment variable names. Do not commit real keys or long fake keys that look like live provider credentials.

## False positives

If CI reports a finding:

1. Inspect the reported path and rule.
2. Confirm whether the artifact contains a real literal secret, a test sentinel, or a placeholder.
3. Remove real literals from the artifact source and rerun generation.
4. If the value is safe but matched by a rule, add a regression test proving the safe case and narrow the rule.

Do not suppress findings by printing or copying the matched value into logs, issues, or review comments.
