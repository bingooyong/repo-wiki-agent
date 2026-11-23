# Module: repo_wiki

Path: `repo_wiki`  
Owner: `unknown`

## Responsibility
Typer CLI entry point, configuration loading, orchestration facade, and public repo-wiki command surface.

## Exports
- none

## Depends On
- `repo_wiki.orchestration`
- `repo_wiki.verifier`
- `repo_wiki.viewer`

## Depended By
- `tests`
- `extensions/repo-wiki-browser`

## Interfaces
- none

## Data Models
- none

## Context Strategy
- Strategy: `A`
- Token budget: `1200`
- Notes: Small module summary from direct metadata and a compact chunk set.

### Graph Neighbors
- `tests`

### Retrieval Chunks
- `init_command` `repo_wiki/cli.py`
- `VerifyResult` `repo_wiki/core/contracts.py`
- `RepositoryScanner._discover_modules` `repo_wiki/scanner/repository_scanner.py`
