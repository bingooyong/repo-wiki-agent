# External Fixture Provenance and Benchmark Refresh Policy

**文档属性**: 运营策略
**版本**: 1.0
**日期**: 2026-04-26
**Agent**: Agent_QualityRelease
**阶段**: Phase 20 Task 20.1

## 1. 背景

Phase 20 需要对外部 qoder baseline fixture 建立明确的 provenance（来源）、freshness（新鲜度）和 confidence（置信度）规则。这是 release-candidate 比较的前提条件 —— 如果 fixture 本身不可信或不新鲜，比较结果就无意义。

## 2. Fixture 来源规范

### 2.1 接受的 Fixture 来源

| 来源类型 | 说明 | 可接受性 |
|---------|------|----------|
| `qoder-style/` 目录 | 预先生成的 qoder 风格快照 | 需验证 |
| AI_API_Atlas 基准仓 | 已知高质量的参考仓库 | 首选 |
| 手动导出的快照 | 用户提供的 fixture | 需审查 |

### 2.2 必需 Capture 元数据

每个 fixture 必须包含 `fixture_metadata.json`，包含以下字段：

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `schema_version` | string | 是 | 当前支持 1.0, 1.1 |
| `repository_name` | string | 是 | 来源仓库名 |
| `repository_type` | string | 是 | 语言/类型如 python, go |
| `generated_at` | ISO timestamp | 是 | 生成时间，用于 freshness 计算 |
| `generator_version` | string | 是 | 生成器版本 |
| `language` | string | 否 | 编程语言 |
| `complexity_score` | float | 否 | 复杂度评分 0.0-1.0 |
| `size_category` | string | 否 | small/medium/large/xlarge |

## 3. Freshness 规则

### 3.1 按 Profile 的最大年龄

| Profile | 最大允许年龄 | 状态 |
|---------|-------------|------|
| strict | 7 天 | fresh |
| transitional | 30 天 | fresh |
| pilot | 90 天 | fresh |

### 3.2 Freshness 状态定义

```
fresh     : Age <= MAX_FIXTURE_AGE[profile]  → 可直接使用
stale     : Age <= 2 * MAX_FIXTURE_AGE[profile]  → 可用但有警告
critical  : Age > 2 * MAX_FIXTURE_AGE[profile]  → 必须拒绝
```

### 3.3 Freshness Score 计算

```
Age = 0 days          → Score 1.0
Age = MAX_AGE         → Score 0.7
Age = 2 * MAX_AGE     → Score 0.4
Age > 2 * MAX_AGE     → Score 0.0
```

## 4. Confidence Scoring

### 4.1 Confidence Score 组成

| 组成部分 | 权重 | 说明 |
|---------|------|------|
| Schema validity | 30% | fixture 状态 VALID=0.3, PARTIAL=0.15, INVALID=0.0 |
| Structural completeness | 30% | 基于 diagnostics，错误越少分数越高 |
| Freshness | 40% | Freshness Score |

### 4.2 Confidence Level 阈值

| Level | 阈值 | 说明 |
|-------|------|------|
| high | >= 0.90 | 满足 strict profile |
| medium | >= 0.70 | 满足 transitional profile |
| low | >= 0.50 | 满足 pilot profile |
| unacceptable | < 0.50 | 不满足任何 profile |

### 4.3 Release Gate 决策

```python
decision = get_release_gate_decision(manifest, profile)

# decision 包含:
# - decision: "APPROVED" / "REJECTED"
# - confidence_score: 0.0-1.0
# - confidence_level: "high"/"medium"/"low"/"unacceptable"
# - freshness_status: "fresh"/"stale"/"critical"
# - age_days: 实际天数
# - is_approved: bool
# - rejection_reasons: [list of reasons if rejected]
```

Profile 最小 confidence 要求:
- strict: >= 0.90
- transitional: >= 0.70
- pilot: >= 0.50

## 5. Fixture Refresh 工作流

### 5.1 刷新触发条件

| 条件 | 动作 |
|------|------|
| Age > MAX_FIXTURE_AGE[profile] | 标记为 stale，生成警告 |
| Age > 2 * MAX_FIXTURE_AGE[profile] | 标记为 critical，必须刷新 |
| Confidence < profile threshold | 拒绝使用，要求刷新 |
| Compare 结果显示 regression | 检查 fixture 是否过时 |

### 5.2 刷新步骤

1. **识别需要刷新**: `python scripts/qoder_fixture_ingestion.py --fixture /path --check-confidence --profile strict`
2. **生成新快照**: 运行生成器获取新的 qoder-style 快照
3. **验证新 fixture**: 确认新 fixture 满足 schema 和 freshness 要求
4. **更新引用**: 将比较命令中的 baseline 路径更新到新 fixture
5. **归档旧 fixture**: 将旧 fixture 移动到 `.repo-agent-eval/archived/` 目录

### 5.3 Maintainer 检查清单

```
[ ] 确认 fixture_metadata.json 存在且包含所有必需字段
[ ] 运行 --check-confidence 确认 confidence >= threshold
[ ] 检查 freshness_status 不是 "critical"
[ ] 确认生成的快照结构完整 (docs/00-overview.md, docs/01-architecture.md, docs/sections/*)
[ ] 运行 compare 命令验证 fixture 可用于比较
[ ] 更新 baseline 路径到新 fixture
```

## 6. 拒绝 Stale/Incomplete Fixtures

### 6.1 Release Gate 拒绝条件

以下情况 fixture 必须被拒绝用于 release gate 比较：

1. **INVALID 状态**: fixture_schema_validator 返回 INVALID
2. **Critical Freshness**: Age > 2 * MAX_FIXTURE_AGE[profile]
3. **Unacceptable Confidence**: confidence_score < 0.50
4. **Profile Threshold 未达标**: confidence < profile 最低要求

### 6.2 使用示例

```bash
# 检查 fixture 是否可用于 strict profile
python scripts/qoder_fixture_ingestion.py \
    --fixture /path/to/qoder_snapshot \
    --check-confidence \
    --profile strict

# 退出码 0 = APPROVED, 1 = REJECTED

# 检查 transitional profile
python scripts/qoder_fixture_ingestion.py \
    --fixture /path/to/qoder_snapshot \
    --check-confidence \
    --profile transitional
```

## 7. 与 compare 命令集成

Release-candidate 比较前应先验证 fixture:

```python
# 在 compare 之前先验证 fixture
from scripts.qoder_fixture_ingestion import (
    FixtureIngestion, ConfidenceScorer
)

fixture_root = Path("/path/to/baseline")
ingestion = FixtureIngestion(fixture_root)
manifest = ingestion.ingest()

decision = ConfidenceScorer.get_release_gate_decision(manifest, "transitional")
if not decision["is_approved"]:
    raise RuntimeError(
        f"Baseline fixture not approved for release: "
        f"{decision['rejection_reasons']}"
    )

# 继续 compare...
```

## 8. 相关文件

- `scripts/qoder_fixture_ingestion.py` - 实现 FreshnessValidator 和 ConfidenceScorer
- `tests/test_fixture_ingestion.py` - 测试覆盖
- `docs/operations/replacement-gate-policy.md` - 门禁策略
- `docs/operations/policy-profiles.yaml` - Profile 配置

## 9. 下一步

Task 20.2 将使用此 provenance 和 freshness 规则运行 release-candidate pilot。