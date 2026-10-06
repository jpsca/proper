## About Proper

Proper is an opinionated, batteries-included Python web framework. It runs only on free-threaded Python (3.14t and later) and serves WSGI through Granian. Controllers are synchronous, with no `async`/`await`. It uses Peewee ORM, Huey task queue, minijx components, and Formidable forms. WebSockets are served by WseCable, with `proper-wse`, which the channels addon adds to the app's dependencies. Deep reference docs are bundled in the `proper` skill (`skills/proper/`).

## General Guidelines

Before suggesting removal or simplification of existing configuration (editable installs, specific build steps, etc.), ask the user first. Do not proactively remove things that look unnecessary.

## Writing / Editing

Unless done to avoid recursive imports, place all the imports at the beginning of the file.

After creating or updating a python file, run `uv run ruff check --fix ${file} 2>/dev/null || true` to fix any linting errors.

The docstrings are written in Markdown (not reStructuredText).

## Testing

Always run `uv run pytest` as the test runner command. Do not use `pytest` directly or any other test runner unless explicitly told otherwise.

When writing tests, use the real filesystem and real objects instead of mocks, unless the test needs a separate running service or you are asked to mock. Avoid unittest.mock patterns for integration-style tests.

Target 100% test coverage on all new and modified files. Run coverage checks after writing tests: `uv run pytest --cov=<module> --cov-report=term-missing`

When debugging test failures, check for framework-specific behaviors.

## Documentation

When a change alters user-visible behavior, update in the same commit:
- `CHANGELOG.md`
- the human docs in `docs/content/`
- the agent docs in `skills/proper/`

## Dependencies

Use `uv add <package>` to add dependencies. Do not manually edit pyproject.toml for adding requirements.
