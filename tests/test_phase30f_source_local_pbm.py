"""Phase 30F regression coverage for source-local PBM contracts."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from pyforestscan_qgis.backend_runner.job_spec import BackendJobSpec, PBM_PROTOCOL_VERSION, build_job_spec_from_request
from pyforestscan_qgis.backend_runner.run_processing_job import _request_from_spec, _validate_runtime_protocol
from pyforestscan_qgis.backend_runner.runtime_contract import inspect_runtime_contract
from pyforestscan_qgis.core.adapter import PyForestScanAdapter, _backend_user_error, _canonicalize_hag_dimension
from pyforestscan_qgis.core.completed_job_summary import completed_job_summary
from pyforestscan_qgis.core.height_normalization import HeightNormalizationDecision, HeightNormalizationMode
from pyforestscan_qgis.core.job_diagnostics import classify_exception
from pyforestscan_qgis.core.point_dimensions import PointDimensionCapabilities, SourceDimensionMismatch
from pyforestscan_qgis.core.spatial_reference_contract import SpatialReferenceContract, SpatialReferenceMode
from pyforestscan_qgis.core.types import ChmRequest, ProductType, RumpleRequest


class Phase30FContractTests(unittest.TestCase):
    def test_dimension_aliases_are_resolved_once(self):
        for alias in ("HeightAboveGround", "height_above_ground", "HAG", "NormalizedHeight"):
            capabilities = PointDimensionCapabilities.from_names(("X", "Y", "Z", alias))
            self.assertTrue(capabilities.has_existing_hag)
            self.assertEqual(capabilities.hag_dimension_name, alias)

    def test_source_local_existing_hag_survives_json_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            request = ChmRequest(
                Path(folder) / "ohia_01_5m_norm.las",
                Path(folder) / "chm.tif",
                1.0,
                None,
                hag_method="existing_normalized_height",
                source_dimensions=("X", "Y", "Z", "HeightAboveGround"),
            )
            spec = build_job_spec_from_request("chm", request)
            payload = spec.to_dict()
            self.assertEqual(payload["protocol_version"], PBM_PROTOCOL_VERSION)
            self.assertEqual(payload["spatial_reference"]["mode"], "source_local")
            self.assertIsNone(payload["spatial_reference"]["crs"])
            self.assertNotEqual(payload["crs"], "None")
            self.assertEqual(payload["height_normalization"]["mode"], "EXISTING_HAG")
            restored = BackendJobSpec.from_dict(json.loads(json.dumps(payload)))
            backend_request = _request_from_spec(restored)
            self.assertIsNone(backend_request.crs)
            self.assertEqual(backend_request.hag_method, "existing_normalized_height")
            self.assertEqual(backend_request.source_dimensions[-1], "HeightAboveGround")

    def test_literal_none_crs_is_canonicalized_to_source_local(self):
        contract = SpatialReferenceContract.from_crs("None")
        self.assertEqual(contract.mode, SpatialReferenceMode.SOURCE_LOCAL)
        self.assertIsNone(contract.crs)
        restored = SpatialReferenceContract.from_dict({"mode": "source_local", "crs": "None"})
        self.assertIsNone(restored.crs)

    def test_hag_alias_is_canonicalized_without_dropping_dimensions(self):
        try:
            import numpy
        except ImportError:
            self.skipTest("numpy is unavailable")
        array = numpy.zeros(4, dtype=[("X", "f8"), ("Y", "f8"), ("Z", "f8"), ("HAG", "f8"), ("Classification", "u1")])
        normalized, capabilities = _canonicalize_hag_dimension(array)
        self.assertEqual(normalized.dtype.names, ("X", "Y", "Z", "HeightAboveGround", "Classification"))
        self.assertTrue(capabilities.has_existing_hag)

    def test_missing_execution_hag_reports_dimension_mismatch(self):
        error = SourceDimensionMismatch("HeightAboveGround", ("X", "Y", "Z", "Classification"))
        structured = classify_exception(error)
        self.assertEqual(structured.code, "SOURCE_DIMENSION_MISMATCH")
        self.assertIn("expected HeightAboveGround", structured.technical_message)
        message = _backend_user_error(ProductType.CHM, error)
        self.assertIn("did not detect", message)
        self.assertNotIn("assign a CRS", message)

    def test_protocol_mismatch_blocks_before_science(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            spec = BackendJobSpec("job", root / "in.las", None, root, "chm", {}, {"primary": root / "out.tif"}, root / "result.json", protocol_version="1", spatial_reference={"mode": "source_local", "crs": None}, height_normalization={"mode": "EXISTING_HAG", "source_dimension": "HeightAboveGround"})
            with self.assertRaisesRegex(RuntimeError, "needs an update"):
                _validate_runtime_protocol(spec)

    def test_runtime_identity_reports_current_module_locations(self):
        contract = inspect_runtime_contract()
        self.assertEqual(contract["protocol_version"], PBM_PROTOCOL_VERSION)
        self.assertIn("backend_runner", contract["module_locations"])
        self.assertIn("adapter.py", contract["module_locations"]["adapter"])
        self.assertEqual(len(contract["runner_sha256"]), 64)

    def test_runtime_identity_command_uses_real_subprocess(self):
        completed = subprocess.run(
            [sys.executable, "-m", "pyforestscan_qgis.backend_runner.run_processing_job", "inspect_runtime_contract"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["protocol_version"], PBM_PROTOCOL_VERSION)

    def test_failed_summary_retains_requested_products_without_preflight(self):
        class Item:
            status = "failed"
            requested_products = (ProductType.CHM, ProductType.RUMPLE)
            outputs = ()
            message = "failed"
            dataset_path = Path("ohia_01_5m_norm.las")
        class Result:
            items = (Item(),)
            batch_id = "batch"
            failure_count = 1
            success_count = 0
            skipped_count = 0
            output_registry_path = None
        self.assertEqual(completed_job_summary(Result()).requested_products, ("chm", "rumple"))


class Phase30FRealScientificIntegrationTests(unittest.TestCase):
    """Optional real scientific subprocess gate for environments with LAS tooling."""

    def test_real_las_source_local_chm_and_rumple(self):
        try:
            import numpy
            import pdal
            import pyforestscan  # noqa: F401
            import rasterio
        except ImportError as exc:
            self.skipTest(f"real PBM scientific dependencies unavailable: {exc}")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source_local_hag.las"
            xs, ys = numpy.meshgrid(numpy.arange(8.0), numpy.arange(8.0))
            points = numpy.zeros(xs.size, dtype=[("X", "f8"), ("Y", "f8"), ("Z", "f8"), ("HeightAboveGround", "f8"), ("Classification", "u1")])
            points["X"], points["Y"] = xs.ravel(), ys.ravel()
            points["HeightAboveGround"] = 4.0 + 0.25 * points["X"] + 0.15 * points["Y"] + numpy.sin(points["X"]) * 0.2
            points["Z"] = points["HeightAboveGround"] + 100.0
            points["Classification"] = 1
            writer = {"pipeline": [{"type": "writers.las", "filename": str(source), "extra_dims": "HeightAboveGround=double"}]}
            pdal.Pipeline(json.dumps(writer), arrays=[points]).execute()
            requests = (
                ("chm", ChmRequest(source, root / "chm.tif", 1.0, None, interpolation=None, hag_method="existing_normalized_height", source_dimensions=points.dtype.names)),
                ("rumple", RumpleRequest(source, root / "rumple.tif", 1.0, None, interpolation=None, source_dimensions=points.dtype.names)),
            )
            for product, request in requests:
                spec = build_job_spec_from_request(product, request, run_folder=root, job_id=product)
                spec_path = spec.write(root / f"{product}.json")
                completed = subprocess.run([sys.executable, "-m", "pyforestscan_qgis.backend_runner.run_processing_job", "--spec", str(spec_path)], check=False, capture_output=True, text=True, timeout=120)
                self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
            for path in (root / "chm.tif", root / "rumple.tif"):
                with rasterio.open(path) as dataset:
                    self.assertIsNone(dataset.crs)
                    self.assertEqual(dataset.tags()["PYFORESTSCAN_SPATIAL_REFERENCE_MODE"], "SOURCE_LOCAL")
                    self.assertTrue(numpy.isfinite(dataset.read(1)[dataset.read(1) != dataset.nodata]).any())
            self.assertTrue((root / "rumple_summary.csv").exists())
            with rasterio.open(root / "chm.tif") as dataset:
                valid = dataset.read(1)
                valid = valid[valid != dataset.nodata]
                self.assertGreater(float(valid.min()), 3.0)
                self.assertLess(float(valid.max()), 10.0)
            with rasterio.open(root / "rumple.tif") as dataset:
                valid = dataset.read(1)
                valid = valid[valid != dataset.nodata]
                self.assertGreater(float(valid.mean()), 1.0)


if __name__ == "__main__":
    unittest.main()
