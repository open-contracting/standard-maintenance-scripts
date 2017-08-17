import json
import os
from collections import OrderedDict
from copy import deepcopy

import json_merge_patch
import pytest
import requests
from jsonschema import FormatChecker
from jsonschema.validators import Draft4Validator as validator


def is_extension():
    # See https://github.com/open-contracting/standard-development-handbook/issues/16
    exceptions = ('ocds_performance_failures', 'public-private-partnerships')
    name = os.path.basename(os.environ.get('TRAVIS_REPO_SLUG', os.getcwd()))
    return name.startswith('ocds') and name.endswith('extension') or name in exceptions


# Draft 6 corrects some problems with Draft 4, e.g. omitting `format`, but it:
# * renames `id` to `$id`
# * changes `exclusiveMinimum` to a number
# * allows additional properties, which makes it possible for typos to go undetected
# See http://json-schema.org/draft-04/schema
metaschema = requests.get('http://json-schema.org/schema').json()
metaschema['properties']['id'] = metaschema['properties'].pop('$id')
metaschema['properties']['exclusiveMinimum'] = {'type': 'boolean', 'default': False}
metaschema['additionalProperties'] = False

# OCDS fields.
metaschema['properties']['codelist'] = {'type': 'string'}
metaschema['properties']['openCodelist'] = {'type': 'boolean'}
# @see https://github.com/open-contracting/standard/blob/1.1-dev/standard/docs/en/schema/deprecation.md
metaschema['properties']['deprecated'] = {
    'type': 'object',
    'properties': {
        'additionalProperties': False,
        'description': {'type': 'string'},
        'deprecatedVersion': {'type': 'string'},
    },
}
# See https://github.com/open-contracting/standard/blob/1.1-dev/standard/docs/en/schema/merging.md
metaschema['properties']['omitWhenMerged'] = {'type': 'boolean'}
metaschema['properties']['wholeListMerge'] = {'type': 'boolean'}
metaschema['properties']['versionId'] = {'type': 'boolean'}

# jsonmerge fields.
# See https://github.com/open-contracting-archive/jsonmerge
metaschema['properties']['mergeStrategy'] = {
    'type': 'string',
    'enum': [
        'append',
        'arrayMergeById',
        'objectMerge',
        'ocdsOmit',
        'ocdsVersion',
        'overwrite',
        'version',
    ],
}
metaschema['properties']['mergeOptions'] = {
    'type': 'object',
    'properties': {
        'additionalProperties': False,
        'idRef': {'type': 'string'},
        'ignoreDups': {'type': 'boolean'},
        'ignoreId': {'type': 'string'},
        'limit': {'type': 'number'},
        'unique': {'type': 'boolean'},
    },
}

if is_extension():
    # See https://tools.ietf.org/html/rfc7396
    metaschema['type'].append('null')
    metaschema['properties']['deprecated']['type'] = ['object', 'null']


def walk():
    """
    Yields all files, except third-party files under `_static` directories.
    """
    for root, dirs, files in os.walk(os.getcwd()):
        if '_static' not in root.split(os.sep):
            for name in files:
                yield (root, name)


def walk_json_data():
    """
    Yields all JSON data.
    """
    for root, name in walk():
        if name.endswith('.json'):
            path = os.path.join(root, name)
            with open(path, 'r') as f:
                text = f.read()
                data = json.loads(text, object_pairs_hook=OrderedDict)
                yield (path, text, data)


def is_json_schema(data):
    """
    Returns whether the data is a JSON Schema.
    """
    return '$schema' in data or 'definitions' in data or 'properties' in data


def validate_json_schema(path, data):
    errors = 0

    for error in validator(metaschema, format_checker=FormatChecker()).iter_errors(data):
        errors += 1
        print(json.dumps(error.instance, indent=2, separators=(',', ': ')))
        print('{} ({})\n'.format(error.message, '/'.join(error.absolute_schema_path)))

    if errors:
        print('{} is not valid JSON Schema ({} errors)'.format(path, errors))

    assert errors == 0


def test_valid():
    """
    Ensures all JSON files are valid.
    """
    for path, text, data in walk_json_data():
        pass  # fails if the JSON can't be read


@pytest.mark.skip(reason='see https://github.com/open-contracting/standard-maintenance-scripts/issues/2')
def test_indent():
    """
    Ensures all JSON files are valid and formatted for humans.
    """
    for path, text, data in walk_json_data():
        # See https://github.com/open-contracting/standard-maintenance-scripts/issues/2
        indent2 = json.dumps(data, indent=2, separators=(',', ': '))
        indent4 = json.dumps(data, indent=4, separators=(',', ': '))
        assert text == indent2 or text == indent4, "{} is not indented as expected".format(path)


def test_json_schema():
    """
    Ensures all JSON Schema files are valid JSON Schema Draft 4.
    """
    for path, text, data in walk_json_data():
        if is_json_schema(data):
            validate_json_schema(path, data)


def test_json_merge_patch():
    """
    Ensures all extension JSON Schema successfully patch core JSON Schema.
    """
    if not is_extension():
        pytest.skip('not an extension')

    schemas = {}

    basenames = (
        'record-package-schema.json',
        'release-package-schema.json',
        'release-schema.json',
        'versioned-release-validation-schema.json',
    )

    for basename in basenames:
        schemas[basename] = requests.get('http://standard.open-contracting.org/latest/en/{}'.format(basename)).json()

    for path, text, data in walk_json_data():
        if is_json_schema(data):
            basename = os.path.basename(path)
            if basename in basenames:
                unpatched = deepcopy(schemas[basename])
                # It's not clear that `json_merge_patch.merge()` can ever fail.
                patched = json_merge_patch.merge(unpatched, data)

                # We don't `assert patched != schemas[basename]`, because empty patches are allowed. json_merge_patch
                # mutates `unpatched`, which is unexpected, which is why we would test against `schemas[basename]`.
                validate_json_schema(path, patched)
