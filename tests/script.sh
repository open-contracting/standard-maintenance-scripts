set -e

# Lint Python
flake8 --max-line-length 119

# Lint Markdown
# See https://github.com/open-contracting/standard-maintenance-scripts/issues/26
# See http://ocds-standard-development-handbook.readthedocs.io/en/latest/coding/
# curl -s -S -o /tmp/mdlrc.rb $BASEDIR/fixtures/mdlrc.rb
# /tmp/bin/mdl --git-recurse --style /tmp/mdlrc.rb .

# Validate JSON and JSON Schema
curl -s -S -o /tmp/test_json.py $BASEDIR/tests/test_json.py
py.test -rs /tmp/test_json.py
