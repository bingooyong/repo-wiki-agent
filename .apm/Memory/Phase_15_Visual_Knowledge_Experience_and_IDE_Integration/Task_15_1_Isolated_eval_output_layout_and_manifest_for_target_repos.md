# Task Log: Task 15.1 - Isolated eval output layout and manifest for target repos

## Summary
实现了一套完整的隔离评估输出布局系统 (`.repo-agent-eval`)，包括配置文件、清单架构、路径安全验证和测试覆盖。

## Details
1. **创建 `eval_layout.py` 模块** (`repo_wiki/orchestration/eval_layout.py`):
   - `EvalOutputProfile`: 配置类，支持 default/ci/local 三种输出配置文件
   - `EvalManifest`/`EvalManifestFile`/`EvalManifestEvidence`: Pydantic 清单数据模型
   - `validate_eval_root_safety()`: 验证 eval root 不与受保护目录重叠
   - `reject_unsafe_output_root()`: 对不安全的 root 抛出 `RepoWikiError`
   - `generate_manifest()`: 扫描输出目录生成完整清单
   - `write_manifest()`: 将清单写入 `manifest.json`
   - `get_eval_output_layout_contract()`: 返回布局合同文档

2. **关键设计决策**:
   - PROTECTED_DIRS 包含: docs/, .repo-wiki/, ai/, .apm/, .claude/, .codex/, scripts/, templates/
   - eval root 默认 `.repo-agent-eval`，CI 模式使用 `.repo-agent-eval-ci`
   - 支持带时间戳的 run subdirectory 隔离 (`<run_id>/`)
   - SHA256 文件哈希用于完整性校验

3. **测试覆盖**:
   - `test_eval_layout.py`: 22 个测试用例覆盖所有核心功能

## Output
- `/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/repo_wiki/orchestration/eval_layout.py` - 核心模块
- `/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/tests/test_eval_layout.py` - 22 个测试用例

## Issues
None

## Next Steps
- Task 15.2 依赖此模块，将在 viewer 中使用 manifest 驱动导航树渲染
