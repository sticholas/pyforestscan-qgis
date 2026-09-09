"""Preparation intent cannot overwrite input or ignore the active edit journal."""
from pathlib import Path
import tempfile
import unittest

from pyforestscan_qgis.core.point_cloud.preparation import PreparationOptions, PreparationRequest
from pyforestscan_qgis.core.point_cloud.session import PointCloudEditSession, SourceIdentity, SpatialSelection


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source.las"
        self.source.write_bytes(b"immutable fixture")
        self.identity = SourceIdentity.capture(self.source)
        self.options = PreparationOptions(thinning="voxel_first", spacing=.5)

    def request(self, name="derived.laz", options=None):
        return PreparationRequest(self.identity, str(self.root / name), options or self.options)

    def test_request_roundtrip_does_not_create_files(self):
        before = list(self.root.iterdir())
        request = self.request()
        restored = PreparationRequest.from_dict(request.to_dict())
        self.assertEqual(request, restored)
        self.assertEqual(request.signature, restored.signature)
        self.assertEqual(before, list(self.root.iterdir()))
        self.assertEqual(request.provenance_path.name, "derived.laz.preparation.json")

    def test_distinct_operations_have_distinct_signatures(self):
        self.assertNotEqual(self.request().signature,
            self.request(options=PreparationOptions(height_action="normalize_z")).signature)

    def test_noop_invalid_methods_and_nonfinite_spacing_fail(self):
        for values in ({}, {"thinning": "voxel_center", "spacing": 1},
                       {"thinning": "poisson", "spacing": True},
                       *({"thinning": "poisson", "spacing": v} for v in (0, -1, float("nan"), float("inf")))):
            with self.subTest(values=values), self.assertRaises(ValueError):
                PreparationOptions(**values)

    def test_existing_outputs_and_source_are_protected(self):
        for name in ("source.las", "derived.laz", "derived.laz.preparation.json"):
            if name != "source.las":
                (self.root / name).write_bytes(b"existing")
            with self.assertRaises(ValueError):
                self.request("source.las" if name == "source.las" else "derived.laz")
            if name != "source.las":
                self.assertEqual((self.root / name).read_bytes(), b"existing")
                (self.root / name).unlink()

    def test_rejects_dangling_symlink_destination(self):
        try:
            (self.root / "derived.laz").symlink_to(self.root / "absent.laz")
        except OSError:
            self.skipTest("Symlink creation unavailable")
        with self.assertRaises(ValueError):
            self.request()

    def test_worker_rechecks_source_and_destination(self):
        request = self.request()
        request.verify_input()
        self.source.write_bytes(b"modified source")
        with self.assertRaises(ValueError):
            request.verify_input()
        (self.root / "derived.laz").write_bytes(b"another job")
        with self.assertRaises(ValueError):
            request.validate_destination()

    def test_verification_cancellation_writes_nothing(self):
        request = self.request()
        with self.assertRaises(InterruptedError):
            request.verify_input(cancelled=lambda: True)
        self.assertEqual(list(self.root.iterdir()), [self.source])

    def test_rejects_metadata_identity_and_relative_output(self):
        with self.assertRaises(ValueError):
            PreparationRequest({"source_type": "EPT"}, str(self.root / "derived.laz"), self.options)
        with self.assertRaises(ValueError):
            PreparationRequest(self.identity, "relative.laz", self.options)

    def test_staged_edits_require_validated_export_as_new_source(self):
        session = PointCloudEditSession(self.identity, "SOURCE_LOCAL:test")
        selection = SpatialSelection("selection", self.identity.sha256,
                                     (0, 0, 0, 1, 1, 1), session.source_crs)
        session.stage(selection, 5)
        with self.assertRaisesRegex(ValueError, "Export staged edits"):
            PreparationRequest.from_session(session, self.root / "derived.laz", self.options)
        session.undo()
        request = PreparationRequest.from_session(session, self.root / "derived.laz", self.options)
        self.assertEqual(request.source, self.identity)
        self.assertTrue(session.can_redo)

    def test_height_actions_are_explicit(self):
        self.assertNotEqual(PreparationOptions(height_action="add_hag"),
                            PreparationOptions(height_action="normalize_z"))
        with self.assertRaises(ValueError):
            PreparationOptions(thinning="poisson", spacing=1, allow_ground_classification=True)

    def test_unqualified_outputs_and_unknown_schema_rejected(self):
        for name in ("derived.copc.laz", "derived.csv", "missing/derived.laz"):
            with self.assertRaises(ValueError):
                self.request(name)
        payload = self.request().to_dict()
        payload["schema_version"] = True
        with self.assertRaises(ValueError):
            PreparationRequest.from_dict(payload)
