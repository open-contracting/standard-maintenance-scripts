import csv
import json
import os
import re
import warnings
from collections import UserDict
from copy import deepcopy

import json_merge_patch
import pytest
import requests
from jsonref import JsonRef, JsonRefError
from jsonschema import FormatChecker
from jsonschema.validators import Draft4Validator as validator


other_extensions = (
    'api_extension',
    'ocds_performance_failures',
    'public-private-partnerships',
    'standard_extension_template',
    'standard_profile_template',
)

# The codelists defined in `standard/schema/codelists`. XXX Hardcoding.
external_codelists = {
    'awardCriteria.csv',
    'awardStatus.csv',
    'contractStatus.csv',
    'currency.csv',
    'documentType.csv',
    'extendedProcurementCategory.csv',
    'initiationType.csv',
    'itemClassificationScheme.csv',
    'method.csv',
    'milestoneStatus.csv',
    'milestoneType.csv',
    'partyRole.csv',
    'procurementCategory.csv',
    'relatedProcess.csv',
    'relatedProcessScheme.csv',
    'releaseTag.csv',
    'submissionMethod.csv',
    'tenderStatus.csv',
    'unitClassificationScheme.csv',
}

cwd = os.getcwd()

repo_name = os.path.basename(os.environ.get('TRAVIS_REPO_SLUG', cwd))

# This should match the logic in `Rakefile`. XXX Hardcoding.
# For identifying extensions, see https://github.com/open-contracting/standard-development-handbook/issues/16
is_extension = (repo_name.startswith('ocds') and repo_name.endswith('extension') or
                repo_name.startswith('ocds-for-') or repo_name in other_extensions)

# Assumes that only profiles have Makefiles.
is_profile = is_extension and os.path.isfile(os.path.join(cwd, 'Makefile'))

url = 'https://raw.githubusercontent.com/open-contracting/standard/1.1/standard/schema/meta-schema.json'
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

if is_profile:
    # Allow null'ing a property in a profile.
    metaschema['type'] = ['object', 'null']


def custom_warning_formatter(message, category, filename, lineno, line=None):
    return str(message).replace(cwd + os.sep, '')


warnings.formatwarning = custom_warning_formatter


class RejectingDict(UserDict):
    """
    Allows a key to be set at most once, in order to raise an error on duplicate keys in JSON.
    """
    def __setitem__(self, k, v):
        # See https://tools.ietf.org/html/rfc7493#section-2.3
        if k in self.keys():
            raise ValueError('Key set more than once {}'.format(k))
        else:
            return super().__setitem__(k, v)


def object_pairs_hook(pairs):
    rejecting_dict = RejectingDict(pairs)
    # We return the wrapped dict, not the RejectingDict itself, because jsonschema checks the type.
    return rejecting_dict.data


def walk(top=cwd):
    """
    Yields all files, except third-party files under `_static` directories.
    """
    for root, dirs, files in os.walk(top):
        for directory in ('.git', '_static', 'fixtures'):
            if directory in dirs:
                dirs.remove(directory)
        for name in files:
            yield (root, name)


def walk_json_data(top=cwd):
    """
    Yields all JSON data.
    """
    for root, name in walk(top):
        if name.endswith('.json'):
            path = os.path.join(root, name)
            with open(path) as f:
                text = f.read()
                if text:
                    try:
                        yield (path, text, json.loads(text, object_pairs_hook=object_pairs_hook))
                    except json.decoder.JSONDecodeError as e:
                        assert False, '{} is not valid JSON ({})'.format(path, e)


