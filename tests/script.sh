set -e

flake8 --max-line-length 119

# Repositories using tox run isort independently.
if ! [ -x "$(command -v tox)" ]; then
  isort --check-only --ignore-whitespace --line-width 119
fi

curl -s -S --retry 3 -o /tmp/test_csv.py $BASEDIR/tests/test_csv.py
curl -s -S --retry 3 -o /tmp/test_json.py $BASEDIR/tests/test_json.py
curl -s -S --retry 3 -o /tmp/test_readme.py $BASEDIR/tests/test_readme.py
py.test -rs --tb=line /tmp/test_csv.py /tmp/test_json.py /tmp/test_readme.py
