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


name = os.path.basename(os.environ.get('TRAVIS_REPO_SLUG', os.getcwd()))

# For identifying extensions, see https://github.com/open-contracting/standard-development-handbook/issues/16
# This should match the logic in `Rakefile`.
other_extensions = ('api_extension', 'ocds_performance_failures', 'public-private-partnerships', 'standard_extension_template')
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

# TODO: See https://github.com/open-contracting/standard-maintenance-scripts/issues/29
url = 'https://raw.githubusercontent.com/open-contracting/standard/3920a12d203df31dc3d31ca64736dab54445c597/standard/schema/meta-schema.json'  # noqa
metaschema = requests.get(url).json()

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

# Draft 6 removes `minItems` from `definitions/stringArray`.
# See https://github.com/open-contracting/api_extension/blob/master/release-package-schema.json#L2
del metaschema['definitions']['stringArray']['minItems']

# See https://tools.ietf.org/html/rfc7396
if is_extension:
    # See https://github.com/open-contracting/ocds_budget_projects_extension/blob/master/release-schema.json#L70
    metaschema['type'] = ['object', 'null']
    # See https://github.com/open-contracting/ocds_milestone_documents_extension/blob/master/release-schema.json#L9
    metaschema['properties']['deprecated']['type'] = ['object', 'null']


def walk():
    """
    Yields all files, except third-party files under `_static` directories.
    """
    for root, dirs, files in os.walk(os.getcwd()):
        if '.git' in dirs:
            dirs.remove('.git')
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
                    # TODO: See https://github.com/open-contracting/standard-maintenance-scripts/issues/16
                    pass
                    # errors += 1
                    # print('{} must set `enum` for closed codelist at {}'.format(path, pointer))
                else:
                    if 'enum' in data:
                        actual = set(data['enum'])
                    else:
                        actual = set(data['items']['enum'])

                    for csvpath, reader in walk_csv_data():
                        # The codelist's CSV file should exist and match the `enum` values.
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


def ensure_title_description_type(path, data, pointer=''):
    """
    Prints and returns the number of errors relating to metadata in a JSON Schema.
    """
    errors = 0

    schema_fields = ('definitions', 'deprecated', 'items', 'patternProperties', 'properties')
    required_fields = ('title', 'description')

    if isinstance(data, list):
        for index, item in enumerate(data):
            errors += ensure_title_description_type(path, item, pointer='{}/{}'.format(pointer, index))
    elif isinstance(data, dict):
        parent = pointer.rsplit('/', 1)[-1]

        # Don't look for metadata fields on non-user-defined objects.
        if parent not in schema_fields:
            for field in required_fields:
                if field not in data:
                    errors += 1
                    print('{} is missing {}/{}'.format(path, pointer, field))
            if 'type' not in data and '$ref' not in data:
                errors += 1
                print('{0} is missing {1}/type or {1}/$ref'.format(path, pointer))

        # Don't iterate into `patternProperties`.
        if parent != 'patternProperties':
            for key, value in data.items():
                errors += ensure_title_description_type(path, value, pointer='{}/{}'.format(pointer, key))

    return errors


def validate_json_schema(path, data, schema, ensure_metadata=not is_extension):  # extensions don't repeat core
    """
    Prints and asserts errors in a JSON Schema.
    """
    errors = 0

    for error in validator(schema, format_checker=FormatChecker()).iter_errors(data):
        errors += 1
        print(json.dumps(error.instance, indent=2, separators=(',', ': ')))
        print('{} ({})\n'.format(error.message, '/'.join(error.absolute_schema_path)))

    if errors:
        print('{} is not valid JSON Schema ({} errors)'.format(path, errors))

    # TODO: https://github.com/open-contracting/standard-maintenance-scripts/issues/27
    # if ensure_metadata and 'versioned-release-validation-schema.json' not in path:
    #     errors += ensure_title_description_type(path, data)

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
    Ensures all JSON Schema files are valid JSON Schema Draft 4 and use codelists correctly. Unless this is an
    extension, ensures JSON Schema files have required metadata.
    """
    for path, text, data in walk_json_data():
        if is_json_schema(data):
            validate_json_schema(path, data, metaschema)


@pytest.mark.skipif(not is_extension, reason='not an extension')
def test_extension_json():
    """
    Ensures the extension's extension.json file is valid against extension-schema.json.
    """
    with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'schema', 'extension-schema.json')) as f:
        schema = json.loads(f.read())

    for path, text, data in walk_json_data():
        if os.path.basename(path) == 'extension.json':
            validate_json_schema(path, data, schema)
            break
    else:
        assert False, 'expected an extension.json file'


@pytest.mark.skipif(not is_extension or name == 'standard_extension_template', reason='not an extension')
def test_empty_files():
    """
    Ensures an extension has no empty files and no versioned-release-validation-schema.json file.
    """
    basenames = (
        'record-package-schema.json',
        'release-package-schema.json',
        'release-schema.json',
    )

    for root, name in walk():
        if name == 'versioned-release-validation-schema.json':
            assert False, 'versioned-release-validation-schema.json should be removed'
        else:
            path = os.path.join(root, name)
            with open(path, 'r') as f:
                text = f.read()
            if name in basenames:
                assert json.loads(text), '{} is empty and should be removed'.format(path)
            else:
                assert text.strip(), '{} is empty and should be removed'.format(path)


@pytest.mark.skipif(not is_extension, reason='not an extension')
def test_json_merge_patch():
    """
    Ensures all extension JSON Schema successfully patch core JSON Schema, generating schema that are valid JSON Schema
    Draft 4, use codelists correctly, and have required metadata.
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

        if basename == 'release-schema.json':
            # TODO: See https://github.com/open-contracting/standard/issues/603
            schemas[basename]['definitions']['Classification']['description'] = ''
            schemas[basename]['definitions']['Identifier']['description'] = ''
            schemas[basename]['definitions']['Milestone']['description'] = ''
            schemas[basename]['definitions']['Organization']['properties']['address']['description'] = ''
            schemas[basename]['definitions']['Organization']['properties']['address']['title'] = ''
            schemas[basename]['definitions']['Organization']['properties']['contactPoint']['description'] = ''
            schemas[basename]['definitions']['Organization']['properties']['contactPoint']['title'] = ''
            schemas[basename]['definitions']['Planning']['properties']['budget']['description'] = ''
            schemas[basename]['definitions']['Planning']['properties']['budget']['title'] = ''
            schemas[basename]['definitions']['Value']['description'] = ''
            schemas[basename]['description'] = ''

            # Two extensions have optional dependencies on ocds_bid_extension.
            if name in ('ocds_lots_extension', 'ocds_requirements_extension'):
                url = 'https://raw.githubusercontent.com/open-contracting/ocds_bid_extension/master/release-schema.json'  # noqa
                json_merge_patch.merge(schemas[basename], requests.get(url).json())

    for path, text, data in walk_json_data():
        if is_json_schema(data):
            basename = os.path.basename(path)
            if basename in basenames:
                unpatched = deepcopy(schemas[basename])
                # It's not clear that `json_merge_patch.merge()` can ever fail.
                patched = json_merge_patch.merge(unpatched, data)

                # We don't `assert patched != schemas[basename]`, because empty patches are allowed. json_merge_patch
                # mutates `unpatched`, which is unexpected, which is why we would test against `schemas[basename]`.
                validate_json_schema(path, patched, metaschema, ensure_metadata=True)
