# JSON Schema, JSON files and CSV files

## JSON Schema

### codelist-schema.json

If changes are made to `codelist-schema.json`, changes may be needed to:

* [standard](https://github.com/open-contracting/standard), extensions, and profiles: codelist CSV files

### extension-schema.json

This repository holds `extension-schema.json` against which each extension's `extension.json` is tested. The schema is documented in [standard_extension_template](https://github.com/open-contracting/standard_extension_template#extensionjson).

If changes are made to `extension-schema.json`, changes may be needed to:

* Extensions and profiles: `extension.json`
* [standard_extension_template](https://github.com/open-contracting/standard_extension_template): [`README.md`](https://github.com/open-contracting/standard_extension_template#extensionjson), `extension.json`
* [extension_registry](https://github.com/open-contracting/extension_registry): `compile.py`
* [extension_creator](https://github.com/open-contracting/extension_creator): [`entry.js`](https://github.com/open-contracting/extension_creator/blob/gh-pages/entry.js#L125) `extension.json` line (and recompile `app.js`)
* CoVE: [schema.py](https://github.com/OpenDataServices/cove/blob/master/cove_ocds/lib/schema.py#L116) `apply_extensions` method

## JSON files

### extensions.json and extensions.js

If changes are made to the extension registry's `extensions.json` or `extensions.js`, changes may be needed to:

* [public-private-partnerships](https://github.com/open-contracting/public-private-partnerships): `apply-extensions.py`
* [sphinxcontrib-opencontracting](https://github.com/open-contracting/sphinxcontrib-opencontracting): `opencontracting.py` `download_extensions` method
* [standard](https://github.com/open-contracting/standard): `extensions.js`, `get-readmes.py`
* [standard-maintenance-scripts](https://github.com/open-contracting/standard-maintenance-scripts): `tasks.py` `download_extensions` task, `Rakefile` `uncloned` task and `core_extensions` method

## CSV files

### Codelist files

If changes are made to the headers of codelist files, changes may be needed to:

* [ocdskit](https://github.com/open-contracting/ocdskit): `set-closed-codelist-enums` command
* [public-private-partnerships](https://github.com/open-contracting/public-private-partnerships): `apply-extensions.py`
* [standard](https://github.com/open-contracting/standard): `fetch_currency_codelist.py`
* [standard-maintenance-scripts](https://github.com/open-contracting/standard-maintenance-scripts): `test_csv.py`, `test_json.py`
