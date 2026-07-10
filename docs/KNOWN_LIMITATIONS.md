# Known Limitations

This document records current limitations for the internal release candidate. It is user-facing and should stay honest: limitations are not failures, but they must be visible before scientific interpretation or wider deployment.

## Scientific Processing

- Product generation uses either PBM backend Python for routed products or QGIS Python for remaining QGIS-Python-only tools. Missing QGIS Python PyForestScan/PDAL packages are optional fallback warnings and do not block PBM-routed products when PBM is `Ready`.
- CHM, Canopy Cover, PAD, PAI, FHD, and Rumple summary are implemented for single datasets, but outputs still require visual QA in QGIS before interpretation.
- PAD is an authoritative multi-band height-bin volume. Mission Control displays a representative grayscale height slice by default; single-band PAD derivatives and RGB composites are visualizations, not replacements for the full PAD volume.
- Rumple currently writes a CSV summary rather than a raster layer.
- Polygon Area Processing now lives in Batch and uses a persistent SQLite/RTree LiDAR catalog for fast polygon source selection. Catalog building reads headers/metadata only and records failures explicitly. Local LAS/LAZ/COPC CRS extraction remains limited until PBM/PDAL metadata inspection is wired into the catalog worker. Raster masking outside the exact polygon is best-effort when rasterio/shapely are available; mosaicking, folder monitoring, and project files remain deferred.

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

`v0.1.0-beta.2` is intended for controlled QGIS testing, workflow validation, and scientific QA. It is not a public QGIS Plugin Repository release candidate. Formal RC1 readiness is gated by the [Release Roadmap](releases/RELEASE_ROADMAP.md), [RC1 Checklist](releases/RC1_CHECKLIST.md), [RC1 Manual QA Script](releases/RC1_MANUAL_QA_SCRIPT.md), and [Release Triage Policy](releases/RELEASE_TRIAGE_POLICY.md). Versioned ZIP artifacts are traceable through `dist/release_manifest.json`.


## PyForestScan Backend Manager

The PyForestScan Backend Manager can run backend installation for Windows internal beta builds only. Linux and macOS installer execution remain planned/experimental until clean platform smoke testing is complete. PBM installs only into the user-local PyForestScan backend folder and must not install into QGIS Python, modify QGIS folders, require administrator privileges, change user environment variables, or enable External Worker mode.

PBM verification can report the managed backend as `Ready`, and Environment Check reports overall `READY` for PBM-routed execution while listing QGIS Python scientific packages as optional fallback status. Phase 23D/23E routes Dataset Explorer local point-cloud inspection, CHM, Canopy Cover, PAD, PAI, FHD, Rumple, DTM, Point Density, and Voxel Statistic through PBM when ready. Phase 23F isolates PBM subprocesses from QGIS profile Python paths and installs PyPI-only backend packages through managed backend Python. Phase 23G verifies staged backend paths before promotion and strict final paths after config write. Phase 23H adds exact dependency diagnostics for staged verification failures; Phase 23I adds backend-local conda DLL/executable discovery for Windows; Phase 23J adds tighter Windows beta GDAL/rasterio/numpy ranges, `pip install --no-deps` for PyPI-only packages, and conda package-build diagnostics for rasterio DLL compatibility; Phase 23K adds explicit conda-forge PyForestScan runtime dependencies before PyForestScan smoke verification; Phase 23L adds tqdm and backend-local GDAL/PROJ data env wiring. If Windows/Python 3.12 package availability still blocks `python-pdal`, `pdal.exe`, `gdalinfo.exe`, `osgeo.gdal`, or `rasterio`, the diagnostic output is the source of truth for the next manifest pinning decision. Height Above Ground point-cloud export and Preprocess Point Cloud still execute inside QGIS Python until their runner payloads are validated separately. QGIS 3.x is the supported target; QGIS 4.x compatibility is prepared defensively but must be tested when available.
