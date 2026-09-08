"""Tier 0/1: source-safe editor contracts; no QGIS/scientific dependencies."""
import json
import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.point_cloud.session import (
    PointCloudEditSession, SourceIdentity, SpatialSelection,
)
from pyforestscan_qgis.core.point_cloud.capabilities import QgisNativePointCloudCapabilities


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cloud = self.root / "source.las"
        self.cloud.write_bytes(b"immutable LAS fixture, identity only")
        self.source = SourceIdentity.capture(self.cloud)
        self.session = PointCloudEditSession(self.source, "EPSG:32605", ("X", "Y", "Z", "Classification"))
        self.selection = SpatialSelection("selection", self.source.sha256,
                                          (0, 0, 0, 10, 10, 20), "EPSG:32605")

    def test_round_trip_undo_redo_and_source_immutable(self):
        self.session.stage(self.selection, 2)
        self.session.stage(self.selection, 7, noise=True)
        self.session.undo()
        path = self.session.save(self.root / "session.json")
        loaded = PointCloudEditSession.load(path)
        self.assertEqual(len(loaded.operations), 1)
        self.assertTrue(loaded.can_redo)
        loaded.redo()
        self.assertEqual(loaded.operations[-1].classification, 7)
        self.source.verify()

    def test_new_edit_discards_redo(self):
        self.session.stage(self.selection, 2)
        self.session.undo()
        self.session.stage(self.selection, 5)
        self.assertFalse(self.session.can_redo)
        self.assertEqual(len(self.session.operations), 1)

    def test_source_change_rejects_reopen(self):
        path = self.session.save(self.root / "session.json")
        self.cloud.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "fingerprint changed"):
            PointCloudEditSession.load(path)

    def test_session_cannot_overwrite_source(self):
        with self.assertRaises(ValueError):
            self.session.save(self.cloud)
        self.source.verify()

    def test_rendered_indices_rejected(self):
        with self.assertRaisesRegex(ValueError, "sample indices"):
            SpatialSelection("s", self.source.sha256, (0, 0, 0, 1, 1, 1),
                             "EPSG:32605", addressing="LOD_SAMPLE")

    def test_wrong_source_rejected(self):
        foreign = SpatialSelection("s", "f" * 64, (0, 0, 0, 1, 1, 1), "EPSG:32605")
        with self.assertRaises(ValueError):
            self.session.stage(foreign, 2)

    def test_invalid_bounds_and_class(self):
        for bounds in ((0, 0, 0, -1, 2, 3), (0, 0, 0, float("nan"), 2, 3)):
            with self.assertRaises(ValueError):
                SpatialSelection("s", self.source.sha256, bounds, "EPSG:32605")
        for value in (-1, 256, True, 2.5):
            with self.assertRaises(ValueError):
                self.session.stage(self.selection, value)

    def test_tampered_cursor_rejected(self):
        path = self.session.save(self.root / "session.json")
        data = json.loads(path.read_text())
        data["_cursor"] = 4
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "cursor"):
            PointCloudEditSession.load(path)

    def test_cancel_hash(self):
        with self.assertRaises(InterruptedError):
            SourceIdentity.capture(self.cloud, cancelled=lambda: True)

    def test_ept_manifest_is_not_whole_source_identity(self):
        path = self.root / "ept.json"
        path.write_text("{}")
        with self.assertRaisesRegex(ValueError, "local LAS"):
            SourceIdentity.capture(path)

    def test_empty_undo_redo(self):
        self.assertFalse(self.session.undo())
        self.assertFalse(self.session.redo())

    def test_capability_probe_without_qgis(self):
        capabilities = QgisNativePointCloudCapabilities.probe()
        self.assertFalse(capabilities.native_edit_capable)
        self.assertFalse(capabilities.source_commit_allowed)

    def test_partial_bindings_do_not_claim_native_edit(self):
        class Partial:
            def startEditing(self): pass
            def rollBack(self): pass
        capabilities = QgisNativePointCloudCapabilities.probe(Partial)
        self.assertTrue(capabilities.native_edit_buffer)
        self.assertFalse(capabilities.attribute_edit)
        self.assertFalse(capabilities.native_edit_capable)


if __name__ == "__main__":
    unittest.main()
