---
agent: Agent_QualityRelease
task_ref: Task 30.1 - End-user configuration documentation
status: Completed
ad_hoc_delegation: false
compatibility_issues: false
important_findings: true
---

# Task Log: Task 30.1 - End-user configuration documentation

## Summary

Added canonical end-user LLM configuration documentation at `docs/configuration.md`, aligned with `resolve_llm_config`, `repo-wiki config` diagnostics, and qoder-like mock/real behavior; pointed `docs/operations/llm-provider-configuration.md` at the new guide.

## Details

1. Verified CLI: diagnostics live under **`repo-wiki config`** (not `config-doctor`); `--ci` emits JSON suitable for automation.
2. Documented YAML/env precedence (CLI overrides → `LLM_*` / Minimax aliases → `llm:` in YAML → defaults), field table, and placeholder-only secrets policy.
3. Wrote provider sections: Minimax (native + `/anthropic` in `base_url`), OpenAI-compatible (incl. Azure-style `base_url`), Anthropic via OpenAI-shaped gateways, local Ollama/LM Studio.
4. Explained mock vs real for **`_resolve_qoder_like_llm`**: real Minimax only when `provider == minimax` and API key present; otherwise mock—called out as user-visible architectural constraint.
5. Added troubleshooting table and cross-links to operations doc.

## Output

- **Created:** `docs/configuration.md` — full end-user configuration guide (Chinese, markdown).
- **Updated:** `docs/operations/llm-provider-configuration.md` — short redirect note to `docs/configuration.md`.

## Issues

None.

## Important Findings

- **Qoder-like composer:** Runtime uses a **real** LLM only when `provider` is **`minimax`** and the key from `api_key_env` is set; other configured providers still fall back to **MockLLMProvider** on this path. Users expecting OpenAI/Anthropic on first `generate --profile qoder-like` should see `docs/configuration.md` §5 or use flows that invoke real OpenAI adapters where implemented.

## Next Steps

None.
