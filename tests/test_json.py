import json
import os
import warnings
from copy import deepcopy

import jscc.testing.json
import json_merge_patch
import pytest
import requests
# Import some tests that will be run by pytest, noqa needed because we don't use them directly
from jscc.testing.json import (development_base_url, difference, extensiondir, is_extension,  # noqa: F401
                               is_json_schema, metaschema, object_pairs_hook, ocds_schema_base_url, ocds_tag,
                               ocds_version, repo_name, check_empty_files, test_indent, test_valid,
                               validate_json_schema, walk_csv_data, walk_json_data)

use_development_version = False
jscc.testing.json.use_development_version = use_development_version

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
jscc.testing.json.external_codelists = external_codelists

exceptional_extensions = (
    'ocds_ppp_extension',
    'public-private-partnerships',
)
jscc.testing.json.exceptional_extensions = exceptional_extensions

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


def is_json_merge_patch(data):
    """
    Returns whether the data is a JSON Merge Patch.
    """
    return '$schema' not in data and ('definitions' in data or 'properties' in data)


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
    ignored = {
        '__init__.py',
    }
    untracked = {
        '.egg-info/',
        '/.tox/',
        '/.ve/',
        '/node_modules/',
    }
    template_repositories = (
        'standard_extension_template',
        'standard_profile_template',
    )
    schema_files = (
        'record-package-schema.json',
        'release-package-schema.json',
        'release-schema.json',
    )

    # Template repositories are allowed to have empty schema files and .keep files.
    def include(path, name):
        if name in ignored or any(substring in path for substring in untracked):
            return False
        if repo_name in template_repositories and name in schema_files + ('.keep',):
            return False
        return True

    def parse_as_json(path, name):
        return name in schema_files

    check_empty_files(include, test, parse_as_json)


def test_no_versioned_release_schema_in_extension():
    for root, name in walk():
        if is_extension and name == 'versioned-release-validation-schema.json':
            assert False, 'versioned-release-validation-schema.json should be removed'


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
