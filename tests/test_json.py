import json
import os
import re
import warnings
from copy import deepcopy
from functools import lru_cache

import jsonref
import pytest
import requests
from jscc.exceptions import DeepPropertiesWarning
from jscc.schema import extend_schema, is_json_merge_patch, is_json_schema, rejecting_dict
from jscc.testing.checks import (get_empty_files, get_invalid_json_files, get_misindented_files, validate_array_items,
                                 validate_codelist_enum, validate_deep_properties, validate_items_type,
                                 validate_letter_case, validate_merge_properties, validate_metadata_presence,
                                 validate_null_type, validate_object_id, validate_ref, validate_schema,
                                 validate_schema_codelists_match)
from jscc.testing.filesystem import walk_csv_data, walk_json_data
from jscc.testing.util import difference, http_get, http_head, warn_and_assert
from jsonschema import FormatChecker
from jsonschema.validators import Draft4Validator
from ocdskit.schema import add_validation_properties

# Whether to use the 1.2-dev version of OCDS.
use_development_version = '1.2' in os.getenv('GITHUB_REF_NAME', '')

# The codelists defined in `schema/codelists`. XXX Hardcoding.
external_codelists = {
    'awardCriteria.csv',
    'awardStatus.csv',
    'classificationScheme.csv',  # 1.2
    'contractStatus.csv',
    'country.csv',  # 1.2
    'currency.csv',
    'documentType.csv',
    'extendedProcurementCategory.csv',
    'initiationType.csv',
    'itemClassificationScheme.csv',  # 1.1
    'language.csv',  # 1.2
    'linkRelationType.csv',  # 1.2
    'mediaType.csv',  # 1.2
    'method.csv',
    'milestoneStatus.csv',
    'milestoneType.csv',
    'partyRole.csv',
    'partyScale.csv',  # 1.2
    'procurementCategory.csv',
    'relatedProcess.csv',
    'relatedProcessScheme.csv',
    'releaseTag.csv',
    'submissionMethod.csv',
    'tenderStatus.csv',
    'unitClassificationScheme.csv',
}

# https://github.com/open-contracting/extension_registry/blob/main/extensions.csv
core_extensions = {
    'ocds_bid_extension',
    'ocds_enquiry_extension',
    'ocds_location_extension',
    'ocds_lots_extension',
    'ocds_participationFee_extension',
    'ocds_process_title_extension',
}

cwd = os.getcwd()
repo_name = os.path.basename(os.getenv('GITHUB_REPOSITORY', cwd))
ocds_version = os.getenv('OCDS_TEST_VERSION')
is_profile = os.path.isfile('Makefile') and os.path.isdir('docs') and repo_name not in ('standard', 'infrastructure')
is_extension = os.path.isfile('extension.json') or is_profile
extensiondir = os.path.join('schema', 'profile') if is_profile else '.'

if repo_name == 'infrastructure':
    ocds_schema_base_url = 'https://standard.open-contracting.org/infrastructure/schema/'
else:
    ocds_schema_base_url = 'https://standard.open-contracting.org/schema/'
development_base_url = 'https://raw.githubusercontent.com/open-contracting/standard/1.2-dev/schema'
ocds_tags = re.findall(r'\d+__\d+__\d+', http_get(ocds_schema_base_url).text)
if ocds_version:
    ocds_tag = ocds_version.replace('.', '__')
else:
    ocds_tag = ocds_tags[-1]


def formatwarning(message, category, filename, lineno, line=None):
    if category != DeepPropertiesWarning:
        message = f'ERROR: {message}'
    return str(message).replace(cwd + os.sep, '')


warnings.formatwarning = formatwarning
pytestmark = pytest.mark.filterwarnings('always')


def patch(text):
    """
    Handle unreleased tag in $ref.
    """
    if match := re.search(r'\d+__\d+__\d+', text):
        tag = match.group(0)
        if tag not in ocds_tags:
            if ocds_version or not use_development_version:
                text = text.replace(tag, ocds_tag)
            else:
                text = text.replace(ocds_schema_base_url + tag, development_base_url)
    return text


