# PyForestScan Adapter Design

Phase 4 introduces the plugin-owned adapter boundary between QGIS Processing
algorithms and the external PyForestScan/PyData/PDAL runtime. The adapter exists
so Processing algorithms can remain thin QGIS classes while PyForestScan can
evolve independently.

## Design Goals

- Keep QGIS imports out of core adapter code.
- Keep direct PyForestScan and PDAL calls out of Processing algorithms.
- Return immutable typed objects instead of ad hoc dictionaries or public mapping payloads.
- Translate dependency, dataset, and future processing failures into plugin-owned
  exceptions.
- Provide structured progress and logging interfaces that can later be bridged to
  `QgsProcessingFeedback`.

## Public Core Modules

- `pyforestscan_qgis/core/adapter.py`: `PyForestScanAdapter`, progress tracking,
  dataset validation, and dataset inspection.
- `pyforestscan_qgis/core/config.py`: immutable adapter, dataset-open, and
  inspection options.
- `pyforestscan_qgis/core/types.py`: immutable value objects and enums used at
  the adapter boundary.
- `pyforestscan_qgis/core/exceptions.py`: plugin-owned error hierarchy.
- `pyforestscan_qgis/core/project.py`: immutable plugin-side project context.

## Adapter Surface

`PyForestScanAdapter` defines the long-term API expected by future Processing
algorithms:

- `check_environment()` returns the existing structured dependency report.
- `open_dataset()` validates and stores a dataset reference.
- `validate_dataset()` checks supported formats, path existence, and remote EPT
  rules.
- `inspect_dataset()` reads metadata and point summaries without creating
  scientific products.
- `clip_dataset()` is reserved for future adapter-managed clipping.
- `list_available_products()` returns product families known to the roadmap.
- `compute_products()` is intentionally not implemented in Phase 4.
- `export_products()` is intentionally not implemented in Phase 4.
- `get_progress()`, `cancel()`, and `close()` provide lifecycle control without
  importing QGIS.

## Dataset Inspection

Inspection is metadata-oriented and must not create output rasters, vectors, or
point clouds. Supported inspection inputs are:

- Local LAS: `.las` via PDAL `readers.las`.
- Local LAZ: `.laz` via PDAL `readers.las`.
- Local COPC: `.copc` and `.copc.laz` via PDAL `readers.copc`.
- Local or remote EPT: `ept.json` via direct EPT metadata reads.

Returned `DatasetInspection` objects include point count, bounds, CRS, available
dimensions, typed classification counts when safely available, point format,
estimated point density, supported product families, metadata source, and
warnings.

EPT inspection uses only `ept.json` metadata, so it does not report a
classification summary. LAS/LAZ/COPC inspection executes a PDAL reader pipeline
to obtain point arrays for non-output summaries. This is still inspection, not
scientific product generation.

## Error Boundary

Core code raises plugin-owned exceptions:

- `AdapterError`: base adapter failure.
- `EnvironmentError`: missing or unusable dependencies.
- `DatasetError`: missing input, unsupported format, invalid metadata, or failed
  inspection.
- `ProcessingError`: reserved for future PyForestScan processing failures.

Future QGIS Processing algorithms should catch these at the algorithm boundary
and convert them to `QgsProcessingException` with user-facing messages.

## Progress and Logging

`AdapterProgress` returns immutable `ProgressSnapshot` values. The adapter also
accepts an optional log sink receiving `LogRecord` objects. This keeps core code
independent from QGIS while preserving a clean path to `QgsProcessingFeedback` in
future phases.

No adapter code should use `print()`, `tqdm`, or QGIS message bars.

## Processing Algorithm Rules

Future algorithms may depend on the adapter API and typed values. They must not
call these PyForestScan internals directly:

- `pyforestscan.pipeline._*` helpers.
- `pyforestscan.handlers._read_point_cloud` or `_build_pdal_pipeline`.
- `pyforestscan.process.process_with_tiles` without an adapter wrapper.
- `pyforestscan.utils.tile_las_in_memory` in default workflows.
- `pyforestscan.visualize.*` from Processing algorithms.

## Phase 4 Non-Goals

The original Phase 4 adapter deliberately did not compute scientific products.
Later phases now implement CHM, Canopy Cover, PAD, and PAI through explicit
product methods while `compute_products()`, export/clip placeholders, FHD,
rumple, density rasters, and polygon summaries remain unimplemented until those
workflows are designed and tested.
