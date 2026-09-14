"""Regression tests for Phase 27K polygon transport and backend materialization."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.backend_runner.job_spec import build_job_spec_from_request
from pyforestscan_qgis.backend_runner.run_processing_job import _request_from_spec
from pyforestscan_qgis.core.adapter import _read_lidar_spatial_kwargs
from pyforestscan_qgis.core.polygon_transport import PolygonExecutionInput, materialize_polygon_input, looks_like_wkt
from pyforestscan_qgis.core.types import ChmRequest


POLYGON_WKT = "POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0))"
MULTIPOLYGON_WKT = "MULTIPOLYGON (((0 0, 1 0, 1 1, 0 0)), ((2 2, 3 2, 3 3, 2 2)))"


class Phase27KPolygonTransportTests(unittest.TestCase):
    def _input(self, wkt: str = POLYGON_WKT) -> PolygonExecutionInput:
        return PolygonExecutionInput(
            source_kind="selected_features",
            geometry_wkt=wkt,
            source_crs_authid="EPSG:6635",
            processing_crs_authid="EPSG:32605",
            transformed_geometry_wkt=wkt,
            envelope=(0.0, 0.0, 10.0, 10.0),
            area=100.0,
            feature_count=1,
            temporary_vector_format="GeoJSON",
        )

    def test_materialize_polygon_writes_real_vector_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            prepared = materialize_polygon_input(self._input(), Path(tmpdir) / "job")
            payload = json.loads(prepared.temporary_vector_path.read_text(encoding="utf-8"))

        self.assertEqual(prepared.temporary_vector_format, "GeoJSON")
        self.assertTrue(prepared.temporary_vector_path.name.endswith(".geojson"))
        self.assertEqual(payload["type"], "FeatureCollection")
        self.assertEqual(payload["features"][0]["geometry"]["type"], "Polygon")
        self.assertEqual(payload["crs"]["properties"]["name"], "EPSG:32605")

    def test_materialize_polygon_supports_multipolygon(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            prepared = materialize_polygon_input(self._input(MULTIPOLYGON_WKT), Path(tmpdir) / "job")
            payload = json.loads(prepared.temporary_vector_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["features"][0]["geometry"]["type"], "MultiPolygon")

    def test_backend_request_receives_polygon_file_path_not_wkt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            request = ChmRequest(
                input_path=Path(tmpdir) / "ept.json",
                output_path=Path(tmpdir) / "outputs" / "chm.tif",
                grid_resolution=1.0,
                crs="EPSG:32605",
                bounds=((0.0, 10.0), (0.0, 10.0)),
                crop_polygon=POLYGON_WKT,
                polygon_execution_input=self._input(),
            )
            spec = build_job_spec_from_request("chm", request, run_folder=Path(tmpdir) / "job")
            backend_request = _request_from_spec(spec)

            self.assertIsNotNone(backend_request.crop_polygon_path)
            self.assertTrue(Path(backend_request.crop_polygon_path).exists())
            self.assertFalse(looks_like_wkt(backend_request.crop_polygon_path))
            self.assertEqual(backend_request.crop_polygon, POLYGON_WKT)

    def test_polygon_job_spec_uses_run_folder_not_outputs_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "run" / "outputs" / "chm.tif"
            request = ChmRequest(
                input_path=Path(tmpdir) / "ept.json",
                output_path=output,
                grid_resolution=1.0,
                crs="EPSG:32605",
                crop_polygon=POLYGON_WKT,
                polygon_execution_input=self._input(),
            )
            spec = build_job_spec_from_request("chm", request)
            backend_request = _request_from_spec(spec)

            self.assertEqual(spec.run_folder, output.parent.parent)
            self.assertTrue(str(backend_request.crop_polygon_path).endswith("inputs/clipping_polygon.geojson"))

    def test_adapter_spatial_kwargs_use_polygon_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            request = ChmRequest(
                input_path=Path(tmpdir) / "ept.json",
                output_path=Path(tmpdir) / "outputs" / "chm.tif",
                grid_resolution=1.0,
                crs="EPSG:32605",
                crop_polygon=POLYGON_WKT,
                polygon_execution_input=self._input(),
            )
            kwargs = _read_lidar_spatial_kwargs(request, hag=True)

            self.assertTrue(kwargs["crop_poly"])
            self.assertTrue(Path(str(kwargs["poly"])).exists())
            self.assertFalse(str(kwargs["poly"]).startswith("POLYGON"))


if __name__ == "__main__":
    unittest.main()
