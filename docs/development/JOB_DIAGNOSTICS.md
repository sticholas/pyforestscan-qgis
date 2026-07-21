# Job Diagnostics

Phase 27L adds diagnostic-first backend processing for polygon EPT jobs.

Every PBM job workspace may contain a `diagnostics/` folder with:

- `summary.json`
- `backend_contract.json`
- `request_validation.json`
- `environment.json`
- `normalized_request.json`
- `pyforestscan_arguments.json`
- `pdal_pipeline.json` when bounds are available
- `progress_events.jsonl`
- `stdout.log`
- `stderr.log`
- `traceback.txt` on failure
- `checksums.json`
- `README.txt`

Diagnostics are written before full product generation when possible. Request validation checks the backend API contract, EPT metadata, bounds syntax, polygon file, CRS declaration/match, output writability, and product request shape without reading the complete point cloud.

Secrets are not logged. Environment diagnostics retain only a small allowlist of variables needed for runtime troubleshooting and redact secret-like strings. Paths remain because local troubleshooting depends on them.

Structured errors use plugin-owned categories such as `REQUEST_VALIDATION_FAILED`, `BACKEND_CONTRACT_MISMATCH`, `EPT_BOUNDS_INVALID`, `EPT_BOUNDS_OUTSIDE_DATASET`, `EPT_READER_REJECTED_BOUNDS`, `POLYGON_FILE_INVALID`, `OUTPUT_NOT_WRITABLE`, `PYFORESTSCAN_EXECUTION_FAILED`, and `UNKNOWN_BACKEND_FAILURE`.

Progress events carry a sequence number and timestamp model in `ProgressEvent`. The final job state should be shown as the primary card, with chronological progress history expanded only when needed.
