# JSON Schema files and CSV files

## JSON Schema

### codelist-schema.json

This repository holds `codelist-schema.json`, against which codelist CSV files are tested.

If changes are made to `codelist-schema.json`, changes may be needed to:

* [standard](https://github.com/open-contracting/standard), extensions, profiles and templates: codelist CSV files (below)
* [standard-maintenance-scripts](https://github.com/open-contracting/standard-maintenance-scripts): `test_csv.py`

### extension-schema.json

This repository holds `extension-schema.json`, against which `extension.json` files are tested. The schema is documented in [standard_extension_template](https://github.com/open-contracting/standard_extension_template#extensionjson).

If changes are made to `extension-schema.json`, changes may be needed to:

* Extensions, profiles and templates: `extension.json`
* [extension_creator](https://github.com/open-contracting/extension_creator): [`entry.js`](https://github.com/open-contracting/extension_creator/blob/gh-pages/entry.js#L125) `extension.json` line (and recompile `app.js`)
* [extension_registry](https://github.com/open-contracting/extension_registry): `compile.py`
* [standard-maintenance-scripts](https://github.com/open-contracting/standard-maintenance-scripts): `test_json.py`
* [standard_extension_template](https://github.com/open-contracting/standard_extension_template): [`README.md`](https://github.com/open-contracting/standard_extension_template#extensionjson)
* CoVE: [schema.py](https://github.com/OpenDataServices/cove/blob/master/cove_ocds/lib/schema.py#L116) `apply_extensions` method

If fields in `extension-schema.json` are renamed, removed or restructured, changes may be needed to:

* [documentation-support](https://github.com/open-contracting/documentation-support): `profile_builder.py` (`name`, `codelists`)
* [sphinxcontrib-opencontracting](https://github.com/open-contracting/sphinxcontrib-opencontracting): `ExtensionList` class (`name`, `description`) and `ExtensionSelectorTable` class (`name`, `description`, `documentationUrl`)
* [standard](https://github.com/open-contracting/standard): `fetch_core_extensions.py` (`codelists`)
* [standard-maintenance-scripts](https://github.com/open-contracting/standard-maintenance-scripts): `test_json.py` `test_extension_json` method

## CSV files

### Codelist files

If changes are made to the headers of codelist files, changes may be needed to:

* [documentation-support](https://github.com/open-contracting/documentation-support): `babel_extractors.py`, `translation.py`
* [ocdskit](https://github.com/open-contracting/ocdskit): `set-closed-codelist-enums` command
* [standard](https://github.com/open-contracting/standard): `fetch_currency_codelist.py`
* [standard-maintenance-scripts](https://github.com/open-contracting/standard-maintenance-scripts): `test_csv.py`, `test_json.py`

### Extension registry files

If changes are made to the registry's `extensions.csv` or `extension_versions.csv`, changes may be needed to:

* [documentation-support](https://github.com/open-contracting/documentation-support): `profile_builder.py`
* [extension_registry.py](https://github.com/open-contracting/extension_registry.py)
* [sphinxcontrib-opencontracting](https://github.com/open-contracting/sphinxcontrib-opencontracting): `opencontracting.py` `extension_registry` method and callers
* [standard](https://github.com/open-contracting/standard): `extensions.js`, `fetch_core_extensions.py`
* [standard-maintenance-scripts](https://github.com/open-contracting/standard-maintenance-scripts): `tasks.py` `download_extensions` task, `Rakefile` `uncloned` task and `core_extensions` method and callers
