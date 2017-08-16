import json
import os
from collections import OrderedDict

import pytest


def walk():
    for root, dirs, files in os.walk(os.getcwd()):
        # Skip third-party JSON files.
        if '_static' not in root.split(os.sep):
            for name in files:
                yield (root, name)


def test_valid():
    """
    Ensures all JSON files are valid.
    """
    for root, name in walk():
        if name.endswith('.json'):
            path = os.path.join(root, name)
            with open(path, 'r') as f:
                json.loads(f.read(), object_pairs_hook=OrderedDict)


@pytest.mark.skip(reason="See https://github.com/open-contracting/standard-maintenance-scripts/issues/2")
def test_indent():
    """
    Ensures all JSON files are valid and formatted for humans.
    """
    for root, name in walk():
        if name.endswith('.json'):
            path = os.path.join(root, name)
            with open(path, 'r') as f:
                actual = f.read()
                data = json.loads(actual, object_pairs_hook=OrderedDict)
                expected = json.dumps(data, indent=4, separators=(',', ': '))
                assert actual == expected, "{} incorrect indentation".format(path)
