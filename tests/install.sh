set -e

# Python dependencies
pip install flake8 isort json-merge-patch jsonref jsonschema ocdskit 'pytest>=3.6' requests rfc3987 strict-rfc3339

# Ruby dependencies
gem install mdl
