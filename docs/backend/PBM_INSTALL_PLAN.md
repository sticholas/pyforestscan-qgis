# PBM Install Plan

Phase 23C keeps Preview Install Plan as a non-mutating preview while enabling Windows internal beta installer execution after explicit user confirmation. Linux/macOS remain planned until tested.

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

No folders are created by the preview. Windows internal beta installation uses staging and rollback below the same user-local backend root after user confirmation.

## Estimated Future Steps

The plan describes preview steps and the Windows internal beta installer sequence:

1. Prepare user-local backend folders.
2. Download a pinned Micromamba bootstrap artifact.
3. Verify artifact checksums before use.
4. Create the managed backend environment.
5. Install manifest-driven required packages.
6. Write backend configuration and registry state.
7. Run backend verification.

These steps are displayed as a preview. Windows internal beta builds may execute them after confirmation; Linux/macOS remain planned until tested.

## Verification Plan

After install, PBM expects to verify:

- Backend Python version.
- `pyforestscan` import.
- `pdal --version` and `python-pdal` import.
- `osgeo.gdal`, `rasterio`, `numpy`, `scipy`, `pandas`, `shapely`, `pyproj`, `fiona`, `geopandas`, and `matplotlib` imports.
- PyForestScan public module smoke imports for calculate, filters, handlers, process, and visualize.
- Structured verification report and logs.

## Rollback And Repair Plan

The plan preview records repair requirements for installer execution:

- Avoid deleting a known-good backend until replacement verification passes.
- Use staging directories for create/repair operations.
- Mark failed installs as repair-required and preserve logs.
- Keep repair execution planned while Windows internal beta users can inspect logs and retry installation.

## Offline Placeholder

Offline installation remains a placeholder after Phase 23C. A later design may accept pre-downloaded Micromamba artifacts, package caches, and lock/spec files, but every artifact must still pass checksum and version verification before activation.
