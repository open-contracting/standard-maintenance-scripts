#!/bin/bash
# This follows broadly the approach from
# http://www.kennethreitz.org/essays/a-better-pip-workflow but with the
# addition of requirements_dev

# This assumes that:
#
# * You have already installed the `virtualenv` package
# * You want a virtual environment in a `.ve` directory at the root of the repository
#
# If you instead prefer to use `pyenv`, etc., you will need to substitute different commands.
set -e

# Delete and re-create a fresh virtual environment, to eliminate any packages not specified in requirements files.
if [[ "$1" != "--skip-virtualenv" ]]; then
  rm -rf .ve
  virtualenv --python=python3 .ve
  source .ve/bin/activate
fi

# If you run this script with a `--new-only` option, then the versions of packages in `requirements.txt` will not be
# upgraded. Instead, only new packages from `requirements.in` and their dependencies will be installed.
if [[ "$1" == "--new-only" ]]; then
  dashupgrade=""
else
  dashupgrade="--upgrade"
fi

# It is important to use the `-r` option with `pip freeze` to preserve any comments and the order of requirements,
# in order to make it easy to compare changes to the requirements.txt file.
if [[ "$1" == "--new-only" ]]; then
  pip install -r requirements.txt
fi
pip install $dashupgrade -r requirements.in
pip freeze -r requirements.in > requirements.txt

# Same as above, but for `requirements_dev.*` and with `-r requirements.in`.
if [[ "$1" == "--new-only" ]]; then
  pip install -r requirements_dev.txt
fi
pip install $dashupgrade -r requirements_dev.in
pip freeze -r requirements.in -r requirements_dev.in > requirements_dev.txt

# macOS fails without `-i ''`, but Linux fails with it.
if [[ $(uname) == "Darwin" ]]; then
  INFIX=" ''"
else
  INFIX=
fi
# Remove lines that might occur in the *.txt files that cause problems.
eval sed -i$INFIX 's/^-r.*//' requirements.txt requirements_dev.txt
eval sed -i$INFIX 's/pkg-resources==0.0.0//' requirements.txt requirements_dev.txt
