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

The [test files](tests/) can perform:

* Linting of:
  * Python ([ruff](https://docs.astral.sh/ruff/))
  * JSON (readable by Python)
  * CSV (readable by Python)
* Various checks against OCDS schema, codelists, readmes, etc.
* Checks for unused requirements or undeclared dependencies in Python (opt-in).

To run the tests locally, run the [install.sh](tests/install.sh) file and then run the desired parts of the [script.sh](tests/script.sh) file.

Control the tests' behavior with these environment variables:

* `OCDS_NOINDENT=1`: Skip the JSON indentation test.
* `STANDARD_MAINTENANCE_SCRIPTS_EXTRAS`: A comma-separated list of `extras_require` keys. Add the packages under these keys to the list of declared requirements.
* `STANDARD_MAINTENANCE_SCRIPTS_IGNORE`: A comma-separated list of Python packages. Don't error if these packages appear in a requirement file but aren't imported by the source code, or vice versa.
* `STANDARD_MAINTENANCE_SCRIPTS_FILES`: A comma-separated list of `.in` files to test, in addition to `requirements.in` and `requirements_dev.in`.

See the [OCP Software Development Handbook](https://ocp-software-handbook.readthedocs.io/en/latest/python/linting.html) to run these tests in a GitHub Actions workflow.

## Access tasks ⏰

Lists members that should be added or removed from the organization:

    bundle exec rake org:members

Lists owners that should be added or removed from the organization:

    bundle exec rake org:owners

Removes admin access to specific repositories from non-admin members (slow):

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

## Code tasks

Count frequent dependencies in Python projects and Python packages:

    ./manage.py count-dependencies ..

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

Lists open and dismissed vulnerabilities (`GITHUB_ACCESS_TOKEN` should match the password in the `~/.netrc` file):

    env GITHUB_ACCESS_TOKEN=... bundle exec rake repos:vulnerabilities ORGS=open-contracting

Lists repositories with unexpected, old branches:

    bundle exec rake repos:branches [EXCLUDE=branch1,branch2]

Lists extension repositories with missing template content:

    bundle exec rake repos:readmes

Lists missing or unexpected licenses:

    bundle exec rake repos:licenses

Lists non-extension, non-Rust releases:

    bundle exec rake repos:releases

Lists GitHub Actions secrets:

    bundle exec rake repos:secrets

Lists non-ReadTheDocs webhooks:

    bundle exec rake repos:webhooks

Lists repository descriptions:

    bundle exec rake repos:descriptions

## Standard development tasks

Download all registered extensions to a directory:

    ./manage.py download-extensions <directory>

Check whether `~/.aspell.en.pws` contains unwanted words:

    ./manage.py check-aspell-dictionary

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

Report the number of contributions by users, per repository:

    ./manage.py github-activity jpmckinney --start 2023-01-01 --end 2023-12-31
