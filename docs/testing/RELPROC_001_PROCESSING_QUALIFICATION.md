# RELPROC-001 Processing Qualification

## Release baseline

- Baseline release version: `0.2.0-beta.1`
- Maintenance release version: `0.2.0-beta.2`
- Release commit: `3962a42aed9f4b65e4cc6cebebd45a256b1395e3`
- Evidence: the repository tag `viewer-editor-baseline-v0.2.0-beta.1` resolves to this commit; the commit's `metadata.txt` and `__version__.py` both declare `0.2.0-beta.1`; Phase 34 viewer development begins at its child commit.
- Original release artifact/build ID: not retained locally.
- Original release ZIP SHA256: not available. The ignored ZIP in the development checkout was rebuilt from a later viewer commit and is not release evidence.
- Maintenance branch: `maintenance/relproc-001-processing-fix`

The original `develop` checkout contained unrelated, uncommitted Point Cloud work. This ticket uses a separate worktree and does not include those changes.

## Real-data defect evidence

Fixture: `20191210_5QKB020880.laz`, 11,052,238 points, EPSG:32605, XYZ plus LAS dimensions and classification. Qualification used the exact 100 m by 100 m bound `([202000,202100],[2188000,2188100])` and PyForestScan 0.4.1 in the installed managed engine.

### DTM

The previously reported structured-array scalar failure is guarded by the baseline's list-of-arrays adapter. Two remaining release defects were reproduced:

1. Local LAS/LAZ bounds were passed to upstream `read_lidar`, which documents and implements bounds only for EPT. The full 1 km tile was read for a 100 m request.
2. PyForestScan returns raw point extrema for DTM while raster dimensions come from resolution-sized bins. Publishing the raw extrema produced a Y cell size of `1.996047904...` for a requested 2 m grid.

The adapter now uses its existing bounded PDAL path for local sources and publishes the exact bin-grid extent without changing terrain values. The fixed raster is 50 by 50, one band, EPSG:32605, exact 2 m cells, exact requested extent, nodata -9999, 2,493 valid cells, and terrain range 994.53 to 1008.34.

### Point Density

The bounded request initially read the full source. After bounded reading was enforced, Point Density independently failed because the adapter imposed HAG preparation on a product whose registry correctly says HAG is not required. Point density sums every vertical voxel; shifting finite source Z to a non-negative voxel coordinate preserves all XY counts without terrain normalization.

The fixed raster is 50 by 50, one band, EPSG:32605, exact 2 m cells, exact requested extent, and contains 5.25 to 40.0 points per square metre. Its raster sum is 36,499.25 points/m2; multiplied by the 4 m2 cell area this is exactly 145,997 points, matching an independent PDAL crop count of 145,997. Empty cells are zero and outside-mask cells remain the output nodata contract.

## Processing provider inventory

This inventory is derived from `PyForestScanProvider.loadAlgorithms`, not documentation. `QGIS TOOLBOX PASS` means the algorithm registered and completed through QGIS 3.44.13 `processing.run(...)` against a bounded real-data fixture.

| Algorithm ID | Display name | Group/module | Backend/science route | Output | Current qualification |
| --- | --- | --- | --- | --- | --- |
| `pyforestscan:environment_check` | Environment Check | Diagnostics / `placeholder_algorithms.py` | PBM environment diagnostics | status/report | QGIS TOOLBOX PASS |
| `pyforestscan:advanced_chm` | CHM | Metrics / `advanced_chm.py` | PBM -> adapter -> `calculate_chm` | GeoTIFF | QGIS TOOLBOX PASS |
| `pyforestscan:advanced_pad` | PAD | Metrics / `advanced_pad.py` | PBM -> adapter -> voxels -> `calculate_pad` | multiband GeoTIFF | QGIS TOOLBOX PASS |
| `pyforestscan:pad_derivative_raster` | PAD Derivative Raster | Metrics / `pad_derivative.py` | PBM -> adapter -> rasterio derivative | GeoTIFF | QGIS TOOLBOX PASS |
| `pyforestscan:advanced_pai` | PAI | Metrics / `advanced_pai.py` | PBM -> adapter -> PAD -> `calculate_pai` | GeoTIFF | QGIS TOOLBOX PASS |
| `pyforestscan:advanced_canopy_cover` | Canopy Cover | Metrics / `advanced_canopy_cover.py` | PBM -> adapter -> PAD -> `calculate_canopy_cover` | GeoTIFF | QGIS TOOLBOX PASS |
| `pyforestscan:advanced_fhd` | FHD | Metrics / `advanced_fhd.py` | PBM -> adapter -> voxels -> `calculate_fhd` | GeoTIFF | QGIS TOOLBOX PASS |
| `pyforestscan:advanced_rumple` | Rumple Index Raster | Metrics / `advanced_rumple.py` | PBM -> adapter -> CHM -> rumple extension | GeoTIFF + CSV | QGIS TOOLBOX PASS |
| `pyforestscan:advanced_point_density` | Point Density | Metrics / `advanced_point_density.py` | PBM -> adapter -> voxels -> `calculate_point_density` | GeoTIFF | QGIS TOOLBOX PASS; numeric reconciliation |
| `pyforestscan:advanced_voxel_statistic` | Voxel Statistic | Metrics / `advanced_voxel_stat.py` | PBM -> adapter -> `calculate_voxel_stat` | GeoTIFF | QGIS TOOLBOX PASS |
| `pyforestscan:normalize_height_above_ground` | Normalize Heights | Preprocessing / `normalize_hag.py` | PBM -> adapter -> `read_lidar`/`write_las` | LAS/LAZ | QGIS TOOLBOX PASS |
| `pyforestscan:extract_ept_subset` | Extract EPT Subset | I/O / `ept_subset.py` | PBM -> adapter -> `read_lidar`/`write_las` | LAS/LAZ | QGIS TOOLBOX PASS |
| `pyforestscan:advanced_dtm` | Generate DTM | Terrain / `advanced_dtm.py` | PBM -> adapter -> ground filter -> `generate_dtm` | GeoTIFF | QGIS TOOLBOX PASS |
| `pyforestscan:advanced_point_cloud_preprocess` | Preprocess Point Cloud | Preprocessing / `point_cloud_preprocess.py` | PBM -> adapter -> filters -> `write_las` | LAS/LAZ | QGIS TOOLBOX PASS |

