.PHONY: run test format lint

run:
	python app.py

test:
	python -m unittest discover -s tests -p 'test_*.py'

format:
	isort .
	black .

lint:
	mypy .
	flake8 --ignore=E501
