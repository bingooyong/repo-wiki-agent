# repo-wiki MVP — 部署指南（Deployment Guide）

**文档编号：** DOC-002
**版本：** v1.0.0
**创建日期：** 2026-05-03
**最后更新：** 2026-05-03

---

## 1. 环境要求

### 1.1 系统要求

| 要求 | 最低版本 | 推荐版本 |
|------|---------|---------|
| Python | 3.10+ | 3.11+ |
| uv | 0.1.0+ | 最新版 |
| Git | 2.30+ | 最新版 |
| 磁盘空间 | 1 GB | 10 GB |

### 1.2 依赖服务

> 📌 **假设 [AS-001]：** 本部署假设不依赖外部数据库服务。SQLite 和 ChromaDB 均为嵌入式运行，无需额外服务。

**可选依赖：**
- LLM API (OpenAI-compatible 或 Minimax)
- GitLab/Jenkins/MCP 等 CI/CD 集成（可选）

---

## 2. 安装步骤

### 2.1 从源码安装

```bash
# 1. 克隆仓库
git clone https://github.com/bingooyong/repo-agent.git
cd repo-agent

# 2. 创建虚拟环境
uv venv .venv
source .venv/bin/activate  # Linux/macOS
# 或 .venv\Scripts\activate  # Windows

# 3. 安装依赖
uv pip install -e .

# 4. 验证安装
uv run repo-wiki --help
```

### 2.2 LLM 配置

#### 方式一：环境变量

```bash
export MINIMAX_API_KEY="your_minimax_api_key_here"
# 或
export OPENAI_API_KEY="your_openai_api_key_here"
```

#### 方式二：YAML 配置文件

创建 `repo-wiki.yaml` 或 `.repo-wiki.yaml`：

```yaml
llm:
  provider: minimax
  model: abab6-chat
  base_url: https://api.minimax.chat/v1
  api_key_env: MINIMAX_API_KEY
```

---

## 3. 初始化

### 3.1 目标仓库初始化

```bash
cd /path/to/your-repo

# 初始化 repo-wiki 索引
uv run repo-wiki init

# 构建搜索索引
uv run repo-wiki index
```

### 3.2 输出目录

初始化后会在目标仓库创建：
- `.repo-wiki/` — SQLite 状态、向量索引
- `.repo-agent-eval/` — qoder-like 生成输出（生成后）

---

## 4. 部署模式

### 4.1 标准模式（Standard）

输出直接写入目标仓库：

```bash
uv run repo-wiki generate
# 输出到: docs/, .repo-wiki/
```

### 4.2 Qoder-like 隔离模式

输出到独立目录，不污染目标仓库：

```bash
uv run repo-wiki generate --profile qoder-like --run-id my-run
# 输出到: .repo-agent-eval/my-run/content/
```

---

## 5. CI/CD 集成

### 5.1 GitHub Actions 示例

```yaml
name: Wiki Generation

on:
  push:
    branches: [main]
  schedule:
    - cron: '0 2 * * *'  # 每天凌晨2点

jobs:
  generate-wiki:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Install repo-wiki
        run: uv pip install -e .

      - name: Generate Wiki
        env:
          MINIMAX_API_KEY: ${{ secrets.MINIMAX_API_KEY }}
        run: |
          uv run repo-wiki init
          uv run repo-wiki generate --profile qoder-like --run-id ci-run

      - name: Verify Quality
        run: |
          uv run repo-wiki verify --profile qoder-like --ci --output ci-run
```

### 5.2 GitLab CI 示例

```yaml
wiki Generation:
  stage: deploy
  script:
    - uv pip install -e .
    - uv run repo-wiki init
    - uv run repo-wiki generate --profile qoder-like --run-id gitlab-run
    - uv run repo-wiki verify --profile qoder-like --ci --output gitlab-run
  only:
    - main
```

---

## 6. 验证部署

### 6.1 编译验证

```bash
uv run repo-wiki --help
# 输出 CLI 帮助信息即成功
```

### 6.2 测试验证

```bash
uv run pytest tests/test_qoder_like_profile.py tests/test_qoder_like_verifier.py -v
```

---

## 7. 故障排查

| 问题 | 可能原因 | 解决方案 |
|------|---------|---------|
| `repo-wiki: command not found` | 安装失败 | 重新执行 `uv pip install -e .` |
| LLM API 错误 | API Key 无效 | 检查环境变量或 YAML 配置 |
| SQLite 锁定 | 多进程冲突 | 确保单 writer 访问 |
| 生成速度慢 | API 限速 | 降低并发调度 (`--concurrency 1`) |

---

## 8. 参考文档

> 详见 [configuration-guide.md](./configuration-guide.md) 配置详解。
> 详见 [operations-runbook.md](./operations-runbook.md) 运维手册。
> 详见 [user-manual.md](./user-manual.md) 用户手册。