excluded = ('.git', '.ve', '_static', 'build', 'fixtures', 'node_modules')
excluded_repo_name = (
    # data-support extends and stores the release schema to, for example, unflatten data.
    'data-support',
    # pelican-frontend and pelican-backend have a copy of the release schema to generate and validate check names.
    'pelican-backend',
    'pelican-frontend',
    # sphincontrib-opencontracting uses simplified schema files in its documentation.
    'sphinxcontrib-opencontracting',
)
json_schemas = [(path, name, data) for path, name, _, data in walk_json_data(patch, excluded=excluded)
                if is_json_schema(data) and repo_name not in excluded_repo_name]


def merge(*objs):
    """
    Copied from json_merge_patch.
    """
    result = objs[0]
    for obj in objs[1:]:
        result = _merge_obj(result, obj)
    return result


def _merge_obj(result, obj, pointer=''):  # changed code
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
                _merge_obj(target, value, pointer=f'{pointer}/{key}')  # changed code
                continue
            result[key] = {}
            _merge_obj(result[key], value, pointer=f'{pointer}/{key}')  # changed code
            continue

        # new code
        if key in result:
            pointer_and_key = f'{pointer}/{key}'
            # Exceptions.
            if (value is None and pointer_and_key == '/definitions/Milestone/properties/documents/deprecated' and
                    repo_name in ('ocds_milestone_documents_extension', 'public-private-partnerships')):
                warnings.warn(f're-adds {pointer}')
            elif (value == [] and pointer_and_key == '/required' and
                    repo_name == 'ocds_pagination_extension'):
                warnings.warn(f'empties {pointer_and_key}')
            else:
                if is_profile:
                    message = ' - check for repeats across extension_versions.json, dependencies, testDependencies'
                else:
                    message = ''
                raise Exception(f'unexpectedly overwrites {pointer_and_key}{message}')

        if value is None:
            result.pop(key, None)
            continue
        result[key] = value
    return result


@lru_cache()
def metaschemas():
    # Novel uses of JSON Schema features may require updates to other repositories.
    # See https://ocds-standard-development-handbook.readthedocs.io/en/latest/meta/schema_style_guide.html#validation-keywords # noqa: E501
    unused_json_schema_properties = {
        # Validation keywords for numeric instances
        'multipleOf',
        'exclusiveMaximum',

        # Validation keywords for strings
        'maxLength',

        # Validation keywords for arrays
        'additionalItems',
        'maxItems',

        # Validation keywords for objects
        'additionalProperties',
        'dependencies',
        'maxProperties',

        # Validation keywords for any instance type
        'allOf',
        'anyOf',
        'not',
    }

    url = 'https://raw.githubusercontent.com/open-contracting/standard/1.1/schema/meta-schema.json'
    metaschema = http_get(url).json()

    # Draft 6 removes `minItems` from `definitions/stringArray`.
    # See https://github.com/open-contracting-extensions/ocds_api_extension/blob/master/release-package-schema.json#L2
    del metaschema['definitions']['stringArray']['minItems']

    # See https://tools.ietf.org/html/rfc7396
    if is_extension:
        # See https://github.com/open-contracting-extensions/ocds_milestone_documents_extension/blob/master/release-schema.json#L9 # noqa: E501
        metaschema['properties']['deprecated']['type'] = ['object', 'null']

    # Fork the project package schema here, to not add merge properties to it.
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

    # Fork the record package schema here, to not delete properties from metaschema.
    record_package_metaschema = deepcopy(metaschema)

    for prop in unused_json_schema_properties:
        del record_package_metaschema['properties'][prop]
        del project_package_metaschema['properties'][prop]

    subschema = {'$ref': '#/definitions/schemaArray'}
    record_package_metaschema['properties']['items']['anyOf'].remove(subschema)
    project_package_metaschema['properties']['items']['anyOf'].remove(subschema)

    # Record package schema allows oneOf, but release package schema does not.
    release_package_metaschema = deepcopy(record_package_metaschema)

    del release_package_metaschema['properties']['oneOf']
    del project_package_metaschema['properties']['oneOf']

    metaschema['$id'] = deepcopy(metaschema['id'])
    metaschema['properties']['$id'] = deepcopy(metaschema['properties']['id'])

    return {
        'metaschema': metaschema,
        'project_package_metaschema': project_package_metaschema,
        'record_package_metaschema': record_package_metaschema,
        'release_package_metaschema': release_package_metaschema,
    }


