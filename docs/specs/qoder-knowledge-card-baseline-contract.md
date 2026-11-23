# Qoder 知识卡基线契约（ai-testing 参考产物）

**来源：** `ai-testing/.qoder/repowiki/knowledge/zh`（只读）
**基线 commit：** `99e14d049fc3b7e0ea2e3d08e29dfd2eb4700b5a` · branch `main` · exported_at `2026-11-22T06:14:22Z`
**registry：** `ai/baselines/registry.json` → `ai-testing-knowledge-zh`
**校验：** `python scripts/verify_baseline_registry.py`
**消费方：** 任务 `11-22-knowledge-card-contract`（导出实现）、`11-22-multi-repo-acceptance`（对标验收）

本契约描述**基线的事实形态**，不是 repo-wiki 的实现说明。禁止把基线内容硬编码进 planner/composer。

---

## 1. 目录布局

```
knowledge/zh/
├── _index.yaml                      # 全仓模块索引 + 关系
└── <root dir_name>/                 # 目录名 = 模块 title（中文）
    ├── _module.yaml
    ├── 概述.md / 架构设计.md / 技术栈.md / 编码规范.md
    ├── 特殊配置与命令.md            # 条件卡，仅有证据时出现
    ├── build_system.md …            # 仓库横切卡，只挂在 root 模块目录
    └── <child dir_name>/            # 子模块按层级嵌套，镜像 children 关系
        ├── _module.yaml
        └── 概述.md …
```

目录层级由 `_index.yaml` 的 `children` 决定，**不是**由源码路径深度决定。基线中 `test_os_core` 的 6 个子模块都嵌套在 `AI Test OS 核心编排层/` 下。

## 2. `_index.yaml` 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema_version` | int | 基线为 `1` |
| `locale` | str | `zh-CN` |
| `commit` | str | 导出时源仓 HEAD 全哈希 |
| `branch` | str | 导出时分支 |
| `exported_at` | str | ISO8601 UTC，带引号 |
| `modules.<module_path>` | map | key 是逻辑模块路径（`root`、`test_os_core/llm_workers`），不是目录名 |

模块节点字段：`dir_name`、`title`、`scope[]`、`source_files[]`、`children[]`、`depends_on[]`、`related_to[{path,reason}]`、`version_of[{path,reason}]`。

- `scope` 是仓库内相对路径或目录前缀（`test_os/workers/`、`README.md`）。
- `dir_name` 与 `title` 在基线中一致，均为中文人类可读名。
- `source_files` 在基线中全部为 `[]`（事实由 `scope` 承载）。

## 3. `_module.yaml` 字段

`schema_version`、`module_path`、`title`、`scope`、`source_files`、`depends_on`、`related_to`、`kk_module_id`、`kk_cards.<type>{id,title}`、`kk_repo_cards[]`。部分模块另含两个可选字段：`kk_ordinal`（int，兄弟排序序号，基线 15 个模块中 12 个携带）与 `version_of[{path,reason}]`（语义同 `_index.yaml`，基线仅 `vulnerable_app_tests` 非空）。

- `module_path` 必须能在 `_index.yaml.modules` 中找到同名 key（基线 15/15 匹配）。
- `kk_module_id` / `kk_cards.*.id` 是 UUID。repo-wiki 导出应使用**确定性 UUID**（由 module_path + card_type + commit 派生），保证重复导出稳定。
- `kk_cards` 同时包含模块卡与仓库卡；`kk_repo_cards` 只列出仓库卡类型名。

## 4. 卡片类型与文件名映射

| type | 文件名 | ai-testing | repo-agent | 备注 |
|------|--------|-----------|------------|------|
| `overview` | `概述.md` | 15 | 40 | 每模块必有；基线为一句话 |
| `architecture_design` | `架构设计.md` | 15 | 40 | 每模块必有；一段讲清编排与契约 |
| `tech_stack` | `技术栈.md` | 15 | 37 | **条件卡**：repo-agent 中 `adapter_qoder`/`generator`/`scanner` 缺失 |
| `coding_conventions` | `编码规范.md` | 15 | 37 | **条件卡**：repo-agent 中 `adapter_qoder`/`ai_source_of_truth`/`scanner` 缺失 |
| `unique_setup_and_commands` | `特殊配置与命令.md` | 7 | 13 | **条件卡**：仅当模块有独特配置/命令证据 |
| `build_system` | `build_system.md` | 1 | 1 | 仓库横切卡，挂 root |
| `configuration_system` | `configuration_system.md` | 1 | 1 | 同上 |
| `dependency_management` | `dependency_management.md` | 1 | 1 | 同上 |
| `error_handling` | `error_handling.md` | 1 | 1 | 同上 |
| `logging_system` | `logging_system.md` | 1 | 1 | 同上 |
| `frontend_style` | `frontend_style.md` | 0 | 1 | **新增横切卡类型**（2026-11-23 repo-agent 导出观察到），英文文件名，挂 root |

