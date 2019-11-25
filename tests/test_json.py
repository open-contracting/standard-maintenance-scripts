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

# Whether to use the 1.1-dev version of OCDS.
use_development_version = False

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

exceptional_extensions = (
    'ocds_ppp_extension',
    'public-private-partnerships',
)

# See https://tools.ietf.org/html/draft-fge-json-schema-validation-00
unused_json_schema_properties = {
    # Validation keywords for numeric instances
    'multipleOf',
    'exclusiveMaximum',
    'exclusiveMinimum',

    # Validation keywords for arrays
    'additionalItems',

    # Validation keywords for objects
    'additionalProperties',
    'dependencies',

    # Validation keywords for any instance type
    'allOf',
    'anyOf',
    'not',
}

cwd = os.getcwd()
repo_name = os.path.basename(os.environ.get('TRAVIS_REPO_SLUG', cwd))
ocds_version = os.environ.get('OCDS_TEST_VERSION')
is_profile = os.path.isfile(os.path.join(cwd, 'Makefile')) and repo_name not in ('standard', 'infrastructure')
is_extension = os.path.isfile(os.path.join(cwd, 'extension.json')) or is_profile
extensiondir = os.path.join(cwd, 'schema', 'profile') if is_profile else cwd

if repo_name == 'infrastructure':
    ocds_schema_base_url = 'https://standard.open-contracting.org/infrastructure/schema/'
else:
    ocds_schema_base_url = 'https://standard.open-contracting.org/schema/'
development_base_url = 'https://raw.githubusercontent.com/open-contracting/standard/1.1-dev/standard/schema'
ocds_tags = re.findall(r'\d+__\d+__\d+', requests.get(ocds_schema_base_url).text)
if ocds_version:
    ocds_tag = ocds_version.replace('.', '__')
else:
    ocds_tag = ocds_tags[-1]

url = 'https://raw.githubusercontent.com/open-contracting/standard/1.1/standard/schema/meta-schema.json'
metaschema = requests.get(url).json()

# Draft 6 removes `minItems` from `definitions/stringArray`.
# See https://github.com/open-contracting-extensions/ocds_api_extension/blob/master/release-package-schema.json#L2
del metaschema['definitions']['stringArray']['minItems']

# See https://tools.ietf.org/html/rfc7396
if is_extension:
    # noqa: See https://github.com/open-contracting-extensions/ocds_milestone_documents_extension/blob/master/release-schema.json#L9
    metaschema['properties']['deprecated']['type'] = ['object', 'null']

if repo_name in exceptional_extensions:
    # Allow null'ing a property in these repositories.
    metaschema['type'] = ['object', 'null']

project_package_metaschema = deepcopy(metaschema)

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

# Novel uses of JSON Schema features may require updates to other repositories.
# See https://github.com/open-contracting/standard/issues/757
record_package_metaschema = deepcopy(metaschema)
for prop in unused_json_schema_properties:
    del record_package_metaschema['properties'][prop]
    del project_package_metaschema['properties'][prop]
