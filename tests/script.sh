#!/bin/sh

set -xeu

# Ignore version control, untracked files and executable scripts.
find . -type f \! -perm 644 \! -path '*/.git/*' \! -path '*/.ruff_cache/*' \! -path '*/.tox/*' \
    \! -path '*/__pycache__/*' \! -path '*/cache/*' \! -path '*/node_modules/*' \! -path '*/venv/*' \
    \! -path '*/script/*' \! -name '*.sh' \! -name '*-cli' \! -name 'manage.py' \! -name 'run.py' \
    -o -type d \! -perm 755 \! -path '*/deploy/cache/*' | grep . && exit 1

ruff check . --select E,C4,F,I,W --config "line-length = 119"

pytest -rs --tb=line /tmp/test_csv.py /tmp/test_json.py /tmp/test_readme.py # test_requirements.py is opt-in
