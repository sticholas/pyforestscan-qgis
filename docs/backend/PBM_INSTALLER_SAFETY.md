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

The internal beta installer downloads Micromamba, verifies the checksum when a pinned checksum exists, extracts the archive with path-traversal checks, creates the managed environment from the backend spec, installs PyPI-only backend packages through the managed backend Python, verifies staged imports/executables from `staging/micromamba` and `staging/env` without requiring final config, promotes staged files, writes READY config with final backend paths, runs strict final verification, and records logs under the backend root.

If a stage fails, staging is rolled back and the Backend page shows failure guidance, repair planning, and log previews.

## Subprocess Isolation

Phase 23F runs PBM installer subprocesses with a sanitized environment. The policy removes `PYTHONPATH`, `PYTHONHOME`, `PYTHONUSERBASE`, Python user-site contamination, pip user-install switches, and QGIS profile dependency paths before running Micromamba, backend Python pip, verification commands, or PBM runner jobs. It sets `PYTHONNOUSERSITE=1`, `PIP_NO_INPUT=1`, and `PIP_DISABLE_PIP_VERSION_CHECK=1`. Phase 23I prepends backend-local conda runtime paths for subprocesses; on Windows that means `env`, `env/Scripts`, `env/Library/bin`, and `env/bin` are available to child processes without modifying user or system PATH.

Logs record the command kind, executable path, whether the clean environment was used, staged versus final verification paths, per-check verification status, command, executable, detected version, and short first/last stderr or stdout previews on failure. Logs do not dump the full environment.

## Package Install Split

Micromamba creates the conda-forge environment from the backend spec. The spec keeps `pip` available but does not use an inline `pip:` section. GDAL, libgdal, PDAL, python-pdal, rasterio, and numpy are conda-forge owned. Registry entries sourced from PyPI, currently `pyforestscan>=0.4`, are installed afterward with `<backend env>/python -m pip install --no-deps ...` using the same sanitized environment. That prevents pip from replacing conda-forge geospatial DLLs or Python extension modules. The installer must never call QGIS Python pip. Package/import mapping is audited in [PBM Internal Beta Troubleshooting](PBM_INTERNAL_BETA_TROUBLESHOOTING.md).
