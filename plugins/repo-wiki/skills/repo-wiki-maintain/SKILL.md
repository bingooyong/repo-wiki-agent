---
name: repo-wiki-maintain
description: Maintain an existing Repo Wiki using runner-backed lifecycle workflows.
---

Resolve `<plugin_dir>` as this installed plugin's root and `<repo-root>` as the active repository. Use `python "<plugin_dir>/scripts/workflow.py" doctor --cwd "<repo-root>"` before writes. Run `init`, `index`, `update`, or `sync` through that same runner path and `--cwd`.

When the required human and external evidence has already been supplied, compile its canonical G005 bundle through the runner: `python "<plugin_dir>/scripts/workflow.py" quality-gate --run-id <id> --review-allowed-signers "<trusted-signers-file>" --cwd "<repo-root>"`. This command validates and compiles supplied evidence; it does not create, infer, or auto-approve human reviews, Qoder comparisons, acceptance results, signatures, or attestations. Stop and report any missing evidence. Pass explicit evidence options to this runner when non-default artifact paths are required; never invoke `repo-wiki quality-gate` directly.

For a stable release, first run `python "<plugin_dir>/scripts/workflow.py" publish --run-id <id> --review-allowed-signers "<trusted-signers-file>" --cwd "<repo-root>"` to inspect an explicit G005-gated run. Report the resolved repository, output root, and run ID. After the user explicitly confirms that exact local replacement, repeat the runner command with `--run-id <id> --confirm-run-id <id> --review-allowed-signers "<trusted-signers-file>" --cwd "<repo-root>"`. The signer path must be the same trusted, external file in both invocations; do not rely on ambient signer environment variables. Never publish latest implicitly.
