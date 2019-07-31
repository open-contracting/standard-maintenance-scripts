import os
import re
import warnings

import pytest

# Copied from test_json.py.
cwd = os.getcwd()
repo_name = os.path.basename(os.environ.get('TRAVIS_REPO_SLUG', cwd))
is_extension = os.path.isfile(os.path.join(cwd, 'extension.json'))


# Copied from test_json.py.
def custom_warning_formatter(message, category, filename, lineno, line=None):
    return str(message).replace(cwd + os.sep, '')


warnings.formatwarning = custom_warning_formatter


@pytest.mark.skipif(not is_extension, reason='not an extension (test_example)')
def test_example():
    """
    Ensures the extension's documentation contains an example.
    """
    exceptions = {
        'ocds_budget_and_spend_extension',
    }

    if repo_name in exceptions:
        return

    path = os.path.join(cwd, 'README.md')
    if os.path.isfile(path):
        with open(path) as f:
            readme = f.read()

        # ocds_enquiry_extension doesn't have an "Example" heading.
        if not re.search(r'\bexamples?\b', readme, re.IGNORECASE) or '```json' not in readme:
            warnings.warn('{} expected an example'.format(path))
    else:
        assert False, 'expected a README.md file'
