# Agent Guide

This document provides instructions for agents on how to maintain code quality and run tests in this project.

## Code Quality (Ruff)

We use [Ruff](https://astral.sh/ruff) for linting and formatting. It's configured in [ruff.toml](ruff.toml).

### Linting
To check for linting errors without fixing them:
```powershell
uvx ruff check .
```

To automatically fix safe errors:
```powershell
uvx ruff check . --fix
```

### Formatting
To format the codebase:
```powershell
uvx ruff format .
```

### Pre-commit
We use `pre-commit` to ensure code quality before commits. You can run all hooks manually:
```powershell
uv run pre-commit run -a
```

## Testing (Pytest)

We use [pytest](https://docs.pytest.org/) for unit and integration tests.

### Running all tests
```powershell
uv run pytest
```

### Running specific tests
You can target specific directories or files:
```powershell
# Run unit tests
uv run pytest tests/unit

# Run a specific file
uv run pytest tests/unit/core/recognition/test_recognizer.py
```

### Useful Pytest flags
- `-v`: Verbose output.
- `-s`: Show stdout/stderr during test execution.
- `-k "text"`: Run tests with names matching the expression.
