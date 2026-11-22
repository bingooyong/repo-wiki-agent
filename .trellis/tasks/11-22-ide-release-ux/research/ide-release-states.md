# IDE 发布闭环状态与契约（任务：ide-release-ux）

## 五种侧栏状态

| 状态 | 判定 | 下一步命令 |
|------|------|-----------|
| 未生成 | 无 run 且无 release manifest | `repo-wiki generate --profile qoder-like --output .repo-agent-eval` |
| 已生成未验证 | 有 run，无 strict PASS 报告 | `repo-wiki verify --profile qoder-like --ci --output .repo-agent-eval` |
| 已验证未发布 | strict PASS，无 release manifest | `repo-wiki release-publish --output .repo-agent-eval` |
| release 非 READY | manifest 存在但 readiness 非 READY | 重新生成/验证，禁止回退到最新 run |
| 导航为空 | manifest READY 但 `navigation_tree` 为空 | 视为发布缺陷，提示重生成 |

## 数据契约

- 徽标：fresh/stale、verify 结果、citation coverage、生成模式（LLM/rule/fallback）、生成时间、commit；字段必须来自真实 manifest，禁止编造。
- 状态面板：readiness、wiki/target commit、工作区 drift、页面数、warning 数、provider/model 摘要、最近 run。
- citation 跳转：解析文件与行号，`vscode.open` 打开；Markdown Preview 用 fallback 链接；失效引用显示 warning。

## 术语（README 与 docs 必须一致）

run=过程产物；strict verify=候选质量判定；release=READY 稳定发布面；plugin 只读 `.repo-agent-eval/repowiki/zh/manifest.json`。

## 约束

插件不内嵌 Python、不直接调用 LLM；密钥仍只走 SecretStorage，遵守 `docs/specs/vscode-llm-configuration-spec.md`。

## 验收

五种状态逐一人造并截图/记录；跳转行号正确；失效引用有提示；Cursor 冒烟通过；README 术语一致。