def test_empty():
    def include(path, name):
        return name not in {'.gitkeep', 'py.typed'} and (
            # Template repositories are allowed to have empty schema files.
            name not in {'record-package-schema.json', 'release-package-schema.json', 'release-schema.json'}
            or repo_name not in {'standard_extension_template', 'standard_profile_template'}
        )

    warn_and_assert(get_empty_files(include), '{0} is empty, run: rm {0}',
                    'Files are empty. See warnings below.')


@pytest.mark.skipif(os.getenv('OCDS_NOINDENT', False), reason='skipped indentation')
def test_indent():
    def include(path, name):
        # http://json-schema.org/draft-04/schema
        return name not in ('json-schema-draft-4.json', 'package.json', 'package-lock.json')

    warn_and_assert(get_misindented_files(include), '{0} is not indented as expected, run: ocdskit indent {0}',
                    'Files are not indented as expected. See warnings below, or run: ocdskit indent -r .')


def test_json_valid():
    excluded = ('.git', '.ve', '_static', 'build', 'fixtures', 'node_modules')
    warn_and_assert(get_invalid_json_files(excluded=excluded), '{0} is not valid JSON: {1}',
                    'JSON files are invalid. See warnings below.')


def validate_json_schema(path, name, data, schema, full_schema=not is_extension):
    """
    Prints and asserts errors in a JSON Schema.
    """
    errors = 0

    # The standard repository has an example extension.
    if 'docs/examples/organizations/organizational_units/ocds_divisionCode_extension' in path:
        full_schema = False

    # Kingfisher Collect uses JSON Schema files to validate Scrapy items.
    code_repo = repo_name == 'kingfisher-collect'

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
        'dereferenced-release-schema.json',
        # standard-maintenance-scripts
        'codelist-schema.json',
        'extension-schema.json',
        # extension_registry
        'extensions-schema.json',
        'extension_versions-schema.json',
        # spoonbill
        'ocds-simplified-schema.json',
    }
    schema_exceptions = json_schema_exceptions | ocds_schema_exceptions

    validate_items_type_kwargs = {
        'allow_invalid': {
            '/definitions/Amendment/properties/changes/items',  # deprecated
            '/definitions/AmendmentUnversioned/properties/changes/items',  # deprecated
            '/definitions/record/properties/releases/oneOf/0/items',  # 1.1
        },
    }

    def validate_codelist_enum_allow_missing(codelist):
        return is_extension and codelist in external_codelists

    validate_codelist_enum_kwargs = {
        'fallback': {
            '/definitions/Metric/properties/id': ['string'],
            '/definitions/Milestone/properties/code': ['string', 'null'],
        },
        'allow_missing': validate_codelist_enum_allow_missing,
    }

    validate_letter_case_kwargs = {
        'property_exceptions': {'former_value'},  # deprecated
        'definition_exceptions': {'record'},  # 1.1
    }

    def validate_metadata_presence_allow_missing(pointer):
        return 'links' in pointer.split('/') or code_repo  # ocds_pagination_extension

    validate_metadata_presence_kwargs = {
        'allow_missing': validate_metadata_presence_allow_missing,
    }

    def validate_object_id_allow_missing(pointer):
        parts = pointer.split('/')
        return 'versionedRelease' in parts or parts[-1] in {
            'changes',  # deprecated
            'records',  # uses `ocid` not `id`
            '0',  # linked releases
        }

    validate_object_id_kwargs = {
        'allow_missing': validate_object_id_allow_missing,
        'allow_optional': {
            # 2.0 fixes.
            # See https://github.com/open-contracting/standard/issues/650
            '/definitions/Amendment',
            '/definitions/Organization',
            '/definitions/OrganizationReference',
            '/definitions/RelatedProcess',
        },
    }
    if repo_name == 'infrastructure':
        validate_object_id_kwargs['allow_optional'].add('/definitions/Classification')

    validate_null_type_kwargs = {
        # OCDS allows null. OC4IDS disallows null.
        'no_null': repo_name == 'infrastructure' or code_repo,
        'allow_object_null': {
            '/definitions/Amendment/properties/changes/items/properties/former_value',  # deprecated
            # See https://github.com/open-contracting/standard/pull/738#issuecomment-440727233
            '/definitions/Organization/properties/details',
        },
        'allow_no_null': {
            '/definitions/Amendment/properties/changes/items/properties/property',  # deprecated

            # Children of fields with omitWhenMerged.
            '/definitions/Link/properties/rel',
            '/definitions/Link/properties/href',

            # 2.0 fixes.
            # See https://github.com/open-contracting/standard/issues/650
            '/definitions/LinkedRelease/properties/tag',
            '/definitions/Organization/properties/id',
            '/definitions/OrganizationReference/properties/id',
            '/definitions/RelatedProcess/properties/id',
        },
    }

    validate_array_items_kwargs = {
        'allow_invalid': {
            '/definitions/Amendment/properties/changes/items/properties/former_value',  # deprecated
            '/definitions/Location/properties/geometry/properties/coordinates/items',  # recursion
        },
    }

    validate_deep_properties_kwargs = {
        'allow_deep': {
            '/definitions/Amendment/properties/changes/items',  # deprecated
        },
    }
    if is_extension:  # avoid repetition in extensions
        validate_deep_properties_kwargs['allow_deep'].add('/definitions/Item/properties/unit')

    validator = Draft4Validator(schema, format_checker=FormatChecker())

    errors += validate_schema(path, data, validator)
    if errors:
        warnings.warn(f'{path} is not valid JSON Schema ({errors} errors)')

    if name not in schema_exceptions:
        if 'versioned-release-validation-schema.json' in path:
            validate_items_type_kwargs['additional_valid_types'] = ['object']
        errors += validate_array_items(path, data, **validate_array_items_kwargs)
        errors += validate_items_type(path, data, **validate_items_type_kwargs)
        if not code_repo:
            errors += validate_codelist_enum(path, data, **validate_codelist_enum_kwargs)
            errors += validate_letter_case(path, data, **validate_letter_case_kwargs)
        errors += validate_merge_properties(path, data)

    # `full_schema` is set to not expect extensions to repeat information from core.
    if full_schema:
        exceptions_plus_versioned = schema_exceptions | {
            'versioned-release-validation-schema.json',
        }

        exceptions_plus_versioned_and_packages = exceptions_plus_versioned | {
            'project-package-schema.json',
            'record-package-schema.json',
            'release-package-schema.json',
        }

        exceptions_plus_versioned_and_packages_and_record = exceptions_plus_versioned_and_packages | {
            'record-schema.json',
        }

        if not code_repo:
            # Extensions aren't expected to repeat referenced `definitions`.
            errors += validate_ref(path, data)

        if name not in exceptions_plus_versioned:
            # Extensions aren't expected to repeat `title`, `description`, `type`.
            errors += validate_metadata_presence(path, data, **validate_metadata_presence_kwargs)
            if not code_repo:
                # Extensions aren't expected to repeat referenced `definitions`.
                errors += validate_object_id(path, jsonref.replace_refs(data), **validate_object_id_kwargs)

        if name not in exceptions_plus_versioned_and_packages:
            # Extensions aren't expected to repeat `required`. Packages don't have merge rules.
            errors += validate_null_type(path, data, **validate_null_type_kwargs)

        if name not in exceptions_plus_versioned_and_packages_and_record:
            # Extensions aren't expected to repeat referenced codelist CSV files.
            # Only the release schema is presently expected to use all codelists.
            errors += validate_schema_codelists_match(path, data, cwd, is_extension, is_profile, external_codelists)

    else:
        # Don't count these as errors.
        validate_deep_properties(path, data, **validate_deep_properties_kwargs)

    assert not errors, 'One or more JSON Schema files are invalid. See warnings below.'


