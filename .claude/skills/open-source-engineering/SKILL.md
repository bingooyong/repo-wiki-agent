# Skill: open-source-engineering

**版本：** v2.0
**类型：** 工作流型 Skill（Workflow Skill）
**语言：** 中文（技术术语保留英文原文，首次出现时附中英文对照）

## 1. Skill 目标

将任意代码仓库升级为符合专业开源工程标准（Kubernetes/FastAPI/LangChain 级别）的完整基础设施。涵盖治理文件、CI/CD、质量工具、开发者体验、社区模板、安全扫描等全方位工程化能力。

**已验证的工程标准（基于 repo-wiki-agent 实际实施）：**
- Python 项目完整工程化
- 1729+ 测试通过
- GitHub Actions CI 全流程覆盖
- Dependabot + Codecov 集成

## 2. 适用场景

| 场景编号 | 场景描述 |
|---------|---------|
| SC-01 | 项目开发完成，准备对外开源或发布 |
| SC-02 | 现有项目工程化程度不足，需要系统化升级 |
| SC-03 | 团队协作规范缺失，需要统一贡献流程 |
| SC-04 | CI/CD 不完整，需要补全质量门禁 |
| SC-05 | 开发者体验差，需要完善工具链 |
| SC-06 | 需要 GitHub Actions 自动发布（如 VSCode 扩展）|

## 3. 触发条件

用户消息中出现以下任一关键词或输入模式时触发：
- "创建开源工程"、"专业开源"、"开源基础设施"
- "完善 CI/CD"、"添加质量工具"
- "添加 CONTRIBUTING"、"添加 LICENSE"
- "专业工程化"、"工程化升级"
- "GitHub Actions"、"Dependabot"、"Codecov"

## 4. 用户决策参数

| 参数 | 选项 | 默认值 |
|------|------|--------|
| `license` | MIT / Apache 2.0 | Apache 2.0 |
| `linter` | ruff / black+isort+flake8 | ruff |
| `pypi` | 是 / 否 | 否 |
| `code_coverage` | 是 / 否 | 是 |
| `vscode_extension` | 是 / 否 | 否 |

## 5. 输出目标

### 5.1 治理文件（Governance Files）

| 文件 | 说明 |
|------|------|
| `LICENSE` | 开源许可证（Apache 2.0 / MIT） |
| `CONTRIBUTING.md` | 贡献流程和 Commit 规范（Conventional Commits） |
| `CODE_OF_CONDUCT.md` | 社区行为准则（Contributor Covenant 2.0） |
| `SECURITY.md` | 漏洞报告策略 |
| `CHANGELOG.md` | 版本变更记录（Keep a Changelog 格式） |

### 5.2 GitHub 基础设施

| 文件 | 说明 |
|------|------|
| `.github/ISSUE_TEMPLATE/bug_report.yml` | Bug 报告模板 |
| `.github/ISSUE_TEMPLATE/feature_request.yml` | 功能请求模板 |
| `.github/ISSUE_TEMPLATE/config.yml` | Issue 配置 |
| `.github/PULL_REQUEST_TEMPLATE.md` | PR 模板 |
| `.github/dependabot.yml` | 依赖自动更新（pip + npm） |
| `.github/workflows/ci.yml` | CI 流水线（lint + typecheck + test + coverage） |
| `.github/workflows/release.yml` | Release 构建（可选，用于 VSCode 扩展等） |

### 5.3 开发者工具

| 文件 | 说明 |
|------|------|
| `.pre-commit-config.yaml` | pre-commit 钩子 |
| `Makefile` | 开发命令（install-dev, lint, format, typecheck, test, coverage） |
| `pyproject.toml` | 工具配置（ruff + coverage + pytest） |

### 5.4 README 徽章

```
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)
![CI](https://github.com/USER/REPO/workflows/CI/badge.svg)
![codecov](https://codecov.io/gh/USER/REPO/branch/main/graph/badge.svg)
![Tests](https://img.shields.io/badge/Tests-1200%2B-blue)
```

## 6. 工作流程

### Step 1: 环境检测

检查当前项目状态：
```bash
# 检测已有文件
ls -la LICENSE CONTRIBUTING.md CODE_OF_CONDUCT.md SECURITY.md CHANGELOG.md 2>/dev/null

# 检测语言类型和包管理器
cat pyproject.toml 2>/dev/null | head -20
ls package.json go.mod Cargo.toml 2>/dev/null

# 检测现有工具链
which ruff mypy pytest eslint 2>/dev/null
```

### Step 2: 治理文件生成

根据用户选择的 `license` 生成：

1. **`LICENSE`** - 完整许可证文本（Apache 2.0 或 MIT）
2. **`CONTRIBUTING.md`** - Conventional Commits 规范 + PR 流程
3. **`CODE_OF_CONDUCT.md`** - Contributor Covenant 2.0
4. **`SECURITY.md`** - 漏洞报告流程（email / GitHub SECURITY tab）
5. **`CHANGELOG.md`** - 空骨架（Keep a Changelog 格式）

### Step 3: GitHub 模板生成

```bash
mkdir -p .github/ISSUE_TEMPLATE

# 生成以下文件：
# - .github/ISSUE_TEMPLATE/bug_report.yml
# - .github/ISSUE_TEMPLATE/feature_request.yml
# - .github/ISSUE_TEMPLATE/config.yml
# - .github/PULL_REQUEST_TEMPLATE.md
```

