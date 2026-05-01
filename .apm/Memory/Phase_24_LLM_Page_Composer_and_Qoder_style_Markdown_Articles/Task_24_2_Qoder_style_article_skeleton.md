---
task_ref: "Task 24.2 - Qoder-style article skeleton"
status: "completed"
important_findings: false
compatibility_issue: false
---

## 交付物

### Article Skeleton Builder (repo_wiki/prompts/skeleton.py)

#### Section Keys
- 支持的章节：目录、简介、项目结构、核心组件、架构总览、详细分析、依赖、性能、排障、结论、附录

#### HeadingSection 和 HeadingContract
- `HeadingSection`: 单个标题节定义（key, heading_text, level, required, min_prose_chars）
- `HeadingContract`: 页面类型的标题结构契约
  - 7种页面类型的预定义契约：overview, service, api, data, entity, ops, development
  - 每个契约定义必需和可选章节
  - 支持 TOC 生成和深度控制

#### ArticleSkeleton
- 包含 page_type, title, headings, toc_entries, context
- `render_toc()`: 渲染目录为 markdown
- `render_skeleton_markdown()`: 渲染骨架为 markdown 标题
- `get_heading_count()`: 按级别统计标题数量

#### SkeletonBuilder
- 构建者模式，支持链式调用
- `set_title()`: 设置文章标题
- `set_context()`: 设置模板上下文
- `include_optional_sections()`: 显式包含可选章节
- `build()`: 构建 ArticleSkeleton

#### 工具函数
- `get_heading_contract()`: 获取页面类型的标题契约
- `build_skeleton()`: 便捷函数，一步构建 skeleton
- `extract_toc_from_markdown()`: 从 markdown 提取 TOC
- `validate_toc_completeness()`: 验证 TOC 完整性
- `validate_heading_hierarchy()`: 验证标题层级合法性
- `generate_heading_snapshot()`: 生成标题快照
- `headings_match_snapshot()`: 比较标题快照

### 导出 (repo_wiki/prompts/__init__.py)
- 新增 skeleton 模块所有导出的重新导出
- 共新增约 25 个新导出符号

### 测试 (tests/test_article_skeleton.py)
- 52 个测试用例，覆盖：
  - SECTION_KEYS 常量
  - HeadingSection 和 HeadingContract 数据类
  - 7种页面类型的标题契约
  - ArticleSkeleton 渲染方法
  - SkeletonBuilder 构建者
  - TOC 提取和验证
  - 标题层级验证
  - 快照生成和比较

### 编译命令
`uv run repo-wiki --help` - 通过

### 自测命令
`uv run pytest tests/test_article_skeleton.py tests/test_page_prompts.py` - 103 passed
