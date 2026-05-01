---
agent: Agent_AdapterGovernance
task_ref: Task 11.1
status: Completed
ad_hoc_delegation: false
compatibility_issues: false
important_findings: false
---

# Task Log: Task 11.1 - Hard gate vs soft gate verify redesign

## Summary

成功将 verify 从 soft gate 重新设计为支持 hard/soft gate 分流的验收决策系统。添加了 GateType 枚举、SeverityThreshold 配置类、gate_type 字段到 CheckResult，以及配套的测试覆盖。

## Details

### 1. 新增 GateType 枚举 (`service.py`)

定义了两类门禁类型：
- `HARD`: 结构失败（缺失文件、损坏路径、缺失 section）- 阻塞性，必须修复
- `SOFT`: 质量问题（prose 不足、列表过多、缺少聚合）- 非阻塞，但需改进

### 2. 新增 SeverityThreshold 配置类

可配置的严重性阈值：
- `hard_gate_codes`: 阻塞性错误码集合（默认包含 STRUCT_* 和 CONTENT_EMPTY）
- `soft_gate_codes`: 非阻塞错误码集合（默认包含 CONTENT_TOO_SHORT、CONTENT_LIST_ONLY、AGG_*、ARCH_*）
- `warn_on_soft`: 控制 soft gate 失败是产生 WARN 还是 FAIL
- `fail_on_hard`: 控制 hard gate 失败是否阻塞（默认 True）

### 3. 更新 CheckResult 添加 gate_type 字段

每个 CheckResult 现在包含：
- `gate_type`: HARD 或 SOFT
- `is_hard_gate_failure()`: 是否为阻塞性失败
- `is_soft_gate_failure()`: 是否为非阻塞性失败

### 4. 更新 verify() 方法的 grade 和 exit_code 逻辑

grade 决定逻辑：
- 任何 HARD gate 失败 → FAIL
- SOFT gate 失败且 warn_on_soft=True → WARN
- SOFT gate 失败且 warn_on_soft=False → FAIL
- 仅 warnings → WARN
- 无失败 → PASS

exit_code 决定逻辑：
- 0: PASS（无阻塞问题）
- 1: 存在 HARD gate 失败
- 2: 存在 SOFT gate 失败（当 warn_on_soft=False 时）

### 5. 门禁分类策略

**HARD gate（阻塞性）**:
- STRUCT_SECTION_DIR_MISSING
- STRUCT_MISSING_SECTIONS
- STRUCT_NAVIGATION_BROKEN
- STRUCT_NAV_BAD_DEPTH
- STRUCT_NAV_TARGET_MISSING
- CONTENT_EMPTY（空文件）

**SOFT gate（警告性）**:
- CONTENT_LIST_ONLY
- CONTENT_TOO_SHORT
- CONTENT_MISSING_SECTIONS
- AGG_API_NOT_GROUPED
- AGG_API_ENDPOINT_DUMP
- AGG_DM_NOT_GROUPED
- AGG_DM_MODEL_DUMP
- ARCH_MERMAID_MISSING
- ARCH_MERMAID_INSUFFICIENT
- ARCH_LAYER_EXPLANATION_MISSING

### 6. 新增测试

添加了 14 个新测试覆盖 hard/soft gate 场景：
- test_hard_gate_failure_blocks_acceptance
- test_soft_gate_warning_with_passing_hard_gates
- test_hard_gate_codes_are_correctly_classified
- test_soft_gate_codes_are_correctly_classified
- test_empty_content_is_hard_gate
- test_gate_summary_accurate
- test_custom_severity_thresholds_fail_on_soft
- test_verify_result_includes_gate_type_in_checks
- test_hard_gate_cannot_be_overridden
- test_severity_threshold_is_blocking
- test_gate_type_enum_values

## Output

### Modified Files

- `/repo_wiki/verifier/service.py` - 添加 GateType、SeverityThreshold，重新设计 verify() 的 grade/exit_code 逻辑
- `/tests/test_verifier.py` - 添加 14 个 hard/soft gate 测试，修复 _write_quality_artifacts fixture

### Key Code: GateType Enum

```python
class GateType(Enum):
    """Classification of gate severity for acceptance decisions.

    HARD gate violations are non-recoverable structural failures that MUST be
    fixed before acceptance. SOFT gate violations are quality issues that can
    be addressed later but indicate the output needs improvement.
    """
    HARD = "HARD"   # Structural failures - must fix before acceptance
    SOFT = "SOFT"   # Quality issues - should fix but not blocking
```

### Key Code: SeverityThreshold

```python
class SeverityThreshold:
    def __init__(
        self,
        hard_gate_codes: set[str] | None = None,
        soft_gate_codes: set[str] | None = None,
        warn_on_soft: bool = True,
        fail_on_hard: bool = True,
    ) -> None:
        self.hard_gate_codes = hard_gate_codes or {
            "STRUCT_SECTION_DIR_MISSING",
            "STRUCT_MISSING_SECTIONS",
            "STRUCT_NAVIGATION_BROKEN",
            "STRUCT_NAV_BAD_DEPTH",
            "STRUCT_NAV_TARGET_MISSING",
            "CONTENT_EMPTY",
        }
        self.soft_gate_codes = soft_gate_codes or {
            "CONTENT_LIST_ONLY",
            "CONTENT_TOO_SHORT",
            "CONTENT_MISSING_SECTIONS",
            "AGG_API_NOT_GROUPED",
            "AGG_API_ENDPOINT_DUMP",
            "AGG_DM_NOT_GROUPED",
            "AGG_DM_MODEL_DUMP",
            "ARCH_MERMAID_MISSING",
            "ARCH_MERMAID_INSUFFICIENT",
            "ARCH_LAYER_EXPLANATION_MISSING",
        }
        self.warn_on_soft = warn_on_soft
        self.fail_on_hard = fail_on_hard
```

### Key Code: Updated verify() output

```python
{
    "grade": "FAIL",  # or "WARN" or "PASS"
    "exit_code": 1,    # 0=PASS, 1=HARD fail, 2=SOFT fail
    "checks": [...],
    "summary": {
        "total": 12,
        "pass": 6,
        "warn": 2,
        "fail": 4,
        "hard_gate_failures": 2,
        "soft_gate_failures": 2,
    },
    "hard_gate_codes": ["STRUCT_MISSING_SECTIONS"],
    "soft_gate_codes": ["CONTENT_TOO_SHORT", "ARCH_MERMAID_MISSING"],
    "gate_summary": {
        "hard_gate_blocking": True,
        "soft_gate_warnings": True,
        "acceptance_blocked": True,
    },
}
```

## Issues

None - 所有测试通过

## Next Steps

Task 11.1 完成。Task 11.2 依赖 Task 8.2 和 Task 11.1，将重新设计基线比较器和分数完整性恢复。
