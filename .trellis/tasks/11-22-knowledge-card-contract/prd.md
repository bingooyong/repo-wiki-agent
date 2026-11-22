# Qoder 知识卡输出契约（模块卡+仓库卡+关系索引）

## Goal

在长文 Wiki 之外，新增与 Qoder 知识卡兼容的导出形态，使 repo-wiki 产物可被知识库/Agent 直接消费，并能与 ai-testing 基线逐字段对比。

## Requirements

- 输出布局（隔离、不污染目标仓）：

  ```text
  .repo-agent-eval/repowiki/knowledge/zh/
  ├── _index.yaml
  └── <模块显示名>/
      ├── _module.yaml
      ├── 概述.md / 架构设计.md / 技术栈.md / 编码规范.md
      ├── 特殊配置与命令.md        # 有证据时
      └── <子模块>/
  ```

- `_index.yaml` 字段对齐基线：`schema_version`、`locale`、`commit`、`branch`、`exported_at`、`modules{dir_name,title,scope,source_files,children,depends_on,related_to,version_of}`。
- `_module.yaml` 字段对齐：`module_path`、`title`、`scope`、`depends_on`、`related_to`、`kk_module_id`、`kk_cards`、`kk_repo_cards`；ID 用确定性 UUID（如同输入同 ID），不依赖外部服务。
- 卡片生成规则：
  - 模块卡：`overview`、`architecture_design`、`tech_stack`、`coding_conventions` 为默认卡；`unique_setup_and_commands` 仅在有证据时生成。
  - 仓库横切卡（`kk_repo_cards`）：`build_system`、`configuration_system`、`dependency_management`、`error_handling`、`logging_system`，仅在有证据时生成。
  - 卡片为精炼 prose（对标基线：概述一句话、架构一段讲清编排与契约），不是字段清单；证据不足则不生成该卡，而不是编造。
- 模块关系：`depends_on`/`related_to` 必须带 `reason`，且 reason 引用具体文件/符号/调用关系（对标 `run_petclinic_pilot.py` 示例）；`version_of` 用于平行变体。
- 复用任务 2 的净化事实源与任务 3 的证据门禁；提供 CLI 入口（profile 或子命令）与 manifest 关联。

## Out of Scope

- 不实现 Qoder 云端知识库同步、不伪造 `kk_*` 外部 ID 语义。
- 不改 ai-testing 的任何文件。

## Acceptance Criteria

- [ ] schema 校验器通过：本仓与 ai-testing 两个目标各导出一次，字段与基线契约一致。
- [ ] 与基线的对比报告落盘：模块覆盖率、卡片类型覆盖率、关系 reason 覆盖率达标或有明确差距说明。
- [ ] 关系 reason 抽样可追溯：随机抽 10 条，均能指到真实文件与调用关系。
- [ ] 无证据卡片被跳过并记录原因；strict verify 增加知识卡结构检查且不破坏既有长文门禁。

## References

- 基线：`ai-testing/.qoder/repowiki/knowledge/zh/_index.yaml`、`.../AI Test OS 多子模块编排仓库/_module.yaml`
- 代码：`repo_wiki/scanner/knowledge_model_v3.py`、`repo_wiki/ia/taxonomy_compiler.py`、`repo_wiki/knowledge_plan/`、`repo_wiki/orchestration/eval_layout.py`
- 依赖：任务 1（契约文档）、2（事实纯度）、3（证据门禁）
