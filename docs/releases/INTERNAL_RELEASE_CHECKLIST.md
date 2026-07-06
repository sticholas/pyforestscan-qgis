# Internal Release Checklist

Use this checklist before sharing an internal PyForestScan QGIS build with testers.

## Phase 24A Release Candidate Status

Artifact SHA-256: `90c9bfd7405d89a2f401adac8132472ae1c7ac93b7cfb944ba2282f89da13e30`

| Area | Status | Evidence / next action |
| --- | --- | --- |
| Branch | Pass | `develop` |
| Working tree before QA | Pass | Clean before Phase 24A edits. |
| Unit tests | Pass | 291 tests passed in repository validation. |
| Compile check | Pass | `python3 -m compileall pyforestscan_qgis` |
| Package validation | Pass | `dist/pyforestscan_qgis.zip` validated. |
| Docs links | Pass | Local Markdown links resolve. |
| Release validation | Pass | `scripts/validate_release.py` passed. |
| ZIP install in QGIS | Pending manual tester | Requires clean Windows/QGIS GUI environment. |
| Mission Control opens | Pending manual tester | Confirm from installed ZIP. |
| PBM backend install | Pending manual tester | Confirm Backend page progress reaches Backend Ready. |
| Environment Check after PBM | Pending manual tester | Expected overall `READY`; QGIS Python deps optional fallback. |
| Guided Mode products | Pending manual tester | Dataset Explorer, CHM, Canopy Cover, PAD, PAI, FHD, Rumple. |
| Advanced Toolbox groups | Pending manual tester | Diagnostics, Input / I/O, Preprocessing / Filters, Terrain, Metrics. |
| Small batch run | Pending manual tester | Sequential batch with PBM-routed product. |
| No manual QGIS Python deps | Pending manual tester | Confirm PBM-routed products run without QGIS Python PyForestScan/PDAL. |

## Repository Health

- Confirm branch is `develop`.
- Confirm working tree is clean.
- Review `CHANGELOG.md` for the release summary.
- Confirm `metadata.txt` version and plugin name are correct.
- Confirm external workers remain disabled in UI and core guardrails.

## Automated Validation

Run from `/home/milo/repos/pyforestscan-qgis`. Phase 24A executed these commands except the dry-run GitHub release helper, which is prepared below:

```bash
python3 -m unittest discover tests
python3 -m compileall pyforestscan_qgis
git diff --check
python3 scripts/package_plugin.py
python3 scripts/validate_plugin_package.py dist/pyforestscan_qgis.zip
python3 scripts/check_docs_links.py
python3 scripts/validate_release.py
python3 scripts/prepare_github_release.py --dry-run
```

## Manual QGIS Smoke Test

- Complete [Clean Machine ZIP Smoke Test](CLEAN_MACHINE_SMOKE_TEST.md).
- Review [Dependency State Matrix](DEPENDENCY_STATE_MATRIX.md).
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

- `dist/pyforestscan_qgis-v0.1.0-beta.1.zip` versioned package.
- `dist/pyforestscan_qgis.zip` latest convenience package.
- `dist/release_manifest.json` trace manifest.
- `CHANGELOG.md` entry.
- `docs/KNOWN_LIMITATIONS.md`.
- `docs/development/MANUAL_QA_SCRIPT.md`.
- Any manual test notes or screenshots captured outside the repository.

## Go / No-Go

Go only when tests pass, package validation passes, QGIS smoke tests pass, and known limitations are acceptable for internal testers.


## Tag And Release Commands

Prepared for maintainer execution after manual clean-machine QA passes:

```bash
git status --short --branch
git tag -a v0.1.0-beta.1 -m "v0.1.0-beta.1 internal beta"
git push origin v0.1.0-beta.1
python3 scripts/prepare_github_release.py --dry-run
```

Do not create the GitHub release unless explicitly instructed after internal tester QA is recorded.
