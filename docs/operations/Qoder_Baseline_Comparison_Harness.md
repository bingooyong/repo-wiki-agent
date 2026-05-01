# Qoder Baseline Comparison Harness

文档属性：操作指南
目标：为 repo-agent 提供 qoder 风格基线对比工具的使用说明

## 1. 概述

Qoder 基线比较工具（`scripts/qoder_baseline_comparison.py`）用于比较生成的 repo-wiki 输出与 qoder 风格基线仓库的差距，输出机器可读和人类可读的 gap 报告。

## 2. 比较维度

工具对比以下 6 个维度：

| 维度 | 描述 | 关键指标 |
|------|------|----------|
| **Directory Hierarchy** | docs/ 目录结构 | sections/ 存在性、子目录完整性 |
| **Section Coverage** | section 页覆盖率 | 必需 section 页存在性 |
| **Heading Coverage** | overview 文档 heading 模式 | 必需章节标题存在性 |
| **Prose Density** | prose vs list/table 比例 | 最小 prose 字符数、最大列表比例 |
| **Navigation Completeness** | 文档间导航链接完整性 | section 页到 overview 链接、内部链接数 |
| **Aggregation Quality** | API/DataModel 聚合质量 | 原始端点/模型数、分组结构存在性 |

## 3. 使用方法

### 3.1 基本用法

```bash
python scripts/qoder_baseline_comparison.py \
    --target /path/to/generated/output \
    --baseline /path/to/qoder/baseline \
    --output /path/to/gap-report.json \
    --format both
```

### 3.2 仅输出 JSON

```bash
python scripts/qoder_baseline_comparison.py \
    --target ./docs \
    --baseline /Users/bingooyong/Code/01Code/github.com/bingooyong/AI_API_Atlas \
    --output ./gap-report.json \
    --format json
```

### 3.3 仅输出 Markdown

```bash
python scripts/qoder_baseline_comparison.py \
    --target ./docs \
    --baseline /Users/bingooyong/Code/01Code/github.com/bingooyong/AI_API_Atlas \
    --output ./gap-report.md \
    --format markdown
```

## 4. 输出格式

### 4.1 JSON 格式

```json
{
  "target_root": "/path/to/target",
  "baseline_root": "/path/to/baseline",
  "dimensions": [
    {
      "dimension": "directory_hierarchy",
      "status": "PARTIAL",
      "score": 0.65,
      "gaps": [
        {
          "dimension": "directory_hierarchy",
          "severity": "CRITICAL",
          "description": "docs/sections/ directory missing",
          "target_path": "/path/to/target/docs/sections",
          "recommendation": "Create docs/sections/ with topic-based section pages"
        }
      ],
      "metrics": {}
    }
  ],
  "summary": {
    "generated_at": "2026-04-18",
    "total_gaps": 8,
    "critical_gaps": 2,
    "major_gaps": 5,
    "minor_gaps": 1,
    "overall_score": 0.55,
    "passed_dimensions": 1,
    "failed_dimensions": 3,
    "partial_dimensions": 2
  }
}
```

### 4.2 Markdown 格式

报告包含：
- 执行摘要（Overall Score, Total Gaps, Critical/Major Issues）
- 每个维度的状态和评分
- Gap 列表及修复建议
- 详细 Gap 说明

## 5. Gap 严重级别

| 级别 | 说明 | 典型原因 |
|------|------|----------|
| **CRITICAL** | 核心结构缺失 | 缺少 docs/sections/、缺少必需 section 页 |
| **MAJOR** | 重要内容缺失 | 缺少 prose、缺少聚合结构、缺少导航链接 |
| **MINOR** | 质量改进建议 | 导航链接数量不足 |
| **INFO** | 仅供参考 | 基准对比信息 |

## 6. 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 通过（overall_score >= 0.5, 无 critical gaps）|
| 1 | 有 critical gaps |
| 2 | major gaps 较多（overall_score < 0.5）|

