import json
import os
from collections import OrderedDict
from copy import deepcopy

import pytest
import requests
from jsonschema import FormatChecker
from jsonschema.validators import Draft4Validator as validator


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


def test_valid():
    """
    Ensures all JSON files are valid.
    """
    for path, text, data in walk_json_data():
        pass


@pytest.mark.skip(reason="See https://github.com/open-contracting/standard-maintenance-scripts/issues/2")
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
    """
    # Draft 6 corrects some problems with Draft 4, e.g. omitting `format`, but it:
    # * renames `id` to `$id`
    # * changes `exclusiveMinimum` to a number
    # * allows additional properties, which makes it possible for typos to go undetected
    # See http://json-schema.org/draft-04/schema
    metaschema = requests.get('http://json-schema.org/schema').json()
    metaschema['properties']['id'] = metaschema['properties'].pop('$id')
    metaschema['properties']['exclusiveMinimum'] = {'type': 'boolean', 'default': False}
    metaschema['additionalProperties'] = False

    # See https://tools.ietf.org/html/rfc7396
    metaschema['type'].append('null')

    # OCDS fields.
    metaschema['properties']['codelist'] = {'type': 'string'}
    metaschema['properties']['openCodelist'] = {'type': 'boolean'}
    # @see https://github.com/open-contracting/standard/blob/1.1-dev/standard/docs/en/schema/deprecation.md
    metaschema['properties']['deprecated'] = {
        'type': ['object', 'null'],
        'properties': {
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

    for path, text, data in walk_json_data():
        if '$schema' in data or 'definitions' in data or 'properties' in data:
            errors = 0
            for error in validator(metaschema, format_checker=FormatChecker()).iter_errors(data):
                errors += 1
                print(json.dumps(error.instance, indent=2, separators=(',', ': ')))
                print('{} ({})\n'.format(error.message, '/'.join(error.absolute_schema_path)))
            if errors:
                print('{} is not valid JSON Schema ({} errors)'.format(path, errors))
            assert errors == 0
