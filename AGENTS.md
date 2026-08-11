# AGENTS

This repository maintains generated docs and source-of-truth artifacts for AI tooling.

## Start Here
- `README.md`
- `docs/configuration.md`
- `docs/operations/vscode-extension-manual-llm-configuration.md`
- `docs/specs/vscode-llm-configuration-spec.md`
- `docs/plans/vscode-llm-configuration-implementation-plan.md`
- `docs/plans/display-and-wiki-generation-optimization-roadmap.md`
- `ai/source-of-truth/api-index.yaml`
- `ai/source-of-truth/data-models.yaml`
- `ai/source-of-truth/module-index.yaml`
- `ai/source-of-truth/repo-map.yaml`
- `ai/source-of-truth/task-catalog.yaml`
- `docs/00-overview.md`
- `docs/01-architecture.md`
- `docs/03-module-map.md`
- `docs/04-api-contracts.md`
- `docs/05-data-model.md`

## Command Surface
- `repo-wiki init`
- `repo-wiki index`
- `repo-wiki generate --profile qoder-like --output .repo-agent-eval`
- `repo-wiki verify --profile qoder-like --ci --output .repo-agent-eval`
- `repo-wiki release-publish --output .repo-agent-eval`
- `repo-wiki update`
- `repo-wiki search <query>`
- `repo-wiki graph <module>`
- `repo-wiki verify --ci`
- `repo-wiki config --ci`

## Current Product Notes
- The repository's primary deliverable is the Python CLI package `repo-wiki`, a local-first repository Wiki generator.
- The VS Code/Cursor extension is `extensions/repo-wiki-browser`. Current packaged versions browse READY releases and run a configurable terminal command; they do **not** yet provide visual LLM provider/model/base URL/API Key configuration.
- Because Wiki generation requires LLM access, new target projects must configure the CLI manually before using the extension:
  1. Create non-secret `repo-wiki.yaml` / `.repo-wiki.yaml`, or set `LLM_*` environment variables.
  2. Keep real API Keys out of settings, YAML, command strings, logs, docs, and committed files.
  3. Prefer temporary integrated-terminal environment variables until SecretStorage support is implemented; shell profile and untracked `.env` are local-disk persistence options only when the user accepts that risk.
  4. Validate with `repo-wiki config --ci`.
  5. Generate, verify, and publish with `generate --profile qoder-like`, `verify --profile qoder-like --ci`, and `release-publish`.
- The VS Code extension reads the stable READY release at `.repo-agent-eval/repowiki/zh/manifest.json`; if a run is generated but not published, the extension may show no browsable Wiki.
