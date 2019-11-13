import json
import os
import re
import warnings
from copy import deepcopy

import json_merge_patch
import pytest
import requests
from jsonschema import FormatChecker
from jsonschema.validators import Draft4Validator as validator


# Copied from test_json.py.

# Whether to use the 1.1-dev version of OCDS.
use_development_version = False

cwd = os.getcwd()
repo_name = os.path.basename(os.environ.get('TRAVIS_REPO_SLUG', cwd))
ocds_version = os.environ.get('OCDS_TEST_VERSION')
is_extension = os.path.isfile(os.path.join(cwd, 'extension.json'))

ocds_schema_base_url = 'https://standard.open-contracting.org/schema/'
development_base_url = 'https://raw.githubusercontent.com/open-contracting/standard/1.1-dev/standard/schema'
ocds_tags = re.findall(r'\d+__\d+__\d+', requests.get(ocds_schema_base_url).text)
if ocds_version:
    ocds_tag = ocds_version.replace('.', '__')
else:
    ocds_tag = ocds_tags[-1]

# End copy.

if ocds_version or not use_development_version:
    url_prefix = ocds_schema_base_url + ocds_tag
else:
    url_prefix = development_base_url

schema = requests.get(url_prefix + '/release-schema.json').json()

# Same as tests/fixtures/release_minimal.json in ocdskit.
minimal_release = {
    "ocid": "ocds-213czf-1",
    "id": "1",
    "date": "2001-02-03T04:05:06Z",
    "tag": ["planning"],
    "initiationType": "tender",
}


# Copied from test_json.py.
def custom_warning_formatter(message, category, filename, lineno, line=None):
    return str(message).replace(cwd + os.sep, '')


warnings.formatwarning = custom_warning_formatter


def read_readme():
    path = os.path.join(cwd, 'README.md')
    if os.path.isfile(path):
        with open(path) as f:
            return f.read()
    else:
        assert os.path.isfile(path), 'expected a README.md file'


def examples():
    for i, text in enumerate(re.findall(r'```json(.+?)```', read_readme(), re.DOTALL)):
        try:
            yield i, text, json.loads(text)
        except json.decoder.JSONDecodeError as e:
            assert False, 'JSON block {} is not valid JSON ({})'.format(i, e)


@pytest.mark.skipif(not is_extension, reason='not an extension (test_example_present)')
def test_example_present():
    """
    Ensures the extension's documentation contains an example.
    """
    exceptions = {
        'ocds_budget_and_spend_extension',
    }

    if repo_name in exceptions:
        return

    readme = read_readme()

    # ocds_enquiry_extension has "Example" as text, instead of as a heading.
    if not re.search(r'\bexamples?\b', readme, re.IGNORECASE) or '```json' not in readme:
        warnings.warn('README.md expected an example')


@pytest.mark.skipif(not is_extension, reason='not an extension (test_example_indent)')
def test_example_indent():
    """
    Ensures all JSON snippets in the extension's documentation are valid and formatted for humans.
    """
    for i, text, data in examples():
        expected = '\n{}\n'.format(json.dumps(data, ensure_ascii=False, indent=2, separators=(',', ': ')))
        assert text == expected


@pytest.mark.skipif(not is_extension, reason='not an extension (test_example_indent)')
def test_example_valid():
    """
    Ensures all JSON snippets in the extension's documentation are snippets of OCDS data with no additional fields.
    """
    def set_additional_properties_false(data):
        if isinstance(data, list):
            for item in data:
                set_additional_properties_false(item)
        elif isinstance(data, dict):
            if 'properties' in data:
                data['additionalProperties'] = False
            for value in data.values():
                set_additional_properties_false(value)

    # Adapted from test_json.py.
    def get_dependencies(extension):
        dependencies = extension.get('dependencies', []) + extension.get('testDependencies', [])
        for url in dependencies:
            dependency = requests.get(url).json()
            schema_url = url.rsplit('/', 1)[0] + '/release-schema.json'
            json_merge_patch.merge(patched, requests.get(schema_url).json())
            get_dependencies(dependency)

    patched = deepcopy(schema)
    with open(os.path.join(cwd, 'extension.json')) as f:
        get_dependencies(json.loads(f.read()))
    with open(os.path.join(cwd, 'release-schema.json')) as f:
        json_merge_patch.merge(patched, json.loads(f.read()))
    set_additional_properties_false(patched)

    for i, text, data in examples():
        # Skip packages (only occurs once in ocds_ppp_extension).
        if 'releases' in data:
            continue

        errors = 0

        release = deepcopy(minimal_release)
        json_merge_patch.merge(release, data)
        if 'tender' in release and 'id' not in release['tender']:
            release['tender']['id'] = '1'

        for error in validator(patched, format_checker=FormatChecker()).iter_errors(release):
            errors += 1
            warnings.warn(json.dumps(error.instance, indent=2, separators=(',', ': ')))
            warnings.warn('{} ({})\n'.format(error.message, '/'.join(error.absolute_schema_path)))

        assert errors == 0, 'JSON block {} is invalid. See warnings below.'.format(i)