Total registered: 14. All 14 actual QGIS Toolbox entry points passed. The EPT route used a retained EPT fixture built from the same 145,997-point bounded LAZ and extracted the exact 100 m validation area.

Shared product parameters include input LAS/LAZ/COPC/EPT path, CRS, output path, X/Y resolution, and load-to-project. Product-specific parameters are authoritatively registered by each module and covered by `test_advanced_processing.py` and `test_processing_toolbox_registration.py`.

## Parity and legacy-route findings

- Mission Control and Toolbox product adapters now share bounded local reads.
- Toolbox display labels are normalized to registry keys before HAG planning. This repairs PAD, PAI, FHD, Canopy Cover, and Voxel Statistic preparation parity.
- Toolbox Point Density now defaults to per-area, matching Mission Control and the released product definition.
- HAG checkpoint publication now passes a list of arrays to PyForestScan 0.4.1. The former tuple was nested by upstream and rejected by PDAL.
- All nine raster products use PBM dispatch from their Toolbox algorithms.
- PAD Derivative, Normalize Heights, and Preprocess Point Cloud now dispatch to the managed engine. The optional no-output HAG inspection path uses a managed temporary job folder instead of constructing a bogus `None` path. External Worker code remains disabled legacy infrastructure.
- PointSourceID is now an optional Toolbox string, matching its disabled-by-default filter; QGIS previously rejected the default empty value before preprocessing could start.
- Dataset Explorer now advertises DTM and Point Density feasibility to the shared planner. Their Mission Control pipeline stages perform real managed-backend science instead of reporting a successful pipeline while silently skipping product generation.

## Test and environment status

- Focused processing/parity/provider tests: 46 passed before final regression additions.
- Full QGIS-free suite: 1,020 passed, 7 dependency/environment skips.
- Managed Windows engine: PyForestScan 0.4.1; all local-source science routes passed on bounded real LAZ.
- QGIS 3.44.13: PASS. QtCore imports through `python-qgis-ltr.bat`; the 100-construction/100-navigation lifecycle smoke passed with no scientific imports in the QGIS process; all 14 algorithms registered and completed through `processing.run(...)`.
- Real sequential multi-file Mission Control path: PASS. Two 145,997-point LAZ inputs each produced CHM, DTM, and Point Density (six rasters total); an immediate repeat produced the same six-output result.
- Real polygon mask: PASS. An EPSG:32605 inset polygon was applied to a real CHM raster through `BackendRasterMaskService`, cropped successfully, and outside cells were assigned nodata -9999.
- Failure injection: PASS. A 145,997-point fixture with ground classifications removed returned the actionable no-ground DTM error through QGIS/PBM without publishing a false output.
- Cancellation/ownership/failure isolation matrix: 45 passed, including queued-file cancellation, owned-process termination, preparation cancellation, retry/backoff, circuit breaking, and partial-success truthfulness.
- QGIS 4.0.0: BLOCKED by the equivalent QtCore DLL failure and is not a supported processing target for this release.

Clean-profile package installation, import, and Mission Control startup remain the final gate before the product ZIP is published.
