#!/usr/bin/env python
import csv
import datetime
import json
import os
import re
import subprocess
from collections import Counter, defaultdict
from operator import itemgetter
from pathlib import Path

import click
import requests
import tomli
from ocdsextensionregistry import ExtensionRegistry

extensions_url = "https://raw.githubusercontent.com/open-contracting/extension_registry/main/extensions.csv"
extension_versions_url = (
    "https://raw.githubusercontent.com/open-contracting/extension_registry/main/extension_versions.csv"
)


def get(*args, **kwargs):
    response = requests.get(*args, **kwargs)
    response.raise_for_status()
    return response


def default(obj):
    if isinstance(obj, set):
        return list(obj)
    return json.JSONEncoder().default(obj)


@click.group()
def cli():
    pass


@cli.command()
@click.argument("path")
@click.option("--match", help="")
def download_extensions(path, match):
    """Download all registered extensions to a directory."""
    path = path.rstrip("/")

    for version in ExtensionRegistry(extension_versions_url):
        if not match or match in version.base_url:
            directory = os.path.join(path, version.repository_name)
            if not os.path.isdir(directory):
                command = ["git", "clone", version.repository_url, directory]
                click.echo(" ".join(command))
                subprocess.call(command)  # noqa: S603 # trusted input


@cli.command()
def set_topics():
    """
    Add topics to repositories in the open-contracting-extensions organization.

    -  ocds-extension
    -  ocds-core-extension
    -  ocds-community-extension
    -  ocds-profile
    -  european-union
    -  public-private-partnerships
    """
    format_string = "https://raw.githubusercontent.com/open-contracting-extensions/{}/{}/docs/extension_versions.json"

    profiles = defaultdict(list)
    for profile, branch in (("european-union", "latest"), ("public-private-partnerships", "1.0-dev")):
        for extension_id in get(format_string.format(profile, branch)).json():
            profiles[extension_id].append(profile)

    registry = ExtensionRegistry(extension_versions_url, extensions_url)

    for repo in get("https://api.github.com/orgs/open-contracting-extensions/repos?per_page=100").json():
        topics = []

        if repo["name"].endswith("_extension"):
            topics.append("ocds-extension")
        else:
            topics.append("ocds-profile")

        for version in registry:
            if f"/{repo['full_name']}/" in version.base_url:
                if version.core:
                    topics.append("ocds-core-extension")
                else:
                    topics.append("ocds-community-extension")
                topics.extend(profiles[version.id])
                break
        else:
            if "ocds-profile" not in topics:
                click.echo(f"{name} is not registered")

        requests.put(
            f"https://api.github.com/repos/{repo['full_name']}/topics",
            data=json.dumps({"names": topics}),
            headers={"accept": "application/vnd.github.mercy-preview+json"},
            timeout=10,
        ).raise_for_status()


@cli.command()
def check_aspell_dictionary():
    """Check whether ~/.aspell.en.pws contains unwanted words."""
    with open(os.path.expanduser("~/.aspell.en.pws"), encoding="iso-8859-1") as f:
        aspell = f.read()

    def report(method, exceptions):
        stems = defaultdict(int)

        for line in aspell.split("\n"):
            stems[method(line)] += 1

        for stem, count in stems.items():
            if count > 1 and stem not in exceptions:
                click.echo(f"{count} {stem}")

    plural_exceptions = [
        # Prose
        "codelist",
        "dataset",
        "funder",
        "sublicense",
        "KPI",
        # Terms
        "disqualifiedBidder",  # singular organizationRole code, plural bidStatistics code
        "preferredBidder",  # singular organizationRole code, plural Award field
        "qualifiedBidder",  # singular organizationRole code, plural bidStatistics code
        "relatedLot",  # see Lots extension
        "relatedProcess",  # singular codelist name, plural Release and Contract field
    ]

    capital_exceptions = [
        # Prose
        "anytown",
        # File extensions
        "png",
    ]

    combined_exceptions = (
        [exception.lower() for exception in plural_exceptions]
        + capital_exceptions
        + [
            # Prose
            "validator",
            # Terms
            "ocid",
            "ppp",
            "sme",
            "uri",
        ]
    )

    # Check that a singular or plural form isn't inappropriately included.
    report(lambda line: re.sub(r"e?s$", "", line), plural_exceptions)

    # Check that a capitalized or uncapitalized form isn't inappropriately included.
    report(lambda line: line.lower(), capital_exceptions)

    # It's okay for there to be a capitalized singular building block and an uncapitalized plural field. Check anyway.
    report(lambda line: re.sub(r"e?s$", "", line).lower(), combined_exceptions)


