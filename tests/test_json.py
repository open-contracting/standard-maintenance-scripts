import json
import os
import re
import warnings
from copy import deepcopy
from functools import lru_cache

import jscc.testing.checks
import json_merge_patch
import pytest
import requests
# Import some tests that will be run by pytest, noqa needed because we don't use them directly
from jscc.testing.checks import (difference, get_empty_files, get_invalid_json_files,  # noqa: F401
                                 get_unindented_files, is_extension, is_profile, get_json_schema_errors,
                                 validate_json_schema)
from jscc.testing.schema import is_json_schema, is_json_merge_patch
from jscc.testing.traversal import walk_csv_data, walk_json_data
from jscc.testing.util import http_get, http_head, rejecting_dict, warn_and_assert


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
jscc.testing.checks.external_codelists = external_codelists

exceptional_extensions = {
    'ocds_ppp_extension',
    'public-private-partnerships',
}
jscc.testing.checks.exceptional_extensions = exceptional_extensions

template_repositories = {
    'standard_extension_template',
    'standard_profile_template',
}
schema_files = (
    'record-package-schema.json',
    'release-package-schema.json',
    'release-schema.json',
)

cwd = os.getcwd()
repo_name = os.path.basename(os.environ.get('TRAVIS_REPO_SLUG', cwd))
ocds_version = os.environ.get('OCDS_TEST_VERSION')
extensiondir = os.path.join(cwd, 'schema', 'profile') if is_profile else cwd

if repo_name == 'infrastructure':
    ocds_schema_base_url = 'https://standard.open-contracting.org/infrastructure/schema/'
else:
    ocds_schema_base_url = 'https://standard.open-contracting.org/schema/'
development_base_url = 'https://raw.githubusercontent.com/open-contracting/standard/1.1-dev/standard/schema'
ocds_tags = re.findall(r'\d+__\d+__\d+', http_get(ocds_schema_base_url).text)
if ocds_version:
    ocds_tag = ocds_version.replace('.', '__')
else:
    ocds_tag = ocds_tags[-1]

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


def custom_warning_formatter(message, category, filename, lineno, line=None):
    return str(message).replace(cwd + os.sep, '')


warnings.formatwarning = custom_warning_formatter
pytestmark = pytest.mark.filterwarnings('always')


@lru_cache()
def metaschemas():
    url = 'https://raw.githubusercontent.com/open-contracting/standard/1.1/standard/schema/meta-schema.json'
    metaschema = http_get(url).json()

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

    return {
        'metaschema': metaschema,
        'project_package_metaschema': project_package_metaschema,
        'record_package_metaschema': record_package_metaschema,
        'release_package_metaschema': release_package_metaschema,
    }


def get_metaschema_for_filename(name):
    schemas = metaschemas()
    if name in ('release-schema.json', 'release-package-schema.json'):
        return schemas['release_package_metaschema']
    elif name == 'record-package-schema.json':
        return schemas['record_package_metaschema']
    elif name in ('project-schema.json', 'project-package-schema.json'):
        return schemas['project_package_metaschema']
    return schemas['metaschema']


def patch(text):
    """
    Handle unreleased tag in $ref.
    """
    match = re.search(r'\d+__\d+__\d+', text)
    if match:
        tag = match.group(0)
        if tag not in ocds_tags:
            if ocds_version or not use_development_version:
                text = text.replace(tag, ocds_tag)
            else:
                text = text.replace(ocds_schema_base_url + tag, development_base_url)
    return text