def walk_csv_data(top=cwd):
    """
    Yields all CSV data.
    """
    for root, name in walk(top):
        if name.endswith('.csv'):
            path = os.path.join(root, name)
            with open(path) as f:
                yield (path, csv.DictReader(f))


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

    # new code
    removal_exceptions = {
        '/properties/buyer',  # becomes publicAuthority
        '/definitions/Award/properties/suppliers',  # becomes preferredBidders
        '/definitions/Budget/properties/project',
        '/definitions/Budget/properties/projectID',
    }

    for key, value in obj.items():
        if isinstance(value, dict):
            target = result.get(key)
            if isinstance(target, dict):
                merge_obj(target, value, pointer='{}/{}'.format(pointer, key))  # changed code
                continue
            result[key] = {}
            merge_obj(result[key], value, pointer='{}/{}'.format(pointer, key))  # changed code
            continue

        # new code
        if key in result:
            pointer_and_key = '{}/{}'.format(pointer, key)
            # Exceptions.
            if (value is None and pointer_and_key == '/definitions/Milestone/properties/documents/deprecated' and
                    repo_name == 'ocds_milestone_documents_extension'):
                warnings.warn('re-adds {}'.format(pointer))
            elif (value == [] and pointer_and_key == '/required' and
                    repo_name == 'api_extension'):
                warnings.warn('empties {}'.format(pointer_and_key))
            elif repo_name == 'public-private-partnerships':
                if pointer_and_key == '/properties/tag/items/enum':
                    warnings.warn('overwrites {}'.format(pointer_and_key))
                elif value is None and 'deprecated' in result[key]:
                    warnings.warn('removes deprecated {}'.format(pointer_and_key))
                elif value is None and pointer_and_key in removal_exceptions:
                    warnings.warn('removes {}'.format(pointer_and_key))
                else:
                    raise Exception('unexpectedly overwrites {}'.format(pointer_and_key))
            else:
                raise Exception('unexpectedly overwrites {}'.format(pointer_and_key))

        if value is None:
            result.pop(key, None)
            continue
        result[key] = value
    return result


def collect_codelist_values(path, data, pointer=''):
    """
    Collects `codelist` values from JSON Schema.
    """
    codelists = set()

    if isinstance(data, list):
        for index, item in enumerate(data):
            codelists.update(collect_codelist_values(path, item, pointer='{}/{}'.format(pointer, index)))
    elif isinstance(data, dict):
        if 'codelist' in data:
            codelists.add(data['codelist'])

        for key, value in data.items():
            codelists.update(collect_codelist_values(path, value, pointer='{}/{}'.format(pointer, key)))

    return codelists


def difference(actual, expected):
    """
    Returns strings describing the differences between actual and expected values.
    """
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

    return added, removed


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
    properties_exceptions = {'former_value'}  # deprecated
    definition_exceptions = {'record'}  # 2.0 fix

    def block(path, data, pointer):
        errors = 0

        parent = pointer.rsplit('/', 1)[-1]

        if parent == 'properties':
            for key in data.keys():
                if not re.search(r'^[a-z][A-Za-z]+$', key) and key not in properties_exceptions:
                    errors += 1
                    warnings.warn('{} {}/{} should be lowerCamelCase ASCII letters'.format(path, pointer, key))
        elif parent == 'definitions':
            for key in data.keys():
                if not re.search(r'^[A-Z][A-Za-z]+$', key) and key not in definition_exceptions:
                    errors += 1
                    warnings.warn('{} {}/{} should be UpperCamelCase ASCII letters'.format(path, pointer, key))

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

        parts = pointer.rsplit('/')
        if len(parts) >= 3:
            grandparent = parts[-2]
        else:
            grandparent = None
        parent = parts[-1]

        # Look for metadata fields on user-defined objects only.
        if parent not in schema_fields and grandparent not in schema_sections:
            for field in required_fields:
                # Exception: api_extension has a concise links section.
                if (field not in data or not data[field] or not data[field].strip()) and 'links' not in parts:
                    errors += 1
                    warnings.warn('{} is missing {}/{}'.format(path, pointer, field))
            if 'type' not in data and '$ref' not in data and 'oneOf' not in data:
                errors += 1
                warnings.warn('{0} is missing {1}/type or {1}/$ref or {1}/oneOf'.format(path, pointer))

        return errors

    return traverse(block)(*args)


