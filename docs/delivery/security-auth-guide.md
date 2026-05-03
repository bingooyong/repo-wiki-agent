# repo-wiki MVP — 安全与认证指南（Security Auth Guide）

**文档编号：** DOC-012
**版本：** v1.0.0
**创建日期：** 2026-05-03
**最后更新：** 2026-05-03

---

## 1. 安全特性

### 1.1 敏感信息过滤

repo-wiki 内置敏感信息检测和脱敏：

| 模式 | 替换为 | 示例 |
|------|-------|------|
| API Key | `[REDACTED]` | `sk-xxx...` |
| Bearer Token | `[REDACTED]` | `Bearer eyJ...` |
| Private Key | `[REDACTED]` | `-----BEGIN PRIVATE KEY-----` |
| Database Connection | `[REDACTED]` | `postgresql://user:...` |

### 1.2 输出隔离

Qoder-like 模式输出到独立目录，不修改目标仓库：

```bash
# 输出到 .repo-agent-eval/，不污染目标仓库
uv run repo-wiki generate --profile qoder-like

# 受保护的路径（默认不修改）
- .qoder/**
- .repo-wiki/**
- docs/**
```

---

## 2. LLM API 安全

### 2.1 API Key 管理

> 📌 **假设 [AS-001]：** API Key 通过环境变量注入，不写入配置文件。

**推荐方式：**

```bash
# 环境变量（推荐）
export MINIMAX_API_KEY="your_key_here"

# 不推荐：写入配置文件
# llm:
#   api_key: "your_key_here"  # 不安全
```

### 2.2 Secret Redaction

CLI 不会打印明文 API Key：

```
# 错误示例（不会发生）
$ uv run repo-wiki config
MINIMAX_API_KEY: your_actual_key_here  # ❌ 不会显示

# 正确示例
$ uv run repo-wiki config
MINIMAX_API_KEY: [REDACTED]  # ✅ 安全
```

---

## 3. 本地安全

### 3.1 SQLite 权限

确保 `.repo-wiki/` 目录权限正确：

```bash
# 仅当前用户可读写
chmod 700 .repo-wiki/
chmod 600 .repo-wiki/state.sqlite3
```

### 3.2 磁盘加密

> 📌 **假设 [AS-002]：** 敏感仓库应使用磁盘加密（如 FileVault、dm-crypt）。

---

## 4. 安全检查清单

- [ ] LLM API Key 通过环境变量注入，不写入配置文件
- [ ] `.repo-wiki/` 目录权限为 700
- [ ] SQLite 数据库文件权限为 600
- [ ] 生产环境启用磁盘加密
- [ ] 定期更新 repo-wiki 版本（安全补丁）

---

## 5. 合规说明

### 5.1 数据处理

> ⚠️ **待确认 [TBC-001]：** 如处理敏感仓库，确认数据处理符合组织安全策略。

### 5.2 LLM 数据

> ⚠️ **待确认 [TBC-002]：** 确认 LLM Provider 的数据处理条款是否适合您的用例。

---

## 6. 参考文档

> 详见 [configuration-guide.md](./configuration-guide.md) 配置指南。
> 详见 [deployment-guide.md](./deployment-guide.md) 部署指南。