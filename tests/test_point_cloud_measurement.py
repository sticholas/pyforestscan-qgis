"""Authoritative point-to-point measurement contracts without QGIS."""
from pathlib import Path
from tempfile import TemporaryDirectory
import math
import unittest

try:
    import numpy as np
except ImportError:
    np = None

from pyforestscan_qgis.core.point_cloud.measurement import (
    AreaMeasurement, MeasurementAnchor, create_area_measurement,
    create_point_measurement, create_profile_measurement, measurement_summary,
    measurement_unit_context, resolve_anchor_chunks, resolve_profile_anchor_chunks,
    source_pick_tolerance,
    validate_measurements)
from pyforestscan_qgis.core.point_cloud.session import PointCloudEditSession, SourceIdentity
from pyforestscan_qgis.core.point_cloud.workspace import SliceGeometry


class FakeProjectedCrs:
    is_geographic = False
    axis_info = tuple(type("Axis", (), {"unit_name":"metre"})() for _ in range(2))

    @classmethod
    def from_user_input(cls, _value):
        return cls()


class FakeGeographicCrs(FakeProjectedCrs):
    is_geographic = True


class ValidPolygon:
    is_valid = True
    is_empty = False
    area = 1

    def __init__(self, _vertices):
        pass


class InvalidPolygon(ValidPolygon):
    is_valid = False