release_package_metaschema = deepcopy(record_package_metaschema)
del release_package_metaschema['properties']['oneOf']
del project_package_metaschema['properties']['oneOf']


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
    Yields all files, except third-party files under virtual environment, static, build, and test fixture directories.
    """
    for root, dirs, files in os.walk(top):
        for directory in ('.git', '.ve', '_static', 'build', 'fixtures'):
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
                    # Handle unreleased tag in $ref.
                    match = re.search(r'\d+__\d+__\d+', text)
                    if match:
                        tag = match.group(0)
                        if tag not in ocds_tags:
                            if ocds_version or not use_development_version:
                                text = text.replace(tag, ocds_tag)
                            else:
                                text = text.replace(ocds_schema_base_url + tag, development_base_url)
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
            with open(path, newline='') as f:
                yield (path, csv.DictReader(f))


def is_json_schema(data):
    """
    Returns whether the data is a JSON Schema.
    """
    return '$schema' in data or 'definitions' in data or 'properties' in data


def is_json_merge_patch(data):
    """
    Returns whether the data is a JSON Merge Patch.
    """
    return '$schema' not in data and ('definitions' in data or 'properties' in data)


def is_codelist(reader):
    """
    Returns whether the CSV is a codelist.
    """
    return 'Code' in reader.fieldnames


def is_array_of_objects(data):
    """
    Returns whether the field is an array of objects.
    """
    return 'array' in data.get('type', []) and any(key in data.get('items', {}) for key in ('$ref', 'properties'))


def get_types(data):
    """
    Returns a field's `type` as a list.
    """
    if 'type' not in data:
        return []
    if isinstance(data['type'], str):
        return [data['type']]
    return data['type']


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
    overwrite_exceptions = {
        '/properties/tag/items/enum',
        '/properties/initiationType/enum',
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
                    repo_name in ('ocds_milestone_documents_extension', 'public-private-partnerships')):
                warnings.warn('re-adds {}'.format(pointer))
            elif (value == [] and pointer_and_key == '/required' and
                    repo_name == 'ocds_api_extension'):
                warnings.warn('empties {}'.format(pointer_and_key))
            elif repo_name in exceptional_extensions:
                if pointer_and_key in overwrite_exceptions:
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
                    warnings.warn('ERROR: {} {}/{} should be lowerCamelCase ASCII letters'.format(path, pointer, key))
        elif parent == 'definitions':
            for key in data.keys():
                if not re.search(r'^[A-Z][A-Za-z]+$', key) and key not in definition_exceptions:
                    errors += 1
                    warnings.warn('ERROR: {} {}/{} should be UpperCamelCase ASCII letters'.format(path, pointer, key))

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

        # Look for metadata fields on user-defined objects only. (Add exceptional condition for "items" field.)
        if parent not in schema_fields and grandparent not in schema_sections or grandparent == 'properties':
            for field in required_fields:
                # If a field has `$ref`, then its `title` and `description` might defer to the reference.
                # Exceptionally, the ocds_api_extension has a concise links section.
                if (field not in data or not data[field] or not data[field].strip()) and '$ref' not in data and 'links' not in parts:  # noqa
                    errors += 1
                    warnings.warn('ERROR: {} is missing {}/{}'.format(path, pointer, field))

            if 'type' not in data and '$ref' not in data and 'oneOf' not in data:
                errors += 1
                warnings.warn('ERROR: {0} is missing {1}/type or {1}/$ref or {1}/oneOf'.format(path, pointer))

        return errors

    return traverse(block)(*args)


def validate_null_type(path, data, pointer='', allow_null=True, should_be_nullable=True):
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
        # Core extensions.
        '/definitions/ParticipationFee/properties/id',
        '/definitions/Lot/properties/id',
        '/definitions/LotGroup/properties/id',
    }
    non_null_exceptions = {
        '/definitions/LotDetails',  # actually can be null
    }
    object_null_exceptions = {
        '/definitions/Organization/properties/details',
        '/definitions/Amendment/properties/changes/items/properties/former_value',
    }

    if not allow_null:
        should_be_nullable = False

    if isinstance(data, list):
        for index, item in enumerate(data):
            errors += validate_null_type(path, item, pointer='{}/{}'.format(pointer, index), allow_null=allow_null)
    elif isinstance(data, dict):
        if 'type' in data and pointer:
            nullable = 'null' in data['type']
            # Objects should not be nullable.
            if 'object' in data['type'] and 'null' in data['type'] and pointer not in object_null_exceptions:
                errors += 1
                warnings.warn('ERROR: {}: nullable object {} at {}'.format(path, data['type'], pointer))
            if should_be_nullable:
                # A special case: If it's not required (should be nullable), but isn't nullable, it's okay if and only
                # if it's an object or an array of objects/references.
                if not nullable and data['type'] != 'object' and not is_array_of_objects(data) and pointer not in null_exceptions:  # noqa
                    errors += 1
                    warnings.warn('ERROR: {}: non-nullable optional {} at {}'.format(path, data['type'], pointer))
            elif nullable and pointer not in non_null_exceptions:
                errors += 1
                warnings.warn('ERROR: {}: nullable required {} at {}'.format(path, data['type'], pointer))

        required = data.get('required', [])

        for key, value in data.items():
            if key == 'properties':
                for k, v in data[key].items():
                    errors += validate_null_type(path, v, pointer='{}/{}/{}'.format(pointer, key, k),
                                                 allow_null=allow_null, should_be_nullable=k not in required)
            elif key == 'definitions':
                for k, v in data[key].items():
                    errors += validate_null_type(path, v, pointer='{}/{}/{}'.format(pointer, key, k),
                                                 allow_null=allow_null, should_be_nullable=False)
            elif key == 'items':
                errors += validate_null_type(path, data[key], pointer='{}/{}'.format(pointer, key),
                                             allow_null=allow_null, should_be_nullable=False)
            else:
                errors += validate_null_type(path, value, pointer='{}/{}'.format(pointer, key), allow_null=allow_null)

    return errors


def validate_codelist_enum(*args):
    """
    Prints and returns the number of errors relating to codelists in a JSON Schema.
    """
    enum_exceptions = {
        '/properties/tag',
        '/properties/initiationType',
    }

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
            else:
                types = get_types(data)

            if data['openCodelist']:
                if ('string' in types and 'enum' in data or 'array' in types and 'enum' in data['items']):
                    # Open codelists shouldn't set `enum`.
                    errors += 1
                    warnings.warn('ERROR: {} must not set `enum` for open codelist at {}'.format(path, pointer))
            else:
                if 'string' in types and 'enum' not in data or 'array' in types and 'enum' not in data['items']:
                    # Fields with closed codelists should set `enum`.
                    errors += 1
                    warnings.warn('ERROR: {} must set `enum` for closed codelist at {}'.format(path, pointer))

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
                                warnings.warn('ERROR: {} has mismatch between `enum` and codelist at {}{}{}'.format(
                                    path, pointer, added, removed))

                        break
                else:
                    # When validating a patched schema, the above code will fail to find the core codelists in an
                    # extension, but that is not an error. This duplicates a test in `validate_json_schema`.
                    if is_extension and data['codelist'] not in external_codelists:
                        errors += 1
                        warnings.warn('ERROR: {} is missing codelist: {}'.format(path, data['codelist']))
        elif 'enum' in data and parent != 'items' or 'items' in data and 'enum' in data['items']:
            # Exception: This profile overwrites `enum`.
            if repo_name not in exceptional_extensions or pointer not in enum_exceptions:
                # Fields with `enum` should set closed codelists.
                errors += 1
                warnings.warn('ERROR: {} has `enum` without codelist at {}'.format(path, pointer))

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
            types = get_types(data)

            invalid_type = next((_type for _type in types if _type not in valid_types), None)

            if invalid_type and pointer not in exceptions:
                errors += 1
                warnings.warn('ERROR: {} {} is an invalid `items` `type` at {}'.format(path, invalid_type, pointer))

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
    Prints and returns the number of errors relating to objects within arrays lacking `id` fields.
    """
    exceptions = {
        'changes',  # deprecated
        'records',  # uses `ocid` not `id`
        '0',  # linked releases
    }

    required_id_exceptions = {
        # 2.0 fixes.
        # See https://github.com/open-contracting/standard/issues/650
        '/definitions/Amendment',
        '/definitions/Organization',
        '/definitions/OrganizationReference',
        '/definitions/RelatedProcess',
        '/definitions/Lot',
        '/definitions/LotGroup',
        '/definitions/ParticipationFee',
        # See https://github.com/open-contracting/ocds-extensions/issues/83
        '/definitions/Enquiry',
    }

    if repo_name == 'infrastructure':
        required_id_exceptions.add('/definitions/Classification')

    def block(path, data, pointer):
        errors = 0

        parts = pointer.split('/')
        parent = parts[-1]

        # If it's an array of objects.
        if ('type' in data and 'array' in data['type'] and 'properties' in data.get('items', {}) and
                parent not in exceptions and 'versionedRelease' not in parts):
            required = data['items'].get('required', [])

            if hasattr(data['items'], '__reference__'):
                original = data['items'].__reference__['$ref'][1:]
            else:
                original = pointer

            # See https://standard.open-contracting.org/latest/en/schema/merging/#whole-list-merge
            if 'id' not in data['items']['properties'] and not data.get('wholeListMerge'):
                errors += 1
                if original == pointer:
                    warnings.warn('ERROR: {} object array has no `id` property at {}'.format(path, pointer))
                else:
                    warnings.warn('ERROR: {} object array has no `id` property at {} (from {})'.format(
                        path, original, pointer))

            if 'id' not in required and not data.get('wholeListMerge') and original not in required_id_exceptions:
                errors += 1
                if original == pointer:
                    warnings.warn('ERROR: {} object array should require `id` property at {}'.format(path, pointer))
                else:
                    warnings.warn('ERROR: {} object array should require `id` property at {} (from {})'.format(
                        path, original, pointer))

        return errors

    return traverse(block)(*args)


