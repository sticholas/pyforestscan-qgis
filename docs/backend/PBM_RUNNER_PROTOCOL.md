# PBM Runner Protocol

The PBM runner is a small Python module packaged with the QGIS plugin and executed by PBM backend Python:

```bash
<backend_python> -m pyforestscan_qgis.backend_runner.run_processing_job --spec <job_spec.json>
```

The subprocess working directory is the parent directory of the installed `pyforestscan_qgis` package, so backend Python can import the packaged runner without installing the plugin into QGIS Python or modifying global environment variables.

## Job Spec

A job spec JSON contains:

- `job_id`
- `input_lidar_path`
- `crs`
- `run_folder`
- `product`
- `product_parameters`
- `output_paths`
- `result_path`
- optional `hag_options`
- optional `dtm_path`
- `plugin_version`
- `protocol_version`

Specs are written under the run folder in `.pbm_jobs/`.

## Job Result

The runner writes `result_path` with:

- `status`: `success` or `failed`
- `outputs`
- `warnings`
- `errors`
- `started_at`
- `finished_at`
- `product_metrics`
- captured `stdout` / `stderr` from the QGIS-side subprocess call
- traceback only inside the technical result/log payload

QGIS reads this result and maps it back to adapter result types such as `ChmResult`, `PadResult`, or `DtmResult`.

## Product Dispatch

The runner constructs adapter request dataclasses from the JSON spec and calls `PyForestScanAdapter(execution_mode="qgis_python")` inside backend Python. This deliberately reuses the existing adapter scientific implementation while preventing recursive PBM subprocess calls.

## Non-Goals

The runner does not:

- modify QGIS Python
- modify PATH or user environment variables
- start QGIS GUI executables
- replace the disabled External Worker mode
- perform package installation
