---
agent: Agent_QualityRelease
task_ref: Task 14.2
status: Completed
ad_hoc_delegation: false
compatibility_issues: false
important_findings: false
---

# Task Log: Task 14.2 - Comparator calibration with external baseline and weighted rubric

## Summary

成功为 compare 工具添加了显式权重系统、防 alias/overlay 膨胀机制和文档化评分标准，确保评分可重现且可解释。

## Details

### 1. 显式权重系统

定义了 DIMENSION_WEIGHTS，为每个维度分配明确权重：
- **结构性维度** (总权重 0.60):
  - DIRECTORY_HIERARCHY: 0.20
  - SECTION_COVERAGE: 0.20
  - NAVIGATION_COMPLETENESS: 0.20
- **质量维度** (总权重 0.40):
  - HEADING_COVERAGE: 0.133
  - PROSE_DENSITY: 0.133
  - AGGREGATION_QUALITY: 0.134

### 2. 防 alias/overlay 膨胀机制

通过 `_calculate_weighted_scores()` 方法实现：
- 使用显式权重替代隐式平均
- 限制单个维度的 raw score 影响上限为 1.0
- 确保没有单一维度能主导整体分数

### 3. 评分可重现性保证

新增 `WeightedScore` dataclass，包含：
- raw_score: 原始分数
- weighted_score: 加权分数
- weight: 权重值
- dimension: 维度名称
- delta_type: 差距类型

### 4. 文档化评分标准

在 GapReport summary 中新增：
- `weighting_scheme`: 权重方案标识
- `dimension_weights`: 每个维度的权重
- `weighted_breakdown`: 详细的加权分数分解

### 5. 测试覆盖

更新了 `tests/test_baseline_comparator.py`，新增：
- `TestPhase14Calibration` 测试类 (6 个测试)
- 验证权重分解、结构/质量分数求和、防主导机制
- 验证分数跨运行稳定性
- 验证文档化评分标准

## Output

### Modified Files

- `/scripts/qoder_baseline_comparison.py` - 添加显式权重系统和防膨胀机制
- `/tests/test_baseline_comparator.py` - 新增 6 个 Phase 14 校准测试

### Key Code Changes

**DIMENSION_WEIGHTS:**
```python
DIMENSION_WEIGHTS = {
    # Structural (total: 0.60)
    ComparisonDimension.DIRECTORY_HIERARCHY: 0.20,
    ComparisonDimension.SECTION_COVERAGE: 0.20,
    ComparisonDimension.NAVIGATION_COMPLETENESS: 0.20,
    # Quality (total: 0.40)
    ComparisonDimension.HEADING_COVERAGE: 0.133,
    ComparisonDimension.PROSE_DENSITY: 0.133,
    ComparisonDimension.AGGREGATION_QUALITY: 0.134,
}
```

**WeightedScore dataclass:**
```python
@dataclass
class WeightedScore:
    raw_score: float
    weighted_score: float
    weight: float
    dimension: str
    delta_type: DeltaType
```

**Anti-inflation calculation:**
```python
def _calculate_weighted_scores(self, dimensions: list[DimensionResult]) -> list[WeightedScore]:
    # Cap raw score influence at 1.0 to prevent domination
    capped_raw = min(dim.score, 1.0)
    weighted_score = capped_raw * weight
```

## Issues

None - 所有 19 个测试通过

## Next Steps

Task 14.3 依赖 Task 14.2，将构建多仓库 benchmark 矩阵与阈值档位。
