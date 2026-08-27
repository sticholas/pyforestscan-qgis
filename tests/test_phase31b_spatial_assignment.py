"""Phase 31B trusted spatial-assignment and large-LAS completion regressions."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from pyforestscan_qgis.core.classification_inspection import ClassificationAssessment, ClassificationInspectionService
from pyforestscan_qgis.core.dataset_report import build_dataset_explorer_report, report_to_dict
from pyforestscan_qgis.core.lidar_preparation import HeightNormalizationPlanMode, HeightNormalizationPlanner, PreparationReadiness, build_preparation_assessment
from pyforestscan_qgis.core.source_coordinate_units import SourceCoordinateUnits, assess_source_coordinate_units
from pyforestscan_qgis.core.spatial_assignment import AssignmentScope, LinearUnit, SpatialAssignmentType
from pyforestscan_qgis.core.spatial_reference_resolver import SpatialReferenceAssignmentStore, SpatialReferenceResolver, SpatialReferenceStatus
from pyforestscan_qgis.core.types import Bounds3D, ClassificationCount, DatasetInspection, DatasetSource, DatasetFormat
from pyforestscan_qgis.core.batch_preflight import _check_preparation_spatial_readiness


class SpatialAssignmentStoreTests(unittest.TestCase):
    def test_units_only_file_assignment_is_typed_persisted_and_source_local(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "large.las"
            source.write_bytes(b"LAS")
            store = SpatialReferenceAssignmentStore(root / "assignments.json")
            assignment = store.assign_units(source, LinearUnit.METERS)
            restored = store.spatial_assignment_for(source, source.parent)
            self.assertEqual(SpatialAssignmentType.USER_UNITS_ONLY, assignment.assignment_type)
            self.assertEqual(LinearUnit.METERS, restored.linear_units)
            self.assertFalse(restored.crs_assigned)
            profile = SpatialReferenceResolver(store).spatial_profile(source)
            self.assertTrue(profile.preparation_safe)
            self.assertFalse(profile.polygon_alignment_safe)
            self.assertEqual(SpatialReferenceStatus.SOURCE_LOCAL_ONLY, SpatialReferenceResolver(store).resolve(source, source_local_allowed=True).status)

    def test_file_precedes_repository_and_authoritative_conflict_is_not_silent(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "repo"
            root.mkdir()
            source = root / "plot.las"
            source.write_bytes(b"LAS")
            store = SpatialReferenceAssignmentStore(Path(folder) / "assignments.json")
            store.assign_repository(root, "EPSG:32605")
            store.assign_file(source, "EPSG:6635")
            result = SpatialReferenceResolver(store).resolve(source)
            self.assertEqual("EPSG:6635", result.resolved_crs)
            conflict = SpatialReferenceResolver(store).resolve(source, embedded_crs="EPSG:32605")
            self.assertEqual(SpatialReferenceStatus.CONFLICT, conflict.status)

    def test_repository_assignment_invalidates_after_inventory_change(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "repo"
            root.mkdir()
            source = root / "a.las"
            source.write_bytes(b"a")
            store = SpatialReferenceAssignmentStore(Path(folder) / "assignments.json")
            store.assign_units(root, LinearUnit.US_SURVEY_FEET, scope=AssignmentScope.REPOSITORY)
            self.assertEqual(LinearUnit.US_SURVEY_FEET, store.spatial_assignment_for(source, root).linear_units)
            (root / "b.las").write_bytes(b"b")
            self.assertIsNone(store.spatial_assignment_for(source, root))

    def test_units_derive_from_assigned_crs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "plot.las"
            source.write_bytes(b"LAS")
            store = SpatialReferenceAssignmentStore(root / "assignments.json")
            assignment = store.assign(source, scope=AssignmentScope.FILE, crs="EPSG:32605")
            self.assertEqual(LinearUnit.METERS, assignment.linear_units)
            self.assertTrue(SpatialReferenceResolver(store).spatial_profile(source).polygon_alignment_safe)


class UnitAwarePreparationTests(unittest.TestCase):
    def _classification(self, coverage=1.0):
        return ClassificationAssessment(True, 50_000, True, 0.0502, (), "HIGH", "storage-stratified bounded PDAL sample", class_counts=((1, 47490), (2, 2510)), observed_dimensions=("X", "Y", "Z", "Classification"), strata_sampled=5, strata_with_ground=round(coverage * 5), ground_coverage_ratio=coverage, ground_coverage_confidence="HIGH")

    def _plan(self, units, classification=None, crs=None):
        assessment = build_preparation_assessment(source="OlaaFR_RoadSite_Heli_Thin05_CropPC_Norm.las", spatial_reference_mode="resolved" if crs else "source_local", crs=crs, coordinate_units=assess_source_coordinate_units(crs, units), dimensions=("X", "Y", "Z", "Classification"), classification=classification or self._classification(), dtm_path=None, requested_products=("chm", "rumple"), point_count=104_819_538)
        return HeightNormalizationPlanner().plan(assessment)

    def test_plan_rebuilds_after_units_without_losing_ground_evidence(self):
        before = self._plan(None)
        after = self._plan(LinearUnit.METERS)
        self.assertEqual(PreparationReadiness.NEEDS_USER_INPUT, before.readiness)
        self.assertIn("Choose the coordinate units", before.blockers[0])
        self.assertEqual(PreparationReadiness.READY_AFTER_PREPARATION, after.readiness)
        self.assertEqual(HeightNormalizationPlanMode.DELAUNAY_FROM_EXISTING_GROUND, after.height_mode)

    def test_international_and_us_survey_feet_have_exact_distinct_conversion(self):
        international = assess_source_coordinate_units(None, LinearUnit.INTERNATIONAL_FEET)
        survey = assess_source_coordinate_units(None, LinearUnit.US_SURVEY_FEET)
        self.assertAlmostEqual(3.280839895013123, international.from_meters(1.0))
        self.assertAlmostEqual(3937.0 / 1200.0, survey.from_meters(1.0))
        self.assertNotEqual(international.units, survey.units)

    def test_poor_stratum_coverage_is_specific_scientific_blocker(self):
        plan = self._plan(LinearUnit.METERS, self._classification(0.2))
        self.assertEqual(PreparationReadiness.BLOCKED, plan.readiness)
        self.assertIn("GROUND_SPATIAL_COVERAGE_INSUFFICIENT", plan.blockers[0])

    def test_polygon_requires_crs_even_when_units_are_trusted(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "plot.las"
            source.touch()
            store = SpatialReferenceAssignmentStore(Path(folder) / "assignments.json")
            store.assign_units(source, LinearUnit.METERS)
            result = SpatialReferenceResolver(store).resolve(source, spatial_alignment_required=True, source_local_allowed=True, polygon_crs="EPSG:6635")
            self.assertEqual(SpatialReferenceStatus.AMBIGUOUS, result.status)
            self.assertIn("spatial alignment requires", result.warnings[0])


class BoundedGroundCoverageTests(unittest.TestCase):
    def test_inspection_reports_ground_distribution_across_strata(self):
        arrays = []
        for index in range(5):
            values = np.ones(10_000, dtype=[("Classification", "u1")])
            if index != 4:
                values["Classification"][:500] = 2
            arrays.append(values)
        class Pipeline:
            def __init__(self, array): self.arrays = (array,)
            def execute(self): return len(self.arrays[0])
        iterator = iter(arrays)
        assessment = ClassificationInspectionService(lambda _spec: Pipeline(next(iterator))).inspect("large.las", point_count=104_819_538)
        self.assertEqual(5, assessment.strata_sampled)
        self.assertEqual(4, assessment.strata_with_ground)
        self.assertEqual(0.8, assessment.ground_coverage_ratio)


class DatasetAssignmentTests(unittest.TestCase):
    def test_units_only_assignment_updates_report_without_fake_crs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "raw.las"
            source.write_bytes(b"LAS")
            store = SpatialReferenceAssignmentStore(root / "assignments.json")
            store.assign_units(source, LinearUnit.METERS)
            inspection = DatasetInspection(DatasetSource(source, DatasetFormat.LAS, False), 104_819_538, Bounds3D(0, 0, 0, 1, 1, 1), None, ("X", "Y", "Z", "Classification"), (ClassificationCount(2, 2510),), "6", None, (), "test")
            report = build_dataset_explorer_report(inspection, assignment_store=store)
            payload = report_to_dict(report)
            self.assertIsNone(report.crs)
            self.assertEqual(SourceCoordinateUnits.METERS.value, payload["preparation"]["source_coordinate_units"])
            self.assertEqual("SOURCE_LOCAL", payload["preparation"]["crs_assignment_status"])
            self.assertEqual("READY_AFTER_PREPARATION", report.preparation_readiness)


class UiContractTests(unittest.TestCase):
    def test_compact_intervention_and_tools_labels_exist(self):
        source = (Path(__file__).parents[1] / "pyforestscan_qgis" / "ui" / "pages.py").read_text(encoding="utf-8")
        for label in ("Spatial reference needed", "Use Project CRS", "Choose Coordinate System", "LiDAR units needed", "Coordinate system needed"):
            self.assertIn(label, source)
        self.assertIn("self.spatial_assignment_frame.setVisible(False)", source)
        settings = source[source.index("class SettingsPage"):source.index("def _processing_lifecycle_stage")]
        self.assertNotIn('add_section("LiDAR Spatial Reference', settings)
        self.assertNotIn("Save Trusted Units", settings)

    def test_preflight_surfaces_units_as_resolvable_setup(self):
        adapter = SimpleNamespace(inspect_dataset=lambda _path: object())
        request = SimpleNamespace(settings=SimpleNamespace(products=("chm", "rumple")))
        blockers, warnings = [], []
        report = SimpleNamespace(preparation_readiness="NEEDS_USER_INPUT")
        with patch("pyforestscan_qgis.core.batch_preflight.build_dataset_explorer_report", return_value=report):
            _check_preparation_spatial_readiness(request, (Path("large.las"),), adapter, blockers, warnings)
        self.assertEqual([], warnings)
        self.assertIn("SOURCE_UNITS_UNKNOWN", blockers[0])
        self.assertIn("Choose trusted coordinate units", blockers[0])


if __name__ == "__main__":
    unittest.main()
