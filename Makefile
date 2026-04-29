.PHONY: lint test coverage

lint:
	python -m pylint check_sensorProbe2plus.py
test:
	python -m unittest -v test_check_sensorProbe2plus.py
coverage:
	python -m coverage run -m unittest -b test_check_sensorProbe2plus.py
	python -m coverage report -m --include check_sensorProbe2plus.py
