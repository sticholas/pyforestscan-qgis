"""Phase 31A intelligent preparation and HAG recovery regressions."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.backend_runner.job_result import BackendJobResult
from pyforestscan_qgis.backend_runner.job_spec import build_job_spec_from_request
from pyforestscan_qgis.backend_runner.pbm_lidar_preparation import _pipeline
from pyforestscan_qgis.core.classification_inspection import ClassificationAssessment, ClassificationInspectionService, assessment_from_array
from pyforestscan_qgis.core.dataset_report import build_dataset_explorer_report, report_to_dict
from pyforestscan_qgis.core.lidar_preparation import HeightNormalizationPlanMode, HeightNormalizationPlanner, PreparationReadiness, build_preparation_assessment, preparation_recommendations
from pyforestscan_qgis.core.lidar_preparation_execution import checkpoint_is_compatible, execute_preparation, validate_hag_quality
from pyforestscan_qgis.core.source_coordinate_units import SourceCoordinateUnits, assess_source_coordinate_units
from pyforestscan_qgis.core.types import Bounds3D, ChmRequest, DatasetFormat, DatasetInspection, DatasetSource, RumpleRequest


def classification(ground: bool, *, present: bool = True) -> ClassificationAssessment:
    return ClassificationAssessment(present, 1000, ground, 0.1 if ground else 0.0, (), "MEDIUM", "test")


class PreparationPlannerTests(unittest.TestCase):
    def assessment(self, dimensions, ground=False, crs="EPSG:32605", units="", dtm=None, points=1000):
        return build_preparation_assessment(
            source=Path("raw.las"),
            spatial_reference_mode="resolved" if crs else "source_local",
            crs=crs or None,
            coordinate_units=assess_source_coordinate_units(crs, units or ("meters" if crs else "")),
            dimensions=dimensions,
            classification=classification(ground, present="Classification" in dimensions),
            dtm_path=Path(dtm) if dtm else None,
            requested_products=("chm", "rumple"),
            point_count=points,
        )

    def test_existing_hag_is_fast_path(self):
        plan = HeightNormalizationPlanner().plan(self.assessment(("X", "Y", "Z", "HeightAboveGround")))
        self.assertEqual(plan.readiness, PreparationReadiness.READY)
        self.assertEqual(plan.height_mode, HeightNormalizationPlanMode.USE_EXISTING_HAG)
        self.assertFalse(plan.steps)

    def test_existing_ground_selects_delaunay(self):
        plan = HeightNormalizationPlanner().plan(self.assessment(("X", "Y", "Z", "Classification"), ground=True))
        self.assertEqual(plan.readiness, PreparationReadiness.READY_AFTER_PREPARATION)
        self.assertEqual(plan.height_mode, HeightNormalizationPlanMode.DELAUNAY_FROM_EXISTING_GROUND)

    def test_missing_ground_selects_smrf_then_delaunay(self):
        plan = HeightNormalizationPlanner().plan(self.assessment(("X", "Y", "Z", "Classification"), ground=False))
        self.assertEqual(plan.height_mode, HeightNormalizationPlanMode.AUTO_CLASSIFY_GROUND_THEN_DELAUNAY)
        self.assertEqual([step.step_id for step in plan.steps], ["classify_ground", "hag_delaunay"])

    def test_dtm_precedes_ground_generation(self):
        plan = HeightNormalizationPlanner().plan(self.assessment(("X", "Y", "Z"), dtm="terrain.tif"))
        self.assertEqual(plan.height_mode, HeightNormalizationPlanMode.DTM_EXISTING)

    def test_source_local_unknown_units_needs_input(self):
        plan = HeightNormalizationPlanner().plan(self.assessment(("X", "Y", "Z", "Classification"), ground=True, crs=""))
        self.assertEqual(plan.readiness, PreparationReadiness.NEEDS_USER_INPUT)
        self.assertIn("SOURCE_UNITS_UNKNOWN", plan.blockers[0])

    def test_source_local_meter_assignment_allows_delaunay(self):
        plan = HeightNormalizationPlanner().plan(self.assessment(("X", "Y", "Z", "Classification"), ground=True, crs="", units="meters"))
        self.assertEqual(plan.height_mode, HeightNormalizationPlanMode.DELAUNAY_FROM_EXISTING_GROUND)

    def test_vegetation_classes_are_not_required(self):
        plan = HeightNormalizationPlanner().plan(self.assessment(("X", "Y", "Z", "Classification"), ground=True))
        self.assertTrue(plan.can_execute)

    def test_large_conceptual_source_is_marked(self):
        plan = HeightNormalizationPlanner().plan(self.assessment(("X", "Y", "Z", "Classification"), ground=True, points=104_819_538))
        self.assertTrue(plan.large_source)

    def test_recommendations_explain_missing_crs_and_hag(self):
        assessment = self.assessment(("X", "Y", "Z", "Classification"), ground=True, crs="")
        plan = HeightNormalizationPlanner().plan(assessment)
        report = preparation_recommendations(assessment, plan)
        self.assertIn("CRS metadata is missing.", report.observed)
        self.assertTrue(report.blocking_actions)

    def test_pdal_pipeline_contracts(self):
        existing = self.assessment(("X", "Y", "Z", "Classification"), ground=True)
        plan = HeightNormalizationPlanner().plan(existing)
        stages = _pipeline(existing, plan, Path("prepared.laz"))
        self.assertIn("filters.hag_delaunay", [stage["type"] for stage in stages])
        self.assertNotIn("filters.smrf", [stage["type"] for stage in stages])
        automatic = self.assessment(("X", "Y", "Z", "Classification"), ground=False)
        stages = _pipeline(automatic, HeightNormalizationPlanner().plan(automatic), Path("prepared.laz"))
        self.assertIn("filters.smrf", [stage["type"] for stage in stages])


class ClassificationInspectionTests(unittest.TestCase):
    def test_bounded_windows_and_ground_fraction(self):
        try:
            import numpy
        except ImportError:
            self.skipTest("numpy unavailable")
        arrays = []
        specs = []
        class Pipeline:
            def __init__(self, spec):
                specs.append(json.loads(spec)); self.arrays = [numpy.array([(2,), (1,), (1,), (3,)], dtype=[("Classification", "u1")])]
            def execute(self): return 4
        result = ClassificationInspectionService(Pipeline).inspect("large.las", point_count=104_819_538, sample_target=100, strata=5)
        self.assertEqual(len(specs), 5)
        self.assertEqual(result.sampled_points, 20)
        self.assertTrue(result.ground_class_2_observed)
        self.assertAlmostEqual(result.ground_fraction_estimate, 0.25)
        self.assertEqual(result.sampling_method, "storage-stratified bounded PDAL sample")

    def test_missing_classification_is_not_ground_absence_claim(self):
        try:
            import numpy
        except ImportError:
            self.skipTest("numpy unavailable")
        class Pipeline:
            arrays = [numpy.zeros(5, dtype=[("X", "f8")])]
            def __init__(self, spec): pass
            def execute(self): return 5
        result = ClassificationInspectionService(Pipeline).inspect("raw.las", point_count=5)
        self.assertFalse(result.classification_present)
        self.assertIn("dimension", result.warnings[0].lower())


class PreparationExecutionTests(unittest.TestCase):
    def setUp(self):
        try:
            import numpy
        except ImportError:
            self.skipTest("numpy unavailable")
        self.numpy = numpy
        self.array = numpy.zeros(12, dtype=[("X", "f8"), ("Y", "f8"), ("Z", "f8"), ("Classification", "u1")])
        self.array["X"] = numpy.arange(12) % 4
        self.array["Y"] = numpy.arange(12) // 4
        self.array["Z"] = numpy.arange(12) * 0.5
        self.array["Classification"][::4] = 2

    def test_existing_ground_executes_hag_once_and_records_provenance(self):
        assessment = build_preparation_assessment(source="raw.las", spatial_reference_mode="resolved", crs="EPSG:32605", coordinate_units=assess_source_coordinate_units("EPSG:32605", "meters"), dimensions=self.array.dtype.names, classification=assessment_from_array(self.array), dtm_path=None, requested_products=("chm", "rumple"))
        with tempfile.TemporaryDirectory() as folder:
            plan = HeightNormalizationPlanner().plan(assessment)
            calls = []
            class Filters:
                __file__ = "filters.py"
                @staticmethod
                def add_height_above_ground(arrays, method=None, dtm=None):
                    calls.append(method)
                    source = arrays[0]
                    out = self.numpy.empty(source.shape, dtype=[*source.dtype.descr, ("HeightAboveGround", "f8")])
                    for name in source.dtype.names: out[name] = source[name]
                    out["HeightAboveGround"] = self.numpy.linspace(0, 10, len(source))
                    return [out]
            result = execute_preparation((self.array,), assessment, plan, run_folder=Path(folder), job_identity="job", filters_module=Filters)
            self.assertEqual(calls, ["delaunay"])
            self.assertTrue(result.quality.valid)
            self.assertTrue(result.provenance_path.exists())

    def test_quality_retains_negative_values_but_warns(self):
        array = self.numpy.zeros(20, dtype=[("HeightAboveGround", "f8")])
        array["HeightAboveGround"] = self.numpy.linspace(-2, 10, 20)
        quality = validate_hag_quality(array)
        self.assertTrue(quality.valid)
        self.assertGreater(quality.negative_fraction, 0)
        self.assertTrue(quality.warnings)

    def test_checkpoint_requires_signature(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "prepared_hag.laz"
            path.write_bytes(b"las")
            path.with_suffix(".checkpoint.json").write_text(json.dumps({"complete": True, "signature": "abc"}), encoding="utf-8")
            self.assertTrue(checkpoint_is_compatible(path, "abc"))
            self.assertFalse(checkpoint_is_compatible(path, "other"))


class DatasetSemanticsTests(unittest.TestCase):
    def test_missing_hag_is_preparable_not_generic_failure(self):
        inspection = DatasetInspection(DatasetSource("large.las", DatasetFormat.LAS, "EPSG:32605"), 104_819_538, Bounds3D(271369, 272119, 2152760, 2153462, -7.078, 23.643), "EPSG:32605", ("X", "Y", "Z", "Classification"), (), "6", 199.085, (), "pdal")
        payload = report_to_dict(build_dataset_explorer_report(inspection))
        self.assertEqual(payload["preparation"]["readiness"], "READY_AFTER_PREPARATION")
        self.assertIn("prepare", payload["preparation"]["message"].lower())
        statuses = {item["product"]: item["status"] for item in payload["supported_products"]}
        self.assertEqual(statuses["chm"], "Ready after preparation")

    def test_unknown_crs_raw_source_uses_controlled_standalone_fallback(self):
        inspection = DatasetInspection(DatasetSource("large.las", DatasetFormat.LAS), 104_819_538, None, None, ("X", "Y", "Z", "Classification"), (), "6", None, (), "pdal")
        payload = report_to_dict(build_dataset_explorer_report(inspection))
        self.assertEqual(payload["preparation"]["readiness"], "READY_AFTER_PREPARATION")
        self.assertEqual(payload["preparation"]["source_units_basis"], "ASSUMED_SOURCE_LOCAL")
        self.assertFalse(payload["preparation"]["source_units_authoritative"])


class ManagedBackendPreparationIntegrationTests(unittest.TestCase):
    def test_real_pbm_delaunay_checkpoint_chm_rumple(self):
        try:
            import numpy
            import pdal
            import pyforestscan  # noqa: F401
            import rasterio
        except ImportError as exc:
            self.skipTest(f"managed scientific stack unavailable: {exc}")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "raw_ground.las"
            xs, ys = numpy.meshgrid(numpy.arange(10.0), numpy.arange(10.0))
            points = numpy.zeros(xs.size * 2, dtype=[("X", "f8"), ("Y", "f8"), ("Z", "f8"), ("Classification", "u1")])
            points["X"] = numpy.tile(xs.ravel(), 2); points["Y"] = numpy.tile(ys.ravel(), 2)
            points["Z"][:xs.size] = 100.0 + 0.05 * points["X"][:xs.size]
            points["Z"][xs.size:] = 105.0 + 0.2 * points["X"][xs.size:] + 0.1 * points["Y"][xs.size:]
            points["Classification"][:xs.size] = 2; points["Classification"][xs.size:] = 1
            writer = {"pipeline": [{"type": "writers.las", "filename": str(source), "a_srs": "EPSG:32605"}]}
            pdal.Pipeline(json.dumps(writer), arrays=[points]).execute()
            requests = (
                ("chm", ChmRequest(source, root / "chm.tif", 1.0, "EPSG:32605", interpolation=None, source_dimensions=points.dtype.names, source_point_count=len(points))),
                ("rumple", RumpleRequest(source, root / "rumple.tif", 1.0, "EPSG:32605", interpolation=None, source_dimensions=points.dtype.names, source_point_count=len(points))),
            )
            reused = []
            for product, request in requests:
                spec = build_job_spec_from_request(product, request, run_folder=root, job_id=product)
                spec_path = spec.write(root / f"{product}.json")
                completed = subprocess.run([sys.executable, "-m", "pyforestscan_qgis.backend_runner.run_processing_job", "--spec", str(spec_path)], check=False, capture_output=True, text=True, timeout=180)
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                result = BackendJobResult.read(spec.result_path)
                reused.append(bool(result.product_metrics["preparation"]["reused"]))
            self.assertEqual(reused, [False, True])
            self.assertTrue((root / "chm.tif").exists())
            self.assertTrue((root / "rumple.tif").exists())
            provenance = list((root / "preparation").glob("*/preparation_provenance.json"))
            self.assertEqual(len(provenance), 1)
            with rasterio.open(root / "chm.tif") as dataset:
                self.assertEqual(dataset.tags().get("HAG_SOURCE"), "delaunay")

    def test_real_pbm_source_local_meter_delaunay(self):
        try:
            import numpy
            import pdal
            import pyforestscan  # noqa: F401
            import rasterio
        except ImportError as exc:
            self.skipTest(f"managed scientific stack unavailable: {exc}")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); source = root / "source_local_ground.las"
            xs, ys = numpy.meshgrid(numpy.arange(8.0), numpy.arange(8.0))
            points = numpy.zeros(xs.size * 2, dtype=[("X", "f8"), ("Y", "f8"), ("Z", "f8"), ("Classification", "u1")])
            points["X"] = numpy.tile(xs.ravel(), 2); points["Y"] = numpy.tile(ys.ravel(), 2)
            points["Z"][:xs.size] = 10.0; points["Z"][xs.size:] = 14.0 + 0.1 * points["X"][xs.size:]
            points["Classification"][:xs.size] = 2; points["Classification"][xs.size:] = 1
            pdal.Pipeline(json.dumps({"pipeline": [{"type": "writers.las", "filename": str(source)}]}), arrays=[points]).execute()
            request = ChmRequest(source, root / "chm.tif", 1.0, None, interpolation=None, source_dimensions=points.dtype.names, source_coordinate_units="meters", source_point_count=len(points))
            spec = build_job_spec_from_request("chm", request, run_folder=root, job_id="source-local")
            path = spec.write(root / "source-local.json")
            completed = subprocess.run([sys.executable, "-m", "pyforestscan_qgis.backend_runner.run_processing_job", "--spec", str(path)], check=False, capture_output=True, text=True, timeout=180)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            with rasterio.open(root / "chm.tif") as dataset:
                self.assertIsNone(dataset.crs)
                self.assertEqual(dataset.tags().get("HAG_SOURCE"), "delaunay")
                self.assertEqual(dataset.tags().get("PYFORESTSCAN_SPATIAL_REFERENCE_MODE"), "SOURCE_LOCAL")


if __name__ == "__main__":
    unittest.main()
