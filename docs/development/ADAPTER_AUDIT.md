# Adapter Architecture Audit

Phase 4B audited the Phase 4 adapter implementation against the Phase 3A
PyForestScan API discovery documents and the installed PyForestScan package in
the Windows QGIS/OSGeo4W Python environment.

## Audit Scope

Reviewed documentation:

- `docs/api/PYFORESTSCAN_API.md`
- `docs/development/ADAPTER_DESIGN.md`

Reviewed adapter implementation:

- `pyforestscan_qgis/core/adapter.py`
- `pyforestscan_qgis/core/config.py`
- `pyforestscan_qgis/core/types.py`
- `pyforestscan_qgis/core/project.py`
- `pyforestscan_qgis/core/exceptions.py`

Reviewed tests:

- `tests/test_adapter.py`
- `tests/test_dependency_check.py`

## Installed PyForestScan API Check

WSL `python3` does not have PyForestScan installed, which is expected for this
repository. The installed package was inspected through the Windows
QGIS/OSGeo4W Python environment. The probe found PyForestScan at:

```text
C:\Users\Lama\AppData\Roaming\Python\Python312\site-packages\pyforestscan\__init__.py
```

Observed public top-level names matched the Phase 3A inventory:

```text
assign_voxels
calculate_chm
calculate_pad
calculate_pai
calculate_fhd
calculate_canopy_cover
calculate_rumple
calculate_point_density
calculate_voxel_stat
generate_dtm
```

Observed public modules matched the Phase 3A inventory:

```text
calculate
filters
handlers
pipeline
process
utils
visualize
```

Important API observations confirmed during the audit:

- PyForestScan remains function-oriented; it does not provide a project/session
  object.
- There is no dedicated PyForestScan dataset-inspection API.
- `handlers.read_lidar` is the future public read path for LAS, LAZ, COPC, COPC
  LAZ, and EPT when scientific processing begins.
- `process.process_with_tiles` remains inappropriate as the first QGIS
  integration target because it owns output writing, progress, and warnings.
- Visualization helpers remain unsuitable for QGIS Processing algorithms.

## Adapter Interface Alignment

The Phase 4 adapter interface is aligned with the Phase 3A findings. Because
PyForestScan has no project object, the plugin owns `PyForestScanProject`,
configuration dataclasses, request/result placeholders, progress state, and
structured logging.

The adapter intentionally exposes these methods for future phases:

- `check_environment()`
- `open_dataset()`
- `validate_dataset()`
- `inspect_dataset()`
- `clip_dataset()`
- `list_available_products()`
- `compute_products()`
- `export_products()`
- `get_progress()`
- `cancel()`
- `close()`

`compute_products()`, `clip_dataset()`, and `export_products()` intentionally
raise `NotImplementedError`. This is correct for Phase 4B because no CHM, PAI,
PAD, FHD, canopy cover, rumple, raster writing, vector writing, or clipping
workflow has been implemented yet.

## Dataset Inspection Path

Dataset inspection does not use PyForestScan calculation functions. This is
intentional. PyForestScan 0.4.0 does not expose a stable public inspection API,
so the adapter uses:

- direct `ept.json` metadata reads for EPT sources;
- PDAL reader pipelines for LAS, LAZ, and COPC inspection.

This keeps inspection separate from scientific product generation. The adapter
does not call `pyforestscan.calculate_*`, `assign_voxels`, `handlers.create_geotiff`,
`handlers.write_las`, or `process.process_with_tiles`.

## QGIS Dependency Boundary

No QGIS dependency is present in the adapter layer. `pyforestscan_qgis/core` uses
plain Python modules and lazy dependency imports. The dependency-check module can
probe `qgis.core` when asked to create an environment report, but importing the
core adapter itself does not require QGIS.

The adapter tests do not require QGIS. They use plain `unittest`, temporary
files, local EPT metadata, and a fake PDAL module for pipeline inspection tests.

## Scientific Processing Check

No scientific processing was found in the adapter implementation. The audit
confirmed no calls to:

- `calculate_chm`
- `calculate_pad`
- `calculate_pai`
- `calculate_fhd`
- `calculate_canopy_cover`
- `calculate_rumple`
- `assign_voxels`
- `generate_dtm`
- `create_geotiff`
- `write_las`
- `process_with_tiles`

The adapter can read dataset metadata and point arrays for inspection, but it
does not create products or outputs.

## Fix Applied During Audit

One small concrete issue was found and fixed: `InspectionOptions.include_dimensions`
existed but was not honored by `inspect_dataset()`. The adapter now omits returned
dimensions when this option is `False`, while still using internal dimensions as
needed to decide whether a classification summary can be produced. A unit test
was added for this behavior.

This fix does not change the public adapter interface and does not affect
Processing algorithms.

## Risks Before Phase 5

- PDAL inspection for LAS, LAZ, and COPC may load substantial point arrays. This
  is acceptable for Phase 4 inspection, but Phase 5 should decide whether large
  dataset inspection needs metadata-only, sampled, or bounded modes.
- EPT inspection uses metadata only, so classification summaries are unavailable
  unless a future sampled EPT inspection path is added.
- PyForestScan does not expose progress or cancellation callbacks; future
  processing phases must wrap long-running work carefully and keep QGIS feedback
  responsive where possible.
- CRS handling remains plugin-owned. Phase 5 should avoid relying on PyForestScan
  to validate or transform QGIS vector CRS inputs.
- The installed package exposes no `__version__` attribute at top level in the
  inspected environment, so version checks should continue using package metadata
  where possible.
- Direct PDAL metadata structures can vary by PDAL version. Adapter parsing
  should remain defensive and covered by tests as real datasets are introduced.

## Approval Decision

Approved for Phase 5 with risks noted. The adapter boundary is correctly
separated from QGIS, aligned with the discovered PyForestScan 0.4.0 API, and has
not implemented scientific processing. Future Processing algorithms should use
the adapter rather than importing PyForestScan or PDAL directly.

## Validation Commands

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q pyforestscan_qgis tests
rg "from qgis|import qgis|Qgs" pyforestscan_qgis/core tests
```

Validation result: 14 tests passed; compile check passed; QGIS import search
returned no adapter/core test matches.
