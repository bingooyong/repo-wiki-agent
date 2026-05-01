# Task 22.3 - Repository identity resolver

## Status: COMPLETED

## Objective
Resolve real repository identity from metadata and source evidence.

## Deliverables
- **Identity resolver** (`repo_wiki/planner/identity.py`)
  - `resolve_repository_identity(root: Path) -> RepositoryIdentity`
  - Reads: package.json, pyproject.toml, pom.xml, git remote, README
  - Prefers explicit metadata over generic workspace names
  - `detect_language_and_framework(root: Path) -> tuple[str, str]`
  - `detect_package_manager(root: Path) -> str`
  - `_human_readable_name(name: str) -> str` (preserves acronyms like AI, API)

- **Identity tests** (`tests/test_repository_identity.py`)
  - 21 tests covering all resolution paths
  - AI_API_Atlas regression: project name is NOT "workspace"

## Self-Test Results
```
uv run pytest tests/test_repository_identity.py tests/test_scanner.py  # PASSED (21 tests)
```

## Key Implementation Details
- Priority order for name: package.json > pyproject.toml > pom.xml > git-remote > directory-name
- Description优先从package.json读取，fallback到README
- Acronym preservation: "AI_API_Atlas" -> "AI API Atlas" (not "Ai Api Atlas")
