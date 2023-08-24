import csv
import json
import os
import warnings
from io import StringIO

import pytest
import requests
from jscc.schema import is_codelist
from jscc.testing.filesystem import walk_csv_data
from jsonschema import FormatChecker
from jsonschema.validators import Draft4Validator as validator

cwd = os.getcwd()
repo_name = os.path.basename(os.getenv('GITHUB_REPOSITORY', cwd))


def formatwarning(message, category, filename, lineno, line=None):
    return str(message).replace(cwd + os.sep, '')


warnings.formatwarning = formatwarning
pytestmark = pytest.mark.filterwarnings('always')


@pytest.mark.skipif(repo_name in ('pelican-backend',), reason='cached upstream file')
@pytest.mark.skipif(repo_name in ('data-support',), reason='expected trailing whitespace')
def test_valid():
    """
    Ensures all CSV files are valid: no empty rows or columns, no leading or trailing whitespace in cells, same number
    of cells in each row.
    """
    errors = 0

    for path, name, text, fieldnames, rows in walk_csv_data():
        codelist = is_codelist(fieldnames)
        width = len(fieldnames)
        columns = []

        duplicates = len(fieldnames) - len(set(fieldnames))
        if duplicates:
            errors += 1
            warnings.warn(f'ERROR: {path} has {duplicates} duplicate column headers')

        for row_index, row in enumerate(rows, 2):
            expected = len(row) + duplicates
            if expected != width:
                errors += 1
                warnings.warn(f'ERROR: {path} has {expected} not {width} columns in row {row_index}')
            if not any(row.values()):
                errors += 1
                warnings.warn(f'ERROR: {path} has empty row {row_index}')
            else:
                for col_index, (header, cell) in enumerate(row.items(), 1):
                    if col_index > len(columns):
                        columns.append([])

                    columns[col_index - 1].append(cell)

                    # Extra cells are added to a None columns.
                    if header is None and isinstance(cell, list):
                        cells = cell
                    else:
                        cells = [cell]

                    for cell in cells:
                        if cell is not None and cell != cell.strip():
                            errors += 1
                            warnings.warn(f'ERROR: {path} {header} "{cell}" has leading or trailing whitespace at '
                                          f'{row_index},{col_index}')

        for col_index, column in enumerate(columns, 1):
            if not any(column) and codelist:
                errors += 1
                warnings.warn(f'ERROR: {path} has empty column {col_index}')

        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
        expected = output.getvalue()

        if text != expected and repo_name != 'sample-data':
            errors += 1
            warnings.warn(f'ERROR: {path} is improperly formatted (e.g. missing trailing newline, extra quoting '
                          f'characters, non-"\\n" line terminator):\n{text!r}\n{expected!r}')

    assert errors == 0, 'One or more codelist CSV files are invalid. See warnings below.'


@pytest.mark.skipif(repo_name in ('pelican-backend',), reason='not a codelist')
def test_codelist():
    """
    Ensures all codelists files are valid against codelist-schema.json.
    """
    exceptions = {
        'currency.csv': "'Description' is a required property",
        'language.csv': "'Description' is a required property",
        'mediaType.csv': "'Description' is a required property",
        # ocds_countryCode_extension
        'country.csv': "'Description' is a required property",
        # ocds_coveredBy_extension
        'coveredBy.csv': "'Description' is a required property",
        # ocds_medicine_extension
        'administrationRoute.csv': "'Description' is a required property",
        'container.csv': "None is not of type 'string'",
        'dosageForm.csv': "None is not of type 'string'",
    }

    array_columns = ('Framework', 'Section')

    path = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'schema', 'codelist-schema.json')
    if os.path.isfile(path):
        with open(path) as f:
            codelist_schema = json.load(f)
    else:
        url = 'https://raw.githubusercontent.com/open-contracting/standard-maintenance-scripts/main/schema/codelist-schema.json'  # noqa: E501
        codelist_schema = requests.get(url).json()

    minus_schema = {
      "$schema": "http://json-schema.org/draft-04/schema#",
      "type": "array",
      "items": {
        "type": "object",
        "required": [
          "Code"
        ],
        "additionalProperties": False,
        "properties": {
          "Code": {
            "title": "Code",
            "description": "The value to use in OCDS data.",
            "type": "string",
            "pattern": "^[A-Za-z0-9-]*$"
          }
        }
      }
    }

    any_errors = False

    for path, name, text, fieldnames, rows in walk_csv_data():
        codes_seen = set()
        if is_codelist(fieldnames):
            data = []
            for row_index, row in enumerate(rows, 2):
                code = row['Code']
                if code in codes_seen:
                    any_errors = True
                    warnings.warn(f'{path}: Duplicate code "{code}" on row {row_index}')
                codes_seen.add(code)

                item = {}
                for k, v in row.items():
                    if k in array_columns:
                        item[k] = v.split(', ')
                    elif k == 'Code' or v:
                        item[k] = v
                    else:
                        item[k] = None
                data.append(item)

            if os.path.basename(path).startswith('-'):
                schema = minus_schema
            else:
                schema = codelist_schema

            for error in validator(schema, format_checker=FormatChecker()).iter_errors(data):
                if error.message != exceptions.get(os.path.basename(path)):
                    any_errors = True
                    warnings.warn(f"{path}: {error.message} ({'/'.join(error.absolute_schema_path)})\n")

    assert not any_errors
