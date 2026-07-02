# PBM Install Plan

Phase 22D keeps the dry-run installation preview for normal users and makes it manifest-driven. Developer-only installer execution remains behind `PYFORESTSCAN_QGIS_ENABLE_BACKEND_INSTALL=1`.

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

No folders are created by the preview. Developer-only installation uses staging and rollback below the same user-local backend root.

## Estimated Future Steps

The plan describes normal-user preview steps and the developer-only installer sequence:

1. Prepare user-local backend folders.
2. Download a pinned Micromamba bootstrap artifact.
3. Verify artifact checksums before use.
4. Create the managed backend environment.
5. Install manifest-driven required packages.
6. Write backend configuration and registry state.
7. Run backend verification.

These steps are displayed as planned actions for normal users. They may execute only in developer mode with `PYFORESTSCAN_QGIS_ENABLE_BACKEND_INSTALL=1`.

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
- Keep repair execution disabled until public installer activation is approved.

## Offline Placeholder

Offline installation remains a placeholder after Phase 22D. A later design may accept pre-downloaded Micromamba artifacts, package caches, and lock/spec files, but every artifact must still pass checksum and version verification before activation.
