#!/bin/sh

set -eu

pip install ruff jscc json-merge-patch jsonref jsonschema ocdskit packaging pytest requests rfc3339-validator \
    rfc3986-validator setuptools tomli # Python 3.10 or less

curl -s -S --retry 3 -o /tmp/test_csv.py "$BASEDIR"/tests/test_csv.py
curl -s -S --retry 3 -o /tmp/test_json.py "$BASEDIR"/tests/test_json.py
curl -s -S --retry 3 -o /tmp/test_readme.py "$BASEDIR"/tests/test_readme.py
curl -s -S --retry 3 -o /tmp/test_requirements.py "$BASEDIR"/tests/test_requirements.py
