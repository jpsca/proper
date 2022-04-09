test:
	pytest -x proper tests

lint:
	flake8 --config=setup.cfg proper tests

coverage:
	pytest --cov-report html --cov proper --cov tests proper tests

install:
	pip install -U pip wheel
	pip install -e .[dev,test]
	pre-commit install
