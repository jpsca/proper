.PHONY: install
install:
	uv sync --group dev --group test
	proper db migrate

.PHONY: test
test:
	pytest -x app tests

.PHONY: lint
lint:
	ruff check .

.PHONY: lintfix
lintfix:
	ruff check . --fix