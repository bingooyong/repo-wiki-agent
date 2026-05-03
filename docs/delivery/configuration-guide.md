# repo-wiki MVP — 配置指南（Configuration Guide）

**文档编号：** DOC-008
**版本：** v1.0.0
**创建日期：** 2026-05-03
**最后更新：** 2026-05-03

---

## 1. 配置方式

repo-wiki 支持多种配置方式，优先级（高到低）：

1. CLI 参数
2. 环境变量
3. YAML 配置文件
4. 默认值

---

## 2. YAML 配置文件

### 2.1 配置文件位置

按以下顺序查找：
1. `./repo-wiki.yaml`
2. `./.repo-wiki.yaml`
3. `~/.repo-wiki.yaml`

### 2.2 配置示例

```yaml
# repo-wiki.yaml

llm:
  provider: minimax          # openai-compatible | minimax
  model: abab6-chat          # 模型名称
  base_url: https://api.minimax.chat/v1
  api_key_env: MINIMAX_API_KEY  # 环境变量名
  max_retries: 3
  timeout: 120

generation:
  profile: qoder-like
  min_pages: 24
  max_pages: 220
  concurrency: 4
  cache_enabled: true

output:
  eval_dir: .repo-agent-eval
  protect_patterns:
    - .qoder/**
    - .repo-wiki/**
    - docs/**

security:
  redact_api_keys: true
  redact_tokens: true
  redact_private_keys: true
```

---

## 3. 环境变量

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `MINIMAX_API_KEY` | Minimax API Key | - |
| `OPENAI_API_KEY` | OpenAI API Key | - |
| `REPO_WIKI_FORCE_MOCK_LLM` | 强制使用 Mock LLM | false |
| `REPO_WIKI_LLM_PAGE_LIMIT` | 单次最大页面数 | 8 |
| `REPO_WIKI_LLM_REAL_MAX_CALLS` | 最大真实 LLM 调用数 | 0 (无限) |

---

## 4. CLI 参数

### 4.1 全局参数

| 参数 | 说明 |
|------|------|
| `--config <path>` | 指定配置文件 |
| `--verbose` | 详细输出 |
| `--quiet` | 静默模式 |

### 4.2 generate 参数

| 参数 | 说明 |
|------|------|
| `--profile` | 生成 profile |
| `--run-id` | 运行 ID |
| `--llm-model` | LLM 模型 |
| `--max-pages` | 最大页面数 |
| `--min-pages` | 最小页面数 |
| `--concurrency` | 并发数 |

### 4.3 verify 参数

| 参数 | 说明 |
|------|------|
| `--profile` | 验证 profile |
| `--ci` | CI 模式 |
| `--output` | 验证运行 ID |

---

## 5. LLM 配置详解

### 5.1 Minimax Provider

```yaml
llm:
  provider: minimax
  model: abab6-chat
  base_url: https://api.minimax.chat/v1
  api_key_env: MINIMAX_API_KEY
```

### 5.2 OpenAI-compatible Provider

```yaml
llm:
  provider: openai-compatible
  model: gpt-4o
  base_url: https://api.openai.com/v1
  api_key_env: OPENAI_API_KEY
```

### 5.3 Mock Provider (开发/测试)

```bash
export REPO_WIKI_FORCE_MOCK_LLM=1
# 或
llm:
  provider: mock
```

---

## 6. 生成配置详解

### 6.1 Page Count 配置

```yaml
generation:
  min_pages: 24    # 最小页面数
  max_pages: 220    # 最大页面数（默认 220，移除旧 120 下限）
```

### 6.2 并发配置

```yaml
generation:
  concurrency: 4    # 并发 LLM 调用数
```

---

## 7. 输出配置详解

### 7.1 Qoder-like 输出

```yaml
output:
  eval_dir: .repo-agent-eval  # 输出根目录
```

### 7.2 保护路径

```yaml
output:
  protect_patterns:
    - .qoder/**      # Qoder 目录（只读）
    - .repo-wiki/**  # 状态目录
    - docs/**        # 目标文档目录
```

---

## 8. 故障排查

| 问题 | 解决方案 |
|------|---------|
| LLM API 403/401 | 检查 API Key 配置和环境变量 |
| 配置不生效 | 确认配置文件位置和格式 |
| 端口占用 | 可能是多进程冲突，减少 concurrency |

---

## 9. 参考文档

> 详见 [deployment-guide.md](./deployment-guide.md) 部署指南。
> 详见 [operations-runbook.md](./operations-runbook.md) 运维手册。