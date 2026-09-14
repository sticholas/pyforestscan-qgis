# Releases

The current accepted baseline is [Pre-point-viewer Release 1](PRE_POINT_VIEWER_RELEASE_1.md).

## Package

Build a versioned ZIP, then validate it:

```bash
python3 scripts/package_plugin.py --no-latest \
  --output dist/pyforestscan_qgis-v0.1.0.zip
python3 scripts/validate_plugin_package.py \
  dist/pyforestscan_qgis-v0.1.0.zip
python3 scripts/validate_packaged_import_graph.py \
  dist/pyforestscan_qgis-v0.1.0.zip
```

## Release history

- [Pre-point-viewer Release 1](PRE_POINT_VIEWER_RELEASE_1.md)
- [v0.2.0-beta.7](v0.2.0-beta.7.md)
- [v0.2.0-beta.6](v0.2.0-beta.6.md)
- [Earlier release notes](../../CHANGELOG.md)

Maintainer gates: [roadmap](RELEASE_ROADMAP.md) · [checklist](RC1_CHECKLIST.md) · [manual QA](RC1_MANUAL_QA_SCRIPT.md) · [results](RC1_QA_RESULTS.md) · [blockers](RC1_BLOCKERS.md) · [triage](RELEASE_TRIAGE_POLICY.md)

Detailed checklists and phase reports remain available in this directory for maintainers.
