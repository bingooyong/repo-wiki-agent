# Contributing to repo-wiki

Thank you for your interest in contributing to repo-wiki!

## Getting Started

### Prerequisites

- Python 3.11+
- `uv` package manager

### Development Setup

```bash
# Clone the repository
git clone https://github.com/bingooyong/repo-agent.git
cd repo-agent

# Create virtual environment
uv venv .venv && source .venv/bin/activate

# Install in development mode
pip install -e "."
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=repo_wiki --cov-report=term-missing

# Run specific test file
pytest tests/test_cli.py -v
```

## Code Style

We use **Ruff** for linting and formatting:

```bash
# Check code style
ruff check .

# Format code
ruff format .
```

## Commit Messages

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

Types:
- feat: New feature
- fix: Bug fix
- docs: Documentation changes
- style: Code style changes (formatting, semicolons, etc)
- refactor: Code refactoring
- test: Adding or updating tests
- chore: Maintenance tasks

Examples:
feat(cli): add new generate command
fix(verifier): resolve strict verify false positive
docs(readme): update installation instructions
```

## Pull Request Process

1. **Fork** the repository and create a branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Write tests** for any new functionality

3. **Ensure tests pass**:
   ```bash
   pytest
   ruff check .
   ```

4. **Update documentation** if needed

5. **Push** to your fork and open a Pull Request

6. Fill in the PR template with:
   - Description of changes
   - Related issue (if applicable)
   - Testing performed

## Reporting Issues

- Use [GitHub Issues](../issues) for bug reports
- For security issues, see [SECURITY.md](SECURITY.md)
- Include version info and reproduction steps

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.