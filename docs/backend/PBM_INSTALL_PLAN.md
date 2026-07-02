# PBM Install Plan

Phase 22B adds a dry-run installation plan for the PyForestScan Backend Manager (PBM). It prepares the future installer design without downloading Micromamba, creating environments, installing packages, modifying QGIS Python, or changing user environment variables.

## Planned Backend Layout

PBM continues to use a user-local backend root:

| Platform | Planned backend root |
| --- | --- |
| Windows | `%LOCALAPPDATA%/PyForestScan/backend/` |
| Linux | `~/.local/share/PyForestScan/backend/` |
| macOS | `~/Library/Application Support/PyForestScan/backend/` |

The dry-run plan reports these paths:

- Backend root.
- Micromamba executable location.
- Managed environment path.
- Download cache path.
- Logs and verification report locations.

No folders are created by the preview.

## Estimated Future Steps

The Phase 22B planner describes future installer work only:

1. Prepare user-local backend folders.
2. Download a pinned Micromamba bootstrap artifact.
3. Verify artifact checksums before use.
4. Create the managed backend environment.
5. Install registry-driven required packages.
6. Write backend configuration and registry state.
7. Run backend verification.

These steps are displayed as planned actions. They are not executed in Phase 22B.

## Verification Plan

After a future install, PBM expects to verify:

- Backend Python version.
- `pyforestscan` import.
- `pdal --version` and `python-pdal` import.
- `osgeo.gdal`, `rasterio`, and `numpy` imports.
- Structured verification report and logs.

## Rollback And Repair Plan

The dry-run plan records repair requirements for the future installer:

- Avoid deleting a known-good backend until replacement verification passes.
- Use staging directories for create/repair operations.
- Mark failed installs as repair-required and preserve logs.
- Keep repair disabled until controlled installer work begins.

## Offline Placeholder

Offline installation is only a placeholder in Phase 22B. A later design may accept pre-downloaded Micromamba artifacts, package caches, and lock/spec files, but every artifact must still pass checksum and version verification before activation.
