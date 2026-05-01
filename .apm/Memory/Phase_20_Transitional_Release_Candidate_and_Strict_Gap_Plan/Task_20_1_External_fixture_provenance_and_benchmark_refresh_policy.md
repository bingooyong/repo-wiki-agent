---
agent: Agent_QualityRelease
task_ref: Task 20.1
status: Completed
ad_hoc_delegation: false
compatibility_issues: false
important_findings: true
---

# Task Log: Task 20.1 - External fixture provenance and benchmark refresh policy

## Summary

定义了外部 qoder fixture 的 provenance、freshness 和 confidence 规则，实现了相应的验证器和评分系统，并创建了 fixture refresh workflow 和 maintainer checklist。

## Details

### 1. 新增 FreshnessValidator 类

**位置**: `scripts/qoder_fixture_ingestion.py`

新增 freshness 验证功能：

- `compute_age_days(generated_at)`: 从 ISO timestamp 计算 fixture 年龄
- `get_freshness_status(generated_at, profile)`: 返回 (status, age_days, is_usable)
  - status: "fresh" | "stale" | "critical"
  - Age <= MAX: fresh
  - Age <= 2*MAX: stale (可用但警告)
  - Age > 2*MAX: critical (必须拒绝)
- `get_freshness_score(generated_at, profile)`: 返回 0.0-1.0 的 freshness score

**最大年龄阈值**:
```python
MAX_FIXTURE_AGE = {
    "strict": 7,       # 7 days
    "transitional": 30, # 30 days
    "pilot": 90,        # 90 days
}
```

### 2. 新增 ConfidenceScorer 类

**位置**: `scripts/qoder_fixture_ingestion.py`

实现综合 confidence scoring：

- `compute_confidence_score(manifest, profile)`: 计算综合 confidence score
  - Schema validity 贡献 30% (VALID=0.3, PARTIAL=0.15, INVALID=0.0)
  - Structural completeness 贡献 30% (基于 diagnostics 错误/警告数)
  - Freshness 贡献 40% (Freshness Score * 0.4)
- `get_confidence_level(score)`: 映射到 "high"/"medium"/"low"/"unacceptable"
- `get_release_gate_decision(manifest, profile)`: 返回完整的 release gate 决策

**Confidence 阈值**:
```python
CONFIDENCE_THRESHOLDS = {
    "high": 0.90,       # >= 90% for strict
    "medium": 0.70,     # >= 70% for transitional
    "low": 0.50,        # >= 50% for pilot
    "unacceptable": 0.0
}
```

### 3. 新增 CLI 选项

在 `qoder_fixture_ingestion.py` 的 `main()` 函数中新增：

- `--profile`: 选择验证使用的 profile (strict/transitional/pilot)
- `--check-confidence`: 运行 release gate confidence 检查

```bash
# 示例：检查 fixture 是否满足 strict profile
python scripts/qoder_fixture_ingestion.py \
    --fixture /path/to/fixture \
    --check-confidence \
    --profile strict

# 退出码 0 = APPROVED, 1 = REJECTED
```

### 4. 创建 Policy 文档

**新文件**: `docs/operations/fixture-provenance-and-freshness-policy.md`

包含：
- Fixture 来源规范
- 必需 capture 元数据
- Freshness 规则和 score 计算
- Confidence scoring 算法
- Fixture refresh workflow
- Maintainer checklist

### 5. 验证

所有 18 个现有测试继续通过：
```
tests/test_fixture_ingestion.py .................. [100%] 18 passed
```

## Key Findings

1. **Freshness 是关键**: 旧的 fixture 可能导致 compare 结果不准确，必须有明确的 freshness 约束
2. **Confidence Score 防止误用**: 通过综合评分而非单一指标判断，提高决策可靠性
3. **Profile 差异化**: 不同 profile 有不同的 freshness 和 confidence 要求

## Next Steps

Task 20.2 依赖此任务，将使用 fixture provenance 和 freshness 规则运行 release-candidate pilot。