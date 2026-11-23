# 设计：事实源净化与源码优先冲突策略

## 实测结论（决定本任务形状）

任务 1 已证明 `ai/source-of-truth/` 是干净的（`repo-map.yaml` 标 `source_of_truth_status: curated-current`，`primary_language: python`、`framework: typer-cli`；41 个模型、0 污染）。因此 `docs/0*.md` 的污染是**陈旧产物 + 真实代码缺陷**两类，不是扫描器当前输出。

逐项定位（file:line 已核实）：

| 现象 | 真因 | 证据 |
|------|------|------|
| `docs/01-architecture.md:171` 残留 `${incremental_governance}` | 模板变量名与 context 键名不一致：context 提供 `incremental_update_governance`，模板写 `incremental_governance`；`Template.safe_substitute` 静默保留未知占位符 | `repo_wiki/generator/templates.py:24`、`engine.py:2643`、`templates/docs/01-architecture.md.j2` |
| `docs/01-architecture.md:211` 技术栈 Javascript | 陈旧产物。当前 `repo-map.yaml` 已是 python/typer-cli，重生成即修正 | `ai/source-of-truth/repo-map.yaml:4,8` |
| `docs/03-module-map.md` "Handles API routes /path" | 陈旧产物。当前代码与模板中已无此句式（全仓 grep 无命中） | grep `repo_wiki templates plugins scripts` = 0 |
| `docs/05-data-model.md` `in`/`instanceof` 登顶核心实体 | 真实缺陷：`_identify_core_entities` 用 `model.name.lower() in ep_handler` 子串匹配，短名 `in` 命中一切 handler；且 Signal 4 在 endpoint 循环内逐条 append `"API 参数类型"`，理由重复叠加刷分 | `repo_wiki/generator/engine.py:1125-1131` |
| 测试夹具 `dm_sales_facts` 当核心表 | 核心评分未排除 `tests/` 与依赖目录来源的模型 | `engine.py:1076-1135` |
| `required_keys` 形同虚设 | `validate_contract_coverage` 只检查模板文件存在，从不校验 context 是否提供 required_keys；生成文档却宣称"生成前验证 required_keys" | `repo_wiki/generator/contracts.py:388-418`、`engine.py:2313` |
| `architecture.required_keys` 含 `three_layer_diagram`、`layer_descriptions` | 契约声明与实际 context/模板脱节（模板用的是 `three_layer_overview`） | 脚本审计：required_keys_not_in_context=`['layer_descriptions','three_layer_diagram']` |
| 语言/框架可能误判 | `_detect_language` 纯扩展名计数，无包配置优先；`_detect_framework` 把 package.json/pyproject.toml 内容拼接后子串匹配，JS devDependency 里的 express 会给 Python 仓贴 express；typer 不在信号表 | `repo_wiki/scanner/repository_scanner.py:343-376` |

目录剪枝已含 `node_modules`（`repository_scanner.py:248-258`），无需重复实现，只补回归测试。

## 设计决策

### D1：占位符必须失败快，而不是静默保留

`TemplateRenderer.render` 在 `safe_substitute` 后扫描残留 `${...}`，命中即抛 `ValueError` 并列出键名。理由：静默保留会让伪事实进入 READY release，且违反"无证据写待确认"的原则。

同时修正模板键名（`incremental_governance` → `incremental_update_governance`），并把 `architecture.required_keys` 对齐真实模板变量。**两份模板拷贝都要改**：`templates/docs/` 与 `repo_wiki/templates/docs/`（引擎默认 `template_root = root/"templates"`，包内拷贝供安装态使用）。

### D2：required_keys 在渲染前强制校验

`_render_with_cache` 渲染前校验 contract.required_keys ⊆ context.keys()，缺失即抛错。让文档里"契约验证"的说法变成事实。缓存命中路径也要校验，避免旧缓存绕过契约。

### D3：核心实体评分去伪

- 理由去重：同一 reason 只记一次（用有序去重，保持可读顺序）。
- 符号匹配改为词边界匹配（`re.search(rf"\b{re.escape(name)}\b", handler)`），杜绝 `in`/`instanceof` 这类短名子串命中。
- 来源过滤：`file_path` 落在依赖目录（`node_modules`、`.venv`、`dist`、`build`）或 `tests/`、`fixtures` 下的模型不参与核心评分，标注角色（`dependency` / `test-harness`），仍可出现在索引表但不得标 `[核心]`。
- 名称过短（< 3 字符）的模型不得仅凭 API 信号成为核心。

### D4：GEN-001 源码优先（最小可执行版）

优先级：包配置（`pyproject.toml`/`go.mod`/`package.json`+`tsconfig.json`）> 扩展名计数 > README > `repo-wiki.yaml` > 历史 docs。

- `_detect_language`：先看包配置标记，再回落计数。
- `_detect_framework`：按主语言选择对应 manifest 做信号匹配，新增 `typer` 信号；不允许跨语言 manifest 决定框架。
- 冲突可见性：当扫描结论与 curated `repo-map.yaml` 不一致时，保留 curated 值并在 diagnostics 记 `source-conflict`（沿用 `scanner/artifacts.py:252` 的诊断通道），不静默覆盖。

完整的 `stale-doc`/`low-confidence` 标签体系不在本轮扩建：现有 `verifier/service.py:456-495` 已有 `stale-docs` 检查，本轮只补"技术栈与 repo-map 不一致"这一条可执行判据。

### D5：重生成 + 门禁

- 用默认 profile 跑 `repo-wiki generate` 刷新 `docs/0*.md`（qoder-like 走隔离 eval 分支，不写 docs/）。
- verifier 新增 HARD 检查 `unresolved-placeholders`：扫描生成文档中的 `${...}`，命中判 FAIL。
- 不放宽任何既有 strict 阈值。

### D6：生成缓存键必须包含模板内容

`_render_with_cache` 的键是 `stable_hash({"k": prefix, "tpl": template_path, "ctx": context})`（`engine.py:3173`），**只含模板路径不含模板字节**。因此修好模板后，旧缓存仍会返回带 `${incremental_governance}` 的旧渲染结果，修复看起来"无效"。

对策：把模板文件内容哈希纳入缓存键。这样模板变更自动失效，无需手工清缓存，也不会让 required_keys 校验被缓存命中绕过。

## 边界

- 不改 ai-testing；不实现知识卡导出；不动 qoder-like composer 的页面合同（属任务 5）。
- 不重写历史 phase 文档。
- 重生成会改动 `docs/0*.md`、`docs/modules/*`、`docs/sections/*`、`ai/source-of-truth/task-catalog.generated.json`；这些是本仓自生成产物，允许更新。

## 回滚

代码改动集中在 `templates.py`、`contracts.py`、`engine.py`、`repository_scanner.py` 与两份模板；回滚 = revert 提交。重生成产物可用 `git checkout -- docs/` 还原（需先确认无手工编辑）。