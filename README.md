# Standard maintenance scripts

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
* Indenting JSON files

To create a pull request to set up a new repository, enable the repository on [travis-ci.org](https://travis-ci.org), then:

    git checkout -b travis
    curl -O https://raw.githubusercontent.com/open-contracting/standard-maintenance-scripts/master/fixtures/.travis.yml
    git add .travis.yml
    git commit -m 'Add .travis.yml'
    git push -u origin travis

## Tools

List tasks:

    invoke -l
    rake -AT

Download all extensions to a directory:

    invoke download_extensions <directory>

Check whether `~/.aspell.en.pws` contains unwanted words:

    invoke check_aspell_dictionary

### Review GitHub organization configuration

List organization members not employed by the Open Contracting Partnership or its helpdesk teams:

    rake org:members

### Manage pull requests

Create pull requests from a given branch:

    rake pulls:create REF=branch

Replace the descriptions of pull requests from a given branch:

    rake pulls:update REF=branch BODY=description

Merges pull requests for a given branch:

    rake pulls:merge REF=branch

### Review GitHub repository metadata and configuration

Disables empty wikis and lists repositories with invalid names, unexpected configurations, etc.:

    rake repos:lint

Protects default branches:

    rake repos:protect_branches

The next tasks make no changes, but may require the user to perform an action depending on the output.

Lists repositories with missing or unexpected Travis configuration:

    rake repos:check_travis

Lists repositories with many non-PR branches (so that merged branches without new commits may be deleted):

    rake repos:many_branches [EXCLUDE=branch1,branch2]

Lists repositories with number of issues, PRs, branches, milestones and whether wiki, pages, issues, projects are enabled:

    rake repos:status [ORG=open-contracting]

Lists missing or unexpected licenses:

    rake repos:licenses

Lists repository descriptions:

    rake repos:descriptions

Lists non-default issue labels:

    rake repos:labels

Lists releases:

    rake repos:releases

Lists unreleased tags:

    rake repos:tags

Lists non-Travis webhooks:

    rake repos:webhooks
