# PBM Processing Execution

PBM protocol 2 verifies runtime identity before scientific execution and carries explicit spatial-reference and HAG decisions. Source-local jobs record `backend_module_locations.json` and `source_local_trace.json`; protocol mismatch is blocked with a Repair Backend action before PDAL or PyForestScan runs.

Phase 23D routes supported PyForestScan processing through the managed PBM backend when that backend verifies as `Ready`.

The execution path is:

```text
QGIS plugin UI / Processing algorithm
-> PyForestScanAdapter
-> BackendService / BackendExecutionService
-> PBM backend Python
-> pyforestscan_qgis.backend_runner.run_processing_job
-> output files
-> QGIS loads outputs
```

PBM execution is not External Worker mode. It does not launch `qgis-ltr-bin.exe`, `qgis-bin`, `qgis_process`, or any QGIS GUI executable. External Worker mode remains disabled.

## Selection Rules

The adapter supports these execution modes:

| Mode | Behavior |
| --- | --- |
| `auto` | Prefer PBM backend when `BackendService.can_execute_processing()` is ready; otherwise fall back to QGIS Python. |
| `pbm_backend` | Require PBM backend and fail with an actionable message if it is not ready. |
| `qgis_python` | Use the current in-process QGIS Python path. The backend runner uses this mode internally to avoid recursion. |

Mission Control, Dataset Explorer, Advanced Toolbox algorithms, and Batch use the adapter default `auto` mode. When PBM is ready, local LAS/LAZ/COPC inspection and routed products run in PBM backend Python, while QGIS orchestrates the job and loads output files.

## Routed Products

Phase 23D/23E routes Dataset Explorer local point-cloud inspection and these products through PBM when ready:

- CHM.
- Canopy Cover.
- PAD.
- PAI.
- FHD.
- Rumple summary.
- DTM.
- Point Density.
- Voxel Statistic.

Height Above Ground point-cloud export and Preprocess Point Cloud remain on the QGIS Python path until their runner payloads are validated separately. Remote EPT metadata inspection remains local metadata parsing.

## Safety Checks

Before running a PBM job, the execution service verifies:

- PBM backend verification status is `Ready`.
- Backend Python exists.
- Backend Python looks like `python`, `python.exe`, `python3`, or `python3.exe`.
- The executable path does not contain QGIS GUI markers such as `qgis-ltr-bin`, `qgis-bin`, `qgis.exe`, `qgis-ltr.exe`, or `qgis_process`.

Execution logs include the exact backend Python path and job spec path. Failures return structured errors and are converted to adapter `ProcessingError` messages instead of crashing QGIS.

## Fallback Behavior

If PBM is not ready and QGIS Python has scientific dependencies, the existing QGIS Python path remains available. If neither PBM nor QGIS Python can run a product, users see missing backend/dependency guidance from Environment Check, Mission Control, or Processing error messages.
