# Known Limitations

This document records current limitations for the internal release candidate. It is user-facing and should stay honest: limitations are not failures, but they must be visible before scientific interpretation or wider deployment.

## Scientific Processing

- Product generation depends on the installed PyForestScan, PDAL, GDAL, rasterio, and numpy versions in the active QGIS Python environment.
- CHM, Canopy Cover, PAD, PAI, FHD, and Rumple summary are implemented for single datasets, but outputs still require visual QA in QGIS before interpretation.
- PAD is a multi-band height-bin raster. Mission Control loads it as an RGB 5/3/2 composite when enough bands exist; users may need to inspect individual bands manually.
- Rumple currently writes a CSV summary rather than a raster layer.
- Polygon summaries, mosaicking, cataloging, folder monitoring, and project files are not implemented.

## Batch Processing

- Sequential mode is the safest default.
- Parallel Safe mode runs inside QGIS with bounded workers and guardrails; users should start with two workers.
- Cancellation and pause are checked between files, not during a native PyForestScan/PDAL product calculation.
- Batch output loading into QGIS is off by default to avoid overwhelming a project with many layers.
- External Worker mode is disabled because QGIS GUI Python launched application windows during validation. It remains disabled until a true headless launcher is proven.

## User Experience

- Mission Control manages internal JSON/CSV/HTML files automatically, but raw files remain visible under technical details for reproducibility.
- The Dataset footprint preview is a rectangular extent from inspected bounds, not an exact point-cloud coverage polygon.
- The Scientific Advisor uses deterministic, documented rules and configurable thresholds. It is guidance, not a substitute for scientific review.

## Release Scope

`v0.1.0-beta.1` is intended for controlled QGIS testing, workflow validation, and scientific QA. It is not a public QGIS Plugin Repository release candidate. Versioned ZIP artifacts are traceable through `dist/release_manifest.json`.


## PyForestScan Backend Manager

The PyForestScan Backend Manager can run backend installation for Windows internal beta builds only. Linux and macOS installer execution remain planned/experimental until clean platform smoke testing is complete. PBM installs only into the user-local PyForestScan backend folder and must not install into QGIS Python, modify QGIS folders, require administrator privileges, change user environment variables, or enable External Worker mode.

PBM verification can report the managed backend as `Ready`, and Phase 23D/23E routes Dataset Explorer local point-cloud inspection, CHM, Canopy Cover, PAD, PAI, FHD, Rumple, DTM, Point Density, and Voxel Statistic through PBM when ready. Phase 23F isolates PBM subprocesses from QGIS profile Python paths and installs PyPI-only backend packages through managed backend Python. Phase 23G verifies staged backend paths before promotion and strict final paths after config write. Phase 23H adds exact dependency diagnostics for staged verification failures; Phase 23I adds backend-local conda DLL/executable discovery for Windows. If Windows/Python 3.12 package availability still blocks `python-pdal`, `pdal.exe`, `gdalinfo.exe`, `osgeo.gdal`, or `rasterio`, the diagnostic output is the source of truth for the next manifest pinning decision. Height Above Ground point-cloud export and Preprocess Point Cloud still execute inside QGIS Python until their runner payloads are validated separately. QGIS 3.x is the supported target; QGIS 4.x compatibility is prepared defensively but must be tested when available.
