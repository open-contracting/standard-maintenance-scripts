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

REQUIREMENTS_FILE=""
if [ -f requirements.txt ]; then
    REQUIREMENTS_FILE=requirements.txt
elif [ -f pyproject.toml ]; then
    REQUIREMENTS_FILE=pyproject.toml
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
    EM      # flake8-errmsg (nice backtrace)
    PERF203 # try-except-in-loop ("Why is this bad?" https://docs.astral.sh/ruff/rules/try-except-in-loop/)

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

    # Documentation
    docs/*:D100   # undocumented-public-module
    docs/*:INP001 # implicit-namespace-package

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
    tests/*:FBT003 # boolean-positional-value-in-call
    tests/*:INP001 # implicit-namespace-package
    tests/*:TRY003 # raise-vanilla-args (AssertionError)
    tests/*:S      # security
    test_*:S101    # [credere-backend, kingfisher-collect]
)

BUILTINS_IGNORELIST=("'placeholder'")

if [ -n "$REQUIREMENTS_FILE" ]; then
    if grep babel $REQUIREMENTS_FILE > /dev/null; then
        IGNORE+=(
            # https://babel.pocoo.org/en/latest/api/messages/extract.html#language-parsing
            ARG001 # unused-function-argument
        )
    fi
    if grep click $REQUIREMENTS_FILE > /dev/null; then
        IGNORE+=(
            # https://click.palletsprojects.com/en/8.1.x/options/#callbacks-for-validation
            ARG001 # unused-function-argument
            ARG002 # unused-method-argument
        )
    fi
    if grep django $REQUIREMENTS_FILE > /dev/null; then
        IGNORE+=(
            PT    # pytest
            DJ008 # django-model-without-dunder-str
            S308  # suspicious-mark-safe-usage (false positive)
        )
        PER_FILE_IGNORES+=(
            # signals.py  https://docs.djangoproject.com/en/4.2/topics/signals/
            # views.py    https://docs.djangoproject.com/en/4.2/topics/http/views/
            # migrations/ https://docs.djangoproject.com/en/4.2/howto/writing-migrations/
            {*/signals,*/views,*/migrations/*}.py:ARG001 # unused-function-argument
            # admin.py    https://docs.djangoproject.com/en/4.2/ref/contrib/admin/#modeladmin-methods
            # routers.py  https://docs.djangoproject.com/en/4.2/topics/db/multi-db/#an-example
            # views.py    https://docs.djangoproject.com/en/4.2/topics/class-based-views/
            # commands.py https://docs.djangoproject.com/en/4.2/howto/custom-management-commands/
            {*/admin,*/routers,*/views,*/commands/*}.py:ARG002 # unused-method-argument
            # admin.py    https://docs.djangoproject.com/en/4.2/ref/contrib/admin/
            # forms.py    https://docs.djangoproject.com/en/4.2/topics/forms/modelforms/
            # models.py   https://docs.djangoproject.com/en/4.2/ref/models/options/
            # migrations/ https://docs.djangoproject.com/en/4.2/topics/migrations/#migration-files
            # tests/      https://docs.djangoproject.com/en/4.2/topics/db/fixtures/#how-to-use-a-fixture
            {*/admin,*/forms,*/models,*/routers,*/serializers,*/translation,*/migrations/*,tests/*}.py:RUF012 # mutable-class-default
        )
        BUILTINS_IGNORELIST+=(
            "'id'" # path component
        )
    fi
    if grep django-modeltranslation $REQUIREMENTS_FILE > /dev/null; then
        PER_FILE_IGNORES+=(
            # translation.py https://django-modeltranslation.readthedocs.io/en/latest/registration.html#required-langs
            */translation.py:RUF012
        )
    fi
    if grep djangorestframework $REQUIREMENTS_FILE > /dev/null; then
        PER_FILE_IGNORES+=(
            # serializers.py https://www.django-rest-framework.org/api-guide/serializers/#modelserializer
            # views.py       https://www.django-rest-framework.org/api-guide/viewsets/
            */{serializers,views}.py:RUF012
        )
        BUILTINS_IGNORELIST+=(
            # https://www.django-rest-framework.org/api-guide/format-suffixes/
            "'format'"
        )
    fi
    if grep fastapi $REQUIREMENTS_FILE > /dev/null; then
        IGNORE+=(
            # https://fastapi.tiangolo.com/reference/dependencies/
            ARG001 # unused-function-argument
        )
        BUILTINS_IGNORELIST+=(
            "'id'" # path component
        )
    fi
    if grep pika $REQUIREMENTS_FILE > /dev/null; then
        IGNORE+=(
            # https://pika.readthedocs.io/en/stable/modules/channel.html
            ARG002 # unused-method-argument
        )
    fi
    if grep pandas $REQUIREMENTS_FILE > /dev/null; then
        IGNORE+=(
            PD008 # pandas-use-of-dot-at
            PD901 # pandas-df-variable-name
        )
    fi
    if grep scrapy $REQUIREMENTS_FILE > /dev/null; then
        IGNORE+=(
            # https://docs.scrapy.org/en/latest/topics/spiders.html#spider-arguments
            ARG002 # unused-method-argument
            # https://docs.scrapy.org/en/latest/topics/spiders.html#scrapy.Spider
            RUF012 # mutable-class-default
        )
    fi
    if grep sphinx $REQUIREMENTS_FILE > /dev/null; then
        IGNORE+=(
            # https://www.sphinx-doc.org/en/master/development/tutorials/extending_build.html
            ARG001 # unused-function-argument
            # https://www.sphinx-doc.org/en/master/extdev/appapi.html#sphinx.application.Sphinx.add_directive
            RUF012 # mutable-class-default
        )
    fi
fi
if [ -d docs ]; then
    BUILTINS_IGNORELIST+=(
        "'copyright'"
    )
fi
if [ ! -f .python-version ]; then # Packages support Python 3.9.
    IGNORE+=(
        UP038 # non-pep604-isinstance (Python 3.10+)
    )
fi
if [ ! -f .python-version ] || grep 3.10 .python-version > /dev/null; then
    IGNORE+=(
        PYI024 # collections-named-tuple (Python 3.11+)
    )
fi
if [ -f MANIFEST.in ]; then
    PER_FILE_IGNORES+=(
        tests/*:ARG001 # unused-function-argument (fixtures)
    )
fi
if [ -f requirements_dev.txt ]; then
    if grep pytest requirements_dev.txt > /dev/null; then
        PER_FILE_IGNORES+=(
            tests/*:ARG001 test_*:ARG001 # unused-function-argument (fixtures)
        )
    fi
fi
if [ -f common-requirements.txt ]; then
    if grep pytest common-requirements.txt > /dev/null; then
        PER_FILE_IGNORES+=(
            tests/*:ARG001 # unused-function-argument (fixtures)
        )
    fi
fi

case "${GITHUB_REPOSITORY##*/}" in
jscc | ocds-merge | sample-data | standard-maintenance-scripts | standard)
    IGNORE+=(B028) # no-explicit-stacklevel
    ;;
credere-backend)
    BUILTINS_IGNORELIST+=("'type'")
    ;;
deploy)
    IGNORE+=(EXE003) # shebang-missing-python
    ;;
pelican-backend)
    IGNORE+=(ERA001) # commented-out-code
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
    pytest -rs --tb=line /tmp/test_csv.py /tmp/test_json.py /tmp/test_readme.py # test_requirements.py is opt-in
fi
