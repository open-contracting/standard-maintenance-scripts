## Setup

    pip install -r requirements.txt
    bundle

To run `rake many_branches`:

* [Create a personal access token](https://github.com/settings/tokens) with the scopes `public_repo` and `admin:org`
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

List repositories with empty wikis (so that they may be disabled), unexpected configurations, invalid names, etc.:

    rake repos:lint

List repositories without protected default branches:

    rake repos:protected_branches

List repositories with many non-PR branches (so that merged branches without new commits may be deleted):

    rake repos:many_branches [EXCLUDE=branch1,branch2]

List repositories with number of issues, PRs, branches, milestones and whether wiki, pages, issues, projects are enabled:

    rake repos:status [ORG=open-contracting]

List descriptions:

    rake repos:descriptions

List non-default labels:

    rake repos:labels

List releases:

    rake repos:releases

List unreleased tags:

    rake repos:tags

List non-Travis webhooks:

    rake repos:webhooks
