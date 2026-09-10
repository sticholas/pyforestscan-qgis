"""Authoritative point-to-point measurement contracts without QGIS."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

try:
    import numpy as np
except ImportError:
    np = None

from pyforestscan_qgis.core.point_cloud.measurement import (
    MeasurementAnchor, create_point_measurement, measurement_summary,
    measurement_unit_context, resolve_anchor_chunks, source_pick_tolerance,
    validate_measurements)
from pyforestscan_qgis.core.point_cloud.session import PointCloudEditSession, SourceIdentity


class FakeProjectedCrs:
    is_geographic = False
    axis_info = tuple(type("Axis", (), {"unit_name":"metre"})() for _ in range(2))

    @classmethod
    def from_user_input(cls, _value):
        return cls()


class FakeGeographicCrs(FakeProjectedCrs):
    is_geographic = True


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
