.PHONY: install
install:
	uv sync --group dev --group test
	proper db migrate
	# tailwindcss_install

.PHONY: test
test:
	pytest -x app tests

.PHONY: lint
lint:
	ruff check .
