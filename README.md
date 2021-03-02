# Standard maintenance scripts

Tasks that should be run manually periodically have a ⏰ icon.

## Setup

    pip install -r requirements.txt
    bundle

To run the Rake tasks:

* [Create a GitHub personal access token](https://github.com/settings/tokens) with the scopes `public_repo` and `admin:org`
* [Edit your `~/.netrc` file](https://github.com/octokit/octokit.rb#using-a-netrc-file) using the token as your password

To list all available tasks:

    ./manage.py
    bundle exec rake -AT

## Tests

The common [`.github/workflows/lint.yml`](fixtures/lint.yml) file performs:

* Linting of:
  * Python ([flake8](https://pypi.python.org/pypi/flake8), [isort](https://pypi.org/project/isort/))
  * JSON (readable by Python)
  * CSV (readable by Python)
* Various checks against OCDS schema, codelists, readmes, etc.

To run the tests locally, run the setup commands above, change into a repository's folder, then:

    flake8 . --max-line-length 119
    isort . --check-only --ignore-whitespace --line-width 119
    pytest -rs --tb=line path/to/standard-maintenance-scripts/tests

To skip the JSON indentation test, set the `OCDS_NOINDENT` environment variable, with `export OCDS_NOINDENT=1` (Bash) or `setenv OCDS_NOINDENT 1` (fish).

To create a pull request to set up a new repository, run:

    git checkout -b ci
    mkdir -p .github/workflows
    curl -o .github/workflows/lint.yml https://raw.githubusercontent.com/open-contracting/standard-maintenance-scripts/main/fixtures/lint.yml
    git add .github/workflows/lint.yml
    git commit .github/workflows/lint.yml -m 'Add .github/workflows/lint.yml'
    git push -u origin ci

## Access tasks ⏰

### GitHub

Lists members that should be added or removed from the organization:

    bundle exec rake org:members

Lists owners that should be added or removed from the organization:

    bundle exec rake org:owners

Removes admin access to specific repositories from non-admin members:

    bundle exec rake org:collaborators

Lists members that should be added or removed from teams:

    bundle exec rake org:team_members

Lists repositories that should be added or removed from teams:

    bundle exec rake org:team_repos

Lists incorrect team repository permissions:

    bundle exec rake org:team_perms

Review outside collaborators:

* [open-contracting](https://github.com/orgs/open-contracting/outside-collaborators)
* [open-contracting-extensions](https://github.com/orgs/open-contracting-extensions/outside-collaborators)
* [open-contracting-archive](https://github.com/orgs/open-contracting-archive/outside-collaborators)

### Redmine CRM

Lists users not employed by the Open Contracting Partnership or its helpdesk teams:

    bundle exec rake crm:users

Lists groups with missing or unexpected users:

    bundle exec rake crm:groups

## Code tasks

Check for TODOs that should be made into GitHub issues (skipping Git, vendored, translation, and generated files) ⏰:

    grep -R -i --exclude-dir .git --exclude-dir .sass-cache --exclude-dir .tox --exclude-dir __pycache__ --exclude-dir _build --exclude-dir _static --exclude-dir build --exclude-dir dist --exclude-dir htmlcov --exclude-dir node_modules --exclude-dir sass --exclude-dir LC_MESSAGES --exclude app.js --exclude conf.py '\btodo\b' .

### Change GitHub repository configuration

Enables delete branch on merge, disables empty wikis, updates extensions' descriptions and homepages, and lists repositories with invalid names, unexpected configurations, etc. ⏰:

    bundle exec rake fix:lint_repos

Protects default branches ⏰ and the standard's minor version branches (checks *Require pull request reviews before merging* on Kingfisher and Data Review Tool repositories, checks *Require status checks to pass before merging*, unchecks *Require branches to be up to date before merging*, checks *build*, and checks *Include administrators* on `standard` and `public-private-partnerships`):

    bundle exec rake fix:protect_branches

Sets topics of extensions ⏰:

    ./manage.py set-topics

Prepares repositories for archival (`REPOS` is a comma-separated list of repository names):

    bundle exec rake fix:archive_repos REPOS=…

### Review GitHub repository metadata and configuration ⏰

The next tasks make no changes, but may require the user to perform an action depending on the output.

Lists repositories with number of issues, PRs, branches, milestones and whether wiki, pages, issues, projects are enabled:

    bundle exec rake repos:status [ORG=open-contracting]

* If a repository has multiple branches, delete any branches without commits ahead of the default branch, ask branch creators whether the other branches can be deleted or made into pull requests.

Lists repositories with missing or unexpected continuous integration configuration:

    bundle exec rake repos:ci

Lists repositories with unexpected, old branches:

    bundle exec rake repos:branches [EXCLUDE=branch1,branch2]

Lists extension repositories with missing template content:

    bundle exec rake repos:readmes

Lists missing or unexpected licenses:

    bundle exec rake repos:licenses

Lists non-extension releases:

    bundle exec rake repos:releases

Lists GitHub Actions secrets:

    bundle exec rake repos:secrets

Lists non-ReadTheDocs webhooks:

    bundle exec rake repos:webhooks

Lists repository descriptions:

    bundle exec rake repos:descriptions

## Standard development tasks

Periodically [spell-check](https://ocds-standard-development-handbook.readthedocs.io/en/latest/standard/technical/spellcheck.html) and [Markdownlint](https://ocds-standard-development-handbook.readthedocs.io/en/latest/coding/#linting) the `standard`, extension and profile repositories. ⏰

Download all registered extensions to a directory:

    ./manage.py download_extensions <directory>

Check whether `~/.aspell.en.pws` contains unwanted words:

    ./manage.py check_aspell_dictionary

### Review third-party extensions

Discover new extensions on GitHub:

    bundle exec rake extensions:discover

Download unregistered extensions from GitHub:

    bundle exec rake extensions:download_unregistered BASEDIR=external-extensions

Create forks of unregistered extensions on GitHub:

    bundle exec rake extensions:create_fork_unregistered OWNER=inaimexico

Delete forks of unregistered extensions on GitHub:

    bundle exec rake extensions:delete_fork_unregistered OWNER=inaimexico USERNAME=jpmckinney

Report the language and length of the documentation of unregistered extensions:

    bundle exec rake extensions:documentation_language_length

### Prepare for a release of OCDS

Reviews open pull requests and recent changes to core extensions:

    bundle exec rake release:review_extensions

Releases new versions of core extensions:

    bundle exec rake release:release_extensions REF=v7.8.9

Removes specific releases of *repositories*:

    bundle exec rake release:undo_release_extensions REF=v7.8.9

### Manage pull requests

Lists the pull requests from a given branch:

    bundle exec rake pulls:list REF=branch

Creates pull requests from a given branch:

    bundle exec rake pulls:create REF=branch BODY=description

Replaces the descriptions of pull requests from a given branch:

    bundle exec rake pulls:update REF=branch BODY=description

Compares the given branch to the default branch:

    bundle exec rake pulls:compare REF=branch

Merges pull requests from a given branch:

    bundle exec rake pulls:merge REF=branch

## Local repository tasks

If you copy the [Makefile](/Makefile) to a directory of local repositories, the following commands are available.

Prints a repository's status if it's not clean:

    make -s status

Prints a repository's unpushed commits:

    make -s ahead

Prints a repository's branch if it's not the default branch:

    make -s branch

Prints a repository's stashes:

    make -s stash

Makes a commit on each repository:

    env ARGS='-a -m "The commit message"' make -s commit

Pushes all repositories with unpushed commits:

    make -s push

## Miscellaneous tasks

Regenerates the [badges page](badges.md) ⏰:

    bundle exec rake local:badges

Make local changes to multiple extensions:

    bundle exec rake local:extension_json BASEDIR=../path/to/directory/of/extensions

Convert code titles to sentence case:

    bundle exec rake local:code_titles BASEDIR=../path/to/directory/of/extensions

Lists web traffic statistics over past two weeks:

    bundle exec rake repos:traffic
