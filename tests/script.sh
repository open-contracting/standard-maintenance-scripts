#!/bin/bash

: "${CI:=}"
: "${GITHUB_REPOSITORY:=$PWD}"

if [ -n "$CI" ]; then
    set -xeu
else
    set -eu
fi

if [ -n "$CI" ]; then
    # Ignore version control, untracked files and executable scripts.
    find . -type f \! -perm 644 \! -path '*/.git/*' \! -path '*/.ruff_cache/*' \! -path '*/.tox/*' \
        \! -path '*/__pycache__/*' \! -path '*/cache/*' \! -path '*/node_modules/*' \! -path '*/venv/*' \
        \! -path '*/script/*' \! -name '*.sh' \! -name '*-cli' \! -name 'manage.py' \! -name 'run.py' \
        -o -type d \! -perm 755 \! -path '*/deploy/cache/*' | grep . && exit 1
fi

IGNORE=(
    RUF100 # Specific repositories can have stricter rules in pyproject.toml, with more noqa in files.

    # Duplicate
    ANN # annotation (mypy)

    # Incompatible
    # https://docs.astral.sh/ruff/linter/#rule-selection
    D203 # one-blank-line-before-class (D211 blank-line-before-class)
    D212 # multi-line-summary-first-line (D213 multi-line-summary-second-line)
    D415 # ends-in-punctuation (D400 ends-in-period)
    # https://docs.astral.sh/ruff/formatter/#conflicting-lint-rules
    COM812 # missing-trailing-comma (ruff format)
    ISC001 # single-line-implicit-string-concatenation (ruff format)
    Q000   # bad-quotes-inline-string (ruff format)

    # Complexity
    C901   # complex-structure
    PLR091 # too-many-...

    # Irrelevant
    CPY001 # missing-copyright-notice
    EM     # flake8-errmsg (nice backtrace)

    # Project-specific
    D
    DTZ
    PTH
    FIX002  # line-contains-todo
    PLR2004 # magic-value-comparison
    PLW2901 # redefined-loop-name
    TRY003  # raise-vanilla-args
)

PER_FILE_IGNORES=(
    # Command-line interfaces
    */commands/*:T201 # print
    __main__.py:T201  # print
    manage.py:T201    # print
    run.py:T201       # print

    # Migrations
    *migrations/*:E501   # line-too-long
    *migrations/*:INP001 # implicit-namespace-package

    # Notebooks
    *.ipynb:E501   # line-too-long
    *.ipynb:ERA001 # commented-out-code
    *.ipynb:F401   # unused-import
    *.ipynb:F821   # undefined-name

    # Namespace packages
    sphinxcontrib/*:INP001 # implicit-namespace-package

    # Settings
    */settings.py:ERA001 # commented-out-code

    # Tests
    test_*:S101 # [kingfisher-collect]
)

