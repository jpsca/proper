.PHONE: proper
proper:
	uv build ../proper
	cp ../proper/dist/proper*.whl .
	uv sync --upgrade-package proper

.PHONY: dbuild
dbuild:
	docker compose build --build-arg UID=$$(id -u) --build-arg GID=$$(id -g) --build-arg USER=$$(whoami)

.PHONY: dup
drun:
	docker compose up -d

.PHONY: ddown
ddown:
	docker compose down

.PHONY: dshell
dshell:
	docker compose exec dev bash

.PHONY: install
install:
	uv sync --group dev --group test

.PHONY: test
test:
	pytest -x app tests

.PHONY: lint
lint:
	ruff check .

.PHONY: lint-fix
lint-fix:
	ruff check . --fix