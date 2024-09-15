#!/bin/bash

# shellcheck disable=SC2269
CI="$CI"

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

BUILTINS_IGNORELIST=(
    "'type'" # [credere-backend, pelican-frontend]
)

IGNORE=(
    # Project-specific
    ANN
    D
    DTZ
    PTH
    PLR2004 # magic-value-comparison
    PLW2901 # redefined-loop-name
    S607    # start-process-with-partial-path
    # Error handling
    B028   # no-explicit-stacklevel (nice warnings)
    TRY003 # raise-vanilla-args (nice errors)
    # False positives
    S603 # subprocess-without-shell-equals-true
    # Unique issues
    EXE003 # shebang-missing-python [deploy]

    # Duplicate https://docs.astral.sh/ruff/formatter/#conflicting-lint-rules
    FIX002 # line-contains-todo (TD003 missing-todo-link)
    COM812 # missing-trailing-comma (ruff format)
    Q000   # bad-quotes-inline-string (ruff format)

    # Complexity
    C901   # complex-structure
    PLR091 # too-many-...

    # Irrelevant
    EM      # flake8-errmsg (nice backtrace)
    PERF203 # try-except-in-loop ("Why is this bad?" https://docs.astral.sh/ruff/rules/try-except-in-loop/)
)
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
            # https://docs.djangoproject.com/en/4.2/topics/http/views/
            ARG001 # unused-function-argument
            # https://docs.djangoproject.com/en/4.2/topics/class-based-views/
            ARG002 # unused-method-argument
            # https://docs.djangoproject.com/en/4.2/ref/models/options/#constraints
            # https://docs.djangoproject.com/en/4.2/ref/models/options/#indexes
            # https://docs.djangoproject.com/en/4.2/topics/forms/modelforms/
            # https://docs.djangoproject.com/en/4.2/topics/migrations/#migration-files
            # https://docs.djangoproject.com/en/4.2/topics/db/multi-db/#an-example
            # https://docs.djangoproject.com/en/4.2/topics/db/fixtures/#how-to-use-a-fixture
            # https://www.django-rest-framework.org/api-guide/serializers/#modelserializer
            RUF012 # mutable-class-default
            # https://docs.djangoproject.com/en/4.2/ref/models/meta/
            SLF001 # private-member-access
        )
        BUILTINS_IGNORELIST+=(
            "'id'" # path component
        )
    fi
    if grep djangorestframework $REQUIREMENTS_FILE > /dev/null; then
        BUILTINS_IGNORELIST+=(
            # https://www.django-rest-framework.org/api-guide/format-suffixes/
            "'format'"
        )
    fi
    if grep fastapi $REQUIREMENTS_FILE > /dev/null; then
        IGNORE+=(
            # https://fastapi.tiangolo.com/reference/dependencies/
            ARG001 # unused-function-argument
            B008   # function-call-in-default-argument
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

PER_FILE_IGNORES=(
    # Command-line interfaces
    __main__.py:T201  # print
    manage.py:T201    # print
    run.py:T201       # print
    */commands/*:T201 # print

    # Documentation
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
    tests/*:INP001 # implicit-namespace-package
    tests/*:FBT003 # boolean-positional-value-in-call
    tests/*:RUF012 # mutable-class-default
    tests/*:S      # security
    test_*:S       # [kingfisher-collect]

    # Fixtures
    */fixtures/*:INP001 # implicit-namespace-package
    */fixtures/*:T201   # print [yapw]
)
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

ruff check . --select ALL \
    --ignore "$(
        IFS=,
        echo "${IGNORE[*]}"
    )" \
    --per-file-ignores "$(
        IFS=,
        echo "${PER_FILE_IGNORES[*]}"
    )" \
    --config 'line-length = 119' \
    --config "lint.allowed-confusables = ['’']" \
    --config "lint.flake8-builtins.builtins-ignorelist = [$(
        IFS=,
        echo "${BUILTINS_IGNORELIST[*]}"
    )]" \
    --config 'lint.flake8-self.extend-ignore-names = ["_job"]' \
    --exclude 'demo_docs,t'

if [ -n "$CI" ]; then
    pytest -rs --tb=line /tmp/test_csv.py /tmp/test_json.py /tmp/test_readme.py # test_requirements.py is opt-in
fi
