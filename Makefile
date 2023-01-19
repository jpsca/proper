.PHONY: install
install:
	poetry install --with dev,test
	poetry run pre-commit install

.PHONY: test
test:
	poetry run pytest -x src/proper tests

.PHONY: lint
lint:
	poetry run flake8 src/proper tests

.PHONY: coverage
coverage:
	poetry run pytest --cov-config=pyproject.toml --cov-report html --cov proper src/proper tests

.PHONY: types
types:
	poetry run pyright src/proper
