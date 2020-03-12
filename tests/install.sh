set -e

# Python dependencies
pip install flake8 isort json-merge-patch ocdskit requests
pip install -e git+https://github.com/open-contracting/jscc.git#egg=jscc


# Ruby dependencies
# gem install mdl
