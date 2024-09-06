#!/bin/sh

set -eu

pip install flake8 flake8-comprehensions 'isort>=5' importlib-metadata 'jscc>=0.2' json-merge-patch \
    'jsonref>=1' jsonschema packaging 'pytest<8' 'ocdskit>=1' requests rfc3339-validator rfc3986-validator setuptools

curl -s -S --retry 3 -o /tmp/test_csv.py "$BASEDIR"/tests/test_csv.py
curl -s -S --retry 3 -o /tmp/test_json.py "$BASEDIR"/tests/test_json.py
curl -s -S --retry 3 -o /tmp/test_readme.py "$BASEDIR"/tests/test_readme.py
curl -s -S --retry 3 -o /tmp/test_requirements.py "$BASEDIR"/tests/test_requirements.py
