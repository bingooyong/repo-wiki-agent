# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-05-03

### Added

- Initial release with qoder-like wiki generation
- Strict verify with 13 quality gates
- VS Code extension (repo-wiki-browser)
- Local-first SQLite + ChromaDB storage
- Incremental update via git diff
- LLM provider abstraction (OpenAI-compatible, Minimax)
- 1200+ test cases

### Features

- `repo-wiki init` - Initialize repository index
- `repo-wiki index` - Build search index
- `repo-wiki generate` - Generate wiki documentation
- `repo-wiki verify` - Quality verification
- `repo-wiki update` - Incremental updates
- `repo-wiki search` - Semantic search
- `repo-wiki graph` - Module dependency graph
- `repo-wiki cost-estimate` - LLM cost estimation

[Unreleased]: https://github.com/bingooyong/repo-wiki-agent/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/bingooyong/repo-wiki-agent/releases/tag/v0.1.0