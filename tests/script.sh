set -e

# Lint Python
flake8 --max-line-length 119

# Lint Markdown
# MD013 Line length (breaking lines in paragraphs produces longer diffs)
# MD024 Multiple headers with the same content (see https://github.com/markdownlint/markdownlint/issues/175)
# MD033 Inline HTML (some files require HTML)
/tmp/bin/mdl --git-recurse --rules ~MD013,~MD024,~MD033 .

# Lint and indent JSON and JSON Schema
curl -s -S $BASEDIR/tests/test_json.py -o /tmp/test_json.py
py.test -rs /tmp/test_json.py
