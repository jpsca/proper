.PHONY: install
install:
	uv sync --group dev --group test
	pre-commit install

.PHONY: test
test:
	pytest -x src/proper tests

.PHONY: lint
lint:
	ruff check src/proper tests

.PHONY: coverage
coverage:
	pytest --cov-config=pyproject.toml --cov-report html --cov proper src/proper tests

.PHONY: types
types:
	pyright src/proper
