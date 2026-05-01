# Repo-Wiki Phase 06-08 Review

文档属性：阶段评审  
评审范围：`Phase 06` - `Phase 08`  
评审目标：判断 repo-agent 当前路线是否足以替代 qoder 的 repo-wiki 能力

## 结论摘要

结论先说清楚：`Phase 06-08` 的方向是对的，但当前不能视为“已达到可替代 qoder”的阶段闭环。

- `Phase 06`：方向正确，但 contract 仍不完整，且内部治理层和目标仓库输出层发生了混用。
- `Phase 07`：名义上进入了“领域聚合文档”，实际上 API、Data Model、Section 页仍大量停留在“重排后的清单导出”。
- `Phase 08`：已经把质量门禁纳入治理，但验收工具本身还有口径偏差，导致“真实差距”和“测量噪声”混在一起。

因此，当前更准确的判断不是“Phase 06-08 失败”，而是：

- 这三个 Phase 已经把方向从“导出器”拉向“文档中心”。
- 但它们还没有把 repo-agent 从“可生成知识底座”推进到“可稳定替代 qoder repo-wiki 产品体验”。

## 阶段判定表

| Phase | 设计方向 | 实现完成度 | 阶段结论 | 主要原因 |
|------|------|------|------|------|
| Phase 06 | 正确 | 部分完成 | `Conditional Pass` | 建立了 section/phase/document-center contract，但 phase contract 覆盖不完整，且 phase 文档被错误地下沉到目标仓库生成层 |
| Phase 07 | 正确 | 未达标 | `Fail to Exit` | 模块地图有进展，但 API/Data Model/Section 页仍偏枚举式输出，不是 qoder 风格的聚合阅读中心 |
| Phase 08 | 正确 | 部分完成 | `Fail to Exit` | verify 已升级，但 baseline comparator 仍存在评分口径问题，不能直接作为最终替代性判断依据 |

## 已验证事实

### 1. Phase 06 只完成了 contract 的一半

`DocumentLayer`、`SECTION_DEFINITIONS`、`PHASE_DEFINITIONS` 已经把输出层拆成 overview、section、module、phase 四层，这是正确方向。  
但 `PHASE_DEFINITIONS` 只定义到 `phase-06-architecture`，并没有把已经进入实施计划的 `Phase 07`、`Phase 08` 纳入生成 contract，因此 contract 覆盖和计划本身不一致。【[contracts.py](/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/repo_wiki/generator/contracts.py:129)】【[contracts.py](/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/repo_wiki/generator/contracts.py:180)】

更关键的是，生成引擎会在目标仓库执行时直接生成 `docs/phases/<phase>.md`。这意味着 repo-agent 自身的治理文档层被混入了被分析仓库的知识库输出层，边界不清晰。【[engine.py](/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/repo_wiki/generator/engine.py:116)】【[engine.py](/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/repo_wiki/generator/engine.py:1116)】

### 2. Phase 07 的“聚合”多数仍然是清单式改写

模块地图已经具备域、服务族、运行时角色的组织骨架，这部分是 Phase 07 最接近目标的实现。  
但 API 文档仍然按模块遍历所有 endpoint，`关键入口 API` 也直接枚举所有 endpoint；这不是真正的摘要或聚合，只是把原始清单换了位置。【[engine.py](/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/repo_wiki/generator/engine.py:529)】【[engine.py](/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/repo_wiki/generator/engine.py:591)】【[04-api-contracts.md.j2](/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/templates/docs/04-api-contracts.md.j2:5)】

Data Model 文档同样存在类似问题。当前实现只是把模型拆成 core/service 两类，再继续列出模型和文件路径；迁移策略也是模板化叙述，不是从目标仓库真实数据库结构和迁移机制中归纳出来的摘要。【[engine.py](/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/repo_wiki/generator/engine.py:624)】【[engine.py](/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/repo_wiki/generator/engine.py:686)】

Section 页也还停留在“专题索引页”而不是“专题文档页”。模板本身过于通用，默认结构仍是 `Section Content`、模块列表、API 端点、相关命令，缺少 qoder 风格那种以 prose 为主、以导航为骨架的专题页组织方式。【[section.md.j2](/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/templates/docs/section.md.j2:1)】

### 3. 导航路径 contract 还不稳定，verify 也没有真正兜住

`00-overview.md` 的阅读导航写成了 `../../docs/sections/...`。从 `docs/00-overview.md` 出发，这个相对路径是错误的。  
`03-module-map.md`、`04-api-contracts.md` 等模板里也存在同类问题，把 `docs/` 再次写进了相对路径中。【[engine.py](/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/repo_wiki/generator/engine.py:243)】【[03-module-map.md.j2](/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/templates/docs/03-module-map.md.j2:31)】【[04-api-contracts.md.j2](/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/templates/docs/04-api-contracts.md.j2:41)】

与此同时，`VerifierService` 的导航校验只严格检查 section 页，而且 overview 页只做了“是否包含 `sections/` 字样”的软判断。更糟的是，section 页只要出现任意 `../`，就可能被当作存在 overview link。  
这意味着当前 verify 能挡住“缺文件”，但还挡不住“路径写错”。【[service.py](/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/repo_wiki/verifier/service.py:716)】【[service.py](/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/repo_wiki/verifier/service.py:738)】【[service.py](/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/repo_wiki/verifier/service.py:748)】

