# 知识卡输出 Schema（任务：knowledge-card-contract）

字段契约以 `11-22-baseline-ai-testing-wiki/research/baseline-contract.md` 为准，本文件只定义生成侧决策。

## 生成规则

- 模块卡默认四类：`overview`、`architecture_design`、`tech_stack`、`coding_conventions`；`unique_setup_and_commands` 与五类仓库卡（`build_system`、`configuration_system`、`dependency_management`、`error_handling`、`logging_system`）仅在有证据时生成。
- 卡片为精炼 prose：概述一句话、架构一段讲清编排与契约；禁止字段清单化。证据不足则跳过该卡并记录原因。
- `kk_module_id` / 卡片 `id` 使用确定性 UUID（建议 uuid5，命名空间含仓库标识 + module_path + 卡片类型），同输入同 ID；不伪造外部云端语义。
- `depends_on` / `related_to` 必须带 `reason`，reason 引用真实文件与调用关系。基线示例：`run_petclinic_pilot.py 直接 import test_os.executors.SilverNeedleExecutor …`。`version_of` 仅用于目录结构与配置平行的变体。
- `scope` 必须来自真实扫描路径；`children` 与目录嵌套一致。

## 导出布局

`.repo-agent-eval/repowiki/knowledge/zh/_index.yaml` + 每模块目录 `_module.yaml` 与卡片 md；与长文 `repowiki/zh` 并列，run/release 语义复用现有 publisher，不另起发布面。

## 代码集成点（仅供实现者自行阅读，不注入）

`repo_wiki/scanner/knowledge_model_v3.py`（事实输入）、`repo_wiki/ia/taxonomy_compiler.py`（模块树）、`repo_wiki/orchestration/eval_layout.py`（布局）、`repo_wiki/orchestration/release_publisher.py`（发布）、`repo_wiki/cli.py`（入口）。

## 验收

1. schema 校验器：本仓与 ai-testing 各导出一次，字段与基线一致。
2. 对比报告：模块覆盖率、卡片类型覆盖率、关系 reason 覆盖率。
3. 随机抽 10 条关系 reason，全部可追溯。
4. 无证据卡片被跳过且有日志；strict 新增知识卡结构检查，长文门禁不回退。
