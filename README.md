# Standard maintenance scripts

Tasks that should be run manually periodically have a ⏰ icon.

## Setup

    pip install -r requirements.txt
    bundle

To run the Rake tasks:

* [Create a GitHub personal access token](https://github.com/settings/tokens) with the scopes `public_repo` and `admin:org`
* [Edit your `~/.netrc` file](https://github.com/octokit/octokit.rb#using-a-netrc-file) using the token as your password

## Tests

The standard [`.travis.yml`](fixtures/.travis.yml) file performs:

* Linting of:
  * Python ([flake8](https://pypi.python.org/pypi/flake8))
  * Markdown ([markdownlint](https://github.com/markdownlint/markdownlint))
  * JSON (readable by Python)
* Various checks against OCDS schema, extensions, etc.

To run the tests locally, run the setup commands above, change into a repository's folder, then:

    flake8 --max-line-length 119
    py.test -rs path/to/standard-maintenance-scripts/tests

To run the tests locally against an unreleased version of the standard, replace `http://standard.open-contracting.org/schema/VERSION` with `http://standard.open-contracting.org/BRANCH/en`.

To skip the JSON indentation test, set the `OCDS_NOINDENT` environment variable, with `export OCDS_NOINDENT=1` (Bash) or `setenv OCDS_NOINDENT 1` (fish).

To create a pull request to set up a new repository, enable the repository on [travis-ci.org](https://travis-ci.org), then:

    git checkout -b travis
    curl -O https://raw.githubusercontent.com/open-contracting/standard-maintenance-scripts/master/fixtures/.travis.yml
    git add .travis.yml
    git commit -m 'Add .travis.yml'
    git push -u origin travis

## Miscellaneous tasks

List tasks:

    invoke -l
    bundle exec rake -AT

Download all extensions to a directory:

    invoke download_extensions <directory>

Check whether `~/.aspell.en.pws` contains unwanted words:

    invoke check_aspell_dictionary

Check for files have unexpected permissions ⏰:

    find . \! -perm 644 -type f -not -path '*/.git/*' -not -path '*/__pycache__/*' -not -path '*/node_modules/*' -o \! -perm 755 -type d

Check for TODOs that should be made into GitHub issues (skipping Git, vendored, translation, and generated files) ⏰:

    grep -R -i --exclude-dir .git --exclude-dir _build --exclude-dir _static --exclude-dir build --exclude-dir node_modules --exclude-dir LC_MESSAGES --exclude app.js --exclude conf.py '\btodo\b' .

Periodically [spell-check](http://ocds-standard-development-handbook.readthedocs.io/en/latest/standard/technical/spellcheck/) and [Markdownlint](http://ocds-standard-development-handbook.readthedocs.io/en/latest/coding/#linting) the `standard`, extension and profile repositories.

## Code tasks

### Review GitHub organization configuration

Lists organization members not employed by the Open Contracting Partnership or its helpdesk teams ⏰:

    bundle exec rake org:members

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

### Prepare for a release of OCDS

Reviews open pull requests and recent changes to core extensions:

    bundle exec rake release:review_extensions

Releases new versions of core extensions:

    bundle exec rake release:release_extensions REF=v7.8.9

Removes specific releases of *repositories*:

    bundle exec rake release:undo_release_extensions REF=v7.8.9

### Maintain the extension registry

Discover new extensions on GitHub:

    bundle exec rake registry:discover

Prepare the content of `extension_versions.csv`:

    bundle exec rake registry:extension_versions

### Change GitHub repository configuration

Disables empty wikis, updates extensions' descriptions and homepages, and lists repositories with invalid names, unexpected configurations, etc. ⏰:

    bundle exec rake fix:lint_repos

Protects default branches ⏰:

    bundle exec rake fix:protect_branches

Sets topics of extensions ⏰:

    bundle exec rake fix:set_topics

Prepares repositories for archival (`REPOS` is a comma-separated list of repository names):

    bundle exec rake fix:archive_repos REPOS=…

### Modify local repositories

Regenerates the [badges page](badges.md) ⏰:

    bundle exec rake local:badges

Adds template content to extension readmes:

    bundle exec rake local:readmes BASEDIR=extensions

Updates extension.json to its new format:

    bundle exec rake local:extension_json BASEDIR=extensions

### Review GitHub repository metadata and configuration ⏰

The next tasks make no changes, but may require the user to perform an action depending on the output.

Lists repositories with number of issues, PRs, branches, milestones and whether wiki, pages, issues, projects are enabled:

    bundle exec rake repos:status [ORG=open-contracting]

Lists repositories with missing or unexpected Travis configuration:

    bundle exec rake repos:travis

Lists repositories with unexpected, old branches (so that merged branches without new commits may be deleted):

    bundle exec rake repos:branches [EXCLUDE=branch1,branch2]

Lists extension repositories with missing template content:

    bundle exec rake repos:readmes

Lists missing or unexpected licenses:

    bundle exec rake repos:licenses

Lists repository descriptions:

    bundle exec rake repos:descriptions

Lists non-extension releases:

    bundle exec rake repos:releases

Lists non-Travis webhooks:

    bundle exec rake repos:webhooks

### Assess priority

Lists web traffic statistics over past two weeks:

    bundle exec rake repos:traffic

## Non-code tasks

### Check Redmine's consistency and coherence ⏰

Lists users not employed by the Open Contracting Partnership or its helpdesk teams:

    bundle exec rake crm:users

Lists groups with missing or unexpected users:

    bundle exec rake crm:groups

### Check OCP Resources links ⏰

Lints the Resources section of the OCP website:

    bundle exec rake resources:check

Prints all links from the Resources section of the OCP website:

    bundle exec rake resources:links

Prints the bit.ly links from the Resources section of the OCP website as tab-separated values:

    bundle exec rake resources:bitly
