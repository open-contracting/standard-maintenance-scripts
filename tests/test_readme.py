import csv
import json
import os
import re
import warnings
from copy import deepcopy
from io import StringIO

import json_merge_patch
import jsonref
import pytest
from jscc.schema import extend_schema
from jscc.testing.checks import validate_schema
from jscc.testing.util import http_get
from ocdskit.schema import get_schema_fields

# Whether to use the 1.2-dev version of OCDS.
use_development_version = '1.2' in os.getenv('GITHUB_REF_NAME', '')

cwd = os.getcwd()
repo_name = os.path.basename(os.getenv('GITHUB_REPOSITORY', cwd))
ocds_version = os.environ.get('OCDS_TEST_VERSION')
is_extension = os.path.isfile(os.path.join(cwd, 'extension.json'))

ocds_schema_base_url = 'https://standard.open-contracting.org/schema/'
development_base_url = 'https://raw.githubusercontent.com/open-contracting/standard/1.2-dev/schema'
ocds_tags = re.findall(r'\d+__\d+__\d+', http_get(ocds_schema_base_url).text)
if ocds_version:
    ocds_tag = ocds_version.replace('.', '__')
else:
    ocds_tag = ocds_tags[-1]
if ocds_version or not use_development_version:
    url_prefix = ocds_schema_base_url + ocds_tag
else:
    url_prefix = development_base_url

# Same as tests/fixtures/release_minimal.json in ocdskit.
minimal_release = {
    "ocid": "ocds-213czf-1",
    "id": "1",
    "date": "2001-02-03T04:05:06Z",
    "tag": ["planning"],
    "initiationType": "tender",
}


def showwarning(message, category, filename, lineno, file=None, line=None):
    return str(message).replace(cwd + os.sep, '')


warnings.showwarning = showwarning
pytestmark = pytest.mark.filterwarnings('always')


def read_metadata():
    path = os.path.join(cwd, 'extension.json')
    with open(path) as f:
        return json.load(f)


def read_readme():
    path = os.path.join(cwd, 'README.md')
    if os.path.isfile(path):
        with open(path) as f:
            return f.read()
    else:
        assert os.path.isfile(path), 'expected a README.md file'


def examples():
    for i, text in enumerate(re.findall(r'```json(.+?)```', read_readme(), re.DOTALL)):
        try:
            yield i, text, json.loads(text)
        except json.decoder.JSONDecodeError as e:
            assert False, f'README.md: JSON block {i} is not valid JSON ({e})'


def patch_schema(basename='release-schema.json'):
    schema = http_get(url_prefix + '/' + basename).json()
    patched = extend_schema(basename, schema, read_metadata())
    with open(os.path.join(cwd, basename)) as f:
        json_merge_patch.merge(patched, json.load(f))

    return patched


@pytest.mark.skipif(not is_extension, reason='not an extension (test_example_present)')
def test_example_present():
    """
    Ensures the extension's documentation contains an example.
    """
    exceptions = {
        'ocds_budget_and_spend_extension',  # examples are linked
    }

    if repo_name in exceptions:
        return

    readme = read_readme()

    # ocds_enquiry_extension has "Example" as text, instead of as a heading.
    assert re.search(r'\bexamples?\b', readme, re.IGNORECASE) and '```json' in readme, 'README.md: expected an example'


@pytest.mark.skipif(not is_extension, reason='not an extension (test_example_indent)')
def test_example_indent():
    """
    Ensures all JSON snippets in the extension's documentation are valid and formatted for humans.
    """
    for i, text, data in examples():
        expected = f'\n{json.dumps(data, ensure_ascii=False, indent=2)}\n'
        assert text == expected, f'README.md: JSON example {i} is not indented as expected'


@pytest.mark.skipif(not is_extension or repo_name == 'standard_extension_template',
                    reason='not an extension (test_example_valid)')
def test_example_valid():
    """
    Ensures all JSON snippets in the extension's documentation are snippets of OCDS data with no additional fields.
    """
    def set_additional_properties_false(data):
        if isinstance(data, list):
            for item in data:
                set_additional_properties_false(item)
        elif isinstance(data, dict):
            if 'properties' in data:
                data['additionalProperties'] = False
            for value in data.values():
                set_additional_properties_false(value)

    for basename in ('release-schema.json', 'release-package-schema.json', 'record-package-schema.json'):
        if os.path.isfile(os.path.join(cwd, basename)):
            patched = patch_schema(basename)
            break
    else:
        return

    set_additional_properties_false(patched)

    for i, text, data in examples():
        # Skip packages (only occurs once in ocds_ppp_extension).
        if 'releases' in data:
            continue

        release = deepcopy(minimal_release)
        json_merge_patch.merge(release, data)
        if 'tender' in release and 'id' not in release['tender']:
            release['tender']['id'] = '1'

        errors = validate_schema('README.md', release, patched)

        assert not errors, f'README.md: JSON block {i} is invalid. See warnings below.'


@pytest.mark.skipif(not is_extension or repo_name == 'standard_extension_template',
                    reason='not an extension (test_example_backticks)')
