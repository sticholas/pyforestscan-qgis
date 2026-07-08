"""QGIS-free tests for EPT subset extraction models and routing."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from pyforestscan_qgis.backend_runner.job_spec import build_job_spec_from_request
from pyforestscan_qgis.core.adapter import PyForestScanAdapter
from pyforestscan_qgis.core.ept_subset import (
    EptSubsetRequest,
    build_ept_subset_request,
    compact_ept_subset_summary,
    ept_read_lidar_kwargs,
    parse_ept_bounds,
)
from pyforestscan_qgis.core.exceptions import ProcessingError


class EptSubsetTests(unittest.TestCase):
    """EPT subset validation does not require QGIS."""

    def test_parse_bounds_supports_xy_and_xyz(self) -> None:
        self.assertEqual(((1.0, 2.0), (3.0, 4.0)), parse_ept_bounds("1,2,3,4"))
        self.assertEqual(((1.0, 2.0), (3.0, 4.0), (5.0, 6.0)), parse_ept_bounds("1,2,3,4,5,6"))
        self.assertIsNone(parse_ept_bounds(""))

    def test_request_validation_requires_ept_source_srs_and_las_laz_output(self) -> None:
        with self.assertRaises(ProcessingError):
            build_ept_subset_request(input_path="plot.laz", crs="EPSG:32610", output_path="subset.laz")
        with self.assertRaises(ProcessingError):
            build_ept_subset_request(input_path="ept.json", crs="", output_path="subset.laz")
        with self.assertRaises(ProcessingError):
            build_ept_subset_request(input_path="ept.json", crs="EPSG:32610", output_path="subset.tif")

    def test_request_validation_catches_read_lidar_option_conflicts(self) -> None:
        with self.assertRaises(ProcessingError):
            build_ept_subset_request(input_path="ept.json", crs="EPSG:32610", output_path="subset.laz", thin_radius=0)
        with self.assertRaises(ProcessingError):
            build_ept_subset_request(input_path="ept.json", crs="EPSG:32610", output_path="subset.laz", hag=True, hag_dtm=True)
        with self.assertRaises(ProcessingError):
            build_ept_subset_request(input_path="ept.json", crs="EPSG:32610", output_path="subset.laz", hag_dtm=True)
        with self.assertRaises(ProcessingError):
            build_ept_subset_request(input_path="ept.json", crs="EPSG:32610", output_path="subset.laz", crop_poly=True)

    def test_request_maps_exact_read_lidar_kwargs(self) -> None:
        request = build_ept_subset_request(
            input_path="ept.json",
            crs="EPSG:32610",
            output_path="subset.laz",
            bounds_text="1,2,3,4,5,6",
            thin_radius=0.5,
            hag_dtm=True,
            dtm_path="dtm.tif",
            crop_poly=True,
            poly="POLYGON ((0 0, 1 0, 1 1, 0 0))",
            reproject=True,
        )

        self.assertEqual(
            ept_read_lidar_kwargs(request),
            {
                "bounds": ((1.0, 2.0), (3.0, 4.0), (5.0, 6.0)),
                "thin_radius": 0.5,
                "hag": False,
                "hag_dtm": True,
                "dtm": "dtm.tif",
                "crop_poly": True,
                "poly": "POLYGON ((0 0, 1 0, 1 1, 0 0))",
                "reproject": True,
            },
        )

    def test_pbm_job_spec_maps_ept_subset_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            request = EptSubsetRequest(root / "ept.json", "EPSG:32610", root / "subset.laz", bounds=((1.0, 2.0), (3.0, 4.0)), thin_radius=0.25)
            spec = build_job_spec_from_request("ept_subset_extract", request, run_folder=root, job_id="job-ept")

        self.assertEqual(spec.product, "ept_subset_extract")
        self.assertEqual(spec.output_paths["primary"].name, "subset.laz")
        self.assertEqual(spec.product_parameters["bounds"], [[1.0, 2.0], [3.0, 4.0]])
        self.assertEqual(spec.hag_options["bounds"], [[1.0, 2.0], [3.0, 4.0]])
        self.assertEqual(spec.hag_options["thin_radius"], 0.25)

    def test_adapter_routes_ept_subset_through_pbm_when_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            class FakeService:
                def can_execute_processing(self):
                    return SimpleNamespace(ready=True, backend_python=Path("/backend/python"), message="ready")

                def run_product(self, product, request):  # type: ignore[no-untyped-def]
                    self.product = product
                    return SimpleNamespace(
                        product_metrics={
                            "output_path": str(request.output_path),
                            "point_count": 12,
                            "written": True,
                            "message": "subset ready",
                        },
                        outputs={"primary": request.output_path},
                    )

            request = EptSubsetRequest(root / "ept.json", "EPSG:32610", root / "subset.laz")
            adapter = PyForestScanAdapter(backend_service_factory=FakeService)
            result = adapter.extract_lidar_subset(request)

        self.assertEqual(result.output_path.name, "subset.laz")
        self.assertEqual(result.point_count, 12)
        self.assertEqual(result.message, "subset ready")

    def test_compact_result_summary_is_user_facing(self) -> None:
        summary = compact_ept_subset_summary(
            SimpleNamespace(output_path=Path("subset.laz"), point_count=1200, written=True, message="ok")
        )

        self.assertEqual(summary, "EPT subset written: subset.laz (1,200 points).")


if __name__ == "__main__":
    unittest.main()
