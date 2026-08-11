# External Fixture Provenance and Benchmark Refresh Policy

**文档属性**: 运营策略
**版本**: 1.2
**日期**: 2026-07-14
**Agent**: release-maintainers
**阶段**: Phase 20 Task 20.1

## 1. 背景

Phase 20 需要对外部 qoder baseline fixture 建立明确的 provenance（来源）、freshness（新鲜度）和 confidence（置信度）规则。这是 release-candidate 比较的前提条件 —— 如果 fixture 本身不可信或不新鲜，比较结果就无意义。

## 2. Fixture 来源规范

### 2.1 接受的 Fixture 来源

| 来源类型 | 说明 | 可接受性 |
|---------|------|----------|
| `qoder-style/` 目录 | 预先生成的 qoder 风格快照 | 需验证 |
| reference-repo 基准仓 | 已知高质量的参考仓库 | 首选 |
| 手动导出的快照 | 用户提供的 fixture | 需审查 |

### 2.2 必需 Capture 元数据

每个 fixture 必须包含 `fixture_metadata.json`，包含以下字段：

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `schema_version` | string | Gate 必需 | 当前支持 1.0、1.1；旧 fixture 缺失时告警导入 |
| `contract_version` | string | Gate 必需 | 当前支持 `qoder.fixture_provenance/1.1`；旧 fixture 缺失时告警导入 |
| `repository_name` | string | 是 | 来源仓库名 |
| `repository_type` | string | 是 | 语言/类型如 python, go |
| `source` | string | Gate 必需 | fixture 来源标识；旧 fixture 缺失时导入告警，门禁拒绝 |
| `generated_at` | ISO timestamp | Gate 必需 | 必须是带时区、可解析的 ISO 时间，用于 freshness 计算 |
| `generator_version` / `generator` | string | Gate 必需 | 生成器版本；`generator` 是导出契约字段，兼容读取 `generator_version` |
| `fixture_hash` | string | 导出必需 | 稳定 fixture hash；由内容 hash 与结构 hash 计算 |
| `hash_algorithm` | string | 建议 | 当前为 `qoder.fixture_hash/2`；声明后必须受支持 |
| `language` | string | 否 | 编程语言 |
| `complexity_score` | float | 否 | 复杂度评分 0.0-1.0 |
| `size_category` | string | 否 | small/medium/large/xlarge |

导入工具导出的 manifest 包含：

- `schema_version`: `qoder.fixture_manifest/1.1`
- `contract_version`: `qoder.fixture_provenance/1.1`
- `fixture_hash`: 基于相对 POSIX 路径、Markdown 原始 bytes 与文件结构计算的稳定 hash
- `hash_algorithm`: `qoder.fixture_hash/2`
- `provenance`: `schema_version`、`contract_version`、`source`、`generator`、`generated_at`、`fixture_hash`

旧版 metadata 缺少 provenance 字段时仍可导入，状态为 `PARTIAL` 并产生 warning；release gate 必须拒绝，benchmark 必须标记为 `non_gating`。字段已存在但类型错误、`generated_at` 不可解析、schema 或 contract version 不受支持时，fixture 状态为 `INVALID`，不能作为门禁证据。`metadata.generator` 无效时不得覆盖有效的 `generator_version`，但该类型错误仍会导致门禁拒绝。

### 2.3 Fixture Hash 稳定性

Hash 不包含 fixture 根目录绝对路径。所有相对路径先转换为 POSIX `/` 分隔形式，再按相对路径排序：

1. `content_hash` 对每个 Markdown 文件依次写入域标签、路径 byte 长度、路径 UTF-8 bytes、内容 byte 长度和原始内容 bytes。
2. `structure_hash` 对 fixture 内每个文件依次写入域标签、记录类型、相对路径 byte 长度和路径 UTF-8 bytes。
3. `fixture_hash` 对 `content_hash` 与 `structure_hash` 使用独立域标签和长度 framing 后再计算 SHA-256。

长度 framing 消除 `ab` + `c` 与 `a` + `bc` 这类拼接边界歧义。相同相对内容树位于不同根目录时 hash 相同；任一 Markdown 内容或相对路径变化时 hash 必须变化。POSIX 路径规范保证 Windows、macOS 和 Linux 使用相同的结构输入。