@pytest.mark.parametrize('path,name,data', json_schemas)
def test_schema_valid(path, name, data):
    """
    Ensures all JSON Schema files are valid JSON Schema Draft 4 and use codelists correctly. Unless this is an
    extension, ensures JSON Schema files have required metadata and valid references.
    """
    schemas = metaschemas()
    if name in ('release-schema.json', 'release-package-schema.json'):
        metaschema = schemas['release_package_metaschema']
    elif name == 'record-package-schema.json':
        metaschema = schemas['record_package_metaschema']
    elif name in ('project-schema.json', 'project-package-schema.json'):
        metaschema = schemas['project_package_metaschema']
    else:
        metaschema = schemas['metaschema']

    validate_json_schema(path, name, data, metaschema)


@pytest.mark.skipif(is_profile or not is_extension or repo_name in core_extensions,
                    reason='is a profile, or is not a community extension (test_schema_strict)')
def test_schema_strict():
    """
    Ensures `ocdskit schema-strict` has been run on all JSON Schema files.
    """
    path = os.path.join(extensiondir, 'release-schema.json')
    if os.path.isfile(path):
        with open(path) as f:
            data = json.load(f)

        original = deepcopy(data)
        add_validation_properties(data)

        assert data == original, f'{path} is missing validation properties, run: ocdskit schema-strict {path}'