def validate_merge_properties(*args):
    nullable_exceptions = {
        '/definitions/Amendment/properties/changes/items/properties/former_value',  # deprecated
        # See https://github.com/open-contracting/ocds-extensions/issues/83
        '/definitions/Tender/properties/enquiries',
    }

    def block(path, data, pointer):
        errors = 0

        types = get_types(data)

        if 'wholeListMerge' in data:
            if 'array' not in types:
                errors += 1
                warnings.warn('ERROR: {} `wholeListMerge` is set on non-array at {}'.format(path, pointer))
            if 'null' in types:
                errors += 1
                warnings.warn('ERROR: {} `wholeListMerge` is set on nullable at {}'.format(path, pointer))
        elif is_array_of_objects(data) and 'null' in types and pointer not in nullable_exceptions:
            errors += 1
            warnings.warn('ERROR: {} array should be `wholeListMerge` instead of nullable at {}'.format(path, pointer))

        if data.get('omitWhenMerged') and data.get('wholeListMerge'):
            errors += 1
            warnings.warn('ERROR: {} both `omitWhenMerged` and `wholeListMerge` are set at {}'.format(path, pointer))

        return errors

    return traverse(block)(*args)


def validate_ref(path, data):
    ref = JsonRef.replace_refs(data)

    try:
        # `repr` causes the references to be loaded, if possible.
        repr(ref)
    except JsonRefError as e:
        warnings.warn('ERROR: {} has {} at {}'.format(path, e.message, '/'.join(e.path)))
        return 1

    return 0


