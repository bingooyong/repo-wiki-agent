# 证据与引用门禁设计（任务：evidence-citation-gate）

## 证据链

页面计划声明 evidence requirements → evidence bundle（文件/行号/符号）→ composer 仅消费 bundle → verifier 校验 → publisher 放行。

## 必须实现的约束

1. composer prompt 明确"不得补全未证实接口"；API、配置项、命令、数据模型只接受 scanner 或显式文档证据白名单。
2. 引用文件与行号必须存在，且落在页面声明的证据范围内。
3. 服务页 primary citation 必须来自该服务 `evidence_roots`；跨服务误绑直接 FAIL。
4. 证据不足：输出 `待确认` 段落并置 `low_confidence`，禁止编造。
5. 幻觉风险摘要写入 manifest `quality_summary`；高风险候选禁止发布。
6. 知识卡正文断言同样适用本约束（与任务 4 共用）。

## 代码集成点（仅供实现者自行阅读，不注入）

- `repo_wiki/evidence/ranking.py`、`citation_renderer.py`、`service_ownership.py`、`page_evidence_scorer.py`
- `repo_wiki/verifier/qoder_strict_verifier.py`、`citation_fact_coverage.py`
- `repo_wiki/orchestration/release_publisher.py`

## 负例验收（必须全部判负）

- 引用不存在的文件或行号；
- 服务页引用其他服务目录作为 primary citation；
- 无证据却给出确定性 API/字段清单的页面；
- 幻觉风险为高的候选 run 执行 `release-publish`。

正例：本仓与 ai-testing 各生成一次，引用校验 100% 通过，抽样人工复核记录归档；新增检查写入 strict 门禁文档。
