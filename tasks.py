import json
import os
import re
from collections import defaultdict

import requests
from invoke import run, task
from ocdsextensionregistry import ExtensionRegistry

extensions_url = 'https://raw.githubusercontent.com/open-contracting/extension_registry/main/extensions.csv'
extension_versions_url = 'https://raw.githubusercontent.com/open-contracting/extension_registry/main/extension_versions.csv'  # noqa: E501


@task
def download_extensions(ctx, path):
    path = path.rstrip('/')

    registry = ExtensionRegistry(extension_versions_url)
    for version in registry:
        directory = os.path.join(path, version.repository_name)
        if not os.path.isdir(directory):
            run('git clone {} {}'.format(version.repository_url, directory))


@task
def set_topics(ctx):
    """
    Adds topics to repositories in the open-contracting-extensions organization.

    -  ocds-extension
    -  ocds-core-extension
    -  ocds-community-extension
    -  ocds-profile
    -  european-union
    -  public-private-partnerships
    """
    format_string = 'https://raw.githubusercontent.com/open-contracting-extensions/{}/{}/docs/extension_versions.json'

    profiles = defaultdict(list)
    for profile, branch in (('european-union', 'master'), ('public-private-partnerships', '1.0-dev')):
        extension_versions = requests.get(format_string.format(profile, branch)).json()
        for extension_id in extension_versions.keys():
            profiles[extension_id].append(profile)

    registry = ExtensionRegistry(extension_versions_url, extensions_url)

    repos = requests.get('https://api.github.com/orgs/open-contracting-extensions/repos?per_page=100').json()
    for repo in repos:
        topics = []

        if repo['name'].endswith('_extension'):
            topics.append('ocds-extension')
        else:
            topics.append('ocds-profile')

        for version in registry:
            if '/{}/'.format(repo['full_name']) in version.base_url:
                if version.core:
                    topics.append('ocds-core-extension')
                else:
                    topics.append('ocds-community-extension')
                topics.extend(profiles[version.id])
                break
        else:
            if 'ocds-profile' not in topics:
                print('{} is not registered'.format(repo['name']))

        response = requests.put('https://api.github.com/repos/{}/topics'.format(repo['full_name']),
                                data=json.dumps({'names': topics}),
                                headers={'accept': 'application/vnd.github.mercy-preview+json'})
        response.raise_for_status()


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