def validate_json_schema(path, data, schema, full_schema=not is_extension, top=cwd):
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
        'codelist-schema.json',
        'extension-schema.json',
        'extensions-schema.json',
        'extension_versions-schema.json',
        'dereferenced-release-schema.json',
    }
    exceptions = json_schema_exceptions | ocds_schema_exceptions
    allow_null = repo_name != 'infrastructure'

    for error in validator(schema, format_checker=FormatChecker()).iter_errors(data):
        errors += 1
        warnings.warn(json.dumps(error.instance, indent=2, separators=(',', ': ')))
        warnings.warn('ERROR: {} ({})\n'.format(error.message, '/'.join(error.absolute_schema_path)))

    if errors:
        warnings.warn('ERROR: {} is not valid JSON Schema ({} errors)'.format(path, errors))

    if all(basename not in path for basename in exceptions):
        kwargs = {}
        if 'versioned-release-validation-schema.json' in path:
            kwargs['additional_valid_types'] = ['object']
        errors += validate_items_type(path, data, **kwargs)
        errors += validate_codelist_enum(path, data)
        errors += validate_letter_case(path, data)
        errors += validate_merge_properties(path, data)

    # `full_schema` is set to not expect extensions to repeat information from core.
    if full_schema:
        exceptions_plus_versioned = exceptions | {
            'versioned-release-validation-schema.json',
        }

        exceptions_plus_versioned_and_packages = exceptions_plus_versioned | {
            'project-package-schema.json',
            'record-package-schema.json',
            'release-package-schema.json',
            'project-package-schema.json',
        }

        # Extensions aren't expected to repeat referenced `definitions`.
        errors += validate_ref(path, data)

        if all(basename not in path for basename in exceptions_plus_versioned):
            # Extensions aren't expected to repeat `title`, `description`, `type`.
            errors += validate_title_description_type(path, data)
            # Extensions aren't expected to repeat referenced `definitions`.
            errors += validate_object_id(path, JsonRef.replace_refs(data))

        if all(basename not in path for basename in exceptions_plus_versioned_and_packages):
            # Extensions aren't expected to repeat `required`. Packages don't have merge rules.
            errors += validate_null_type(path, data, allow_null=allow_null)

            # Extensions aren't expected to repeat referenced codelist CSV files.
            # TODO: This code assumes each schema uses all codelists. So, for now, skip package schema.
            codelist_files = set()
            for csvpath, reader in walk_csv_data(top):
                parts = csvpath.replace(top, '').split(os.sep)  # maybe inelegant way to isolate consolidated extension
                if is_codelist(reader) and (
                        # Take all codelists in extensions.
                        (is_extension and not is_profile) or
                        # Take non-extension codelists in core, and non-core codelists in profiles.
                        not any(c in parts for c in ('extensions', 'patched'))):
                    name = os.path.basename(csvpath)
                    if name.startswith(('+', '-')):
                        if name[1:] not in external_codelists:
                            errors += 1
                            warnings.warn('ERROR: {} {} modifies non-existent codelist'.format(path, name))
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
                warnings.warn('ERROR: {} has unused codelists: {}'.format(path, ', '.join(unused_codelists)))
            if missing_codelists:
                errors += 1
                warnings.warn('ERROR: repository is missing codelists: {}'.format(', '.join(missing_codelists)))
    else:
        errors += validate_deep_properties(path, data)

    assert errors == 0, 'One or more JSON Schema files are invalid. See warnings below.'


