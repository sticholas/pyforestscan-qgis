"""Source-bound linked annotation contracts without QGIS."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

try:
    import numpy as np
except ImportError:
    np = None

from pyforestscan_qgis.core.point_cloud.annotation import (
    annotation_summary, create_annotation, remove_annotation,
    replace_annotation, resolve_source_annotation,
    resolve_source_profile_annotation, validate_annotations)
from pyforestscan_qgis.core.point_cloud.measurement import MeasurementAnchor
from pyforestscan_qgis.core.point_cloud.session import PointCloudEditSession, SourceIdentity


class PointCloudAnnotationTests(unittest.TestCase):
    def annotation(self, **changes):
        values = dict(source_sha256="a"*64, source_crs="EPSG:6635",
            anchor=MeasurementAnchor((1,2,3),(1,2,3),0,5,2),
            title="Crown fork", note="Review from profile",
            resolution_seconds=.2, source_point_count=100,
            annotation_id="marker", created_at="2026-09-09T00:00:00+00:00")
        values.update(changes)
        return create_annotation(**values)

    def test_annotation_is_source_bound_validated_and_summarized(self):
        item = self.annotation()
        self.assertEqual(item.anchor.classification, 5)
        self.assertIn("Crown fork | X 1.000, Y 2.000, Z 3.000", annotation_summary(item))
        restored = validate_annotations([item.to_dict()], "a"*64)
        self.assertEqual(restored[0]["addressing"],
                         "FULL_RESOLUTION_ORIGINAL_SOURCE_POINT_RESOLUTION")
        with self.assertRaisesRegex(ValueError, "another source"):
            validate_annotations(restored, "b"*64)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_annotations(restored * 2, "a"*64)

    def test_annotation_text_is_bounded_and_control_characters_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "title is required"):
            self.annotation(title="  ")
        with self.assertRaisesRegex(ValueError, "exceeds 80"):
            self.annotation(title="x"*81)
        with self.assertRaisesRegex(ValueError, "note is invalid"):
            self.annotation(note="bad\x00note")

    def test_update_and_remove_preserve_anchor_and_source(self):
        original = self.annotation().to_dict()
        updated = replace_annotation([original], "a"*64, "marker",
            title="Main leader", note="Confirmed", updated_at="2026-09-10T00:00:00+00:00")
        self.assertEqual(updated[0]["title"], "Main leader")
        self.assertEqual(updated[0]["anchor"], original["anchor"])
        self.assertEqual(updated[0]["created_at"], original["created_at"])
        self.assertEqual(remove_annotation(updated, "a"*64, "marker"), [])
        with self.assertRaisesRegex(ValueError, "no longer exists"):
            remove_annotation(updated, "a"*64, "missing")

    @unittest.skipIf(np is None, "NumPy required")
    def test_resolution_scans_original_source_and_verifies_before_and_after(self):
        points = np.array([(1.,2.,3.,5,2.),(9.,9.,9.,2,0.)],
            dtype=[("X","f8"),("Y","f8"),("Z","f8"),
                   ("Classification","u1"),("HeightAboveGround","f8")])
        source = SimpleNamespace(sha256="a"*64, source_type="LAS", path="source.las",
                                 verify=Mock())
        class Pipeline:
            def __init__(self, _spec): pass
            def iterator(self, **_kwargs): return iter((points,))
        progress = []
        item = resolve_source_annotation(source, 2, (1,2,3), "EPSG:6635",
            "Exact point", pdal_module=SimpleNamespace(Pipeline=Pipeline),
            progress=progress.append)
        self.assertEqual(item.anchor.source_xyz, (1,2,3))
        self.assertEqual(item.anchor.height_above_ground, 2)
        self.assertEqual(progress, [2])
        self.assertEqual(source.verify.call_count, 2)

    def test_annotations_survive_session_roundtrip_without_becoming_edits(self):
        with TemporaryDirectory() as folder:
            path = Path(folder)/"source.las"
            path.write_bytes(b"immutable")
            source = SourceIdentity.capture(path)
            session = PointCloudEditSession(source, "SOURCE_LOCAL:"+source.sha256)
            item = create_annotation(source.sha256, session.source_crs,
                MeasurementAnchor((1,2,3),(1,2,3),0), "Saved marker",
                source_point_count=1, annotation_id="saved",
                created_at="2026-09-09T00:00:00+00:00")
            session.visibility["annotations"] = validate_annotations(
                [item.to_dict()], source.sha256)
            loaded = PointCloudEditSession.load(session.save(Path(folder)/"session.json"))
            restored = validate_annotations(loaded.visibility["annotations"], source.sha256)
            self.assertEqual(restored[0]["annotation_id"], "saved")
            self.assertEqual(loaded.operations, ())
            source.verify()

    @unittest.skipIf(np is None, "NumPy required")
    def test_profile_annotation_resolves_flattened_pick_to_original_source(self):
        points = np.array([(5., 0., 3., 5, 2.), (10., 5., 7., 2, 0.)],
            dtype=[("X", "f8"), ("Y", "f8"), ("Z", "f8"),
                   ("Classification", "u1"), ("HeightAboveGround", "f8")])
        identity = "a" * 64
        source = SimpleNamespace(sha256=identity, source_type="LAS", path="source.las",
                                 verify=Mock())
        class Pipeline:
            def __init__(self, _spec): pass
            def iterator(self, **_kwargs): return iter((points,))
        profile = dict(a=(0, 0), b=(10, 10), thickness=2,
            crs="SOURCE_LOCAL:" + identity, path=((0, 0), (10, 0), (10, 10)),
            display_projection="PROFILE_DISTANCE")
        item = resolve_source_profile_annotation(source, 2, (15, 0, 7),
            "SOURCE_LOCAL:" + identity, profile, "Profile marker",
            pdal_module=SimpleNamespace(Pipeline=Pipeline))
        self.assertEqual(item.anchor.requested_xyz, (10, 5, 7))
        self.assertEqual(item.anchor.source_xyz, (10, 5, 7))
        self.assertEqual(item.anchor.classification, 2)
        self.assertEqual(source.verify.call_count, 2)

    def test_worker_owns_resolution_and_session_persistence(self):
        worker = (Path(__file__).parents[1]/"pyforestscan_qgis"/"viewer"/
                  "editor_worker.py").read_text(encoding="utf-8")
        self.assertIn('elif action == "add_annotation":', worker)
        self.assertIn("resolve_source_profile_annotation", worker)
        self.assertIn("else resolve_source_annotation", worker)
        self.assertIn('if command.get("profile_geometry")', worker)
        self.assertIn('session.visibility["annotations"]', worker)
        self.assertIn('elif action == "update_annotation":', worker)
        self.assertIn('elif action == "remove_annotation":', worker)


if __name__ == "__main__":
    unittest.main()
