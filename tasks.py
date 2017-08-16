import re
from collections import defaultdict
from os.path import expanduser
from urllib.parse import urlparse

import requests
from invoke import run, task


@task
def download_extensions(ctx, path):
    path = path.rstrip('/')

    url = 'http://standard.open-contracting.org/extension_registry/master/extensions.json'

    for extension in requests.get(url).json()['extensions']:
        if extension['active']:
            components = urlparse(extension['url']).path.split('/')
            repo = '/'.join(components[1:3])
            command = 'git clone git@github.com:{}.git {}/{}'.format(repo, path, components[2])
            run(command)


@task
def check_aspell_dictionary(ctx):
    with open(expanduser('~/.aspell.en.pws'), 'r', encoding='iso-8859-1') as f:
        aspell = f.read()

    def report(method, exceptions):
        stems = defaultdict(int)

        for line in aspell.split('\n'):
            stems[method(line)] += 1

        for stem, count in stems.items():
            if count > 1 and stem not in exceptions:
                print('{} {}'.format(count, stem))

    plural_exceptions = [
        # Prose
        'codelist',
        'dataset',
        'funder',
        'sublicense',
        'KPI',
        # Terms
        'disqualifiedBidder',  # singular organizationRole code, plural bidStatistics code
        'preferredBidder',  # singular organizationRole code, plural Award field
        'qualifiedBidder',  # singular organizationRole code, plural bidStatistics code
        'relatedLot',  # see Lots extension
        'relatedProcess',  # singular codelist name, plural Release and Contract field
    ]

    capital_exceptions = [
        # Prose
        'anytown',
        # File extensions
        'png',
    ]

    combined_exceptions = [exception.lower() for exception in plural_exceptions] + capital_exceptions + [
        # Prose
        'validator',
        # Terms
        'ocid',
        'ppp',
        'sme',
        'uri',
    ]

    # Check that a singular or plural form isn't inappropriately included.
    report(lambda line: re.sub(r'e?s$', '', line), plural_exceptions)

    # Check that a capitalized or uncapitalized form isn't inappropriately included.
    report(lambda line: line.lower(), capital_exceptions)

    # It's okay for there to be a capitalized singular building block and an uncapitalized plural field. Check anyway.
    report(lambda line: re.sub(r'e?s$', '', line).lower(), combined_exceptions)
