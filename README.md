## Setup

    pip install -r requirements.txt
    bundle

To run `rake many_branches`:

* [Create a personal access token](https://github.com/settings/tokens) with the scope `public_repo`
* [Edit your `~/.netrc` file](https://github.com/octokit/octokit.rb#using-a-netrc-file) using the token as your password

## Tools

List tasks:

    invoke -l
    rake -AT

Download all extensions to a directory:

    invoke download_extensions <directory>

List repositories with many branches (so that merged branches without new commits may be deleted):

    rake many_branches

List repositories with empty wikis (so that they may be disabled):

    rake empty_wikis

List repositories with number of open issues, issues enabled, wiki enabled, pages enabled:

    rake status