# The ignores for a Python project's documentation and tests. See add_project_ignores.
PROJECT_PER_FILE_IGNORES=(
    # Documentation
    docs/*:D100   # undocumented-public-module
    docs/*:INP001 # implicit-namespace-package

    # Tests
    tests/*:FBT003 # boolean-positional-value-in-call
    tests/*:INP001 # implicit-namespace-package
    tests/*:TRY003 # raise-vanilla-args (AssertionError)
    tests/*:S      # security
)

BUILTINS_IGNORELIST=("'placeholder'")

# Add ignores for the frameworks in a Python project's requirements file. The project is at the repository root, if
# the prefix is empty, or else in a subdirectory, like a Django app in a monorepo, whose ignores are scoped to it.
# Ruff's per-file-ignores patterns are relative to the repository root, and "*" matches "/".
add_framework_ignores() {
    local file=$1 prefix=$2 rules=() patterns=() rule pattern

    if grep babel "$file" > /dev/null; then
        rules+=(
            # https://babel.pocoo.org/en/latest/api/messages/extract.html#language-parsing
            ARG001 # unused-function-argument
        )
    fi
    if grep click "$file" > /dev/null; then
        rules+=(
            # https://click.palletsprojects.com/en/8.1.x/options/#callbacks-for-validation
            ARG001 # unused-function-argument
            ARG002 # unused-method-argument
        )
    fi
    if grep django "$file" > /dev/null; then
        rules+=(
            PT    # pytest
            DJ008 # django-model-without-dunder-str
            S308  # suspicious-mark-safe-usage (false positive)
        )
        patterns+=(
            manage.py:PLC0415 # import-outside-top-level
            # signals.py  https://docs.djangoproject.com/en/stable/topics/signals/
            # views.py    https://docs.djangoproject.com/en/stable/topics/http/views/
            # migrations/ https://docs.djangoproject.com/en/stable/howto/writing-migrations/
            {*/signals,*/views,*/migrations/*}.py:ARG001 # unused-function-argument
            # admin.py    https://docs.djangoproject.com/en/stable/ref/contrib/admin/#modeladmin-methods
            # routers.py  https://docs.djangoproject.com/en/stable/topics/db/multi-db/#an-example
            # views.py    https://docs.djangoproject.com/en/stable/topics/class-based-views/
            # commands.py https://docs.djangoproject.com/en/stable/howto/custom-management-commands/
            {*/admin,*/routers,*/views,*/commands/*}.py:ARG002 # unused-method-argument
            # admin.py    https://docs.djangoproject.com/en/stable/ref/contrib/admin/
            # forms.py    https://docs.djangoproject.com/en/stable/topics/forms/modelforms/
            # models.py   https://docs.djangoproject.com/en/stable/ref/models/options/
            # migrations/ https://docs.djangoproject.com/en/stable/topics/migrations/#migration-files
            # tests/      https://docs.djangoproject.com/en/stable/topics/db/fixtures/#how-to-use-a-fixture
            {*/admin,*/forms,*/models,*/routers,*/migrations/*,tests/*}.py:RUF012 # mutable-class-default
        )
        BUILTINS_IGNORELIST+=(
            "'id'" # path component
        )
    fi
    if grep django-modeltranslation "$file" > /dev/null; then
        patterns+=(
            # translation.py https://django-modeltranslation.readthedocs.io/en/latest/registration.html#required-langs
            */translation.py:RUF012
        )
    fi
    if grep djangorestframework "$file" > /dev/null; then
        patterns+=(
            # serializers.py https://www.django-rest-framework.org/api-guide/serializers/#modelserializer
            # views.py       https://www.django-rest-framework.org/api-guide/viewsets/
            */{serializers,views}.py:RUF012
        )
        BUILTINS_IGNORELIST+=(
            # https://www.django-rest-framework.org/api-guide/format-suffixes/
            "'format'"
        )
    fi
    if grep fastapi "$file" > /dev/null; then
        rules+=(
            # https://fastapi.tiangolo.com/reference/dependencies/
            ARG001 # unused-function-argument
        )
        BUILTINS_IGNORELIST+=(
            "'id'" # path component
        )
    fi
    if grep pika "$file" > /dev/null; then
        rules+=(
            # https://pika.readthedocs.io/en/stable/modules/channel.html
            ARG002 # unused-method-argument
        )
    fi
    if grep pandas "$file" > /dev/null; then
        rules+=(
            PD008 # pandas-use-of-dot-at
        )
    fi
    if grep scrapy "$file" > /dev/null; then
        rules+=(
            # https://docs.scrapy.org/en/latest/topics/spiders.html#spider-arguments
            ARG002 # unused-method-argument
            # https://docs.scrapy.org/en/latest/topics/spiders.html#scrapy.Spider
            RUF012 # mutable-class-default
        )
    fi
    if grep sphinx "$file" > /dev/null; then
        rules+=(
            # https://www.sphinx-doc.org/en/master/development/tutorials/extending_build.html
            ARG001 # unused-function-argument
            # https://www.sphinx-doc.org/en/master/extdev/appapi.html#sphinx.application.Sphinx.add_directive
            RUF012 # mutable-class-default
        )
    fi

    for rule in ${rules[@]+"${rules[@]}"}; do
        if [ -z "$prefix" ]; then
            IGNORE+=("$rule")
        else
            PER_FILE_IGNORES+=("$prefix*:$rule")
        fi
    done
    for pattern in ${patterns[@]+"${patterns[@]}"}; do
        PER_FILE_IGNORES+=("$prefix$pattern")
    done
}

