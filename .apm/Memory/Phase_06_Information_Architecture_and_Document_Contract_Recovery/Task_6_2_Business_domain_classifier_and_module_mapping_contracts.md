---
agent: Agent_DocGen
task_ref: Task 6.2
status: Completed
ad_hoc_delegation: false
compatibility_issues: false
important_findings: false
---

# Task Log: Task 6.2 - Business-domain classifier and module mapping contracts

## Summary

成功实现业务域分类器，为模块添加 `domain`、`service_family`、`runtime_role` 元数据。分类器使用确定性启发式策略，基于模块路径、导出、接口、数据模型和文件扩展名进行分类。当信号较弱时使用稳定回退策略。

## Details

### 1. 扩展 Module 模型

在 `repo_wiki/core/contracts.py` 中为 `Module` 类新增四个字段：
- `domain: str = "unknown"` - 高级业务域 (如 'core-platform', 'ai-services', 'frontend')
- `service_family: str = "unknown"` - 域内服务族 (如 'python-backend', 'typescript-frontend')
- `runtime_role: str = "unknown"` - 运行时角色 (如 'api-server', 'worker', 'data-pipeline', 'tooling')
- `domain_confidence: float = 0.0` - 分类置信度 0.0-1.0
- `domain_classification_reason: str = ""` - 人类可读的分类原因

### 2. 分类策略实现

在 `repo_wiki/scanner/repository_scanner.py` 中实现三层分类：

**Domain 分类信号** (`_DOMAIN_SIGNALS`):
- `core-platform`: repo_wiki, core, shared, common, base, foundation (confidence 0.8)
- `ai-services`: ai, ml, model, embedding, vector, indexer, retrieval, graph (confidence 0.9)
- `api-gateway`: api, gateway, router, endpoint, route, handler (confidence 0.7)
- `data-pipeline`: pipeline, worker, queue, task, job, batch, stream (confidence 0.7)
- `frontend`: ui, web, client, view, component, pages, static (confidence 0.7)
- `persistence`: db, storage, migration, repository, dal, dao (confidence 0.7)
- `tooling`: scripts, tools, cli, cmd, bin, script (confidence 0.9)
- `testing`: test, spec, mock, fixture, e2e, integration (confidence 0.9)
- `operations`: deploy, ops, monitoring, logging, config, ci, cd (confidence 0.6)

**Service Family 分类信号** (`_SERVICE_FAMILY_SIGNALS`):
- `python-backend`: python, .py, pyproject, poetry, requirements (confidence 0.8)
- `typescript-frontend`: .ts, .tsx, .jsx, package.json, tsconfig (confidence 0.8)
- `golang-service`: .go, go.mod, go.sum (confidence 0.9)
- `jvm-service`: .java, .kt, pom.xml, build.gradle (confidence 0.8)

**Runtime Role 分类信号** (`_RUNTIME_ROLE_SIGNALS`):
- `api-server`: router, endpoint, handler, get, post, put, delete, patch (confidence 0.7)
- `worker`: worker, job, task, queue, background, async (confidence 0.7)
- `data-pipeline`: pipeline, stream, batch, etl, transform (confidence 0.7)
- `data-store`: db, storage, cache, repository, dal, dao (confidence 0.7)
- `tooling`: script, cli, cmd, bin, main (confidence 0.8)
- `test-harness`: test, spec, fixture, mock, assert (confidence 0.8)

### 3. 回退策略

- 当没有匹配信号时，domain 使用 "unknown"，confidence 为 0.1
- 当没有语言信号时，service_family 使用 "unknown"，confidence 为 0.1
- 当没有角色信号时：
  - 如果有 data_models，默认为 "data-store"
  - 如果有 interfaces，默认为 "api-server"
  - 否则默认为 "tooling"

### 4. 分类流程

1. 构建模块文件索引 (包括文件内容和扩展名)
2. 收集所有信号 (path, exports, interfaces, data_models, file_contents, extensions)
3. 调用 `_score_classification` 进行 domain 评分
4. 调用 `_score_service_family` 进行服务族评分
5. 调用 `_score_runtime_role` 进行运行时角色评分
6. 每个评分返回 (classification, confidence, reason)

### 5. 测试覆盖

创建 `tests/test_domain_classifier.py`，包含 8 个测试用例覆盖各种场景。

## Output

### Modified Files

- `/repo_wiki/core/contracts.py` - Module 模型新增域分类字段 (Phase 06 已确认)
- `/repo_wiki/scanner/repository_scanner.py` - 新增域分类逻辑 (`_classify_module_domains`)
- `/repo_wiki/scanner/artifacts.py` - 更新 `write_source_of_truth` 包含新字段，新增诊断报告生成

### New Files

- `/tests/test_domain_classifier.py` - 业务域分类器测试
- `/tests/test_scanner_artifacts.py` - 新增 `test_source_of_truth_includes_domain_classification_metadata` 和 `test_classification_diagnostics_for_mixed_repository`

### Key Changes in artifacts.py

**module-index.yaml 更新:**
```python
module_index = {
    "modules": [
        {
            ...
            # Business domain classification metadata (Phase 06)
            "domain": module.domain,
            "service_family": module.service_family,
            "runtime_role": module.runtime_role,
            "domain_confidence": module.domain_confidence,
            "domain_classification_reason": module.domain_classification_reason,
        }
        for module in snapshot.modules
    ]
}
```

**新增诊断报告:**
- `emit_classification_diagnostics()` - 生成低置信度和回退分类诊断
- `write_diagnostics_report()` - 写入 `classification-diagnostics.json`
- `_get_fallback_suggestion()` - 为回退分类提供改进建议
- 诊断阈值: `domain_confidence < 0.3` 视为低置信度

## Issues

None

## Next Steps

Task 6.3 依赖 Task 6.1 和 Task 6.2。Task 6.3 将重写 `docs/00-overview.md` 合同和生成逻辑，添加固定章节约束和最小 prose 验证。