class PointMeasurementTests(unittest.TestCase):
    def test_distances_use_two_resolved_source_anchors(self):
        anchors = (MeasurementAnchor((0,0,0), (0,0,0), 0, 2, 0),
                   MeasurementAnchor((3,4,12), (3,4,12), 0, 5, 12))
        item = create_point_measurement("a"*64, "EPSG:32605", anchors,
            horizontal_unit="metre", resolution_seconds=.2, source_point_count=100,
            measurement_id="measurement", created_at="fixed")
        self.assertEqual(item.horizontal_distance, 5)
        self.assertEqual(item.vertical_distance, 12)
        self.assertEqual(item.elevation_difference, 12)
        self.assertEqual(item.distance_3d, 13)
        self.assertIn("3D 13.000 metre", measurement_summary(item))

    @unittest.skipIf(np is None, "NumPy required")
    def test_anchor_resolution_scans_original_chunks_once_and_snaps_exactly(self):
        points = np.array([(0.,0.,0.,2,0.),(3.,4.,12.,5,12.),(20.,20.,20.,1,20.)],
            dtype=[("X","f8"),("Y","f8"),("Z","f8"),
                   ("Classification","u1"),("HeightAboveGround","f8")])
        progress = []
        anchors, duration = resolve_anchor_chunks((points[:1], points[1:]), 3,
            ((.0000001,0,0),(3,4,12)), progress=progress.append)
        self.assertEqual(progress, [1,3])
        self.assertEqual(anchors[0].source_xyz, (0,0,0))
        self.assertEqual(anchors[1].classification, 5)
        self.assertEqual(anchors[1].height_above_ground, 12)
        self.assertGreaterEqual(duration, 0)

    @unittest.skipIf(np is None, "NumPy required")
    def test_unmatched_pick_count_mismatch_and_cancel_fail_closed(self):
        points = np.array([(0.,0.,0.)], dtype=[("X","f8"),("Y","f8"),("Z","f8")])
        with self.assertRaisesRegex(ValueError, "could not be matched"):
            resolve_anchor_chunks((points,), 1, ((10,10,10),))
        with self.assertRaisesRegex(ValueError, "count differs"):
            resolve_anchor_chunks((points,), 2, ((0,0,0),))
        with self.assertRaises(InterruptedError):
            resolve_anchor_chunks((points,), 1, ((0,0,0),), cancelled=lambda: True)

    @unittest.skipIf(np is None, "NumPy required")
    def test_nonfinite_source_coordinates_are_not_measurement_anchors(self):
        points = np.array([(float("nan"), 0., 0.), (1., 2., 3.)],
                          dtype=[("X","f8"),("Y","f8"),("Z","f8")])
        anchors, _ = resolve_anchor_chunks((points,), 2, ((1.,2.,3.),))
        self.assertEqual(anchors[0].source_xyz, (1.,2.,3.))

    def test_units_are_explicit_and_geographic_mixing_is_rejected(self):
        self.assertEqual(measurement_unit_context("EPSG:32605", FakeProjectedCrs),
                         ("metre","metre",""))
        local = measurement_unit_context("SOURCE_LOCAL:"+"a"*64, FakeProjectedCrs)
        self.assertEqual(local[0], "source units")
        self.assertIn("unknown", local[2])
        with self.assertRaisesRegex(ValueError, "geographic"):
            measurement_unit_context("EPSG:4326", FakeGeographicCrs)
        self.assertLessEqual(source_pick_tolerance((1e9,1e9,1e9)), 1)

    def test_planar_area_uses_stable_source_coordinate_math_and_explicit_units(self):
        vertices = ((1_000_000.,2_000_000.),(1_000_003.,2_000_000.),
                    (1_000_003.,2_000_004.),(1_000_000.,2_000_004.),
                    (1_000_000.,2_000_000.))
        item = create_area_measurement("a"*64, "EPSG:32605", vertices,
            horizontal_unit="metre", display_elevation=900,
            measurement_id="area", created_at="fixed", polygon_type=ValidPolygon)
        self.assertIsInstance(item, AreaMeasurement)
        self.assertEqual(item.area, 12)
        self.assertEqual(item.perimeter, 14)
        self.assertEqual(item.area_unit, "square metre")
        self.assertIn("Area 12.000 square metre", measurement_summary(item))
        restored = validate_measurements([item.to_dict()], "a"*64)
        self.assertEqual(restored[0]["kind"], "PLANAR_AREA")

    def test_invalid_or_tampered_area_fails_closed(self):
        vertices = ((0.,0.),(2.,0.),(0.,2.),(0.,0.))
        with self.assertRaisesRegex(ValueError, "empty or invalid"):
            create_area_measurement("a"*64, "EPSG:32605", vertices,
                horizontal_unit="metre", display_elevation=0,
                polygon_type=InvalidPolygon)
        item = create_area_measurement("a"*64, "EPSG:32605", vertices,
            horizontal_unit="metre", display_elevation=0,
            polygon_type=ValidPolygon).to_dict()
        item["area"] = 999
        with self.assertRaisesRegex(ValueError, "do not match"):
            validate_measurements([item], "a"*64)

    @unittest.skipIf(np is None, "NumPy required")
    def test_hag_profile_resolves_original_xyz_and_cross_section_metrics(self):
        points = np.array([(0.,0.,100.,2,0.),(5.,1.,120.,5,8.),(9.,-1.,140.,5,20.)],
            dtype=[("X","f8"),("Y","f8"),("Z","f8"),
                   ("Classification","u1"),("HeightAboveGround","f8")])
        profile = SliceGeometry((0,0),(10,0),4,"EPSG:32605","HeightAboveGround")
        progress = []
        anchors, duration = resolve_profile_anchor_chunks((points[:1],points[1:]),3,
            ((5,1,8),(9,-1,20)),profile,progress=progress.append)
        self.assertEqual(progress,[1,3])
        self.assertEqual(anchors[0].source_xyz,(5,1,120))
        self.assertEqual(anchors[0].display_xyz,(5,1,8))
        self.assertEqual(anchors[0].profile_position,(5,8))
        self.assertEqual(anchors[0].cross_track,1)
        item = create_profile_measurement("a"*64,"EPSG:32605","slice","Slice 1",
            profile,anchors,horizontal_unit="metre",resolution_seconds=duration,
            source_point_count=3,measurement_id="profile",created_at="fixed")
        self.assertEqual(item.along_distance,4)
        self.assertEqual(item.vertical_distance,12)
        self.assertEqual(item.vertical_difference,12)
        self.assertTrue(math.isclose(item.cross_section_distance,math.hypot(4,12)))
        self.assertIn("HAG change +12.000 metre",measurement_summary(item))
        restored = validate_measurements([item.to_dict()],"a"*64)
        self.assertEqual(restored[0]["kind"],"PROFILE_DISTANCE")

    @unittest.skipIf(np is None, "NumPy required")
    def test_profile_missing_axis_and_outside_corridor_fail_closed(self):
        ordinary = np.array([(5.,5.,10.,2)],dtype=[("X","f8"),("Y","f8"),
            ("Z","f8"),("Classification","u1")])
        hag = SliceGeometry((0,0),(10,0),2,"EPSG:32605","HeightAboveGround")
        with self.assertRaisesRegex(ValueError,"HeightAboveGround"):
            resolve_profile_anchor_chunks((ordinary,),1,((5,0,2),(6,0,3)),hag)
        elevation = SliceGeometry((0,0),(10,0),2,"EPSG:32605")
        with self.assertRaisesRegex(ValueError,"could not be matched"):
            resolve_profile_anchor_chunks((ordinary,),1,((5,5,10),(5,5,10)),elevation)

    def test_saved_measurements_are_source_bound_and_duplicate_guarded(self):
        anchors = (MeasurementAnchor((0,0,0),(0,0,0),0),
                   MeasurementAnchor((1,0,0),(1,0,0),0))
        item = create_point_measurement("a"*64, "EPSG:32605", anchors,
            horizontal_unit="metre", source_point_count=2,
            measurement_id="one", created_at="fixed").to_dict()
        self.assertEqual(validate_measurements([item], "a"*64)[0]["measurement_id"], "one")
        with self.assertRaisesRegex(ValueError, "another source"):
            validate_measurements([item], "b"*64)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_measurements([item,item], "a"*64)

    def test_measurements_survive_session_roundtrip_without_becoming_edits(self):
        with TemporaryDirectory() as folder:
            source_path = Path(folder)/"source.las"
            source_path.write_bytes(b"immutable source")
            source = SourceIdentity.capture(source_path)
            session = PointCloudEditSession(source, "SOURCE_LOCAL:"+source.sha256)
            anchors = (MeasurementAnchor((0,0,0),(0,0,0),0),
                       MeasurementAnchor((1,2,3),(1,2,3),0))
            item = create_point_measurement(source.sha256, session.source_crs, anchors,
                horizontal_unit="source units", source_point_count=2,
                measurement_id="saved", created_at="fixed").to_dict()
            session.visibility["measurements"] = validate_measurements([item], source.sha256)
            loaded = PointCloudEditSession.load(session.save(Path(folder)/"session.json"))
            restored = validate_measurements(loaded.visibility["measurements"], source.sha256)
            self.assertEqual(restored[0]["measurement_id"], "saved")
            self.assertEqual(restored[0]["end"]["source_xyz"], (1.,2.,3.))
            self.assertEqual(loaded.operations, ())
            source.verify()

    def test_worker_owns_resolution_and_session_persistence(self):
        worker = (Path(__file__).parents[1]/"pyforestscan_qgis"/"viewer"/
                  "editor_worker.py").read_text(encoding="utf-8")
        self.assertIn('elif action == "add_measurement":', worker)
        self.assertIn("resolve_source_measurement(session.source, point_count", worker)
        self.assertIn('session.visibility["measurements"]', worker)
        self.assertIn('elif action == "clear_measurements":', worker)
        self.assertIn('elif action == "add_area_measurement":', worker)
        self.assertIn("create_area_measurement(session.source.sha256", worker)
        self.assertIn('elif action == "add_profile_measurement":', worker)
        self.assertIn("resolve_source_profile_measurement(session.source", worker)
