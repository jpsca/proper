.PHONY: install
install:
	uv sync --group dev --group test
	uv run pre-commit install

.PHONY: test
test:
	pytest -x src/proper tests

.PHONY: tests
tests:
	make test

.PHONY: lint
lint:
	ruff check src/proper tests

.PHONY: lintfix
lintfix:
	ruff check src/proper tests --fix

.PHONY: coverage
coverage:
	pytest --cov-config=pyproject.toml --cov-report html --cov proper src/proper tests

.PHONY: types
types:
	pyright src/proper
