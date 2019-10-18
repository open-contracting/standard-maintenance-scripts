#!/bin/bash
# This follows broadly the approach from
# http://www.kennethreitz.org/essays/a-better-pip-workflow but with the
# addition of requirements_dev
#
# This assumes you want to use the virtualenv tool,
# and want to create a virtual environment called ".ve".
#
# If using a different process, please make sure to preserve the same "-r" option
# to freeze as here.
# This means it is easy to compare changes in lock files between commits and see
# what libraries have had their versions upgraded and which haven't.

# Delete and recreate a virtualenv to ensure that we don't have any extra
# packages installed in it
rm -rf .ve
virtualenv --python=python3 .ve
source .ve/bin/activate

if [[ "$1" == "--new-only" ]]; then
    # If --new-only is supplied then we install the current versions of
    # packages into the virtualenv, so that the only change will be any new
    # packages and their dependencies.
    pip install -r requirements.txt
    dashupgrade=""
else
    dashupgrade="--upgrade"
fi
pip install $dashupgrade -r requirements.in
pip freeze -r requirements.in > requirements.txt

# Same again for requirements_dev
if [[ "$1" == "--new-only" ]]; then
    pip install -r requirements_dev.txt
fi
pip install $dashupgrade -r requirements_dev.in
cat requirements.in requirements_dev.in > requirements_combined_tmp.in
pip freeze -r requirements_combined_tmp.in > requirements_dev.txt
rm requirements_combined_tmp.in

# Some cleanups needed to remove some things in the locked files that cause problems
sed -i 's/^-r.*//' requirements.txt requirements_dev.txt
sed -i 's/pkg-resources==0.0.0//' requirements.txt requirements_dev.txt