### Step 4: Dependabot 配置

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 10
    labels:
      - "dependencies"
      - "automated"
```

### Step 5: CI/CD 流水线

**Python 项目 `ci.yml`：**
```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install UV
        uses: astral-sh/setup-uv@v4
      - name: Install dependencies
        run: uv pip install -e ".[dev]"
      - name: Lint
        run: ruff check .
      - name: Format check
        run: ruff format --check .
      - name: Type check
        run: mypy repo_wiki
      - name: Run tests
        run: pytest --cov=repo_wiki --cov-report=term-missing
      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v4
        with:
          token: ${{ secrets.CODECOV_TOKEN }}
          fail_ci_if_error: false
```

### Step 6: 开发者工具配置

**`.pre-commit-config.yaml`：**
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.9.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.14.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
        args: [--ignore-missing-imports]
```

**`Makefile`：**
```makefile
install-dev:
	uv pip install -e ".[dev]"

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy repo_wiki

test:
	pytest

coverage:
	pytest --cov=repo_wiki --cov-report=term-missing

clean:
	rm -rf .pytest_cache __pycache__ .coverage .mypy_cache
```

### Step 7: pyproject.toml 配置

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "C4", "SIM"]

[tool.coverage.run]
source = ["repo_wiki"]
branch = true

[tool.pytest.ini_options]
addopts = "-q"
pythonpath = ["."]
asyncio_default_fixture_loop_scope = "function"
```

## 7. GitHub Secrets 和 Labels 配置

### 7.1 添加 Codecov Token（通过 API）

```python
# 使用 PyNaCl 加密并调用 GitHub API
import nacl.public
import base64, json

# 1. 获取 repo public key
# 2. 用 sealed_box 加密 token
# 3. PUT to /repos/{owner}/{repo}/actions/secrets/CODECOV_TOKEN
```

### 7.2 创建 Labels（通过 API）

```bash
curl -X POST "https://api.github.com/repos/OWNER/REPO/labels" \
  -H "Authorization: token $GH_TOKEN" \
  -d '{"name":"enhancement","color":"a2eeef","description":"New feature"}'
```

**建议 Labels：**
- `bug` (d73a4a) - Something isn't working
- `enhancement` (a2eeef) - New feature or request
- `good first issue` (7057ff) - Good for newcomers
- `documentation` (0075ca) - Improvements to documentation
- `high priority` (ff4500) - High priority issue
- `tech-debt` (fef2c0) - Technical debt

### 7.3 启用 Security Features（通过 API）

```bash
# 启用 Dependabot Security Updates
curl -X PATCH "https://api.github.com/repos/OWNER/REPO" \
  -H "Authorization: token $GH_TOKEN" \
  -d '{
    "security_and_analysis": {
      "dependabot_security_updates": {"enabled": true},
      "secret_scanning": {"enabled": true}
    }
  }'
```

## 8. 验证方式

### 8.1 本地验证

```bash
# 安装开发环境
make install-dev

# 运行所有检查
make lint
make format
make typecheck
make test
make coverage

# 本地 pre-commit
pre-commit install
pre-commit run --all-files
```

### 8.2 CI 验证

```bash
# 推送触发 CI
git push origin main

# 检查 GitHub Actions
gh run list --repo OWNER/REPO
gh run watch --repo OWNER/REPO
```

### 8.3 Codecov 验证

1. 在 https://codecov.io 绑定仓库
2. 获取 token 并添加到 GitHub Secrets `CODECOV_TOKEN`
3. CI 成功后查看 https://codecov.io/gh/USER/REPO

## 9. 文件路径参考

| 文件 | 操作 | 状态 |
|------|------|------|
| `LICENSE` | 新建 | ✅ 已验证 |
| `CONTRIBUTING.md` | 新建 | ✅ 已验证 |
| `CODE_OF_CONDUCT.md` | 新建 | ✅ 已验证 |
| `SECURITY.md` | 新建 | ✅ 已验证 |
| `CHANGELOG.md` | 新建 | ✅ 已验证 |
| `.github/ISSUE_TEMPLATE/` | 新建目录 | ✅ 已验证 |
| `.github/PULL_REQUEST_TEMPLATE.md` | 新建 | ✅ 已验证 |
| `.github/dependabot.yml` | 新建 | ✅ 已验证 |
| `.github/workflows/ci.yml` | 新建 | ✅ 已验证 |
| `.github/workflows/release.yml` | 新建（如需） | ✅ 已验证 |
| `.pre-commit-config.yaml` | 新建 | ✅ 已验证 |
| `Makefile` | 修改/新建 | ✅ 已验证 |
| `pyproject.toml` | 修改 | ✅ 已验证 |
| `README.md` | 修改 | ✅ 已验证 |

## 10. 示例触发语句

1. "为这个项目创建专业开源工程基础设施"
2. "添加 Apache 2.0 LICENSE 和 CONTRIBUTING.md"
3. "完善 CI/CD，添加 ruff lint 和 pytest + codecov"
4. "创建 .pre-commit-config.yaml 和 Makefile"
5. "使用 ruff 作为 linter，添加 VSCode 扩展 release workflow"
6. "启用 Dependabot Security Updates 和 Secret scanning"