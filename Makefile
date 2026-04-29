.PHONY: lint

lint:
	python -m pylint check_sensorProbe2plus.py --disable=invalid-name
