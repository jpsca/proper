.PHONY: install
install:
	uv sync --group dev --group test
	# tailwindcss_install
	proper db migrate

.PHONY: test
test:
	pytest -x app tests

.PHONY: lint
lint:
	ruff check .
