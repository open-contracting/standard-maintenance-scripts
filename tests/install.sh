set -e

# Python dependencies
pip install flake8 isort json-merge-patch ocdskit
pip install -e git+https://github.com/open-contracting/jscc.git@f2739ccc7fb1422330b9af8bfe7a850059e2a91a#egg=jscc


# Ruby dependencies
# gem install mdl