json_schemas = [(path, name, data) for path, name, text, data in walk_json_data(patch) if is_json_schema(data)]


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
        schema = http_get(url).json()

    expected_codelists = {name for _, name, _ in
                          walk_csv_data(top=os.path.join(extensiondir, 'codelists'))}
    expected_schemas = {name for _, name, _, _ in
                        walk_json_data(patch, top=extensiondir) if path.endswith('-schema.json')}

    path = os.path.join(extensiondir, 'extension.json')
    if os.path.isfile(path):
        with open(path) as f:
            data = json.load(f, object_pairs_hook=rejecting_dict)

        validate_json_schema(path, 'extension.json', data, schema)

        urls = data.get('dependencies', []) + data.get('testDependencies', [])
        for url in urls:
            try:
                status_code = http_head(url).status_code
                assert status_code == 200, 'HTTP {} on {}'.format(status_code, url)
            except requests.exceptions.ConnectionError as e:
                assert False, '{} on {}'.format(e, url)

        urls = list(data['documentationUrl'].values())
        for url in urls:
            try:
                status_code = http_get(url).status_code  # allow redirects
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


@pytest.mark.parametrize('path,name,data', json_schemas)
def test_schema_valid(path, name, data):
    """
    Ensures all JSON Schema files are valid JSON Schema Draft 4 and use codelists correctly. Unless this is an
    extension, ensures JSON Schema files have required metadata and valid references.
    """
    errors = list(get_json_schema_errors(data, get_metaschema_for_filename(name)))

    for error in errors:
        warnings.warn(json.dumps(error.instance, indent=2, separators=(',', ': ')))
        warnings.warn('ERROR: {0} ({1})\n'.format(error.message, '/'.join(error.absolute_schema_path)))

    assert not errors, '{0} is not valid JSON Schema ({1} errors)'.format(path, len(errors))


def test_json_valid():
    warn_and_assert(get_invalid_json_files(), '{0} is not valid JSON: {1}',
                    'JSON files are invalid. See warnings below.')


@pytest.mark.skipif(os.environ.get('OCDS_NOINDENT', False), reason='skipped indentation')
def test_indent():
    def include(path, name):
        return name != 'json-schema-draft-4.json'  # http://json-schema.org/draft-04/schema

    warn_and_assert(get_unindented_files(include), '{0} is not indented as expected, run: ocdskit indent {0}',
                    'Files are not indented as expected. See warnings below, or run: ocdskit indent -r .')


# Template repositories are allowed to have empty schema files and .keep files.
def test_empty():
    def include(path, name):
        return repo_name not in template_repositories or name not in schema_files + ('.keep',)

    warn_and_assert(get_empty_files(include), '{0} is empty, run: rm {0}',
                    'Files are empty. See warnings below.')


@pytest.mark.skipif(not is_extension, reason='not an extension (test_versioned_release_schema)')
def test_versioned_release_schema():
    path = os.path.join(cwd, 'versioned-release-validation-schema.json')
    if os.path.exists(path):
        warn_and_assert([path], '{0} is present, run: rm {0}',
                        'Versioned release schema files are present. See warnings below.')


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
            dependency = http_get(url).json()
            external_codelists.update(dependency.get('codelists', []))
            schema_url = '{}/{}'.format(url.rsplit('/', 1)[0], basename)
            json_merge_patch.merge(schemas[basename], http_get(schema_url).json())
            get_dependencies(dependency, basename)

    for basename in basenames:
        schemas[basename] = http_get(url_pattern.format(basename)).json()

        if basename == 'release-schema.json':
            path = os.path.join(extensiondir, 'extension.json')
            with open(path) as f:
                get_dependencies(json.load(f, object_pairs_hook=rejecting_dict), basename)

    # This loop is somewhat unnecessary, as repositories contain at most one of each schema file.
    for path, name, text, data in walk_json_data(patch):
        if is_json_merge_patch(data):
            if name in basenames:
                unpatched = deepcopy(schemas[name])
                try:
                    patched = merge(unpatched, data)
                except Exception as e:
                    assert False, 'Exception: {} {}'.format(e, path)

                # All metadata should be present.
                validate_json_schema(path, name, patched, metaschemas()['metaschema'], full_schema=True)

                # Empty patches aren't allowed. json_merge_patch mutates `unpatched`, so `schemas[name]` is tested.
                assert patched != schemas[name]
