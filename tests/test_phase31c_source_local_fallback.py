"""Phase 31C controlled source-local fallback policy regressions."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.classification_inspection import ClassificationAssessment
from pyforestscan_qgis.core.dataset_report import build_dataset_explorer_report, report_to_dict
from pyforestscan_qgis.core.batch_preflight import _check_preparation_spatial_readiness
from pyforestscan_qgis.core.lidar_preparation import HeightNormalizationPlanMode, HeightNormalizationPlanner, PreparationReadiness, build_preparation_assessment
from pyforestscan_qgis.core.pipeline_context import PipelineContext
from pyforestscan_qgis.core.processing_spatial_context import (
    SourceLocalFallbackChoice,
    SourceLocalFallbackPolicy,
    SourceLocalFallbackPolicyStore,
    SpatialUnitBasis,
    resolve_processing_spatial_context,
)
from pyforestscan_qgis.core.source_coordinate_units import assess_processing_coordinate_units
from pyforestscan_qgis.core.spatial_assignment import LinearUnit
from pyforestscan_qgis.core.types import Bounds3D, ClassificationCount, DatasetFormat, DatasetInspection, DatasetSource


def _context(**overrides):
    values = dict(crs=None, explicit_units=None, requested_products=("chm",), source_local_allowed=True)
    values.update(overrides)
    return resolve_processing_spatial_context(**values)


def _classification(ground=True, coverage=1.0):
    return ClassificationAssessment(True, 50_000, ground, 0.0502 if ground else 0.0, (), "HIGH", "bounded strata", class_counts=((1, 47490), (2, 2510)) if ground else ((1, 50000),), observed_dimensions=("X", "Y", "Z", "Classification"), strata_sampled=5, strata_with_ground=round(coverage * 5), ground_coverage_ratio=coverage, ground_coverage_confidence="HIGH")


def _plan(unit_context, *, ground=True, product="chm"):
    units = assess_processing_coordinate_units(unit_context.crs, unit_context.linear_units, unit_context.unit_basis)
    assessment = build_preparation_assessment(source="large.las", spatial_reference_mode=unit_context.processing_coordinate_mode, crs=unit_context.crs, coordinate_units=units, dimensions=("X", "Y", "Z", "Classification"), classification=_classification(ground), dtm_path=None, requested_products=(product,), point_count=104_819_538)
    return HeightNormalizationPlanner().plan(assessment)


class SourceLocalPolicyTests(unittest.TestCase):
    def test_default_is_assumed_meters_not_authoritative(self):
        value = _context(requested_products=("chm", "rumple"))
        self.assertEqual(LinearUnit.METERS, value.linear_units)
        self.assertEqual(SpatialUnitBasis.ASSUMED_SOURCE_LOCAL, value.unit_basis)
        self.assertEqual("ASSUMED", value.confidence)
        self.assertFalse(value.source_units_authoritative)
        self.assertFalse(value.georeferenced)
        self.assertTrue(value.distance_operations_safe)

    def test_explicit_units_and_known_crs_override_fallback(self):
        meters = _context(explicit_units=LinearUnit.METERS)
        feet = _context(explicit_units=LinearUnit.INTERNATIONAL_FEET)
        known = _context(crs="EPSG:32605")
        self.assertEqual(SpatialUnitBasis.USER_ASSIGNED, meters.unit_basis)
        self.assertEqual(LinearUnit.INTERNATIONAL_FEET, feet.linear_units)
        self.assertEqual(SpatialUnitBasis.CRS_DERIVED, known.unit_basis)
        self.assertTrue(known.georeferenced)
        self.assertTrue(known.source_units_authoritative)

    def test_require_explicit_policy_blocks_unknown_units(self):
        value = _context(policy=SourceLocalFallbackPolicy(SourceLocalFallbackChoice.REQUIRE_EXPLICIT_ASSIGNMENT))
        self.assertFalse(value.distance_operations_safe)
        self.assertEqual(SpatialUnitBasis.UNRESOLVED, value.unit_basis)

    def test_policy_store_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            store = SourceLocalFallbackPolicyStore(Path(folder) / "policy.json")
            self.assertEqual(SourceLocalFallbackChoice.METERS, store.read().default_units)
            store.write(SourceLocalFallbackPolicy(SourceLocalFallbackChoice.US_SURVEY_FEET))
            self.assertEqual(SourceLocalFallbackChoice.US_SURVEY_FEET, store.read().default_units)

    def test_polygon_cross_source_and_conflicts_remain_blocked(self):
        polygon = _context(polygon_alignment_required=True)
        cross_source = _context(cross_source_alignment_required=True)
        conflict = _context(contradictory_evidence=True)
        self.assertIn("coordinate system", polygon.blockers[0])
        self.assertFalse(cross_source.distance_operations_safe)
        self.assertIn("Conflicting", conflict.blockers[0])

    def test_noneligible_product_does_not_receive_fallback(self):
        self.assertFalse(_context(requested_products=("pad",)).distance_operations_safe)


class PreparationPolicyTests(unittest.TestCase):
    def test_assumed_meters_class2_selects_delaunay_for_chm_and_rumple(self):
        context = _context(requested_products=("chm", "rumple"))
        for product in ("chm", "rumple"):
            plan = _plan(context, product=product)
            self.assertEqual(PreparationReadiness.READY_AFTER_PREPARATION, plan.readiness)
            self.assertEqual(HeightNormalizationPlanMode.DELAUNAY_FROM_EXISTING_GROUND, plan.height_mode)

    def test_assumed_units_allow_smrf_when_ground_is_not_observed(self):
        plan = _plan(_context(), ground=False)
        self.assertEqual(HeightNormalizationPlanMode.AUTO_CLASSIFY_GROUND_THEN_DELAUNAY, plan.height_mode)

    def test_assumed_and_trusted_cache_identities_differ(self):
        assumed = _plan(_context())
        trusted = _plan(_context(explicit_units=LinearUnit.METERS))
        feet = _plan(_context(explicit_units=LinearUnit.INTERNATIONAL_FEET))
        self.assertNotEqual(assumed.signature, trusted.signature)
        self.assertNotEqual(assumed.signature, feet.signature)

    def test_same_assumption_reuses_product_independent_preparation_identity(self):
        context = _context(requested_products=("chm", "rumple"))
        self.assertEqual(_plan(context, product="chm").signature, _plan(context, product="rumple").signature)


class PrerunExecutionConsistencyTests(unittest.TestCase):
    def _inspection(self, *, hag=False, crs=None):
        dimensions = ("X", "Y", "Z", "Classification") + (("HeightAboveGround",) if hag else ())
        return DatasetInspection(DatasetSource("large.las", DatasetFormat.LAS, crs), 104_819_538, Bounds3D(0, 0, 0, 10, 10, 30), crs, dimensions, (ClassificationCount(2, 2510),), "6", None, (), "test")

    def test_prerun_is_ready_with_warning_and_context_is_frozen(self):
        payload = report_to_dict(build_dataset_explorer_report(self._inspection(), requested_products=("chm", "rumple")))
        self.assertEqual("READY_AFTER_PREPARATION", payload["preparation"]["readiness"])
        self.assertEqual("ASSUMED_SOURCE_LOCAL", payload["preparation"]["source_units_basis"])
        self.assertIn("SOURCE_UNITS_ASSUMED", {item["code"] for item in payload["warnings"]})
        context = PipelineContext("chm", "CHM", Path("plan.json"), Path("out"), {}, {}, payload)
        self.assertEqual(payload["preparation"]["source_coordinate_units"], context.source_coordinate_units)
        self.assertEqual(payload["preparation"]["source_units_basis"], context.source_units_basis)
        self.assertEqual(payload["preparation"]["source_units_authoritative"], context.source_units_authoritative)

    def test_frozen_prerun_context_ignores_later_policy_change(self):
        inspection = self._inspection()
        adapter = type("Adapter", (), {"inspect_dataset": lambda _self, _path: inspection})()
        request = type("Request", (), {"settings": type("Settings", (), {"products": ("chm", "rumple")})()})()
        blockers, warnings = [], []
        contexts = _check_preparation_spatial_readiness(request, (Path("large.las"),), adapter, blockers, warnings)
        self.assertFalse(blockers)
        frozen = dict(contexts)["large.las"]
        rebuilt = report_to_dict(build_dataset_explorer_report(inspection, requested_products=("chm",), fallback_policy=SourceLocalFallbackPolicy(SourceLocalFallbackChoice.INTERNATIONAL_FEET), frozen_spatial_context=frozen))
        self.assertEqual("METERS", rebuilt["preparation"]["source_coordinate_units"])
        self.assertEqual("ASSUMED_SOURCE_LOCAL", rebuilt["preparation"]["source_units_basis"])

    def test_existing_hag_unknown_crs_remains_source_local_ready(self):
        payload = report_to_dict(build_dataset_explorer_report(self._inspection(hag=True), requested_products=("chm", "rumple")))
        self.assertEqual("READY", payload["preparation"]["readiness"])
        self.assertEqual("SOURCE_LOCAL", payload["preparation"]["crs_assignment_status"])

    def test_known_crs_is_never_downgraded(self):
        payload = report_to_dict(build_dataset_explorer_report(self._inspection(crs="EPSG:32605"), requested_products=("chm",)))
        self.assertEqual("EMBEDDED", payload["preparation"]["source_units_basis"])
        self.assertTrue(payload["preparation"]["source_units_authoritative"])


if __name__ == "__main__":
    unittest.main()
