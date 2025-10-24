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
	ty check

.PHONY: lintfix
lintfix:
	ruff check src/proper tests --fix

.PHONY: coverage
coverage:
	pytest --cov-config=pyproject.toml --cov-report html --cov proper src/proper tests

.PHONY: docs
docs:
	cd docs && python docs.py

.PHONY: docs-build
docs-build:
	cd docs && python docs.py build

.PHONY: docs-deploy
docs-deploy:
	cd docs && sh deploy.sh
