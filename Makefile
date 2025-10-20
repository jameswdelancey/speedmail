.PHONY: run test format lint install

PYTHON := python3

run: install
	$(PYTHON) app.py

test: install
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py'

format:
	isort .
	black .

lint: install
	mypy .
	flake8 --ignore=E302,E305,E501

install:
	$(PYTHON) -m pip install --requirement requirements.txt
