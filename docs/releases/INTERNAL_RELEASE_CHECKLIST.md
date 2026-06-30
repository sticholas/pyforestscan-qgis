# Internal Release Checklist

Use this checklist before sharing an internal PyForestScan QGIS build with testers.

## Repository Health

- Confirm branch is `develop`.
- Confirm working tree is clean.
- Review `CHANGELOG.md` for the release summary.
- Confirm `metadata.txt` version and plugin name are correct.
- Confirm external workers remain disabled in UI and core guardrails.

## Automated Validation

Run from `/home/lama/pyforestscan-qgis`:

```bash
python3 -m unittest discover tests
python3 -m compileall pyforestscan_qgis
git diff --check
python3 scripts/package_plugin.py
python3 scripts/validate_plugin_package.py dist/pyforestscan_qgis.zip
```

## Manual QGIS Smoke Test

- Install `dist/pyforestscan_qgis.zip` through QGIS Plugin Manager.
- Confirm Mission Control opens as a floating, movable window.
- Run Environment Check and confirm READY or clear dependency guidance.
- Run Dataset Explorer on a known small dataset.
- Build a Product Planner report.
- Run CHM only and confirm output loads and displays with contrast.
- Run all implemented products on a small dataset and confirm job summary records outputs.
- Run a small sequential batch.
- Run a small Parallel Safe batch with two workers after preflight.
- Confirm External Worker mode is not selectable.

## Release Artifacts

- `dist/pyforestscan_qgis.zip` package.
- `CHANGELOG.md` entry.
- `docs/KNOWN_LIMITATIONS.md`.
- `docs/development/MANUAL_QA_SCRIPT.md`.
- Any manual test notes or screenshots captured outside the repository.

## Go / No-Go

Go only when tests pass, package validation passes, QGIS smoke tests pass, and known limitations are acceptable for internal testers.
