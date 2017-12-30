import csv
import json
import os
import re
import warnings
from collections import OrderedDict
from copy import deepcopy
from io import StringIO

import json_merge_patch
import pytest
import requests
from jsonref import JsonRef, JsonRefError
from jsonschema import FormatChecker
from jsonschema.validators import Draft4Validator as validator


repo_name = os.path.basename(os.environ.get('TRAVIS_REPO_SLUG', os.getcwd()))

# For identifying extensions, see https://github.com/open-contracting/standard-development-handbook/issues/16
# This should match the logic in `Rakefile`.
other_extensions = ('api_extension', 'ocds_performance_failures', 'public-private-partnerships',
                    'standard_extension_template')
is_extension = repo_name.startswith('ocds') and repo_name.endswith('extension') or repo_name in other_extensions

# The codelists defined in the standard.
external_codelists = [
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
    # See https://github.com/open-contracting/ocds_milestone_documents_extension/blob/master/release-schema.json#L9
    metaschema['properties']['deprecated']['type'] = ['object', 'null']


def walk(top=os.getcwd()):
    """
    Yields all files, except third-party files under `_static` directories.
    """
    for root, dirs, files in os.walk(top):
        for directory in ('.git', '_static', 'fixtures'):
            if directory in dirs:
                dirs.remove(directory)
        for name in files:
            yield (root, name)


def walk_json_data(top=os.getcwd()):
    """
    Yields all JSON data.
    """
    for root, name in walk(top):
        if name.endswith('.json'):
            path = os.path.join(root, name)
            with open(path, 'r') as f:
                text = f.read()
                if text:
                    try:
                        yield (path, text, json.loads(text, object_pairs_hook=OrderedDict))
                    except json.decoder.JSONDecodeError as e:
                        assert False, '{} is not valid JSON ({})'.format(path, e)


def walk_csv_data(top=os.getcwd()):
    """
    Yields all CSV data.
    """
    for root, name in walk(top):
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


def merge(*objs):
    """
    Copied from json_merge_patch.
    """
    result = objs[0]
    for obj in objs[1:]:
        result = merge_obj(result, obj)
    return result


def merge_obj(result, obj, pointer=''):  # changed code
    """
    Copied from json_merge_patch, with edits to raise an error if overwriting.
    """
    if not isinstance(result, dict):
        result = {}

    if not isinstance(obj, dict):
        return obj

    for key, value in obj.items():
        if isinstance(value, dict):
            target = result.get(key)
            if isinstance(target, dict):
                merge_obj(target, value, pointer='{}/{}'.format(pointer, key))  # changed code
                continue
            result[key] = {}
            merge_obj(result[key], value, pointer='{}/{}'.format(pointer, key))  # changed code
            continue

        if key in result:  # new code
            if key == 'deprecated' and value is None:  # ocds_milestone_documents_extension
                warnings.warn('reintroduces {}'.format(pointer))
            elif key == 'required' and value == []:  # api_extension
                warnings.warn('empties {}/{}'.format(pointer, key))
            else:
                raise Exception('unexpectedly overwrites {}/{}'.format(pointer, key))

        if value is None:
            result.pop(key, None)
            continue
        result[key] = value
    return result


def traverse(block):
    """
    Implements common logic used by methods below.
    """
    def method(path, data, pointer=''):
        errors = 0

        if isinstance(data, list):
            for index, item in enumerate(data):
                errors += method(path, item, pointer='{}/{}'.format(pointer, index))
        elif isinstance(data, dict):
            errors += block(path, data, pointer)

            for key, value in data.items():
                errors += method(path, value, pointer='{}/{}'.format(pointer, key))

        return errors

    return method


def validate_letter_case(*args):
    """
    Prints and returns the number of errors relating to the letter case of properties and definitions.
    """
    properties_exceptions = {'former_value'}
    definition_exceptions = {'record'}

    def block(path, data, pointer):
        errors = 0

        parent = pointer.rsplit('/', 1)[-1]

        if parent == 'properties':
            for key in data.keys():
                if not re.search(r'^[a-z][A-Za-z]+$', key) and key not in properties_exceptions:
                    errors += 1
                    print('{} {}/{} should be lowerCamelCase ASCII letters'.format(path, pointer, key))
        elif parent == 'definitions':
            for key in data.keys():
                if not re.search(r'^[A-Z][A-Za-z]+$', key) and key not in definition_exceptions:
                    errors += 1
                    print('{} {}/{} should be UpperCamelCase ASCII letters'.format(path, pointer, key))

        return errors

    return traverse(block)(*args)


def validate_title_description_type(*args):
    """
    Prints and returns the number of errors relating to metadata in a JSON Schema.
    """
    schema_fields = ('definitions', 'deprecated', 'items', 'patternProperties', 'properties')
    schema_sections = ('patternProperties',)
    required_fields = ('title', 'description')

    def block(path, data, pointer):
        errors = 0

        parts = pointer.rsplit('/', 2)
        if len(parts) == 3:
            grandparent = parts[-2]
        else:
            grandparent = None
        parent = parts[-1]

        # Don't look for metadata fields on non-user-defined objects.
        if parent not in schema_fields and grandparent not in schema_sections:
            for field in required_fields:
                if field not in data or not data[field] or not data[field].strip():
                    errors += 1
                    print('{} is missing {}/{}'.format(path, pointer, field))
            if 'type' not in data and '$ref' not in data:
                errors += 1
                print('{0} is missing {1}/type or {1}/$ref'.format(path, pointer))

        return errors

    return traverse(block)(*args)


def validate_null_type(path, data, pointer='', should_be_nullable=True):
    """
    Prints and returns the number of errors relating to non-nullable optional fields and nullable required fields.
    """
    errors = 0

    if isinstance(data, list):
        for index, item in enumerate(data):
            errors += validate_null_type(path, item, pointer='{}/{}'.format(pointer, index))
    elif isinstance(data, dict):
        if 'type' in data and pointer:
            nullable = 'null' in data['type']
            array_of_refs_or_objects = data['type'] == 'array' and any(key in data['items'] for key in ('$ref', 'properties'))  # noqa
            if should_be_nullable:
                if not nullable and not array_of_refs_or_objects:
                    errors += 1
                    print('{} has optional but non-nullable {} at {}'.format(path, data['type'], pointer))
            else:
                if nullable:
                    errors += 1
                    print('{} has required but nullable {} at {}'.format(path, data['type'], pointer))

        required = data.get('required', [])

        for key, value in data.items():
            if key == 'properties':
                for k, v in data[key].items():
                    errors += validate_null_type(path, v, pointer='{}/{}/{}'.format(pointer, key, k),
                                                 should_be_nullable=k not in required)
            elif key in ('definitions', 'items'):
                for k, v in data[key].items():
                    errors += validate_null_type(path, v, pointer='{}/{}/{}'.format(pointer, key, k),
                                                 should_be_nullable=False)
            else:
                errors += validate_null_type(path, value, pointer='{}/{}'.format(pointer, key))

    return errors


def validate_codelist_enum(*args):
    """
    Prints and returns the number of errors relating to codelists in a JSON Schema.
    """
    def block(path, data, pointer):
        errors = 0

        if 'codelist' in data:
            if isinstance(data['type'], str):
                types = [data['type']]
            else:
                types = data['type']

            if data['openCodelist']:
                if ('string' in types and 'enum' in data or 'array' in types and 'enum' in data['items']):
                    # Open codelists shouldn't set `enum`.
                    errors += 1
                    print('{} must not set `enum` for open codelist at {}'.format(path, pointer))
            else:
                if 'string' in types and 'enum' not in data or 'array' in types and 'enum' not in data['items']:
                    # Fields with closed codelists should set `enum`.
                    errors += 1
                    print('{} must set `enum` for closed codelist at {}'.format(path, pointer))

                    actual = None
                elif 'string' in types:
                    actual = set(data['enum'])
                else:
                    actual = set(data['items']['enum'])

                # It'd be faster to cache the CSVs, but most extensions have only one closed codelist.
                for csvpath, reader in walk_csv_data():
                    # The codelist's CSV file should exist.
                    if os.path.basename(csvpath) == data['codelist']:
                        # The codelist's CSV file should match the `enum` values, if the field is set.
                        if actual:
                            expected = set([row['Code'] for row in reader])

                            # Add None if the field is nullable.
                            if 'null' in types:
                                expected.add(None)

                            if actual != expected:
                                added = actual - expected
                                if added:
                                    added = '; added {}'.format(added)
                                else:
                                    added = ''

                                removed = expected - actual
                                if removed:
                                    removed = '; removed {}'.format(removed)
                                else:
                                    removed = ''

                                errors += 1
                                print('{} has mismatch between `enum` and codelist at {}{}{}'.format(
                                    path, pointer, added, removed))

                        break
                else:
                    # When validating a patched schema, the above code will fail to find the core codelists in an
                    # extension, but that is not an error.
                    if is_extension and data['codelist'] not in external_codelists:
                        errors += 1
                        print('{} names nonexistent codelist {}'.format(path, data['codelist']))
        elif 'enum' in data:
            pass
            # TODO: See https://github.com/open-contracting/standard-maintenance-scripts/issues/16
            # Fields with `enum` should set closed codelists.
            # errors += 1
            # print('{} has `enum` without codelist at {}'.format(path, pointer))

        return errors

    return traverse(block)(*args)


def validate_deep_properties(*args):
    """
    Prints and returns the number of errors relating to deep objects, which should be modeled as new definitions.
    """
    exceptions = {'/definitions/Item/properties/unit', '/definitions/Amendment/properties/changes/items'}

    def block(path, data, pointer):
        parts = pointer.rsplit('/', 2)
        if len(parts) == 3:
            grandparent = parts[-2]
        else:
            grandparent = None

        if pointer and grandparent != 'definitions' and 'properties' in data and pointer not in exceptions:
            warnings.warn('{} has deep properties at {}'.format(path, pointer))

        return 0

    return traverse(block)(*args)


def validate_object_id(*args):
    """
    Prints and returns the number of errors relating objects within arrays lacking `id` fields.
    """
    # `changes` is deprecated, and `records` uses `ocid`.
    exceptions = {'changes', 'records'}

    def block(path, data, pointer):
        errors = 0

        parts = pointer.rsplit('/')
        if len(parts) >= 3:
            grandparent = parts[-2]
        else:
            grandparent = None
        parent = parts[-1]

        if 'type' in data and data['type'] == 'array':
            if 'properties' in data['items'] and 'id' not in data['items']['properties']:
                if 'versionedRelease' not in pointer and grandparent != 'oneOf' and parent not in exceptions:
                    errors += 1
                    print('{} object array has no `id` property at {}'.format(path, pointer))

        return errors

    return traverse(block)(*args)


def validate_ref(path, data):
    ref = JsonRef.replace_refs(data)

    try:
        # `repr` causes the references to be loaded, if possible.
        repr(ref)
    except JsonRefError as e:
        print('{} has {} at {}'.format(path, e.message, '/'.join(e.path)))
        return 1

    return 0


def validate_json_schema(path, data, schema, full_schema=not is_extension):
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

    errors += validate_codelist_enum(path, data)

    if not full_schema:
        errors += validate_deep_properties(path, data)

    # JSON Schema has definitions that aren't UpperCamelCase.
    if 'json-schema-draft-4.json' not in path:
        errors += validate_letter_case(path, data)

    # `full_schema` is set to not expect extensions to repeat `title`, `description`, `type`, `required` and
    # `definitions` from core.
    if full_schema:
        # TODO: https://github.com/open-contracting/standard/issues/630
        # errors += validate_null_type(path, data)
        errors += validate_ref(path, data)

        object_id_exceptions = [
            'entry-schema.json',
            'json-schema-draft-4.json',
            'versioned-release-validation-schema.json',
        ]

        if all(basename not in path for basename in object_id_exceptions):
            errors += validate_object_id(path, JsonRef.replace_refs(data))

        # TODO: https://github.com/open-contracting/standard-maintenance-scripts/issues/27
        # `versioned-release-validation-schema.json` omits `title` and `description`.
        # if 'versioned-release-validation-schema.json' not in path:
        #     errors += validate_title_description_type(path, data)

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
    extension, ensures JSON Schema files have required metadata and valid references.
    """
    for path, text, data in walk_json_data():
        if is_json_schema(data):
            validate_json_schema(path, data, metaschema)


@pytest.mark.skipif(not is_extension, reason='not an extension')
def test_extension_json():
    """
    Ensures the extension's extension.json file is valid against extension-schema.json, all codelists are included, and
    all URLs resolve.
    """
    path = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'schema', 'extension-schema.json')
    if os.path.isfile(path):
        with open(path) as f:
            schema = json.load(f)
    else:
        url = 'https://raw.githubusercontent.com/open-contracting/standard-maintenance-scripts/master/schema/extension-schema.json'  # noqa
        schema = requests.get(url).json()

    expected = set()

    for path, data in walk_csv_data(os.path.join(os.getcwd(), 'codelists')):
        if 'codelists' in path.split(os.sep):
            expected.add(os.path.basename(path))

    path = os.path.join(os.getcwd(), 'extension.json')
    if os.path.isfile(path):
        with open(path) as f:
            data = json.load(f, object_pairs_hook=OrderedDict)

        validate_json_schema(path, data, schema)

        urls = data.get('dependencies', []) + list(data['documentationUrl'].values())
        for url in urls:
            status_code = requests.head(url).status_code
            assert status_code == 200, 'HTTP {} on {}'.format(status_code, url)

        assert expected == set(data.get('codelists', []))
    else:
        assert False, 'expected an extension.json file'


@pytest.mark.skipif(not is_extension, reason='not an extension')
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
        # __init__.py files are allowed to be empty. PNG files raise UnicodeDecodeError exceptions.
        elif not name == '__init__.py' and not name.endswith('.png'):
            path = os.path.join(root, name)
            try:
                with open(path, 'r') as f:
                    text = f.read()
            except UnicodeDecodeError as e:
                assert False, 'UnicodeDecodeError: {} {}'.format(e, path)
            if name in basenames:
                # standard_extension_template is allowed to have empty schema files.
                if repo_name != 'standard_extension_template':
                    assert json.loads(text), '{} is empty and should be removed'.format(path)
            else:
                assert text.strip(), '{} is empty and should be removed'.format(path)


@pytest.mark.skipif(not is_extension, reason='not an extension')
def test_json_merge_patch():
    """
    Ensures all extension JSON Schema successfully patch and change core JSON Schema, generating schema that are valid
    JSON Schema Draft 4, use codelists correctly, and have required metadata.
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
            # TODO: See https://github.com/open-contracting/standard/issues/630
            schemas[basename]['definitions']['OrganizationReference']['properties']['name']['type'] = ['string']  # noqa
            schemas[basename]['definitions']['Amendment']['properties']['changes']['items']['properties']['property']['type'] = ['string', 'null']  # noqa
            schemas[basename]['definitions']['Item']['properties']['unit']['type'] = ['object', 'null']  # noqa
            schemas[basename]['definitions']['Organization']['properties']['id']['type'] = ['string', 'null']  # noqa
            schemas[basename]['definitions']['OrganizationReference']['properties']['id']['type'] = ['string', 'integer', 'null']  # noqa
            schemas[basename]['definitions']['RelatedProcess']['properties']['id']['type'] = ['string', 'null']  # noqa

            # TODO: See https://github.com/open-contracting/standard/issues/603
            schemas[basename]['definitions']['Classification']['description'] = 'TODO'
            schemas[basename]['definitions']['Identifier']['description'] = 'TODO'
            schemas[basename]['definitions']['Milestone']['description'] = 'TODO'
            schemas[basename]['definitions']['Organization']['properties']['address']['description'] = 'TODO'
            schemas[basename]['definitions']['Organization']['properties']['address']['title'] = 'TODO'
            schemas[basename]['definitions']['Organization']['properties']['contactPoint']['description'] = 'TODO'
            schemas[basename]['definitions']['Organization']['properties']['contactPoint']['title'] = 'TODO'
            schemas[basename]['definitions']['Period']['description'] = 'TODO'
            schemas[basename]['definitions']['Planning']['properties']['budget']['description'] = 'TODO'
            schemas[basename]['definitions']['Planning']['properties']['budget']['title'] = 'TODO'
            schemas[basename]['definitions']['Value']['description'] = 'TODO'
            schemas[basename]['description'] = 'TODO'

            path = os.path.join(os.getcwd(), 'extension.json')
            with open(path) as f:
                data = json.load(f, object_pairs_hook=OrderedDict)
                for extension_url in data.get('dependencies', []):
                    external_codelists.extend(requests.get(extension_url).json().get('codelists', []))
                    schema_url = '{}/{}'.format(extension_url.rsplit('/', 1)[0], basename)
                    json_merge_patch.merge(schemas[basename], requests.get(schema_url).json())

    # This loop is somewhat unnecessary, as repositories contain at most one of each schema file.
    for path, text, data in walk_json_data():
        if is_json_schema(data):
            basename = os.path.basename(path)
            if basename in basenames:
                unpatched = deepcopy(schemas[basename])
                try:
                    patched = merge(unpatched, data)
                except Exception as e:
                    assert False, 'Exception: {} {}'.format(e, path)

                # All metadata should be present.
                validate_json_schema(path, patched, metaschema, full_schema=True)

                # Empty patches aren't allowed. json_merge_patch mutates `unpatched`, so `schemas[basename]` is tested.
                assert patched != schemas[basename]
