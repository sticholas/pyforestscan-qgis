"""Phase 27L PBM request validation and diagnostics tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.backend_runner.api_contract import inspect_api_contract
from pyforestscan_qgis.backend_runner.job_spec import build_job_spec_from_request
from pyforestscan_qgis.backend_runner.request_validation import RequestValidationError, validate_processing_request
from pyforestscan_qgis.backend_runner.run_processing_job import _request_from_spec
from pyforestscan_qgis.core.job_diagnostics import JobErrorCode, classify_exception, support_summary
from pyforestscan_qgis.core.polygon_transport import PolygonExecutionInput
from pyforestscan_qgis.core.types import ChmRequest


POLYGON_WKT = "POLYGON ((1 1, 4 1, 4 4, 1 4, 1 1))"


def compatible_contract() -> dict[str, object]:
    return {
        "compatible": True,
        "python_executable": "python",
        "pyforestscan_version": "test",
        "pdal_version": "test",
        "gdal_version": "test",
        "bounds_parameter_present": True,
        "crop_poly_parameter_present": True,
        "poly_parameter_present": True,
    }


class RequestValidationTests(unittest.TestCase):
    def _polygon_input(self) -> PolygonExecutionInput:
        return PolygonExecutionInput(
            source_kind="selected_features",
            geometry_wkt=POLYGON_WKT,
            source_crs_authid="EPSG:32610",
            processing_crs_authid="EPSG:32610",
            transformed_geometry_wkt=POLYGON_WKT,
            envelope=(1.0, 1.0, 4.0, 4.0),
            area=9.0,
            feature_count=1,
            temporary_vector_format="GeoJSON",
        )

    def test_valid_request_writes_diagnostics_without_reading_point_cloud(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ept = root / "ept.json"
            ept.write_text(json.dumps({"bounds": [0, 0, 0, 10, 10, 5], "srs": {"authority": "EPSG:32610"}}), encoding="utf-8")
            request = ChmRequest(
                input_path=ept,
                output_path=root / "run" / "outputs" / "chm.tif",
                grid_resolution=1.0,
                crs="EPSG:32610",
                bounds=((1.0, 4.0), (1.0, 4.0)),
                crop_polygon=POLYGON_WKT,
                polygon_execution_input=self._polygon_input(),
            )
            spec = build_job_spec_from_request("chm", request, run_folder=root / "run")
            backend_request = _request_from_spec(spec)

            result = validate_processing_request(spec, backend_request, api_contract_provider=compatible_contract)

            self.assertTrue(result.passed)
            self.assertTrue((root / "run" / "diagnostics" / "request_validation.json").exists())
            arguments = json.loads((root / "run" / "diagnostics" / "pyforestscan_arguments.json").read_text(encoding="utf-8"))
            self.assertEqual(arguments["nested_range_types"], ["list", "list"])
            self.assertIn("[1, 4]", arguments["pdal_bounds_expression"])

    def test_non_overlapping_bounds_fail_before_reader(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ept = root / "ept.json"
            ept.write_text(json.dumps({"bounds": [0, 0, 0, 10, 10, 5], "srs": {"authority": "EPSG:32610"}}), encoding="utf-8")
            request = ChmRequest(ept, root / "run" / "outputs" / "chm.tif", 1.0, "EPSG:32610", bounds=((20.0, 21.0), (20.0, 21.0)))
            spec = build_job_spec_from_request("chm", request, run_folder=root / "run")
            backend_request = _request_from_spec(spec)

            with self.assertRaises(RequestValidationError) as raised:
                validate_processing_request(spec, backend_request, api_contract_provider=compatible_contract)

            self.assertIn("do not overlap", str(raised.exception))

    def test_missing_api_parameter_blocks_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ept = root / "ept.json"
            ept.write_text(json.dumps({"bounds": [0, 0, 0, 10, 10, 5], "srs": {"authority": "EPSG:32610"}}), encoding="utf-8")
            request = ChmRequest(ept, root / "run" / "outputs" / "chm.tif", 1.0, "EPSG:32610", bounds=((1.0, 2.0), (1.0, 2.0)))
            spec = build_job_spec_from_request("chm", request, run_folder=root / "run")

            with self.assertRaises(RequestValidationError):
                validate_processing_request(spec, _request_from_spec(spec), api_contract_provider=lambda: {**compatible_contract(), "bounds_parameter_present": False, "compatible": False})

    def test_api_contract_probe_is_structured_without_opening_data(self) -> None:
        contract = inspect_api_contract()
        self.assertIn("python_executable", contract)
        self.assertIn("plugin_adapter_contract_version", contract)
        self.assertIn("compatible", contract)

    def test_error_taxonomy_maps_range_regression(self) -> None:
        try:
            raise RuntimeError("CHM generation failed: No opening '[' in range.")
        except RuntimeError as exc:
            error = classify_exception(exc, stage="Applying EPT Bounds")
        self.assertEqual(error.code, JobErrorCode.EPT_READER_REJECTED_BOUNDS.value)
        text = support_summary(job_id="ept-test", plugin_version="0.1.0-beta.2", product="chm", error=error, bounds_expression="([1, 2], [3, 4])")
        self.assertIn("EPT_READER_REJECTED_BOUNDS", text)
        self.assertIn("([1, 2], [3, 4])", text)


if __name__ == "__main__":
    unittest.main()
