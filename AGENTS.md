## About Proper

Proper is an opinionated, batteries-included Python web framework. It uses ASGI with sync Python controllers, Peewee ORM, Huey task queue, Jx components, and Formidable forms. Deep reference docs are bundled in the `proper` skill.

## General Guidelines

Before suggesting removal or simplification of existing configuration (editable installs, specific build steps, etc.), ask the user first. Do not proactively remove things that look unnecessary.

## Writing / Editing

After creating or updating a python file, run `uv run ruff check --fix ${file} 2>/dev/null || true` to fix any linting errors.

The docstrings are written in Markdown (not reStructuredText).

## Testing

Always run `uv run pytest` as the test runner command. Do not use `pytest` directly or any other test runner unless explicitly told otherwise.

When writing tests, use real filesystem and real objects instead of mocks unless it requires running separated service or asked to mock. Avoid unittest.mock patterns for integration-style tests.

Target 100% test coverage on all new and modified files. Run coverage checks after writing tests: `uv run pytest --cov=<module> --cov-report=term-missing`

When debugging test failures, check for framework-specific behaviors

## Dependencies

Use `uv add <package>` to add dependencies. Do not manually edit pyproject.toml for adding requirements.