def test_valid():
    """
    Ensures all JSON files are valid.
    """
    for path, text, data in walk_json_data():
        pass  # fails if the JSON can't be read


@pytest.mark.skipif(os.environ.get('OCDS_NOINDENT', False), reason='skipped indentation')
def test_indent():
    """
    Ensures all JSON files are valid and formatted for humans.
    """
    path_exceptions = {
        # Files
        'json-schema-draft-4.json',  # http://json-schema.org/draft-04/schema
    }

    errors = 0

    for path, text, data in walk_json_data():
        parts = path.split(os.sep)
        if not any(exception in parts for exception in path_exceptions):
            expected = json.dumps(data, ensure_ascii=False, indent=2, separators=(',', ': ')) + '\n'
            if text != expected:
                errors += 1
                warnings.warn('ERROR: {} is not indented as expected, run: ocdskit indent {}'.format(path, path))

    assert errors == 0, 'Files are not indented as expected. See warnings below, or run: ocdskit indent -r .'


def test_json_schema():
    """
    Ensures all JSON Schema files are valid JSON Schema Draft 4 and use codelists correctly. Unless this is an
    extension, ensures JSON Schema files have required metadata and valid references.
    """
    for path, text, data in walk_json_data():
        if is_json_schema(data):
            basename = os.path.basename(path)
            if basename in ('release-schema.json', 'release-package-schema.json'):
                schema = release_package_metaschema
            elif basename == 'record-package-schema.json':
                schema = record_package_metaschema
            elif basename in ('project-schema.json', 'project-package-schema.json'):
                schema = project_package_metaschema
            else:
                schema = metaschema
            validate_json_schema(path, data, schema)


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

    expected_codelists = {os.path.basename(path) for path, _ in
                          walk_csv_data(os.path.join(extensiondir, 'codelists'))}
    expected_schemas = {os.path.basename(path) for path, _, _ in
                        walk_json_data(extensiondir) if path.endswith('-schema.json')}

    path = os.path.join(extensiondir, 'extension.json')
    if os.path.isfile(path):
        with open(path) as f:
            data = json.load(f, object_pairs_hook=object_pairs_hook)

        validate_json_schema(path, data, schema)

        urls = data.get('dependencies', []) + data.get('testDependencies', [])
        for url in urls:
            try:
                status_code = requests.head(url).status_code
                assert status_code == 200, 'HTTP {} on {}'.format(status_code, url)
            except requests.exceptions.ConnectionError as e:
                assert False, '{} on {}'.format(e, url)

        urls = list(data['documentationUrl'].values())
        for url in urls:
            try:
                status_code = requests.get(url).status_code  # allow redirects
                assert status_code == 200, 'HTTP {} on {}'.format(status_code, url)
            except requests.exceptions.ConnectionError as e:
                assert False, '{} on {}'.format(e, url)

        actual_codelists = set(data.get('codelists', []))
        if actual_codelists != expected_codelists:
            added, removed = difference(actual_codelists, expected_codelists)
            assert False, '{} has mismatch with schema{}{}'.format(
                path, added, removed)

        actual_schemas = set(data.get('schemas', []))
        if actual_schemas != expected_schemas:
            added, removed = difference(actual_schemas, expected_schemas)
            assert False, '{} has mismatch with schema{}{}'.format(
                path, added, removed)
    else:
        # This code is never reached, as the test is only run if there is an extension.json file.
        assert False, 'expected an extension.json file'


