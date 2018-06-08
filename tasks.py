import csv
import os
import re
from collections import defaultdict
from io import StringIO
from urllib.parse import urlparse

import requests
from invoke import run, task


@task
def download_extensions(ctx, path):
    url = 'https://raw.githubusercontent.com/open-contracting/extension_registry/master/extension_versions.csv'

    repos = set()
    for version in csv.DictReader(StringIO(requests.get(url).text)):
        parts = urlparse(version['Base URL'])
        if parts.netloc == 'raw.githubusercontent.com':
            repos.add('/'.join(parts.path.split('/')[1:3]))
        else:
            print('{} not supported'.format(parts.netloc))

    path = path.rstrip('/')
    for repo in repos:
        directory = '{}/{}'.format(path, repo.split('/', 1)[1])
        if not os.path.isdir(directory):
            run('git clone git@github.com:{}.git {}'.format(repo, directory))


@task
def check_aspell_dictionary(ctx):
    with open(os.path.expanduser('~/.aspell.en.pws'), 'r', encoding='iso-8859-1') as f:
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
