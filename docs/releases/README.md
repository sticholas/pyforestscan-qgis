# Release Documentation

Release documentation describes how to package, validate, and evaluate PyForestScan QGIS for internal or public distribution.

- [Release Roadmap](RELEASE_ROADMAP.md)
- [RC1 Checklist](RC1_CHECKLIST.md)
- [RC1 Manual QA Script](RC1_MANUAL_QA_SCRIPT.md)
- [RC1 QA Results](RC1_QA_RESULTS.md)
- [RC1 Blockers](RC1_BLOCKERS.md)
- [Release Triage Policy](RELEASE_TRIAGE_POLICY.md)
- [Packaging](PACKAGING.md)
- [Internal Release Checklist](INTERNAL_RELEASE_CHECKLIST.md)
- [Repository Release Audit](REPOSITORY_RELEASE_AUDIT.md)
- [Release Notes Template](RELEASE_NOTES_TEMPLATE.md)
- [v0.1.0-beta.2 Release Notes](v0.1.0-beta.2.md)
- [v0.1.0-beta.1 Release Notes](v0.1.0-beta.1.md)
- [Clean Machine ZIP Smoke Test](CLEAN_MACHINE_SMOKE_TEST.md)
- [Dependency State Matrix](DEPENDENCY_STATE_MATRIX.md)

The project changelog lives at [CHANGELOG.md](../../CHANGELOG.md). Known limitations are tracked in [docs/KNOWN_LIMITATIONS.md](../KNOWN_LIMITATIONS.md).

## Versioned ZIP Release Pipeline

Phase 23A packages internal releases as versioned ZIP artifacts, keeps `dist/pyforestscan_qgis.zip` as a latest convenience copy, writes `dist/release_manifest.json`, validates release guardrails with `scripts/validate_release.py`, and prints dry-run GitHub release commands with `scripts/prepare_github_release.py --dry-run`.

## Release Candidate Management

Phase 27A establishes RC1, RC2, and v1.0 gates. RC work is release-focused: it should close blockers, improve evidence, and update documentation without adding new scientific products, PBM behavior, processing behavior, Advanced Toolbox behavior, or External Worker behavior.