def test_empty_files():
    """
    Ensures a repository has no empty files and an extension has no versioned-release-validation-schema.json file.
    """
    basenames = (
        '.keep',
        'record-package-schema.json',
        'release-package-schema.json',
        'release-schema.json',
    )

    # Some files raise UnicodeDecodeError exceptions.
    path_exceptions = {
        # Files
        '.DS_Store',
        'cache.sqlite',
        'chromedriver',
        'chromedriver_linux64.zip',
        'chromedriver_mac64.zip',
        # Python
        '.ve',
        '__init__.py',
        # Python packages
        'dependency_links.txt',
    }
    extension_exceptions = {
        # Excel
        '.xlsx',
        # Fonts
        '.eot',
        '.ttf',
        '.woff',
        '.woff2',
        # Gettext
        '.mo',
        # Images
        '.ico',
        '.jpg',
        '.png',
        # Packages
        '.deb',
        # Python
        '.pyc',
        # Python packages
        '.gz',
        # Sphinx
        '.doctree',
        '.inv',
        '.pickle',
    }

    for root, name in walk():
        path = os.path.join(root, name)
        parts = path.split(os.sep)

        if is_extension and name == 'versioned-release-validation-schema.json':
            assert False, 'versioned-release-validation-schema.json should be removed'
        elif not any(e in parts for e in path_exceptions) and os.path.splitext(name)[1] not in extension_exceptions:
            try:
                with open(path) as f:
                    text = f.read()
            except UnicodeDecodeError as e:
                assert False, 'UnicodeDecodeError: {} {}'.format(e, path)
            if name in basenames:
                # Exception: Templates are allowed to have empty schema files.
                if repo_name not in ('standard_extension_template', 'standard_profile_template'):
                    try:
                        assert json.loads(text), '{} is empty and should be removed'.format(path)
                    except json.decoder.JSONDecodeError as e:
                        assert False, '{} is not valid JSON ({})'.format(path, e)
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

    if ocds_version or not use_development_version:
        url_pattern = ocds_schema_base_url + ocds_tag + '/{}'
    else:
        url_pattern = development_base_url + '/{}'

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
            path = os.path.join(extensiondir, 'extension.json')
            with open(path) as f:
                get_dependencies(json.load(f, object_pairs_hook=object_pairs_hook), basename)

    # This loop is somewhat unnecessary, as repositories contain at most one of each schema file.
    for path, text, data in walk_json_data():
        if is_json_merge_patch(data):
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
