# PBM Installer Safety

Phase 23C enables real backend installer execution for Windows internal beta builds only.

## Internal Beta Guard

The normal user-facing guard is build/platform based:

- Windows internal beta builds show **Install Backend**.
- Linux and macOS remain planned/experimental until platform smoke testing is complete.
- Unknown platforms remain disabled.
- A confirmation dialog is required before installation starts.

The confirmation text states that PBM installs PyForestScan backend packages into the user-local PyForestScan folder and does not modify QGIS or system Python. The legacy `PYFORESTSCAN_QGIS_ENABLE_BACKEND_INSTALL=1` override may still be used for controlled developer tests, but it is no longer the normal internal beta user flow.

## Safety Boundaries

The installer must:

- Use only the user-local PBM backend root.
- Avoid administrator privileges.
- Avoid QGIS Python, QGIS install folders, system Python, and global user site-packages.
- Avoid PATH, shell profile, registry, and user environment-variable changes.
- Keep existing Guided Mission Control, Advanced Toolbox, and Batch behavior unchanged unless a workflow explicitly implements PBM execution.
- Keep External Worker mode disabled.

## Transaction Scope

The internal beta installer downloads Micromamba, verifies the checksum when a pinned checksum exists, extracts the archive with path-traversal checks, creates the managed environment from the backend spec, verifies imports/executables, promotes staged files, writes READY config, and records logs under the backend root.

If a stage fails, staging is rolled back and the Backend page shows failure guidance, repair planning, and log previews.
