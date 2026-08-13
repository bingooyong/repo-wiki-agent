# Workflow Safety Contract

The plugin runner fixes one repository root, Python executable, CLI capability set, configuration identity, run ID, output path, and optional allowed-signers identity for each invocation. It validates those identities before lifecycle checks and again between verification, inspection, and final local publication.

Lifecycle subprocesses receive argument arrays and run with the resolved repository as their working directory. Secrets must come from the existing CLI environment/configuration contract; do not place credentials in plugin metadata, skill text, command arguments, or generated evidence.

The runner rejects existing symlinks and detects path replacement before and after each child process. This bounds accidental drift and stops downstream verification or publication after a detected replacement. It is not a sandbox against a malicious process running as the same operating-system user: such a process can race pathname-based writes while the existing CLI is running. Use the plugin only in a trusted local workspace with trusted same-user processes. Preventing writes during a hostile same-user race would require changing the Wiki engine to use descriptor-anchored no-follow writes, which is outside the skills-only v1 boundary.

Generation produces a verified candidate, not a publishable release. Publication requires independently supplied G005 evidence, exact-run verification, authoritative inspect-only validation, and explicit confirmation of the same run ID. The plugin must never fabricate human reviews, Qoder comparisons, acceptance evidence, signatures, or attestations.