合计：ai-testing 72 个 markdown（67 模块卡 + 5 仓库卡）/ 88 文件；repo-agent 173 个 markdown / 214 文件（40 模块）。

**卡片存在性是证据条件的，不是模板全量补齐。** 早期"tech_stack/coding_conventions 每模块必有"的判断只适用于 ai-testing 那次导出；repo-agent 导出证明它们会按证据缺席。任务 4 的导出契约必须允许条件缺席，且不得为凑覆盖率编造卡片。横切卡类型集合也不封闭（`frontend_style` 为新增），schema 校验应接受已知集合之外的横切类型并记录，而不是硬失败。

**卡片是精炼段落，不是长列表。** 基线全部卡片合计 44563 字符，平均每卡约 619 字符。

## 5. 关系语义

| 关系 | 基线数量 | reason 要求 |
|------|----------|-------------|
| `depends_on` | 0 | 基线全为空。**不得凭空发明依赖**；无证据就留空 |
| `related_to` | 6 | 6/6 有 reason，引用具体文件与调用关系 |
| `version_of` | 1 | 1/1 有 reason，说明变体平行关系 |

reason 覆盖率 = 有非空 reason 的关系数 / (`related_to` + `version_of`) 总数 = **1.0**。

reason 样例（基线原文）：

> `run_petclinic_pilot.py 直接 import test_os.executors.SilverNeedleExecutor，传入 product_packs/spring-petclinic-rest 与 silver-needle-vulnerable-app 驱动 E2E。`

契约要求：reason 必须落到**文件名 + 符号/调用**，不能写"两者相关"这类空话。无证据时不建关系。

## 6. 机器可比指标

由 `repo_wiki/verifier/external_baseline_registry.py` 计算，后续任务直接复用：

| 指标 | 定义 | 基线值 |
|------|------|--------|
| `module_count` | `_index.yaml.modules` 节点数 | 15 |
| `module_card_counts` | 按类型统计模块卡 | overview/architecture_design/tech_stack/coding_conventions 各 15，unique_setup_and_commands 7 |
| `repo_card_counts` | 按类型统计仓库卡 | 5 类各 1 |
| `relation_reason_coverage` | 非空 reason / (related_to + version_of) | 1.0 |
| `evidence.refs_per_1k_chars` | 文件路径引用数 / 总字符 × 1000 | 3.927（175 refs / 44563 chars） |
| `missing_module_yaml` | index 有节点但缺 `_module.yaml` | `[]` |
| `missing_card_files` | `kk_cards` 声明但文件缺失 | `[]` |

文件引用识别正则：`[A-Za-z0-9_./\-]+\.(py|md|yaml|yml|toml|json|java|xml|sh|ts|js)`。

## 7. 哈希与只读契约

`content_hash` = sha256，按相对路径排序后依次喂入 `relpath_posix`、`NUL`、`file_bytes`、`NUL`（复用 `qoder_baseline_registry.compute_baseline_fingerprint`）。基线值：

- `ai-testing-knowledge-zh`：`10908d78bbef67c721192112c9b7d93cf72c241788dfdda66877c355f51aa71e`，88 文件
- `ai-testing-longform-zh`：`04889c476170bc011c5f65d58cebaedde54c68878e1090a20cf0744450c0ff20`，71 文件

只读要求：任何消费方不得写基线路径；`verify_baseline_registry.py` 只读基线，`--update` 只写本仓 registry。

## 8. 已知限制

1. ai-testing 的 `.qoder/` 在该仓中是 **untracked**，基线是本地导出而非提交产物；`commit` 字段指导出时源仓 HEAD，不代表基线自身被版本化。本仓 registry 的哈希才是冻结依据。
2. `repo-wiki compare` **不支持**知识卡维度，且跨仓基线不可消费（详见差距报告 §4）。
3. 长文基线已落盘且 `progress_status=completed`（70 页），早期"仅截图"的判断已作废。