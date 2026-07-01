## Summary

Describe the product, scientific, documentation, or infrastructure change.

## Architecture Checklist

- [ ] UI and Processing code do not call PyForestScan directly.
- [ ] Guided processing still flows through JobManager, Pipeline, Adapter, and PyForestScan.
- [ ] Core changes remain QGIS-free where practical.
- [ ] Scientific thresholds or assumptions are documented.
- [ ] External worker mode remains disabled unless this PR is explicitly about safe headless worker research.

## Validation

- [ ] `python3 -m unittest discover tests`
- [ ] `python3 -m compileall pyforestscan_qgis`
- [ ] `python3 scripts/package_plugin.py`
- [ ] `python3 scripts/validate_plugin_package.py dist/pyforestscan_qgis.zip`
- [ ] `python3 scripts/check_docs_links.py`
- [ ] `git diff --check`

## Manual QGIS QA

List manual checks performed, including QGIS version and dataset type.

## Documentation

List docs updated or explain why docs were not needed.
