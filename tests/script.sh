set -e

flake8 --max-line-length 119

# MD013 Line length (breaking lines in paragraphs produces longer diffs)
# MD024 Multiple headers with the same content (see https://github.com/markdownlint/markdownlint/issues/175)
# MD033 Inline HTML (some files require HTML)
bin/mdl -r MD013,MD024,MD033

curl -s $BASEDIR/tests/test_json_format.py | py.test
