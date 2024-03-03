.PHONY: lock
lock:
	uv pip compile --all-extras pyproject.toml -o requirements-dev.txt
	uv pip compile --extra=test pyproject.toml -o requirements-test.txt
	uv pip compile pyproject.toml -o requirements.txt

.PHONY: install
install: lock
	uv pip install -r requirements-dev.txt
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
