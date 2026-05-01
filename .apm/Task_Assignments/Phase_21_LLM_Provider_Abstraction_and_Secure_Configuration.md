# Phase 21 - LLM Provider Abstraction and Secure Configuration

## Task 21.1

```markdown
---
task_ref: "Task 21.1 - LLM config schema and environment resolution"
agent_assignment: "Agent_PlatformCore"
memory_log_path: ".apm/Memory/Phase_21_LLM_Provider_Abstraction_and_Secure_Configuration/Task_21_1_LLM_config_schema_and_environment_resolution.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: LLM config schema and environment resolution

## Task Reference
Implementation Plan: **Task 21.1 - LLM config schema and environment resolution** assigned to **Agent_PlatformCore**

## Context from Dependencies
Read `docs/phases/Phase_21_LLM_Provider_Abstraction_and_Secure_Configuration.md` and `.apm/Memory/Phase_20_Transitional_Release_Candidate_and_Strict_Gap_Plan/Task_20_4_Transitional_go_no_go_dossier_and_manager_handover.md` before implementation.

## Objective
Add the `llm` configuration schema, environment variable resolution, and secret redaction.

## Detailed Instructions
- Define provider/model/base_url/api_key_env/max_tokens/temperature/timeout/max_retries fields.
- Resolve values from config, environment, and CLI overrides without logging secrets.
- Add stable validation reason codes and redaction helpers.

## Expected Output
- Deliverables: typed config schema, env resolution, redacted diagnostics, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_config.py tests/test_llm_config.py`
- Completion rule: do not mark complete unless compile and self-test pass, or the Final Task Report documents a reproducible environmental blocker.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_21_LLM_Provider_Abstraction_and_Secure_Configuration/Task_21_1_LLM_config_schema_and_environment_resolution.md`
```

## Task 21.2

```markdown
---
task_ref: "Task 21.2 - Provider interface and request/response contract"
agent_assignment: "Agent_PlatformCore"
memory_log_path: ".apm/Memory/Phase_21_LLM_Provider_Abstraction_and_Secure_Configuration/Task_21_2_Provider_interface_and_request_response_contract.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Provider interface and request/response contract

## Task Reference
Implementation Plan: **Task 21.2 - Provider interface and request/response contract** assigned to **Agent_PlatformCore**

## Context from Dependencies
Depends on Task 21.1. Read its memory log and reuse the config/redaction contracts it created.

## Objective
Define the unified LLM client request/response/error contract.

## Detailed Instructions
- Add `LLMClient`, `ChatRequest`, `ChatResponse`, and normalized provider errors.
- Cover success, timeout, rate limit, auth failure, and missing key cases.
- Add a mock provider for CI and downstream composer tests.

## Expected Output
- Deliverables: provider interface, data models, mock provider, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_llm_provider_contract.py tests/test_llm_config.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_21_LLM_Provider_Abstraction_and_Secure_Configuration/Task_21_2_Provider_interface_and_request_response_contract.md`
```

## Task 21.3

```markdown
---
task_ref: "Task 21.3 - OpenAI-compatible and Minimax provider implementation"
agent_assignment: "Agent_PlatformCore"
memory_log_path: ".apm/Memory/Phase_21_LLM_Provider_Abstraction_and_Secure_Configuration/Task_21_3_OpenAI_compatible_and_Minimax_provider_implementation.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: OpenAI-compatible and Minimax provider implementation

## Task Reference
Implementation Plan: **Task 21.3 - OpenAI-compatible and Minimax provider implementation** assigned to **Agent_PlatformCore**

## Context from Dependencies
Depends on Task 21.2. Read the provider contract and mock provider tests before adding concrete adapters.

## Objective
Implement OpenAI-compatible and Minimax provider adapters.

## Detailed Instructions
- Support base_url/model/api_key_env configuration.
- Keep real API smoke tests optional and skipped unless required env vars exist.
- Map provider responses and provider failures into the unified contract.

## Expected Output
- Deliverables: OpenAI-compatible provider, Minimax provider, mock-backed tests, optional smoke hook.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_llm_providers.py tests/test_llm_provider_contract.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_21_LLM_Provider_Abstraction_and_Secure_Configuration/Task_21_3_OpenAI_compatible_and_Minimax_provider_implementation.md`
```

## Task 21.4

```markdown
---
task_ref: "Task 21.4 - Token budgeting, retry, and cache policy"
agent_assignment: "Agent_PlatformCore"
memory_log_path: ".apm/Memory/Phase_21_LLM_Provider_Abstraction_and_Secure_Configuration/Task_21_4_Token_budgeting_retry_and_cache_policy.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Token budgeting, retry, and cache policy

## Task Reference
Implementation Plan: **Task 21.4 - Token budgeting, retry, and cache policy** assigned to **Agent_PlatformCore**

## Context from Dependencies
Depends on Task 21.3. Use the provider adapters and normalized error model.

## Objective
Add token budgeting, bounded retry/backoff, and safe LLM cache behavior.

## Detailed Instructions
- Estimate prompt/completion budget per request.
- Retry only safe provider failures and respect max_retries.
- Cache successful deterministic requests; never cache failures or secret-bearing payloads.

## Expected Output
- Deliverables: budget estimator, retry wrapper, cache policy, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_llm_budget.py tests/test_llm_retry_cache.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_21_LLM_Provider_Abstraction_and_Secure_Configuration/Task_21_4_Token_budgeting_retry_and_cache_policy.md`
```

## Task 21.5

```markdown
---
task_ref: "Task 21.5 - CLI configuration validation and diagnostics"
agent_assignment: "Agent_AdapterGovernance"
memory_log_path: ".apm/Memory/Phase_21_LLM_Provider_Abstraction_and_Secure_Configuration/Task_21_5_CLI_configuration_validation_and_diagnostics.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: CLI configuration validation and diagnostics

## Task Reference
Implementation Plan: **Task 21.5 - CLI configuration validation and diagnostics** assigned to **Agent_AdapterGovernance**

## Context from Dependencies
Depends on Task 21.4 by Agent_PlatformCore. Read the LLM config, provider, retry, and cache contracts before wiring diagnostics.

## Objective
Add user-facing LLM configuration diagnostics.

## Detailed Instructions
- Implement `repo-wiki config doctor` or an equivalent diagnostics command.
- Validate provider/model/base_url/api_key_env/budget fields and output reason codes.
- Redact all secrets in terminal and JSON outputs.

## Expected Output
- Deliverables: config diagnostics command, JSON/text output, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_cli_config_doctor.py tests/test_llm_config.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_21_LLM_Provider_Abstraction_and_Secure_Configuration/Task_21_5_CLI_configuration_validation_and_diagnostics.md`
```

