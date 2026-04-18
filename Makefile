.PHONY: test audit build

test:
	pytest

audit:
	edp-release-check

build:
	python -m build
	python -m twine check dist/*.whl dist/*.tar.gz