### 4. Phase 08 的 baseline comparator 还不能直接承担“替代性判决”

对比脚本已经定义了 6 个维度，这是正确方向。  
但它仍然把 canonical section slug、overview heading、最小 prose 阈值直接硬编码成“qoder 基线”，而不是从真实 baseline 中提取“硬性结构项”和“参考质量项”。【[qoder_baseline_comparison.py](/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/scripts/qoder_baseline_comparison.py:51)】【[qoder_baseline_comparison.py](/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/scripts/qoder_baseline_comparison.py:57)】

更严重的是，目录结构评分只比较 `_get_docs_structure()` 返回字典的键集合。由于这个结构对象固定只有 `exists/subdirs/overview_files` 三个键，目录层级维度很容易被错误打满分，不能真实反映文档中心结构差异。【[qoder_baseline_comparison.py](/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/scripts/qoder_baseline_comparison.py:271)】【[qoder_baseline_comparison.py](/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/scripts/qoder_baseline_comparison.py:289)】

heading coverage 也混入了 baseline 文件自己的 heading 结果，导致“目标没有、baseline 也没有”的情况才被记为缺失，这不适合作为稳定治理标准。【[qoder_baseline_comparison.py](/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/scripts/qoder_baseline_comparison.py:400)】【[qoder_baseline_comparison.py](/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/scripts/qoder_baseline_comparison.py:409)】

### 5. 当前验收报告可以说明“还不能替代”，但不能精确说明“差多少”

`AI_API_Atlas` 的 readiness report 明确给出了 `verify --ci = FAIL`，并指出 overview、architecture、sections、API、Data Model 五类问题都未闭环，这个结论是可信的。  
但报告中的 `49.3%` 只能作为粗信号，不能作为精确的产品完成度分数。【[AI_API_Atlas_Readiness_Report.md](/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/docs/operations/AI_API_Atlas_Readiness_Report.md:9)】【[AI_API_Atlas_Readiness_Report.md](/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/docs/operations/AI_API_Atlas_Readiness_Report.md:22)】【[AI_API_Atlas_Readiness_Report.md](/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/docs/operations/AI_API_Atlas_Readiness_Report.md:60)】

## 关键评审意见

### P0. 当前 repo-agent 还不能宣称“可替代 qoder repo-wiki”

这个结论不是因为缺 SQLite、缺 FTS 或缺生成流程，而是因为“文档中心体验层”还没有做成。

repo-agent 现在已经具备：

- 本地扫描、source-of-truth、SQLite/Chroma/graph 这些底座能力。
- overview/module/API/data-model/section 这些文档类型。
- verify 和 baseline compare 的初版治理框架。

repo-agent 现在还缺：

- 稳定的 canonical section 层和正确的路径 contract。
- 真正的 prose-first 页面生成，而不是模板化通用描述。
- 基于真实仓库事实的 API/Data Model 聚合摘要。
- 可以被信任的对比与验收量化方法。

### P0. Phase 06-08 不应该继续直接顺延为“更多模板迭代”

下一轮不应该只继续补文案或多写几个模板。  
当前更缺的是“契约边界、导航图、评测口径、运行时事实提炼”四件事。

如果沿用现在的输出模型继续追加模板，大概率会得到：

- 更多 markdown 文件；
- 更复杂但仍不可靠的 verify 规则；
- 看起来更像文档中心，但仍然无法稳定替代 qoder。

### P1. 需要把“内部治理文档”和“目标仓库知识库”彻底分层

`docs/phases/` 在 repo-agent 自己仓库里是合理的。  
但它不应该默认作为目标仓库知识库的一部分被生成。否则使用 repo-agent 生成出的 wiki，会夹带 repo-agent 自己的工程治理结构。

### P1. SQLite 下一步不是“要不要用”，而是“怎么把它从状态库升级成文档中心运行时”

qoder 大量使用 SQLite，不是因为它想做数据库，而是因为它需要：

- 本地状态与增量更新；
- 内容分块与 FTS；
- 文档质量证据缓存；
- 生成摘要缓存；
- 验收与比较结果落盘。

repo-agent 也应该沿这个方向规划，而不是把 SQLite 只看作 Phase 02 的实现细节。

## Manager 决策建议

建议对当前 Phase 06-08 做如下处理：

1. `Phase 06` 标记为“方向通过，需补 contract 边界修复”。
2. `Phase 07` 不允许退出，直到 API/Data Model/Section 页摆脱清单式输出。
3. `Phase 08` 不允许退出，直到 comparator 评分口径和 acceptance harness 可被信任。
4. 不建议现在就把 repo-agent 对外宣传为 qoder repo-wiki 替代品。
5. 建议立即进入新的后续 Phase，先修输出模型与评测口径，再做更深的生成质量升级。

## 评审后的下一步

后续 Phase 规划已单独写入路线图文档，供继续拆 APM 任务使用：【[repo-wiki-phase-09-12-roadmap.md](/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/docs/repo-wiki-phase-09-12-roadmap.md)】
