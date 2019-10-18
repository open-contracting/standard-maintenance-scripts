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

# Delete and re-create a fresh virtual environment, to eliminate any packages not specified in requirements files.
rm -rf .ve
virtualenv --python=python3 .ve
source .ve/bin/activate

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

# Same as above for requirements_dev.*.
if [[ "$1" == "--new-only" ]]; then
    pip install -r requirements_dev.txt
fi
pip install $dashupgrade -r requirements_dev.in
pip freeze -r requirements.in -r requirements_dev.in > requirements_dev.txt

# The following commands work on Linux only. macOS fails without `-i""`, but Linux fails with `-i""`.

# Remove lines that might occur in the *.txt files that cause problems.
sed -i 's/^-r.*//' requirements.txt requirements_dev.txt
sed -i 's/pkg-resources==0.0.0//' requirements.txt requirements_dev.txt
