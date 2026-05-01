# Task Log: Task 15.2 - Static repo-wiki viewer with tree navigation and Mermaid rendering

## Summary
实现了静态 wiki viewer 模块,提供目录树导航、页面锚点跳转和 Mermaid 图表渲染功能。

## Details
1. **创建 `repo_wiki/viewer/` 目录和模块**:
   - `static_viewer.py`: 核心 viewer 实现
   - `__init__.py`: 模块导出

2. **核心功能**:
   - **Mermaid 渲染**: `render_mermaid_safely()` 将 ```mermaid 块转换为 HTML div
   - **目录树导航**: `build_tree_html()` 从 manifest 构建左侧导航树
   - **TOC 生成**: `build_toc_html()` 从标题提取目录,支持锚点跳转
   - **锚点注入**: `inject_anchors()` 为所有标题添加 id 属性
   - **静态 HTML 构建**: `build_viewer_html()` 组装完整页面

3. **设计决策**:
   - 使用 CSS 类 `.mermaid` + CDN mermaid.js 实现图表渲染
   - 导航树按 overview/section/module/phase 分组
   - 静态模式无需服务器,可直接用浏览器打开

## Output
- `/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/repo_wiki/viewer/__init__.py`
- `/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/repo_wiki/viewer/static_viewer.py`
- `/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/tests/test_viewer.py`

## Issues
None

## Next Steps
- Task 15.3 将基于此 viewer 构建 VS Code 扩展原型
