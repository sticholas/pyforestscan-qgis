# Packaging

PyForestScan QGIS is packaged as a QGIS plugin ZIP with `pyforestscan_qgis/` as
the single top-level folder.

Expected ZIP layout:

```text
pyforestscan_qgis/
  metadata.txt
  __init__.py
  __version__.py
  plugin.py
  provider.py
  processing_provider.py
  icons/
  algorithms/
  core/
  resources/
  styles/
```

## Create a Local Test Package

From the repository root:

```bash
python3 scripts/package_plugin.py
```

The script writes:

```text
dist/pyforestscan_qgis-v0.1.0-beta.1.zip
dist/pyforestscan_qgis.zip
dist/release_manifest.json
```

The package includes only the plugin folder plus packaged backend specs and `backend_manifest.json`. It excludes repository-only files, tests, Git metadata, Python bytecode, and cache directories. The versioned ZIP is the release artifact; `dist/pyforestscan_qgis.zip` is a latest convenience copy.

## Validate the Package

Run:

```bash
python3 scripts/validate_plugin_package.py dist/pyforestscan_qgis.zip
python3 scripts/check_docs_links.py
python3 scripts/validate_release.py
python3 scripts/prepare_github_release.py --dry-run
```

The validation script checks that:

- `metadata.txt` exists.
- `__init__.py` exists.
- `plugin.py` exists.
- provider registration files exist.
- the plugin icon exists.
- no `__pycache__` directories are included.
- no `.git` files are included.
- all ZIP members live under the `pyforestscan_qgis/` top-level folder.

## Sync Into a Local QGIS Profile

For development smoke tests:

```bash
python3 scripts/package_plugin.py --sync-local
```

By default this copies the plugin folder to the Linux default QGIS profile plugin
directory. For other profiles or platforms, pass an explicit plugin directory:

```bash
python3 scripts/package_plugin.py --sync-local --qgis-plugin-dir /path/to/QGIS3/profiles/default/python/plugins
```

Restart QGIS after syncing.

## Release Notes

This packaging workflow is for local testing and release preparation. Official
QGIS Plugin Repository submission may require additional metadata review,
compatibility testing, and repository-specific packaging checks.
