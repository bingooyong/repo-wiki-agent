# Task 24.6: Page composer incremental cache

## Task Status: COMPLETED

## Agent: Agent_IndexGraph

## Completion Date: 2026-04-26

## Dependencies
- Task 24.5 by Agent_AdapterGovernance (Quality guardrails) - Completed
- Phase 12 SQLite invalidation (Task 12.4) - Completed

## Deliverables

### 1. Page Composer Cache Module
**File:** `/repo_wiki/generator/composer_cache.py`

Page composer incremental cache implementation providing:

- **ComposerCacheRecord**: Dataclass for cache entries with page_id, doc_type, input_hash, output_hash, model_name, tokens_used, cost_usd, cached_at, output_markdown

- **ComposerCacheStats**: Dataclass for cache statistics

- **Input Hash Computation Functions**:
  - `compute_page_plan_hash()`: Computes deterministic hash from WikiPagePlan
  - `compute_evidence_hash()`: Computes hash from evidence binding and source digests
  - `compute_skeleton_hash()`: Computes hash from article skeleton structure
  - `compute_context_hash()`: Computes hash from composer context
  - `compute_composer_input_hash()`: Combines all input hashes for overall input hash
  - `compute_output_hash()`: Computes hash from composed markdown output

- **ComposerCache Class**: SQLite-backed cache with:
  - `get()`: Retrieve cached composition by page_id and input_hash
  - `put()`: Store composition result with tokens and cost
  - `invalidate()`: Invalidate all entries for a page
  - `invalidate_by_hash()`: Invalidate specific entry by hash
  - `clear()`: Clear all cache entries
  - `stats()`: Get cache statistics
  - `list_entries()`: List cache entries with optional filtering
  - `get_for_page()`: Convenience method returning (markdown, tokens)

- **CachedComposerMixin**: Mixin class for LLMPageComposer with caching capability

- **Helper Functions**:
  - `create_composer_cache()`: Factory for standard cache location
  - `format_cache_stats()`: Human-readable statistics formatting
  - `estimate_tokens_from_markdown()`: Token estimation
  - `estimate_cost_from_tokens()`: Cost estimation based on model

### 2. Cache Schema

SQLite table `composer_cache` with columns:
- id (PRIMARY KEY)
- page_id (TEXT NOT NULL)
- doc_type (TEXT NOT NULL)
- input_hash (TEXT NOT NULL)
- output_hash (TEXT)
- model_name (TEXT DEFAULT 'mock-gpt')
- tokens_used (INTEGER DEFAULT 0)
- cost_usd (REAL DEFAULT 0.0)
- output_markdown (TEXT)
- cached_at (TEXT NOT NULL)
- updated_at (TEXT NOT NULL)
- UNIQUE(page_id, input_hash)

Indexes:
- idx_composer_cache_page on page_id
- idx_composer_cache_input_hash on input_hash

### 3. Test Coverage

**File:** `/tests/test_page_composer_cache.py`

- TestComputePagePlanHash: Hash computation for page plans
- TestComputeEvidenceHash: Hash computation for evidence bindings
- TestComputeSkeletonHash: Hash computation for article skeletons
- TestComputeContextHash: Hash computation for composer context
- TestComputeComposerInputHash: Combined input hash computation
- TestComputeOutputHash: Output hash computation
- TestEstimateTokens: Token and cost estimation
- TestComposerCache: Full cache put/get/invalidate operations
- TestCreateComposerCache: Factory function
- TestFormatCacheStats: Statistics formatting

## Verification Commands

```bash
# Compile check
uv run repo-wiki --help

# Run tests
uv run pytest tests/test_page_composer_cache.py tests/test_phase12_sqlite_runtime.py
```

## Test Results

- **test_page_composer_cache.py**: 30 passed
- **test_phase12_sqlite_runtime.py**: 22 passed
- **Combined**: 52 passed

## Key Findings

1. Input hash computation is deterministic - same inputs produce same hash
2. Cache avoids repeated LLM calls for unchanged pages by comparing input hashes
3. Token and cost tracking enables budget monitoring
4. SQLite-backed persistence survives process restarts
5. Integration with SQLiteRuntimeStore via ComposerCacheRecord structure
6. Cache schema supports page-level invalidation based on input hash

## Implementation Notes

- Hash computation uses SHA256 truncated to 24-32 characters
- Evidence binding hash uses digest as primary identifier for deduplication
- Skeleton hash includes toc_entries and headings for completeness
- Cost estimation supports mock-gpt (free), gpt-4o, and gpt-4o-mini models
- Cache stores full markdown output for fast retrieval without LLM calls
