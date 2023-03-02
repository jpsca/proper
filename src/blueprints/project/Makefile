.PHONY: install
install:
	poetry install --with dev,test
	poetry run pip install -e ../proper
	make db
	npm install --no-audit --no-fund

.PHONY: db
db:
	poetry run proper db create_tables

.PHONY: test
test:
	poetry run pytest -x demo tests

.PHONY: lint
lint:
	poetry run flake8 demo tests

