# repo-wiki MVP — 第三方集成指南（Third-Party Integration）

**文档编号：** DOC-013
**版本：** v1.0.0
**创建日期：** 2026-05-03
**最后更新：** 2026-05-03

---

## 1. LLM Provider 集成

### 1.1 Minimax

**配置：**

```yaml
llm:
  provider: minimax
  model: abab6-chat
  base_url: https://api.minimax.chat/v1
  api_key_env: MINIMAX_API_KEY
```

**环境变量：**
```bash
export MINIMAX_API_KEY="your_minimax_api_key"
```

### 1.2 OpenAI-compatible

**配置：**

```yaml
llm:
  provider: openai-compatible
  model: gpt-4o
  base_url: https://api.openai.com/v1
  api_key_env: OPENAI_API_KEY
```

**环境变量：**
```bash
export OPENAI_API_KEY="your_openai_api_key"
```

### 1.3 自定义 Provider

实现 `LLMClient` Protocol：

```python
from repo_wiki.llm.base import LLMClient, ChatMessage, ChatResponse

class CustomLLMClient(LLMClient):
    def __init__(self, config: dict):
        self.config = config

    def chat(self, messages: list[ChatMessage], **kwargs) -> ChatResponse:
        # 实现自定义逻辑
        ...
```

---

## 2. Git 集成

### 2.1 GitHub Actions

详见 [deployment-guide.md](./deployment-guide.md#51-github-actions-示例) 的 CI 示例。

### 2.2 GitLab CI

详见 [deployment-guide.md](./deployment-guide.md#52-gitlab-ci-示例) 的 CI 示例。

### 2.3 Jenkins

> ⚠️ **待确认 [TBC-001]：** Jenkins 集成需要确认具体的 pipeline 语法。

---

## 3. 向量存储集成

### 3.1 ChromaDB（默认）

使用嵌入式 ChromaDB，无需额外配置：

```yaml
vector_store:
  type: chromadb  # 默认
  persist_dir: .repo-wiki/chroma_db/
```

### 3.2 其他向量存储

> ⚠️ **待确认 [TBC-002]：** 目前 MVP 仅支持 ChromaDB。Qdrant/FAISS/Lance 为 V2 计划。

---

## 4. 外部工具集成

### 4.1 VS Code Extension

repo-wiki 提供 VS Code 扩展支持 wiki 浏览：

- 扩展位置：`extensions/repo-wiki-viewer/`
- 功能：导航树、Markdown 预览、Mermaid 渲染

### 4.2 IDE 集成

> 📌 **假设 [AS-001]：** IDE 集成通过 VS Code 扩展实现。

---

## 5. 参考文档

> 详见 [deployment-guide.md](./deployment-guide.md) 部署指南。
> 详见 [api-spec.md](./api-spec.md) API 规范。