.PHONY: install
install:
	poetry install
	# tailwindcss_install
	proper db migrate

.PHONY: test
test:
	pytest -x app tests

.PHONY: lint
lint:
	ruff check .
