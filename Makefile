.PHONY: install
install:
	uv sync --all-groups

.PHONY: test
test:
	uv run pytest -x src/proper tests

.PHONY: lint
lint:
	uv run ruff check src/proper tests
	uv run ty check

.PHONY: lintfix
lintfix:
	uv run ruff check src/proper tests --fix

.PHONY: coverage
coverage:
	uv run pytest --cov-config=pyproject.toml --cov-report html --cov proper src/proper tests

.PHONY: docs
docs:
	uv run python docs/docs.py

.PHONY: docs-build
docs-build:
	uv run python docs/docs.py build

.PHONY: docs-deploy
docs-deploy:
	rm -rf docs/build
	uv run python docs/docs.py build
	zip -r docs/build/skill.zip skills/proper -x "*.DS_Store"
	rsync --recursive --delete --progress docs/build code:/var/www/properproject/
