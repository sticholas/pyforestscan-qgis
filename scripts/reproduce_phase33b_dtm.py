"""Re-run a captured PBM DTM request with the current source adapter."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pyforestscan_qgis.backend_runner.run_processing_job import _request_from_spec
from pyforestscan_qgis.backend_runner.job_spec import BackendJobSpec
from pyforestscan_qgis.core.adapter import PyForestScanAdapter


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("request", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.request.read_text(encoding="utf-8"))
    payload["output_paths"]["primary"] = str(args.output)
    payload["product_parameters"]["output_path"] = str(args.output)
    spec = BackendJobSpec.from_dict(payload)
    request = _request_from_spec(spec)
    result = PyForestScanAdapter(execution_mode="qgis_python").generate_dtm(request)
    print(json.dumps({"output": str(result.output_path), "extent": result.spatial_extent, "resolution": result.resolution}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
