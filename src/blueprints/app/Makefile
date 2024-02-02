.PHONY: install
install:
	poetry install --with dev,test
	pip install -e ../proper
	npm install --no-audit --no-fund
	bin/proper db migrate

.PHONY: test
test:
	pytest -x demo tests

.PHONY: lint
lint:
	ruff check .
