import csv
import json
import os
import warnings
from io import StringIO

import requests
from jsonschema import FormatChecker
from jsonschema.validators import Draft4Validator as validator


# Copied from test_json.py.
def custom_warning_formatter(message, category, filename, lineno, line=None):
    return str(message).replace(os.getcwd() + os.sep, '')


# Copied from test_json.py.
warnings.formatwarning = custom_warning_formatter
repo_name = os.path.basename(os.environ.get('TRAVIS_REPO_SLUG', os.getcwd()))

# Copied from test_json.py.
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


# Edited from test_json.py.
def walk_csv_data(top=os.getcwd()):
    """
    Yields all CSV data.
    """
    for root, name in walk(top):
        if name.endswith('.csv'):
            path = os.path.join(root, name)
            with open(path, newline='') as f:
                text = f.read()
                yield (path, text, csv.DictReader(StringIO(text)))


# Copied from test_json.py.
def is_codelist(reader):
    """
    Returns whether the CSV is a codelist.
    """
    return 'Code' in reader.fieldnames


def test_valid():
    """
    Ensures all CSV files are valid: no empty rows or columns, no leading or trailing whitespace in cells, same number
    of cells in each row.
    """
    errors = 0

    for path, text, reader in walk_csv_data():
        width = len(reader.fieldnames)
        rows = [row for row in reader]
        columns = []

        for row_index, row in enumerate(rows, 2):
            if len(row) != width:
                errors += 1
                warnings.warn('{} has {} not {} columns in row {}'.format(path, len(row), width, row_index))
            if not any(row.values()):
                errors += 1
                warnings.warn('{} has empty row {}'.format(path, row_index))
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
                            warnings.warn('{} {} "{}" has leading or trailing whitespace at {},{}'.format(
                                path, header, cell, row_index, col_index))

        for col_index, column in enumerate(columns, 1):
            if not any(column):
                errors += 1
                warnings.warn('{} has empty column {}'.format(path, col_index))

        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=reader.fieldnames, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
        expected = output.getvalue()

        if text != expected and repo_name != 'sample-data':
            errors += 1
            warnings.warn('{} is improperly formatted (e.g. missing trailing newline, extra quoting characters, '
                          'non-"\\n" line terminator):\n{}\n{}'.format(path, repr(text), repr(expected)))

    assert errors == 0


def test_codelist():
    """
    Ensures all codelists files are valid against codelist-schema.json.
    """
    exceptions = {
        'currency.csv': "'Description' is a required property",
    }

    array_columns = ('Framework', 'Section')

    path = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'schema', 'codelist-schema.json')
    if os.path.isfile(path):
        with open(path) as f:
            codelist_schema = json.load(f)
    else:
        url = 'https://raw.githubusercontent.com/open-contracting/standard-maintenance-scripts/master/schema/codelist-schema.json'  # noqa
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

    for path, text, reader in walk_csv_data():
        if is_codelist(reader):
            data = []
            for row in reader:
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
                if exceptions.get(os.path.basename(path)) != error.message:
                    any_errors = True
                    warnings.warn('{}: {} ({})\n'.format(path, error.message, '/'.join(error.absolute_schema_path)))

    assert not any_errors
