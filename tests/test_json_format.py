import json
import os
from collections import OrderedDict


def test_json_format():
    """
    Ensures all JSON files are valid and formatted for humans.
    """

    for root, dirs, files in os.walk(os.getcwd()):
        for name in files:
            if name.endswith('.json'):
                with open(name, 'r') as f:
                    actual = json.loads(f.read(), object_pairs_hook=OrderedDict)
                    expected = json.dumps(actual, indent=4, separators=(',', ': '))
                    assert actual == expected
