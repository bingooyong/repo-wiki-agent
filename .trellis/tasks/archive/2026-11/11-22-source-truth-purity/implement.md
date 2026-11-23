# 执行计划：source-truth-purity

## 顺序（每步完成后跑对应测试）

1. [x] 模板键名修正：`templates/docs/01-architecture.md.j2` 与 `repo_wiki/templates/docs/01-architecture.md.j2` 的 `${incremental_governance}` → `${incremental_update_governance}`。
2. [x] 契约对齐：`repo_wiki/generator/contracts.py` 中 `architecture.required_keys` 去掉 `three_layer_diagram`、`layer_descriptions`，改为模板实际使用的键。
3. [x] 渲染守卫：`repo_wiki/generator/templates.py` 在 `safe_substitute` 后检测残留 `${...}` 并抛 `ValueError`（列出键名）。
4. [x] required_keys 强制：`repo_wiki/generator/engine.py` 的 `_render_with_cache` 渲染前校验 contract 必需键，缓存命中路径同样校验。
5. [x] 核心评分去伪：`engine.py` `DataModelAggregator._identify_core_entities`（约 1076-1135 行）实现理由去重、词边界匹配、依赖/测试来源排除、短名保护。
6. [x] 源码优先探测：`repo_wiki/scanner/repository_scanner.py` `_detect_language`（343-356）与 `_detect_framework`（358-376）按包配置优先，新增 typer 信号，禁止跨语言 manifest 决定框架。
7. [x] 冲突诊断：扫描结论与 curated `repo-map.yaml` 不一致时记 `source-conflict`，沿用 `scanner/artifacts.py` 诊断通道。
8. [x] verifier 新增 HARD 检查 `unresolved-placeholders`。
9. [x] 合同测试（新文件 `tests/test_source_truth_purity.py`）：
   - 模板/context 键审计：所有 CORE 契约无未知占位符、required_keys ⊆ context；
   - 负例：`in`/`instanceof`（node_modules 来源）与 `dm_sales_facts`（tests 来源）不得判为核心；
   - 理由去重：多 endpoint 命中只产生一条 "API 参数类型"；
   - 占位符守卫：缺键渲染必须抛错；
   - 探测：Python 仓带 express devDependency 的 package.json 不得判为 express；有 pyproject.toml 必须判 python。
10. [x] 重生成：`repo-wiki generate`（默认 profile）刷新 `docs/0*.md`，确认污染与错误技术栈消失。
11. [x] 全链路验证并归档证据。
    - 证据：purity 21 passed；子集 437 passed；全量 2318（2308 pass / 6 skip / 4 fail，4 个失败均在 base 665408a worktree 复现，属预存）；默认 `verify --ci` WARN、exit 0、0 hard fail、`unresolved-placeholders` PASS（runtime evidence run_id `verify-1795360062648-e4d0899a`）；qoder-like verify FAIL（15 hard，与 base 代码对同一 verify_root 的结果完全一致，根因是无 READY release，属 G11/task 6 范围）。验收 grep 全部无命中。

## 验证命令

```bash
.venv/bin/python -m pytest tests/test_source_truth_purity.py -q
.venv/bin/python -m pytest tests -q -k "generator or scanner or contract or verifier or template"
.venv/bin/python -m repo_wiki.main generate
grep -R "node_modules" ai/source-of-truth/            # 必须无命中
grep -n '\${' docs/01-architecture.md                  # 必须无命中
grep -n "Handles API routes\|Handles models" docs/03-module-map.md   # 必须无命中
grep -n "Javascript\|Express" docs/01-architecture.md  # 必须无命中
.venv/bin/python -m repo_wiki.main verify --profile qoder-like --ci --output .repo-agent-eval
```

## 评审门

- 重生成后 `docs/01-architecture.md` 技术栈为 Python / typer-cli，与 `pyproject.toml` 一致。
- `docs/05-data-model.md` 核心实体不含依赖目录与测试夹具来源。
- 新增占位符检查能对人工注入的 `${foo}` 判 FAIL（负例验证）。
- 既有 strict 阈值未被放宽；默认 `verify --ci` 零 hard 失败。qoder-like 全链路验收已移交任务 6（本仓无 READY release，base commit 同样失败）。

## 回滚点

步骤 1-8 为代码改动，可单独 revert；步骤 10 的重生成产物在确认无手工编辑后可用 git 还原。