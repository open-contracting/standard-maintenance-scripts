#!/bin/sh

set -eu

pip install flake8 flake8-comprehensions 'isort>=5' importlib-metadata 'jscc>=0.2' json-merge-patch \
    'jsonref>=1' jsonschema packaging 'pytest<8' 'ocdskit>=1' requests rfc3339-validator rfc3986-validator setuptools