# Add ignores for a Python project's documentation, tests and frameworks. The directory and prefix are as for
# add_framework_ignores.
add_project_ignores() {
    local directory=$1 prefix=$2 pattern

    for pattern in "${PROJECT_PER_FILE_IGNORES[@]}"; do
        PER_FILE_IGNORES+=("$prefix$pattern")
    done
    if [ -d "$directory/docs" ]; then
        BUILTINS_IGNORELIST+=("'copyright'")
    fi
    # unused-function-argument (fixtures)
    if [ -f "$directory/MANIFEST.in" ]; then
        PER_FILE_IGNORES+=("${prefix}tests/*:ARG001")
    fi
    if [ -f "$directory/requirements_dev.txt" ] && grep pytest "$directory/requirements_dev.txt" > /dev/null; then
        PER_FILE_IGNORES+=("${prefix}tests/*:ARG001" "${prefix}test_*:ARG001")
    fi
    if [ -f "$directory/common-requirements.txt" ] && grep pytest "$directory/common-requirements.txt" > /dev/null; then
        PER_FILE_IGNORES+=("${prefix}tests/*:ARG001")
    fi

    # A requirements.txt is preferred to a pyproject.toml.
    if [ -f "$directory/requirements.txt" ]; then
        add_framework_ignores "$directory/requirements.txt" "$prefix"
    elif [ -f "$directory/pyproject.toml" ]; then
        add_framework_ignores "$directory/pyproject.toml" "$prefix"
    fi
}

add_project_ignores . ""
# A docs/requirements.txt is skipped, as it is for ReadTheDocs. Glob metacharacters in the prefix are escaped, like
# cookiecutter's "{{" and "}}".
while IFS= read -r directory; do
    add_project_ignores "$directory" "$(printf '%s/' "$directory" | sed 's/[][{}*?]/\\&/g')"
done < <(git ls-files '*/requirements.txt' '*/pyproject.toml' 2> /dev/null | sed 's|/[^/]*$||' | sort -u | grep -v '\(^\|/\)docs$')

case "${GITHUB_REPOSITORY##*/}" in
jscc | ocds-merge | standard-maintenance-scripts | standard)
    IGNORE+=(B028) # no-explicit-stacklevel
    ;;
deploy)
    IGNORE+=(EXE003) # shebang-missing-python
    ;;
pelican-backend)
    IGNORE+=(ERA001)                   # commented-out-code
    PER_FILE_IGNORES+=(tests/*:RUF012) # mutable-class-default
    ;;
pelican-frontend)
    IGNORE+=(ARG001 RUF012) # unused-function-argument mutable-class-default
    BUILTINS_IGNORELIST+=("'type'")
    ;;
yapw)
    PER_FILE_IGNORES+=(tests/fixtures/*:T201) # print
    ;;
esac

ruff check . --select ALL \
    --ignore "$(
        IFS=,
        echo "${IGNORE[*]}"
    )" \
    --per-file-ignores "$(
        IFS=,
        echo "${PER_FILE_IGNORES[*]}"
    )" \
    --config "lint.flake8-builtins.builtins-ignorelist = [$(
        IFS=,
        echo "${BUILTINS_IGNORELIST[*]}"
    )]" \
    --config "lint.allowed-confusables = ['’']" \
    --config 'line-length = 119' \
    --exclude 'demo_docs,t'

if [ -n "$CI" ]; then
    pytest -rs /tmp/test_csv.py /tmp/test_json.py /tmp/test_readme.py # test_requirements.py is opt-in
fi