## 7. 在治理审查中的使用

### 7.1 本地运行

```bash
# 1. 生成 repo-wiki 输出
cd /path/to/your/repository
repo-wiki generate

# 2. 运行基线比较
python /path/to/repo-agent/scripts/qoder_baseline_comparison.py \
    --target ./docs \
    --baseline /Users/bingooyong/Code/01Code/github.com/bingooyong/AI_API_Atlas \
    --output ./qoder-gap-report.json

# 3. 查看结果
cat ./qoder-gap-report.json | jq '.summary'
```

### 7.2 解读报告

**总体评分解释：**
- 0.8-1.0：接近 qoder 风格，无需重大修改
- 0.5-0.8：有改进空间，需要处理 major gaps
- 0.0-0.5：与 qoder 风格差距较大，需要重大重构

**维度评分解释：**
- PASS：达到 qoder 风格标准
- PARTIAL：部分达标，需要改进
- FAIL：严重偏离 qoder 风格

### 7.3 典型 Gap 解释

**"docs/sections/ directory missing"**
- 这是 CRITICAL gap，表示缺少专题层
- 需要创建 `docs/sections/` 目录和必需的 section 页

**"Missing required sections: project, architecture, ..."**
- 这是 MAJOR gap，表示专题页不完整
- 需要创建缺失的 section 页

**"Overview docs have insufficient prose (150 < 500 chars)"**
- 这是 MAJOR gap，表示总览文档缺少叙述性内容
- 需要在总览文档中添加更多文字说明

**"API contracts has 120 raw endpoints (should be aggregated)"**
- 这是 MAJOR gap，表示 API 文档是端点倾倒
- 需要按服务族/认证方式重新组织 API 文档

## 8. 与 verify --ci 的区别

| 特性 | `verify --ci` | `qoder_baseline_comparison.py` |
|------|---------------|-------------------------------|
| **目的** | 内容质量门禁 | 与 qoder 风格对比 |
| **输入** | 单个仓库 | 两个仓库对比 |
| **输出** | PASS/FAIL + reason codes | Gap report + scores |
| **对比基准** | 固定规则 | qoder 风格基线仓库 |
| **适用场景** | CI/CD 门禁 | 治理审查、回归测试 |

## 9. 集成到工作流

### 9.1 生成后检查

```bash
# 生成输出
repo-wiki generate --target /path/to/output

# 运行质量门禁
repo-wiki verify --ci --target /path/to/output

# 运行 qoder 基线比较
python scripts/qoder_baseline_comparison.py \
    --target /path/to/output/docs \
    --baseline /Users/bingooyong/Code/01Code/github.com/bingooyong/AI_API_Atlas \
    --output /path/to/output/qoder-gap-report.json
```

### 9.2 治理审查

在治理审查会议中：
1. 查看 `qoder-gap-report.json` 的 summary 部分
2. 关注 critical 和 major gaps
3. 根据 recommendation 列制定修复计划
4. 在下一轮迭代中修复 gaps

## 10. 故障排除

**"Target path does not exist"**
- 确保 `repo-wiki generate` 已成功执行
- 检查 `--target` 路径是否正确

**"Baseline path does not exist"**
- 确保 qoder 基线仓库路径正确
- 基线仓库通常使用 `AI_API_Atlas`

**"Permission denied"**
- 确保有读取目标路径的权限
- 检查文件是否被其他进程占用

## 11. 高级用法

### 11.1 自定义基线

可以使用其他 qoder 风格仓库作为基线：

```bash
python scripts/qoder_baseline_comparison.py \
    --target /path/to/your/output \
    --baseline /path/to/another/qoder-style/repo \
    --output /path/to/gap-report.json
```

### 11.2 增量监控

可以将 gap report 提交到版本控制，监控每次生成的质量变化：

```bash
# 提交 gap report
git add qoder-gap-report.json
git commit -m "docs: qoder baseline gap report $(date +%Y-%m-%d)"
```
