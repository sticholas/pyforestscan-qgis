import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pyforestscan_qgis.backend_runner.pbm_lidar_preparation import (
    PreparedSourceResult,
    _pipeline,
    _acquire_preparation_lock,
    _scope_plan,
    prepare_durable_source,
)
from pyforestscan_qgis.core.classification_inspection import ClassificationAssessment
from pyforestscan_qgis.core.lidar_preparation import (
    HeightNormalizationPlanMode,
    HeightNormalizationPlanner,
    build_preparation_assessment,
)
from pyforestscan_qgis.core.polygon_batch import _assert_source_preparation_complete
from pyforestscan_qgis.core.source_coordinate_units import assess_source_coordinate_units
from pyforestscan_qgis.core.types import ChmRequest


def _classification():
    return ClassificationAssessment(True, 1000, True, 0.05, (), "HIGH", "bounded sample", (), ((2, 50), (1, 950)), ("X", "Y", "Z", "Classification"), 5, 5, 1.0, "HIGH")


class DurablePreparationPlanningTests(unittest.TestCase):
    def assessment(self, normalized=False):
        return build_preparation_assessment(
            source=Path("normalized.las"),
            spatial_reference_mode="resolved",
            crs="EPSG:6635",
            coordinate_units=assess_source_coordinate_units("EPSG:6635", "meters"),
            dimensions=("X", "Y", "Z", "Classification"),
            classification=_classification(),
            dtm_path=None,
            requested_products=("chm", "rumple"),
            point_count=104_819_538,
            normalized_z_validated=normalized,
        )

    def test_validated_normalized_z_is_explicit_preparation_mode(self):
        plan = HeightNormalizationPlanner().plan(self.assessment(True), checkpoint_root=Path("preparation"))
        self.assertEqual(plan.height_mode, HeightNormalizationPlanMode.EXISTING_NORMALIZED_Z)
        self.assertTrue(plan.large_source)

    def test_normalized_z_pipeline_materializes_hag_once_with_support_bounds(self):
        plan = HeightNormalizationPlanner().plan(self.assessment(True), checkpoint_root=Path("preparation"))
        stages = _pipeline(self.assessment(True), plan, Path("prepared_hag.laz"), {"xmin": 1, "ymin": 2, "xmax": 3, "ymax": 4})
        self.assertEqual(stages[1], {"type": "filters.crop", "bounds": "([1.0,3.0],[2.0,4.0])"})
        self.assertIn({"type": "filters.ferry", "dimensions": "Z=>HeightAboveGround"}, stages)
        self.assertNotIn("filters.hag_delaunay", [stage["type"] for stage in stages])

    def test_support_extent_changes_preparation_signature_and_artifact(self):
        root = Path("preparation")
        plan = HeightNormalizationPlanner().plan(self.assessment(False), checkpoint_root=root)
        first = _scope_plan(plan, root, {"xmin": 0, "ymin": 0, "xmax": 10, "ymax": 10})
        second = _scope_plan(plan, root, {"xmin": 0, "ymin": 0, "xmax": 20, "ymax": 20})
        self.assertNotEqual(first.signature, second.signature)
        self.assertNotEqual(first.prepared_artifact, second.prepared_artifact)

    def test_runtime_contract_changes_preparation_signature(self):
        root = Path("preparation")
        plan = HeightNormalizationPlanner().plan(self.assessment(False), checkpoint_root=root)
        first = _scope_plan(plan, root, {"xmin": 0, "ymin": 0, "xmax": 10, "ymax": 10}, {"engine_id": "first"})
        second = _scope_plan(plan, root, {"xmin": 0, "ymin": 0, "xmax": 10, "ymax": 10}, {"engine_id": "second"})
        self.assertNotEqual(first.signature, second.signature)


