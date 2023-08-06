.PHONY: install
install:
	poetry install --with dev,test
	pip install -e ../proper
	make db
	npm install --no-audit --no-fund

.PHONY: db
db:
	bin/proper db create
	bin/proper db upgrade

.PHONY: test
test:
	pytest -x demo tests

.PHONY: lint
lint:
	flake8 demo tests