def validate_null_type(path, data, pointer='', should_be_nullable=True):
    """
    Prints and returns the number of errors relating to non-nullable optional fields and nullable required fields.
    """
    errors = 0

    null_exceptions = {
        '/definitions/Amendment/properties/changes/items/properties/property',  # deprecated

        # API extension adds metadata fields to which this rule doesn't apply.
        '/properties/packageMetadata',
        '/properties/packageMetadata/properties/uri',
        '/properties/packageMetadata/properties/publishedDate',
        '/properties/packageMetadata/properties/publisher',

        # 2.0 fixes.
        # See https://github.com/open-contracting/standard/issues/650
        '/definitions/Organization/properties/id',
        '/definitions/OrganizationReference/properties/id',
        '/definitions/RelatedProcess/properties/id',
        # Extensions.
        '/definitions/ParticipationFee/properties/id',
        '/definitions/Lot/properties/id',
        '/definitions/LotGroup/properties/id',
        '/definitions/Risk/properties/id',
        '/definitions/Shareholder/properties/id',
        '/definitions/Charge/properties/id',
        '/definitions/Metric/properties/id',
        '/definitions/Observation/properties/id',
        '/definitions/PerformanceFailure/properties/id',
        '/definitions/Tariff/properties/id',
    }
    non_null_exceptions = {
        '/definitions/LotDetails',  # actually can be null
    }

    if isinstance(data, list):
        for index, item in enumerate(data):
            errors += validate_null_type(path, item, pointer='{}/{}'.format(pointer, index))
    elif isinstance(data, dict):
        if 'type' in data and pointer:
            nullable = 'null' in data['type']
            array_of_refs_or_objects = data['type'] == 'array' and any(key in data['items'] for key in ('$ref', 'properties'))  # noqa
            if should_be_nullable:
                # A special case: If it's not required (should be nullable), but isn't nullable, it's okay if and only
                # if it's an array of references or objects.
                if not nullable and not array_of_refs_or_objects and pointer not in null_exceptions:
                    errors += 1
                    warnings.warn('{} has optional but non-nullable {} at {}'.format(path, data['type'], pointer))
            elif nullable and pointer not in non_null_exceptions:
                errors += 1
                warnings.warn('{} has required but nullable {} at {}'.format(path, data['type'], pointer))

        required = data.get('required', [])

        for key, value in data.items():
            if key == 'properties':
                for k, v in data[key].items():
                    errors += validate_null_type(path, v, pointer='{}/{}/{}'.format(pointer, key, k),
                                                 should_be_nullable=k not in required)
            elif key == 'definitions':
                for k, v in data[key].items():
                    errors += validate_null_type(path, v, pointer='{}/{}/{}'.format(pointer, key, k),
                                                 should_be_nullable=False)
            elif key == 'items':
                errors += validate_null_type(path, data[key], pointer='{}/{}'.format(pointer, key),
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

        parent = pointer.rsplit('/', 1)[-1]

        cached_types = {
            '/definitions/Metric/properties/id': ['string'],
            '/definitions/Milestone/properties/code': ['string', 'null'],
        }

        if 'codelist' in data:
            if 'type' not in data:  # e.g. if changing an existing property
                types = cached_types.get(pointer, ['array'])
            elif isinstance(data['type'], str):
                types = [data['type']]
            else:
                types = data['type']

            if data['openCodelist']:
                if ('string' in types and 'enum' in data or 'array' in types and 'enum' in data['items']):
                    # Open codelists shouldn't set `enum`.
                    errors += 1
                    warnings.warn('{} must not set `enum` for open codelist at {}'.format(path, pointer))
            else:
                if 'string' in types and 'enum' not in data or 'array' in types and 'enum' not in data['items']:
                    # Fields with closed codelists should set `enum`.
                    errors += 1
                    warnings.warn('{} must set `enum` for closed codelist at {}'.format(path, pointer))

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
                            if 'string' in types and 'null' in types:
                                expected.add(None)

                            if actual != expected:
                                added, removed = difference(actual, expected)

                                errors += 1
                                warnings.warn('{} has mismatch between `enum` and codelist at {}{}{}'.format(
                                    path, pointer, added, removed))

                        break
                else:
                    # When validating a patched schema, the above code will fail to find the core codelists in an
                    # extension, but that is not an error. This duplicates a test in `validate_json_schema`.
                    if is_extension and data['codelist'] not in external_codelists:
                        errors += 1
                        warnings.warn('{} is missing codelist: {}'.format(path, data['codelist']))
        elif 'enum' in data and parent != 'items' or 'items' in data and 'enum' in data['items']:
            # Exception: This profile overwrites `enum`.
            if repo_name != 'public-private-partnerships' or pointer != '/properties/tag':
                # Fields with `enum` should set closed codelists.
                errors += 1
                warnings.warn('{} has `enum` without codelist at {}'.format(path, pointer))

        return errors

    return traverse(block)(*args)


def validate_items_type(path, data, additional_valid_types=None):
    """
    Prints and returns the number of errors relating to the `type` of `items`.
    """
    exceptions = {
        '/definitions/Amendment/properties/changes/items',  # deprecated
        '/definitions/AmendmentUnversioned/properties/changes/items',  # deprecated
        '/definitions/record/properties/releases/oneOf/0/items',  # `type` is `object`
    }

    valid_types = {
        'array',
        'number',
        'string',
    }
    if additional_valid_types:
        valid_types.update(additional_valid_types)

    def block(path, data, pointer):
        errors = 0

        parent = pointer.rsplit('/', 1)[-1]

        if parent == 'items' and 'type' in data:
            if isinstance(data['type'], str):
                types = [data['type']]
            else:
                types = data['type']

            invalid_type = next((_type for _type in types if _type not in valid_types), None)

            if invalid_type and pointer not in exceptions:
                errors += 1
                warnings.warn('{} {} is an invalid `type` for `items` {}'.format(path, invalid_type, pointer))

        return errors

    return traverse(block)(path, data)


def validate_deep_properties(*args):
    """
    Prints warnings relating to deep objects, which, if appropriate, should be modeled as new definitions.
    """
    exceptions = {
        '/definitions/Amendment/properties/changes/items',  # deprecated
    }
    if is_extension:
        exceptions.add('/definitions/Item/properties/unit')  # avoid repetition in extensions

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
    exceptions = {
        'changes',  # deprecated
        'records',  # uses `ocid` not `id`
        '0',  # linked releases
    }

    # An array of objects without `id` fields are rare, but allowed.
    # See http://standard.open-contracting.org/latest/en/schema/merging/#whole-list-merge
    id_presence_extensions = {
        '/definitions/Location',  # /definitions/Planning/properties/project/properties/locations
    }

    # 2.0 fixes.
    # See https://github.com/open-contracting/standard/issues/650
    required_id_exceptions = {
        '/definitions/Amendment',
        '/definitions/Organization',
        '/definitions/OrganizationReference',
        '/definitions/RelatedProcess',
        # Extensions.
        '/definitions/Lot',
        '/definitions/LotGroup',
        '/definitions/ParticipationFee',
    }

    def block(path, data, pointer):
        errors = 0

        parts = pointer.split('/')
        parent = parts[-1]

        # If it's an array of objects.
        if ('type' in data and data['type'] == 'array' and 'properties' in data['items'] and
                parent not in exceptions and 'versionedRelease' not in parts):
            required = data['items'].get('required', [])
            if hasattr(data['items'], '__reference__'):
                original = data['items'].__reference__['$ref'][1:]
            else:
                original = pointer

            if 'id' not in data['items']['properties'] and original not in id_presence_extensions:
                errors += 1
                if original == pointer:
                    warnings.warn('{} object array has no `id` property at {}'.format(path, pointer))
                else:
                    warnings.warn('{} object array has no `id` property at {} (from {})'.format(
                        path, original, pointer))

            if 'id' not in required and not data.get('wholeListMerge') and original not in required_id_exceptions:
                errors += 1
                if original == pointer:
                    warnings.warn('{} object array should require `id` property at {}'.format(path, pointer))
                else:
                    warnings.warn('{} object array should require `id` property at {} (from {})'.format(
                        path, original, pointer))

        return errors

    return traverse(block)(*args)


def validate_ref(path, data):
    ref = JsonRef.replace_refs(data)

    try:
        # `repr` causes the references to be loaded, if possible.
        repr(ref)
    except JsonRefError as e:
        warnings.warn('{} has {} at {}'.format(path, e.message, '/'.join(e.path)))
        return 1

    return 0


def validate_json_schema(path, data, schema, full_schema=not is_extension):
    """
    Prints and asserts errors in a JSON Schema.
    """
    errors = 0

    # Non-OCDS schema don't:
    # * pair "enum" and "codelist"
    # * disallow "null" in "type" of "items"
    # * UpperCamelCase definitions and lowerCamelCase properties
    # * allow "null" in the "type" of optional fields
    # * include "id" fields in objects within arrays
    # * require "title", "description" and "type" properties
    json_schema_exceptions = {
        'json-schema-draft-4.json',
        'meta-schema.json',
        'meta-schema-patch.json',
    }
    ocds_schema_exceptions = {
        'base-release-schema.json',  # is a copy
        'codelist-schema.json',
        'extension-schema.json',
        'extensions-schema.json',
        'extension_versions-schema.json',
    }
    exceptions = json_schema_exceptions | ocds_schema_exceptions

    for error in validator(schema, format_checker=FormatChecker()).iter_errors(data):
        errors += 1
        warnings.warn(json.dumps(error.instance, indent=2, separators=(',', ': ')))
        warnings.warn('{} ({})\n'.format(error.message, '/'.join(error.absolute_schema_path)))

    if errors:
        warnings.warn('{} is not valid JSON Schema ({} errors)'.format(path, errors))

    if all(basename not in path for basename in exceptions):
        errors += validate_codelist_enum(path, data)

    if all(basename not in path for basename in exceptions):
        kwargs = {}
        if 'versioned-release-validation-schema.json' in path:
            kwargs['additional_valid_types'] = ['object']
        errors += validate_items_type(path, data, **kwargs)

    if all(basename not in path for basename in exceptions):
        errors += validate_letter_case(path, data)

    # `full_schema` is set to not expect extensions to repeat information from core.
    if full_schema:
        exceptions_plus_versioned = exceptions | {
            'versioned-release-validation-schema.json',
        }

        exceptions_plus_versioned_and_packages = exceptions_plus_versioned | {
            'record-package-schema.json',
            'release-package-schema.json',
        }

        # Extensions aren't expected to repeat referenced `definitions`.
        errors += validate_ref(path, data)

        # Extensions aren't expected to repeat `required`. Packages don't have merge rules.
        if all(basename not in path for basename in exceptions_plus_versioned_and_packages):
            errors += validate_null_type(path, data)
        # Extensions aren't expected to repeat `title`, `description`, `type`.
        if all(basename not in path for basename in exceptions_plus_versioned):
            errors += validate_title_description_type(path, data)
        # Extensions aren't expected to repeat referenced `definitions`.
        if all(basename not in path for basename in exceptions_plus_versioned):
            errors += validate_object_id(path, JsonRef.replace_refs(data))
        # Extensions aren't expected to repeat referenced codelist CSV files.
        # TODO: This code assumes each schema uses all codelists. So, for now, skip package schema.
        if all(basename not in path for basename in exceptions_plus_versioned_and_packages):
            codelist_files = set()
            for csvpath, reader in walk_csv_data():
                components = csvpath.split(os.sep)
                if is_codelist(reader) and (
                        # Take all codelists in extensions.
                        (is_extension and not is_profile) or
                        # Take non-extension codelists in core and profiles.
                        ('extensions' not in components and 'compiledCodelists' not in components)):
                    name = os.path.basename(csvpath)
                    if name.startswith('+') or name.startswith('-'):
                        if name[1:] not in external_codelists:
                            errors += 1
                            warnings.warn('{} {} modifies non-existent codelist'.format(path, name))
                    else:
                        codelist_files.add(name)

            codelist_values = collect_codelist_values(path, data)
            if is_extension:
                all_codelist_files = codelist_files | external_codelists
            else:
                all_codelist_files = codelist_files

            unused_codelists = [codelist for codelist in codelist_files if codelist not in codelist_values]
            missing_codelists = [codelist for codelist in codelist_values if codelist not in all_codelist_files]

            if unused_codelists:
                errors += 1
                warnings.warn('{} has unused codelists: {}'.format(path, ', '.join(unused_codelists)))
            if missing_codelists:
                errors += 1
                warnings.warn('repository is missing codelists: {}'.format(', '.join(missing_codelists)))
    else:
        errors += validate_deep_properties(path, data)

    assert errors == 0


def test_valid():
    """
    Ensures all JSON files are valid.
    """
    for path, text, data in walk_json_data():
        pass  # fails if the JSON can't be read


def test_indent():
    """
    Ensures all JSON files are valid and formatted for humans.
    """
    external_exceptions = {
        'json-schema-draft-4.json',  # http://json-schema.org/draft-04/schema
    }

    for path, text, data in walk_json_data():
        if os.path.basename(path) not in external_exceptions:
            # See https://github.com/open-contracting/standard-maintenance-scripts/issues/2
            indent2 = json.dumps(data, indent=2, separators=(',', ': ')) + '\n'
            assert text == indent2, "{} is not indented as expected, run: ocdskit indent {}".format(path, path)


def test_json_schema():
    """
    Ensures all JSON Schema files are valid JSON Schema Draft 4 and use codelists correctly. Unless this is an
    extension, ensures JSON Schema files have required metadata and valid references.
    """
    for path, text, data in walk_json_data():
        if is_json_schema(data):
            validate_json_schema(path, data, metaschema)


@pytest.mark.skipif(not is_extension, reason='not an extension (test_extension_json)')
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

    expected = {os.path.basename(path) for path, _ in walk_csv_data(os.path.join(cwd, 'codelists'))}

    path = os.path.join(cwd, 'extension.json')
    if os.path.isfile(path):
        with open(path) as f:
            data = json.load(f, object_pairs_hook=object_pairs_hook)

        validate_json_schema(path, data, schema)

        urls = data.get('dependencies', []) + list(data['documentationUrl'].values())
        for url in urls:
            try:
                status_code = requests.head(url).status_code
                assert status_code == 200, 'HTTP {} on {}'.format(status_code, url)
            except requests.exceptions.ConnectionError as e:
                assert False, '{} on {}'.format(e, url)

        actual = set(data.get('codelists', []))
        if actual != expected:
            added, removed = difference(actual, expected)
            assert False, '{} has mismatch with schema{}{}'.format(
                path, added, removed)

    else:
        assert False, 'expected an extension.json file'


def test_empty_files():
    """
    Ensures an extension has no empty files and no versioned-release-validation-schema.json file.
    """
    basenames = (
        '.keep',
        'record-package-schema.json',
        'release-package-schema.json',
        'release-schema.json',
    )

    # Some files raise UnicodeDecodeError exceptions.
    filename_exceptions = {
        '.DS_Store',
        'chromedriver',
        'chromedriver_linux64.zip',
        'chromedriver_mac64.zip',
        # Python
        '__init__.py',
        # Python packages
        'dependency_links.txt',
    }
    extension_exceptions = {
        # Sphinx
        '.doctree',
        '.inv',
        '.pickle',
        # Gettext
        '.mo',
        # Images
        '.ico',
        '.png',
        # Python
        '.pyc',
        # Python packages
        '.gz',
    }

    for root, name in walk():
        if is_extension and name == 'versioned-release-validation-schema.json':
            assert False, 'versioned-release-validation-schema.json should be removed'
        elif name not in filename_exceptions and os.path.splitext(name)[1] not in extension_exceptions:
            path = os.path.join(root, name)
            try:
                with open(path) as f:
                    text = f.read()
            except UnicodeDecodeError as e:
                assert False, 'UnicodeDecodeError: {} {}'.format(e, path)
            if name in basenames:
                # Exception: Templates are allowed to have empty schema files.
                if repo_name not in ('standard_extension_template', 'standard_profile_template'):
                    assert json.loads(text), '{} is empty and should be removed'.format(path)
            else:
                assert text.strip(), '{} is empty and should be removed'.format(path)


@pytest.mark.skipif(not is_extension, reason='not an extension (test_json_merge_patch)')
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

    # TODO: Waiting for release after 1.1.3.
    # url_pattern = 'http://standard.open-contracting.org/latest/en/{}'
    url_pattern = 'https://raw.githubusercontent.com/open-contracting/standard/1.1-dev/standard/schema/{}'

    def get_dependencies(extension, basename):
        dependencies = extension.get('dependencies', []) + extension.get('testDependencies', [])
        for url in dependencies:
            dependency = requests.get(url).json()
            external_codelists.update(dependency.get('codelists', []))
            schema_url = '{}/{}'.format(url.rsplit('/', 1)[0], basename)
            json_merge_patch.merge(schemas[basename], requests.get(schema_url).json())
            get_dependencies(dependency, basename)

    for basename in basenames:
        schemas[basename] = requests.get(url_pattern.format(basename)).json()

        if basename == 'release-schema.json':
            path = os.path.join(cwd, 'extension.json')
            with open(path) as f:
                get_dependencies(json.load(f, object_pairs_hook=object_pairs_hook), basename)

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
