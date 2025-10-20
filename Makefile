.PHONY: run test format lint

PYTHON := python3

run:
	$(PYTHON) app.py

test:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py'

format:
	isort .
	black .

lint:
	mypy .
	flake8 --ignore=E302,E305,E501
