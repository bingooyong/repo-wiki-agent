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
- The VS Code/Cursor extension is `extensions/repo-wiki-browser`. It browses READY releases, runs a configurable terminal command, and **does** provide visual LLM provider/model/base URL/`api_key_env` configuration plus SecretStorage for the API Key. Only the Python CLI calls the LLM.
- Because Wiki generation requires LLM access, configure the CLI before generate:
  1. Preferred: extension commands Configure LLM Settings / Set LLM API Key / Test LLM Configuration.
  2. Fallback: non-secret `repo-wiki.yaml` / `.repo-wiki.yaml`, or `LLM_*` environment variables.
  3. Keep real API Keys out of settings, YAML, command strings, logs, docs, and committed files. Store keys in SecretStorage or a temporary env var.
  4. Validate with `repo-wiki config --ci`.
  5. Generate, verify, and publish with `generate --profile qoder-like`, `verify --profile qoder-like --ci`, and `release-publish`.
- The VS Code extension reads the stable READY release at `.repo-agent-eval/repowiki/zh/manifest.json`; if a run is generated but not published, the extension may show no browsable Wiki.
