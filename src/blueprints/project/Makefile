.PHONY: install
install:
	pip install -U pip wheel
	poetry export --with dev,test -o requirements.txt
	pip install -r requirements.txt
	pip install -e ../proper
	make db
	npm install --no-audit --no-fund

.PHONY: db
db:
	proper db create_tables

.PHONY: test
test:
	pytest -x demo tests

.PHONY: lint
lint:
	flake8 demo tests

