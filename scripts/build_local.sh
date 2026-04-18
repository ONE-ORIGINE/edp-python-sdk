#!/usr/bin/env bash
set -euo pipefail
python -m pip install --upgrade pip
pip install -e .[dev]
pytest
edp-release-check
python -m build
python -m twine check dist/*.whl dist/*.tar.gz