# https://ocp-software-handbook.readthedocs.io/en/latest/python/preferences.html#license-compliance
@cli.command()
@click.argument("file", type=click.File())
def check_licenses(file):
    """
    Report strong copyleft and unknown licenses in FILE.

    FILE must be a CSV file with Name,Version,License columns.
    """
    permissive = {
        "Public Domain",
        # https://en.wikipedia.org/wiki/Academic_Free_License
        "Academic Free License (AFL)",
        # https://en.wikipedia.org/wiki/Apache_License
        "Apache 2.0",
        "Apache License 2.0",
        "Apache Software License",
        "Apache Software License 2.0",
        "Apache License, Version 2.0",
        # https://en.wikipedia.org/wiki/BSD_licenses
        "3-Clause BSD License",
        "BSD",
        "BSD 3-Clause",
        "BSD License",
        "BSD-3-Clause",
        # https://en.wikipedia.org/wiki/Artistic_License
        "Artistic License",
        # https://en.wikipedia.org/wiki/Creative_Commons_license#Zero_/_public_domain
        "CC0 1.0 Universal",
        "CC0 (copyright waived)",
        # https://en.wikipedia.org/wiki/Historical_Permission_Notice_and_Disclaimer
        "Historical Permission Notice and Disclaimer (HPND)",
        # https://en.wikipedia.org/wiki/ISC_license
        "ISC License (ISCL)",
        # https://en.wikipedia.org/wiki/MIT_License
        "MIT",
        "MIT License",
        "The MIT License (MIT)",
        # https://en.wikipedia.org/wiki/Python_Software_Foundation_License
        "Python Software Foundation License",
        # https://en.wikipedia.org/wiki/Unlicense
        "The Unlicense (Unlicense)",
        # https://en.wikipedia.org/wiki/Zope_Public_License
        "Zope Public License",
        "ZPL 2.1",
        # https://en.wikipedia.org/wiki/Zlib_License
        "zlib/php",
    }

    # "Weak copyleft" typically means that unmodified use imposes no additional requirements to permissive licenses.
    weak_copyleft = {
        # https://en.wikipedia.org/wiki/Eclipse_Public_License
        # https://fossa.com/blog/open-source-software-licenses-101-eclipse-public-license/
        "Eclipse Public License 2.0 (EPL-2.0)",
        # https://en.wikipedia.org/wiki/GNU_Lesser_General_Public_License
        # https://fossa.com/blog/open-source-software-licenses-101-lgpl-license/
        "GNU Lesser General Public License v2 (LGPLv2)",
        "GNU Lesser General Public License v2 or later (LGPLv2+)",
        "GNU Lesser General Public License v3 or later (LGPLv3+)",
        "GNU Library or Lesser General Public License (LGPL)",
        "LGPL",
        # https://en.wikipedia.org/wiki/Mozilla_Public_License
        # https://fossa.com/blog/open-source-software-licenses-101-mozilla-public-license-2-0/
        "Mozilla Public License 2.0 (MPL 2.0)",
        "MPL-2.0",
    }

    strong_copyleft = {
        # https://en.wikipedia.org/wiki/GNU_Affero_General_Public_License
        "GNU Affero General Public License v3 or later (AGPLv3+)",
        # https://en.wikipedia.org/wiki/GNU_General_Public_License
        "GNU General Public License (GPL)",
        "GNU General Public License v2 (GPLv2)",
        "GNU General Public License v2 or later (GPLv2+)",
        "GNU General Public License v3 (GPLv3)",
        "GNU General Public License v3 or later (GPLv3+)",
        "GPLv2",
        "GPL v2",
    }

    packages = {}
    for row in csv.DictReader(file):
        row["License"] = set(row["License"].split("; "))
        if row["License"] & permissive or row["License"] & weak_copyleft:
            continue
        packages.setdefault(row["Name"], [row, []])
        packages[row["Name"]][1].append(row["Venv"])

    for name, (row, venvs) in packages.items():
        licenses = row["License"]
        if licenses & strong_copyleft:
            click.secho(f'{name}: {", ".join(licenses)}', fg="red")
        else:
            click.secho(f'{name}: {", ".join(licenses)} {row["URL"]}', fg="yellow")
        for venv in venvs:
            click.echo(f"  {venv}")


