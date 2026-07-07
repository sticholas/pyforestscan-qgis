# Release Roadmap

This roadmap moves PyForestScan QGIS from internal beta feature-building into formal release-candidate management. It controls scope for RC1, RC2, and v1.0 without changing processing behavior, PBM behavior, Advanced Toolbox behavior, or scientific calculations.

## Current State: v0.1.0-beta.2

`v0.1.0-beta.2` is the current internal beta ZIP line. It includes a QGIS-installable ZIP, Mission Control guided workflows, PBM Windows internal beta backend installation, PBM-routed Dataset Explorer and routed products, Advanced Toolbox groups, batch processing, Results output loading, Mission Control UX polish, and current-session awareness.

This state is suitable for controlled internal testing. It is not yet a public QGIS Plugin Repository release candidate.

## RC1 Definition

RC1 is the first release candidate for internal release acceptance. RC1 is not for new features. RC1 proves that the beta ZIP can be installed and exercised on a clean Windows/QGIS machine with PBM backend setup and core workflows.

RC1 requires:

- ZIP installs cleanly through QGIS Plugin Manager.
- Plugin loads without known startup errors.
- PBM installs on clean Windows QGIS into the user-local PyForestScan backend folder.
- Environment Check reports `READY` with PBM backend.
- Dataset Explorer works without manual QGIS Python scientific dependency setup for routed inspection.
- Guided products work through PBM where routed: CHM, Canopy Cover, PAD, PAI, FHD, Rumple, DTM, Point Density, and Voxel Statistic.
- A small batch run works through supported routed paths.
- Results loading adds supported outputs without duplicates and with expected styling behavior.
- Advanced Toolbox opens and passes smoke tests for representative Diagnostics, Input / I/O, Preprocessing / Filters, Terrain, and Metrics tools.
- Documentation and known limitations are current.
- Release validation passes.

## RC2 Definition

RC2 is the stabilization candidate after RC1 findings are resolved. RC2 proves repeatability, repair behavior, and documentation accuracy across a wider internal test set.

RC2 requires:

- All RC1 blockers resolved or explicitly deferred with owner/date/justification.
- Repeat clean-machine ZIP + PBM install passes on at least two Windows/QGIS test profiles.
- PBM repair/retry guidance is verified after a controlled failed install or broken backend state.
- Batch resume/retry behavior is smoke tested on a small folder.
- Results loading is verified for raster and table outputs already present in the QGIS project.
- Advanced Toolbox smoke results are recorded with sample inputs or dry-run-safe checks where full data is unavailable.
- Release notes, screenshots, known limitations, and support guidance match actual behavior.

## v1.0 Definition

v1.0 is the first public-quality release target. It may still be a targeted scientific/GIS tool, but it must be supportable by normal QGIS users within the documented platform scope.

v1.0 requires:

- RC2 passes without unresolved blockers or critical issues.
- QGIS 3.x supported target is explicitly documented and tested.
- Clean install, PBM setup, Environment Check, Guided Mode, Results loading, Batch, and Advanced Toolbox workflows are documented with final screenshots or equivalent QA evidence.
- Installer safety claims are validated: no QGIS Python modification, no system Python modification, no admin-rights requirement, no PATH/shell-profile changes, and External Worker mode disabled.
- Known limitations are user-facing, accurate, and linked from release notes.
- Release artifacts are reproducible with `scripts/package_plugin.py` and validated with `scripts/validate_release.py`.
- Public distribution checklist is reviewed before any QGIS Plugin Repository submission.

## Release Gates

Each candidate must pass these gates before tagging:

1. Repository is on `develop`, synchronized with `origin/develop`, and clean before packaging.
2. Unit tests pass with `python3 -m unittest discover tests`.
3. Compile check passes with `python3 -m compileall pyforestscan_qgis`.
4. ZIP packaging succeeds with `python3 scripts/package_plugin.py`.
5. Plugin package validation passes for `dist/pyforestscan_qgis.zip`.
6. Documentation links pass with `python3 scripts/check_docs_links.py`.
7. Release validation passes with `python3 scripts/validate_release.py`.
8. `git diff --check` passes.
9. Manual QA evidence is recorded in the candidate checklist.
10. Blockers and critical issues are triaged before tag preparation.

## Blocking Issues For RC1

These must be proven resolved before RC1 is accepted:

- Clean Windows/QGIS ZIP install must be executed and recorded for the current artifact.
- PBM backend install must be executed and recorded on clean Windows/QGIS for the current artifact.
- Environment Check must report `READY` with PBM after install.
- Dataset Explorer, Guided products, Batch, Results loading, and Advanced Toolbox smoke tests must be recorded for the current artifact.
- Any plugin-load exception, installer exception without clear recovery guidance, or routed processing failure on sample data blocks RC1.

## Non-Blocking Issues

These do not block RC1 if documented accurately:

- Linux/macOS PBM install execution remains planned/experimental until tested.
- QGIS 4.x compatibility remains defensive design only until QGIS 4.x can be tested.
- Height Above Ground point-cloud export and Preprocess Point Cloud may remain QGIS-Python-only if clearly labeled.
- Large EPT/crop/tiling workflows may remain future design work.
- Screenshots may be refreshed after RC1 if manual QA evidence is sufficient for the internal gate.

## Deferred Post-v1 Features

The following are explicitly outside RC1/RC2/v1.0 unless re-scoped:

- External Worker mode.
- Public module marketplace or PBM module registry UI.
- Cross-computer project/session persistence.
- Folder monitoring, cataloging, mosaicking, polygon summaries, and project-file generation.
- Headless QGIS worker execution.
- Linux/macOS PBM production support beyond documented experimental status.
- QGIS 4.x certification before QGIS 4.x is available for validation.