@pytest.mark.skipif(not is_extension, reason='not an extension (test_versioned_release_schema)')
def test_versioned_release_schema():
    """
    Ensures the extension contains no versioned-release-validation-schema.json file.
    """
    path = 'versioned-release-validation-schema.json'
    if os.path.exists(path):
        warn_and_assert([path], '{0} is present, run: rm {0}',
                        'Versioned release schema files are present. See warnings below.')


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
        url = 'https://raw.githubusercontent.com/open-contracting/standard-maintenance-scripts/main/schema/extension-schema.json'  # noqa: E501
        schema = http_get(url).json()

    expected_codelists = {name for _, name, _, _, _ in
                          walk_csv_data(top=os.path.join(extensiondir, 'codelists'))}
    expected_schemas = {name for _, name, _, _ in
                        walk_json_data(patch, top=extensiondir) if name.endswith('-schema.json')}

    path = os.path.join(extensiondir, 'extension.json')
    if os.path.isfile(path):
        with open(path) as f:
            data = json.load(f, object_pairs_hook=rejecting_dict)

        validate_json_schema(path, 'extension.json', data, schema)

        urls = data.get('dependencies', []) + data.get('testDependencies', [])
        for url in urls:
            try:
                status_code = http_head(url).status_code
            except requests.exceptions.ConnectionError as e:
                assert False, f'{e} on {url}'
            else:
                assert status_code == 200, f'HTTP {status_code} on {url}'

        urls = list(data['documentationUrl'].values())
        for url in urls:
            try:
                status_code = http_get(url).status_code  # allow redirects
            except requests.exceptions.ConnectionError as e:
                assert False, f'{e} on {url}'
            else:
                assert status_code == 200, f'HTTP {status_code} on {url}'

        actual_codelists = set(data.get('codelists', []))
        if actual_codelists != expected_codelists:
            added, removed = difference(actual_codelists, expected_codelists)
            assert False, f'{path} has mismatch with codelists{added}{removed}'

        actual_schemas = set(data.get('schemas', []))
        if actual_schemas != expected_schemas:
            added, removed = difference(actual_schemas, expected_schemas)
            assert False, f'{path} has mismatch with schema{added}{removed}'
    else:
        # This code is never reached, as the test is only run if there is an extension.json file.
        assert False, 'expected an extension.json file'


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

    for basename in basenames:
        schemas[basename] = http_get(url_pattern.format(basename)).json()

        if basename == 'release-schema.json':
            path = os.path.join(extensiondir, 'extension.json')
            with open(path) as f:
                metadata = json.load(f, object_pairs_hook=rejecting_dict)
                schemas[basename] = extend_schema(basename, schemas[basename], metadata, codelists=external_codelists)

    # This loop is somewhat unnecessary, as repositories contain at most one of each schema file.
    for path, name, text, data in walk_json_data(patch):
        if is_json_merge_patch(data):
            if name in basenames:
                unpatched = deepcopy(schemas[name])
                try:
                    patched = merge(unpatched, data)
                except Exception as e:
                    assert False, f'Exception: {e} {path}'

                # All metadata should be present.
                validate_json_schema(path, name, patched, metaschemas()['metaschema'], full_schema=True)

                # Empty patches aren't allowed. json_merge_patch mutates `unpatched`, so `schemas[name]` is tested.
                assert patched != schemas[name]
