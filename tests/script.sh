#!/bin/sh

set -xeu

# Ignore version control, untracked files and executable scripts.
find . -type f \! -perm 644 \! -path '*/.git/*' \! -path '*/.ruff_cache/*' \! -path '*/.tox/*' \
    \! -path '*/__pycache__/*' \! -path '*/cache/*' \! -path '*/node_modules/*' \! -path '*/venv/*' \
    \! -path '*/script/*' \! -name '*.sh' \! -name '*-cli' \! -name 'manage.py' \! -name 'run.py' \
    -o -type d \! -perm 755 \! -path '*/deploy/cache/*' | grep . && exit 1

flake8 . --max-line-length 119 --extend-ignore E203,E501,W505

isort . --check-only --line-width 119 --profile black

curl -s -S --retry 3 -o /tmp/test_csv.py "$BASEDIR"/tests/test_csv.py
curl -s -S --retry 3 -o /tmp/test_json.py "$BASEDIR"/tests/test_json.py
curl -s -S --retry 3 -o /tmp/test_readme.py "$BASEDIR"/tests/test_readme.py
curl -s -S --retry 3 -o /tmp/test_requirements.py "$BASEDIR"/tests/test_requirements.py
pytest -rs --tb=line /tmp/test_csv.py /tmp/test_json.py /tmp/test_readme.py # test_requirements.py is opt-in
