.PHONY: install
install:
	poetry install --with dev,test
	tailwindcss_install
	pip install -e ../proper
	bin/proper db migrate

.PHONY: test
test:
	pytest -x demo tests

.PHONY: lint
lint:
	ruff check .
