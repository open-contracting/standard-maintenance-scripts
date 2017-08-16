## Setup

    pip install -r requirements.txt
    bundle

To run the Rake tasks:

* [Create a GitHub personal access token](https://github.com/settings/tokens) with the scopes `public_repo` and `admin:org`
* [Edit your `~/.netrc` file](https://github.com/octokit/octokit.rb#using-a-netrc-file) using the token as your password

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

### Review GitHub repository metadata and configuration

Disables empty wikis and lists repositories with invalid names, unexpected configurations, etc.:

    rake repos:lint

Protects default branches:

    rake repos:protect_branches

The next tasks make no changes, but may require the user to perform an action depending on the output.

Lists repositories with many non-PR branches (so that merged branches without new commits may be deleted):

    rake repos:many_branches [EXCLUDE=branch1,branch2]

Lists repositories with number of issues, PRs, branches, milestones and whether wiki, pages, issues, projects are enabled:

    rake repos:status [ORG=open-contracting]

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