def test_example_backticks():
    exceptions = {
        'ocds_pagination_extension': {
            # Example query string parameters.
            'offset', 'offset=NUMBER', 'page', 'page=1', 'page=NUMBER', 'since', 'since=TIMESTAMP',
            # Changelog entries for non-existent or removed fields.
            'links.all', 'packageMetadata',
        },

        # Substring of pattern property.
        'ocds_exchangeRate_extension': {
            'CODE',
        },

        # Cross-references to other extensions.
        'ocds_contract_signatories_extension': {
            'preferredBidders',
            'publicAuthority',
        },

        # Changelog entries for non-existent or removed fields or codelists.
        'ocds_bid_extension': {
            'BidsStatistic',
            'BidsStatistic.currency',
            'BidsStatistic.id',
            'BidsStatistic.measure',
            'BidsStatistic.requirementResponses',
            'BidsStatistic.value',
            'BidsStatistic.valueGross',
            'BidStatistic',
            'bidStatistics.csv',
        },
        'ocds_countryCode_extension': {
            'countryCode',
        },
        'ocds_eu_extension': {
            'minimumValue',
            'Lot.minimumValue',
        },
        'ocds_legalBasis_extension': {
            '+itemClassificationScheme.csv',
        },
        'ocds_lots_extension': {
            'LotDetails',
            'Bid.relatedLots',
            'Finance.relatedLots',
        },
        'ocds_ppp_extension': {
            '+documentType.csv',
            '+partyRole.csv',
            'initiationType.csv',
        },
        'ocds_project_extension': {
            'Project.source',
            'Project.project',
        },
        'ocds_qualification_extension': {
            'PreQualification.procurementMethodRationale',
            'PreQualification.awardCriteriaDetails',
        },
        'ocds_requirements_extension': {
            'Award.requirementResponses',
            'Contract.requirementResponses',
            'Criterion.relatesTo',
            'Criterion.source',
            'RequirementResponse.relatedTenderer',
            'relatesTo.csv',
            'responseSource.csv',
        },
        'ocds_shareholders_extension': {
            'Organization.beneficialOwnership',
        },
        'ocds_submissionTerms_extension': {
            'requiresGuarantees',
        },
    }

    # Add JSON null, JSON booleans, and a jsonmerge field from OCDS 1.0.
    literals = {'null', 'true', 'false', 'mergeStrategy'}
    patterns = set()

    # Add JSON Schema properties.
    url = 'https://raw.githubusercontent.com/open-contracting/standard/1.1/schema/meta-schema.json'
    literals.update(http_get(url).json()['properties'])

    # Add codelist columns.
    url = 'https://raw.githubusercontent.com/open-contracting/standard-maintenance-scripts/main/schema/codelist-schema.json'  # noqa: E501
    literals.update(http_get(url).json()['items']['properties'])

    # Add codelist names.
    metadata = read_metadata()
    literals.update(metadata.get('codelists', []))

    # Add JSON paths, field names and definition names.
    for basename in ('release-schema.json', 'release-package-schema.json', 'record-package-schema.json'):
        if not os.path.isfile(os.path.join(cwd, basename)):
            continue

        schema = jsonref.replace_refs(patch_schema(basename))
        for field in get_schema_fields(schema):
            if 'patternProperties' in field.pointer_components:
                literal, pattern = re.search(r'^(.*)\(\^?(.+)\$?\)$', field.path).groups()
                patterns.add(re.compile(r'^' + re.escape(literal) + pattern + r'$'))
            else:
                literals.add(field.path)  # e.g. tender.id
                if len(field.path_components) > 1:
                    literals.add(field.path_components[-1])  # e.g. scale
                if field.definition_path_components:
                    literals.add(field.definition_path)  # e.g. Lot
                    literals.add(f'{field.definition_path}.{field.path}')  # e.g. Lot.id
                if 'codelist' in field.schema:
                    literals.add(field.schema['codelist'])
                    literals.add(f"+{field.schema['codelist']}")
                    literals.add(f"-{field.schema['codelist']}")

    errors = 0

    for text in re.findall(r'`([^`\n]+)`', read_readme(), re.DOTALL):
        if (text not in literals and not any(re.search(pattern, text) for pattern in patterns)
                # e.g. `"uniqueItems": true`
                and not text.startswith('"') and text not in exceptions.get(repo_name, [])):
            errors += 1
            warnings.warn(f'README.md: "{text}" term is not in schema')

    assert errors == 0, 'README.md: Backtick terms are invalid. See warnings below.'


@pytest.mark.skipif(not is_extension, reason='not an extension (test_example_codes)')
def test_example_codes():
    metadata = read_metadata()

    exceptions = {
        # Open codelists.
        'ocds_enquiry_extension': {
            'clarifications',
        },

        # Changelog entries for removed codes.
        'ocds_ppp_extension': {
            'bidder',
            'disqualifiedBidder',
            'qualifiedBidder',
        },

        # Codes introduced in OCDS 1.2.
        'ocds_eu_extension': {
            'informationService',
            'securityClearanceDeadline',
        },
    }

    literals = set()

    # Ostensibly, we should download all codelists. To save time, we only download those we presently reference.
    for codelist in ('milestoneStatus', 'tenderStatus', 'partyRole', 'releaseTag'):
        reader = csv.DictReader(StringIO(http_get(f'{url_prefix}/codelists/{codelist}.csv').text))
        for row in reader:
            literals.add(row['Code'])

    if 'codelists' in metadata:
        for codelist in metadata['codelists']:
            with open(os.path.join('codelists', codelist)) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    literals.add(row['Code'])
                    if 'Category' in row:
                        literals.add(row['Category'])

    errors = 0

    for text in re.findall(r"'(\S+)'", read_readme(), re.DOTALL):
        if text not in literals and text not in exceptions.get(repo_name, []):
            errors += 1
            warnings.warn(f'README.md: "{text}" code is not in codelists')

    assert errors == 0, 'README.md: Single-quote terms are invalid. See warnings below.'