metadata 可以声明 `fixture_hash` 和 `hash_algorithm`。声明值必须是有效类型和受支持算法，声明 hash 必须与本地计算结果一致；不一致时 ingestion release gate 拒绝，benchmark 标记为 `non_gating`。旧 metadata 未声明这两个字段时仍使用本地计算的 `qoder.fixture_hash/2` 结果。

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
5. **Provenance 不完整**: 缺少 `schema_version`、`contract_version`、`source`、`generator`、`generated_at`、稳定 `fixture_hash` 或 markdown 样本
6. **Provenance 无效**: 字段不是非空字符串、时间不可解析、schema/contract version 不受支持或声明 hash 与计算 hash 不一致

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

## 8. Benchmark Matrix 契约

`scripts/qoder_benchmark_matrix.py` 导出：

- `schema_version`: `qoder.benchmark_matrix/1.1`
- `contract_version`: `qoder.benchmark_contract/1.1`
- `baseline_provenance`: baseline 的来源、生成器、生成时间、稳定 hash、样本数和缺失字段
- `results[].provenance`: baseline 与样本两侧 provenance
- 顶层 `gating_status`: 整个 matrix 是 `gating` 或 `non_gating`
- 顶层 `non_gating_reasons`: baseline、profile、重复样本或样本不足的完整原因，消费者不得仅检查单条 result
- `results[].threshold_profile.sample_count`: 当前 profile 中 provenance 合格、按 `fixture_hash` 去重后的独立样本数
- `results[].threshold_profile.observed_sample_count`: 当前 profile 实际观察到的结果条数
- `threshold_profiles[].sample_count`: 与 result 相同的独立门禁样本数
- `threshold_profiles[].observed_sample_count`: profile 实际观察到的结果条数
- `threshold_profiles[].calibration_data`: provenance 合格样本数、重复样本数、重复 hash 和最小门槛
- `results[].gating_status` / `threshold_profiles[].gating_status`: 对应证据是否可用于门禁
- `results[].non_gating_reasons` / `threshold_profiles[].non_gating_reasons`: baseline/sample provenance 缺口、无效值、hash 不一致、重复或不足样本
- `drift_analysis` / `results[].drift_evidence` / `threshold_profiles[].drift_evidence`: drift 诊断及证据范围

`sample_count` 不等于结果条数。只有 sample provenance 合格、计算 hash 与 metadata 声明不冲突的样本才能计入，并至少按 `fixture_hash` 去重。重复 hash 会写入 profile 原因；无效样本不会增加 `sample_count`。baseline provenance 缺口同样会阻断 profile 和 matrix 门禁，即使 sample 侧独立样本数已达到最低要求。

Drift 可保留诊断价值，但每份 drift evidence 必须同时导出：

- `evidence.observed_sample_count`: 诊断中观察到的结果数
- `evidence.gating_sample_count`: provenance 合格并去重后的独立样本数
- `evidence.evidence_scope`: `gating` 或 `observed_diagnostic`
- `gating_status`、`non_gating_reasons` 和 `diagnostic_only`
- `observed_analysis`: 所有观察结果的诊断
- `gating_analysis`: 仅在证据可门禁时提供，否则为 `null`

Benchmark 不直接拒绝比较运行。当 baseline 或 sample provenance 缺失/无效、markdown 样本缺失、hash 不一致、profile 存在重复 fixture、独立样本数低于最低门槛，或 matrix 没有样本时，对应结果、profile 和 matrix 标记为 `non_gating`，`passed_thresholds` 为 `false`。这保留诊断价值，同时阻止 non-gating 样本伪装成门禁漂移证据。

## 9. 相关文件

- `scripts/qoder_fixture_ingestion.py` - 实现 FreshnessValidator 和 ConfidenceScorer
- `scripts/qoder_benchmark_matrix.py` - 导出 benchmark contract、profile sample_count、drift evidence 和 non-gating 状态
- `tests/test_fixture_ingestion.py` - 测试覆盖
- `docs/operations/replacement-gate-policy.md` - 门禁策略
- `docs/operations/policy-profiles.yaml` - Profile 配置

## 10. 下一步

Task 20.2 将使用此 provenance 和 freshness 规则运行 release-candidate pilot。
