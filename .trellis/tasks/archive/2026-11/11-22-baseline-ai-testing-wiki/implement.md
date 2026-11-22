# 执行计划：baseline-ai-testing-wiki

## 顺序

1. [x] 采集 ai-testing 真实统计（知识卡 + 长文），修正 PRD/research 的"长文未落盘"错误。
2. [x] 新增 `repo_wiki/verifier/external_baseline_registry.py`：registry 加载、根解析、双形态统计、哈希复算校验。
3. [x] 新增 `scripts/verify_baseline_registry.py`：默认校验，`--update` 重算，`--json` 输出，失败退出 1。
4. [x] 生成 `ai/baselines/registry.json`（两条条目，哈希由脚本写入，不手填）。
5. [x] 写 `docs/specs/qoder-knowledge-card-baseline-contract.md`（任务 4 的字段契约）。
6. [x] 写 `docs/eval/2026-11-22-ai-testing-baseline-gap-report.md` + `.json`，逐项标注归属工作流与 compare 不支持维度。
7. [x] 新增 `tests/test_external_baseline_registry.py`（合成夹具 + 真实基线可选跳过）。
8. [x] 修正 PRD / research / 父任务 PRD / 任务 2 PRD 中的长文与事实源事实错误。

## 验证命令

```bash
.venv/bin/python scripts/verify_baseline_registry.py --json .repo-agent-eval/baseline-registry-verify.json
.venv/bin/python scripts/verify_baseline_registry.py   # 第二次运行，哈希必须一致
.venv/bin/python -m pytest tests/test_external_baseline_registry.py -q
.venv/bin/python -m pytest tests -q -k "baseline or comparator or parity"
.venv/bin/ruff check repo_wiki/verifier/external_baseline_registry.py scripts/verify_baseline_registry.py tests/test_external_baseline_registry.py
```

## 评审门

- 哈希两次运行一致，且 `file_count` 与磁盘一致。
- 全程未写 ai-testing 任何路径（脚本只读；用 `git -C ai-testing status` 佐证）。
- 差距报告数字全部来自脚本输出，不手写估算。
- 不放宽任何 strict 阈值。

## 回滚点

新增文件为主，回滚 = 删除新增文件并还原 PRD/research 修正；不触碰既有 verifier 逻辑。