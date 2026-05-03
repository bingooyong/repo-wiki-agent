# Task 33.4 - Low-confidence fallback

## Objective
Replace unsupported implementation claims with explicit low-confidence sections.

## Completion Rule
Insufficient evidence produces explicit uncertainty rather than unsupported claims.

## Implementation

### 1. Low-confidence composer behavior

Added to `repo_wiki/generator/composer.py`:

**ComposerOutput** now includes:
- `low_confidence: bool = False`
- `uncertainty_reasons: list[str] = field(default_factory=list)`

**ValidationResult** now includes:
- `low_confidence: bool = False`
- `uncertainty_reasons: list[str] = field(default_factory=list)`

**_validate_output** detects:
- `NO_EVIDENCE_BINDING`: when `evidence_binding` is None
- `INSUFFICIENT_CITATIONS`: when >= 3 candidates but < 3 citations
- `LOW_EVIDENCE_BINDING`: when 0 < candidate_count < 3
- `UNSUPPORTED_CLAIMS`: when strong assertions without citation backing

### 2. Prompt updates

**_build_low_confidence_guidance** method added to LLMPageComposer:

When `evidence_binding` is None:
```
[待确认] 证据状态：无可用源码证据。
生成时必须：
- 明确标注「待确认」段落
- 避免声称任何具体实现细节
- 仅描述可以从不完整推断中确认的事实
```

When evidence is insufficient (insufficient_evidence flag or candidate_count < 3):
```
[待确认] 证据状态：证据不足（仅 N 条候选）。
生成时必须：
- 对每一个依赖推断的结论标注「待确认」
- 不允许编造模块名、API 端点、版本号或配置
- 使用「当前证据显示」而非「系统使用」
- 保留所有 `<cite>` 引用，即使推断不确定
```

### 3. Tests added

Added `TestLowConfidenceBehavior` class in `tests/test_llm_page_composer.py`:
- `test_compose_page_with_low_confidence_flags`: Verifies low-confidence pages get appropriate flags
- `test_compose_page_produces_uncertainty_when_no_evidence`: Verifies pages without evidence produce uncertainty markers
- `test_compose_page_prohibits_fabrication_in_low_confidence`: Verifies low-confidence pages cannot fabricate implementation details
- `test_composer_output_has_low_confidence_field`: Verifies ComposerOutput includes low_confidence tracking
- `test_validation_result_has_low_confidence_fields`: Verifies ValidationResult includes low-confidence tracking

Updated `TestValidationResult` to include low-confidence field tests.

## Verification

- Compile command: `uv run repo-wiki --help` - SUCCESS
- Self-test command: `uv run pytest tests/test_llm_page_composer.py tests/test_quality_guardrails.py` - 68 passed

## Completion Status

Task 33.4 completed. Low-confidence fallback behavior implemented:
1. Generating `待确认` sections when evidence is insufficient - DONE
2. Prohibiting fabricated implementation details in low-confidence pages - DONE
3. Ensuring uncertainty text does not dominate otherwise well-evidenced pages - DONE (only set low_confidence when no rejection)
4. Adding tests for insufficient-evidence composition - DONE
