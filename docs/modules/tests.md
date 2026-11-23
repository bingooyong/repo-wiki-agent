# Module: tests

Path: `tests`  
Owner: `unknown`

## Responsibility
Python unit and contract tests for CLI behavior, generation layouts, release contracts, verifier gates, and extension packaging.

## Exports
- none

## Depends On
- `repo_wiki`
- `repo_wiki.orchestration`
- `repo_wiki.verifier`
- `repo_wiki.viewer`
- `extensions/repo-wiki-browser`
- `plugins/repo-wiki`

## Depended By
- none

## Interfaces
- none

## Data Models
- none

## Context Strategy
- Strategy: `B`
- Token budget: `2400`
- Notes: Balanced context from module metadata, interfaces/models and Top-K chunks.

### Graph Neighbors
- `repo_wiki`

### Retrieval Chunks
- `tests` `tests/test_scanner_artifacts.py`
- `_write_minimum_artifacts` `tests/test_verifier.py`
- `test_verifier_pass` `tests/test_verifier.py`
- `test_sanitize_text_redacts_sensitive_values` `tests/test_security.py`
- `tests` `tests/test_verifier.py`
- `test_scanner_and_source_of_truth_outputs` `tests/test_scanner_artifacts.py`