@cli.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False, path_type=Path))
def count_dependencies(directory):
    """Count the most common dependencies across local repositories."""
    pattern = re.compile(r"[<>!;[]")

    counter = Counter()

    for path in directory.iterdir():
        if path.is_dir():
            counter.update(
                pattern.split(req)[0]
                for file in path.glob("*requirements*.in")
                # Ignore development and documentation requirements.
                if not file.name.endswith("_dev.in") and file.name != "common-requirements.in"
                for req in file.read_text().splitlines()
                if req and not req.startswith(("# ", "-r ", "-e file:.#"))
            )

            pyproject = path / "pyproject.toml"
            if pyproject.is_file():
                counter.update(
                    pattern.split(req)[0]
                    for req in tomli.loads(pyproject.read_text()).get("project", {}).get("dependencies", [])
                )

    for requirement, count in reversed(counter.most_common()):
        click.echo(f"{count:3d} {requirement}")
    click.echo(f"{len(counter)} total")


@cli.command()
@click.argument("organization")
@click.option("--days", type=int, default=90, help="Days ago from which to count contributors")
@click.option("--start", help="Datetime from which to count contributors")
@click.option("--end", help="Datetime up to which to count contributors")
@click.option("--verbose", help="Dump contributors data")
def github_contributors(organization, days, start, end, verbose):
    """Report the number of contributors to an organization's repositories."""
    contributors = set()
    contributors_by_repository = {}

    repos = get(f"https://api.github.com/orgs/{organization}/repos?type=sources&per_page=100").json()
    click.echo(f"Retrieving metadata for {len(repos)} source repositories..")
    for i, repo in enumerate(repos, 1):
        name = repo['name']
        logins = set()

        click.echo(f"{i:2d} {name} ", nl=False)

        url = f"https://api.github.com/repos/{repo['full_name']}/issues/comments?per_page=100"
        while url:
            response = get(url)
            logins.update(
                comment["user"]["login"]
                for comment in response.json()
                if not comment["user"]["login"].endswith("[bot]")
            )
            url = response.links.get("next", {}).get("url")
            click.echo(".", nl=False)

        logins.update(
            user["login"]
            for user in get(f"{repo['contributors_url']}?per_page=100").json()
            if not user["login"].endswith("[bot]")
        )

        contributors_by_repository[repo["name"]] = logins
        contributors.update(logins)

        click.echo("")

    if verbose:
        click.echo(json.dumps(contributors_by_repository, indent=2, default=default))
    click.echo(f"\n{len(contributors)} contributors across {len(repos)} repositories")


@cli.command()
@click.argument("user", nargs=-1)
@click.option("--days", type=int, default=90, help="Days ago from which to count contributions")
@click.option("--start", help="Datetime from which to count contributions")
@click.option("--end", help="Datetime up to which to count contributions")
def github_activity(user, days, start, end):
    """Report the number of contributions by users, per repository."""
    format_string = """\
query {{
{queries}
}}
fragment f on User {{
    contributionsCollection(from: "{start}", to: "{end}") {{
        commitContributionsByRepository(maxRepositories: 100) {{
            contributions {{
                totalCount
            }}
            repository {{
                url
            }}
        }}
    }}
}}"""
    if start:
        start += "T00:00:00Z"
    if end:
        end += "T23:59:59Z"

    if not start and days:
        start = (datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(days=days)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    if not end:
        end = datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    query = format_string.format(
        queries="\n".join(f'  user{i}: user(login: "{login}") {{\n    ...f\n  }}' for i, login in enumerate(user)),
        start=start,
        end=end,
    )

    response = requests.post("https://api.github.com/graphql", json={"query": query}, timeout=10)
    response.raise_for_status()
    json = response.json()
    if "errors" in json:
        click.echo(json)
        return

    counter = defaultdict(int)
    for data in response.json()["data"].values():
        try:
            for by in data["contributionsCollection"]["commitContributionsByRepository"]:
                counter[by["repository"]["url"]] += by["contributions"]["totalCount"]
        except KeyError:
            click.echo(data)

    click.echo("  R   C  URL")
    for i, (url, count) in enumerate(sorted(counter.items(), key=itemgetter(1), reverse=True), 1):
        click.echo(f"{i:3d} {count:3d} {url}")


if __name__ == "__main__":
    cli()