class DurablePreparationCheckpointTests(unittest.TestCase):
    def test_live_owner_prevents_duplicate_preparation(self):
        with tempfile.TemporaryDirectory() as folder:
            lock = Path(folder) / "preparation.lock"
            lock.write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "owns this source preparation lock"):
                _acquire_preparation_lock(lock)

    def test_dead_owner_lock_is_recovered(self):
        with tempfile.TemporaryDirectory() as folder:
            lock = Path(folder) / "preparation.lock"
            lock.write_text(json.dumps({"pid": 99999999}), encoding="utf-8")
            descriptor = _acquire_preparation_lock(lock)
            os.close(descriptor)
            self.assertTrue(lock.exists())
    def test_completed_status_is_required_before_worker_start(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            prepared = root / "prepared_hag.laz"
            prepared.write_bytes(b"prepared")
            status = root / "status.json"
            status.write_text(json.dumps({"state": "COMPLETE", "preparation_artifact_path": str(prepared)}), encoding="utf-8")
            _assert_source_preparation_complete(status, prepared)
            status.write_text(json.dumps({"state": "PREPARING"}), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "SOURCE_PREPARATION_FAILED"):
                _assert_source_preparation_complete(status, prepared)

    def test_durable_wrapper_writes_one_complete_source_status(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source.las"
            source.write_bytes(b"source")
            artifact = root / "prepared_hag.laz"
            artifact.write_bytes(b"prepared")
            request = ChmRequest(source, root / "chm.tif", 1.0, "EPSG:6635", source_point_count=104_819_538)
            fake_plan = SimpleNamespace(signature="signature", height_mode=HeightNormalizationPlanMode.DELAUNAY_FROM_EXISTING_GROUND)
            fake_result = PreparedSourceResult(request.__class__(artifact, request.output_path, request.grid_resolution, request.crs, source_dimensions=("X", "Y", "Z", "HeightAboveGround")), fake_plan, root / "provenance.json", False)
            with patch("pyforestscan_qgis.backend_runner.pbm_lidar_preparation.prepare_request_source", return_value=fake_result), patch("pyforestscan_qgis.backend_runner.pbm_lidar_preparation._inspect_prepared_hag", return_value={"valid": True, "warnings": []}):
                result = prepare_durable_source(SimpleNamespace(product="chm"), request, status_root=root / "source_preparation", preparation_bounds={"xmin": 0, "ymin": 0, "xmax": 10, "ymax": 10})
            status = json.loads((root / "source_preparation" / "status.json").read_text(encoding="utf-8"))
            self.assertEqual(status["state"], "COMPLETE")
            self.assertEqual(result.request.input_path, artifact)
            self.assertFalse((root / "source_preparation" / "preparation.lock").exists())

    def test_preparation_failure_is_one_source_level_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source.las"
            source.write_bytes(b"source")
            request = ChmRequest(source, root / "chm.tif", 1.0, "EPSG:6635")
            with patch("pyforestscan_qgis.backend_runner.pbm_lidar_preparation.prepare_request_source", side_effect=RuntimeError("PREPARATION_VALIDATION_FAILED")):
                with self.assertRaisesRegex(RuntimeError, "PREPARATION_VALIDATION_FAILED"):
                    prepare_durable_source(SimpleNamespace(product="chm"), request, status_root=root / "source_preparation")
            status = json.loads((root / "source_preparation" / "status.json").read_text(encoding="utf-8"))
            self.assertEqual(status["state"], "FAILED")
            self.assertEqual(status["error_code"], "SOURCE_PREPARATION_QUALITY_FAILED")


class CoordinatorContractTests(unittest.TestCase):
    def test_polygon_scheduler_prepares_before_scheduler_construction(self):
        root = Path(__file__).parents[1]
        source = (root / "pyforestscan_qgis/core/polygon_batch.py").read_text(encoding="utf-8")
        function = source[source.index("def _execute_source_aware_chm"):source.index("def _prepare_source_dependency")]
        self.assertLess(function.index("_prepare_source_dependency"), function.index("PolygonProductWorkScheduler"))
        self.assertIn("prepared_source_path", function)
        self.assertNotIn("Large sources must complete durable PBM preparation", function)


if __name__ == "__main__":
    unittest.main()
