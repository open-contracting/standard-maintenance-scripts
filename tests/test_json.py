import csv
import json
import os
from collections import OrderedDict
from copy import deepcopy
from io import StringIO

import json_merge_patch
import pytest
import requests
from jsonschema import FormatChecker
from jsonschema.validators import Draft4Validator as validator


# See https://github.com/open-contracting/standard-development-handbook/issues/16
other_extensions = ('ocds_performance_failures', 'public-private-partnerships')
name = os.path.basename(os.environ.get('TRAVIS_REPO_SLUG', os.getcwd()))
is_extension = name.startswith('ocds') and name.endswith('extension') or name in other_extensions

core_codelists = [
    'awardStatus.csv',
    'contractStatus.csv',
    'currency.csv',
    'initiationType.csv',
    'method.csv',
    'milestoneStatus.csv',
    'procurementCategory.csv',
    'releaseTag.csv',
    'tenderStatus.csv',
]

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

# jsonmerge fields for OCDS 1.0.
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

if is_extension:
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
                if text:
                    try:
                        yield (path, text, json.loads(text, object_pairs_hook=OrderedDict))
                    except json.decoder.JSONDecodeError as e:
                        assert False, '{} is not valid JSON ({})'.format(path, e)


def walk_csv_data():
    """
    Yields all CSV data.
    """
    for root, name in walk():
        if name.endswith('.csv'):
            path = os.path.join(root, name)
            with open(path, 'r') as f:
                yield (path, csv.DictReader(StringIO(f.read())))


def is_json_schema(data):
    """
    Returns whether the data is a JSON Schema.
    """
    return '$schema' in data or 'definitions' in data or 'properties' in data


def is_codelist(reader):
    """
    Returns whether the CSV is a codelist.
    """
    return 'Code' in reader.fieldnames


def validate_codelist_enum(path, data, pointer=''):
    """
    Prints and returns the number of errors relating to codelists in a JSON Schema.
    """
    errors = 0

    if isinstance(data, list):
        for index, item in enumerate(data):
            errors += validate_codelist_enum(path, item, pointer='{}/{}'.format(pointer, index))
    elif isinstance(data, dict):
        if 'codelist' in data:
            if isinstance(data['type'], str):
                types = [data['type']]
            else:
                types = data['type']

            if data['openCodelist']:
                # Open codelists shouldn't set `enum`.
                if ('string' in types and 'enum' in data or 'array' in types and 'enum' in data['items']):
                    errors += 1
                    print('{} must not set `enum` for open codelist at {}'.format(path, pointer))
            else:
                # Closed codelists should set `enum`.
                if ('string' in types and 'enum' not in data or 'array' in types and 'enum' not in data['items']):
                    # See https://github.com/open-contracting/standard-maintenance-scripts/issues/16
                    pass
                    # errors += 1
                    # print('{} must set `enum` for closed codelist at {}'.format(path, pointer))
                else:
                    if 'enum' in data:
                        actual = set(data['enum'])
                    else:
                        actual = set(data['items']['enum'])

                    for csvpath, reader in walk_csv_data():
                        if os.path.basename(csvpath) == data['codelist']:
                            expected = set([row['Code'] for row in reader])

                            # Add None if the field is nullable.
                            if None in actual:
                                expected.add(None)

                            if actual != expected:
                                added = actual - expected
                                removed = expected - actual
                                errors += 1
                                print('{} has mismatch between enum and codelist at {}: added {}; removed {}'.format(
                                    path, pointer, ', '.join(added), ', '.join(removed)))

                            break
                    else:
                        # When validating a patched schema, the above code will fail to find the core codelists in an
                        # extension, but that is not an error.
                        if is_extension and data['codelist'] not in core_codelists:
                            errors += 1
                            print('{} refers to nonexistent codelist named {}'.format(path, data['codelist']))
        else:
            for key, value in data.items():
                errors += validate_codelist_enum(path, value, pointer='{}/{}'.format(pointer, key))

    return errors


def validate_json_schema(path, data):
    """
    Prints and asserts errors in a JSON Schema.
    """
    errors = 0

    for error in validator(metaschema, format_checker=FormatChecker()).iter_errors(data):
        errors += 1
        print(json.dumps(error.instance, indent=2, separators=(',', ': ')))
        print('{} ({})\n'.format(error.message, '/'.join(error.absolute_schema_path)))

    if errors:
        print('{} is not valid JSON Schema ({} errors)'.format(path, errors))

    errors += validate_codelist_enum(path, data)

    assert errors == 0


def test_valid():
    """
    Ensures all JSON files are valid.
    """
    for path, text, data in walk_json_data():
        pass  # fails if the JSON can't be read


@pytest.mark.skip(reason='not testing indentation, see open-contracting/standard-maintenance-scripts#2')
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


@pytest.mark.skipif(not is_extension, reason='not an extension')
def test_json_merge_patch():
    """
    Ensures all extension JSON Schema successfully patch core JSON Schema.
    """
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
