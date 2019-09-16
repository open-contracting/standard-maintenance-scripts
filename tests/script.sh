set -e

# Lint Python
flake8 --max-line-length 119

# Lint Markdown
# See https://github.com/open-contracting/standard-maintenance-scripts/issues/26
# See https://ocds-standard-development-handbook.readthedocs.io/en/latest/coding/
# curl -s -S -o /tmp/mdlrc.rb $BASEDIR/fixtures/mdlrc.rb
# /tmp/bin/mdl --git-recurse --style /tmp/mdlrc.rb .

# Validate CSV, JSON and JSON Schema
curl -s -S --retry 3 -o /tmp/test_csv.py $BASEDIR/tests/test_csv.py
curl -s -S --retry 3 -o /tmp/test_json.py $BASEDIR/tests/test_json.py
curl -s -S --retry 3 -o /tmp/test_readme.py $BASEDIR/tests/test_readme.py
py.test -rs --tb=line /tmp/test_csv.py /tmp/test_json.py /tmp/test_readme.py
