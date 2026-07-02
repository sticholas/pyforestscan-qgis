# Release Documentation

Release documentation describes how to package, validate, and evaluate PyForestScan QGIS for internal or public distribution.

- [Packaging](PACKAGING.md)
- [Internal Release Checklist](INTERNAL_RELEASE_CHECKLIST.md)
- [Repository Release Audit](REPOSITORY_RELEASE_AUDIT.md)
- [Release Notes Template](RELEASE_NOTES_TEMPLATE.md)
- [v0.1.0-beta.1 Release Notes](v0.1.0-beta.1.md)
- [Clean Machine ZIP Smoke Test](CLEAN_MACHINE_SMOKE_TEST.md)
- [Dependency State Matrix](DEPENDENCY_STATE_MATRIX.md)

The project changelog lives at [CHANGELOG.md](../../CHANGELOG.md). Known limitations are tracked in [docs/KNOWN_LIMITATIONS.md](../KNOWN_LIMITATIONS.md).

## Versioned ZIP Release Pipeline

Phase 23A packages internal releases as versioned ZIP artifacts, keeps `dist/pyforestscan_qgis.zip` as a latest convenience copy, writes `dist/release_manifest.json`, validates release guardrails with `scripts/validate_release.py`, and prints dry-run GitHub release commands with `scripts/prepare_github_release.py --dry-run`.
