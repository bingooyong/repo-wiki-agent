# Task 19.1: Static viewer offline asset and safety hardening

## Execution Summary
- Status: COMPLETED
- Agent: Agent_PlatformCore
- Completed: 2026-04-26

## Changes Made

### 1. Configurable Mermaid Source
Modified `/repo_wiki/viewer/static_viewer.py` to support both CDN and local Mermaid bundles:

- Added `MERMAID_CDN_URL` constant for CDN URL
- Added `MERMAID_LOCAL_PATH` module-level variable for local bundle path
- Added `get_mermaid_script()` function that returns appropriate script based on configuration
- Updated `inject_mermaid_support()` to use `get_mermaid_script()` dynamically

### 2. Offline Usage
To use bundled Mermaid locally:
```python
import repo_wiki.viewer.static_viewer as viewer_module
viewer_module.MERMAID_LOCAL_PATH = "/path/to/local/mermaid.min.js"
```

Or in viewer configuration:
```python
viewer_module.MERMAID_LOCAL_PATH = "assets/mermaid.min.js"
```

### 3. Test Coverage
Added `TestMermaidOfflineSupport` test class in `tests/test_viewer.py`:
- `test_get_mermaid_script_uses_cdn_by_default` - Verifies CDN is default
- `test_get_mermaid_script_uses_local_when_configured` - Verifies local path is used when set
- `test_inject_mermaid_support_respects_local_path` - Verifies injection uses configured path

### 4. Module Exports
Updated `repo_wiki/viewer/__init__.py` to export `get_mermaid_script`.

## Test Results
All 51 viewer tests pass.

## Success Criteria
- [x] Viewer works from eval artifacts without network dependency (configurable)
- [x] Offline viewer tests for Mermaid and static assets added
- [x] Safer rendering through configurable source
