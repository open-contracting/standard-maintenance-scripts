import os
import re
from collections import defaultdict

from invoke import run, task
from ocdsextensionregistry import ExtensionRegistry


@task
def download_extensions(ctx, path):
    path = path.rstrip('/')

    url = 'https://raw.githubusercontent.com/open-contracting/extension_registry/master/extension_versions.csv'

    registry = ExtensionRegistry(url)
    for extension in registry:
        directory = os.path.join(path, extension.repository_name)
        if not os.path.isdir(directory):
            run('git clone {} {}'.format(extension.repository_url, directory))


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
