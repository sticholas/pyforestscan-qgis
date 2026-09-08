import hashlib
from pathlib import Path
import tempfile
import unittest
from pyforestscan_qgis.core.point_cloud.view_session import (
    ViewerSourceChanged, load_view_session, save_view_session, session_view_state, validate_view_state, view_state_matches,
)
from pyforestscan_qgis.core.point_cloud.session import SpatialSelection


class ViewerSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "cloud.laz"
        self.source.write_bytes(b"immutable source fixture")
        self.state = {"camera": {"position": [1., 2., 3.], "yaw": .5, "pitch": -.25, "radius": 12.},
                      "mode": "Elevation", "classes": [2, 5, 231], "height_filter": [2., 9.]}

    def test_round_trip_uses_existing_session_and_preserves_source(self):
        before = hashlib.sha256(self.source.read_bytes()).hexdigest()
        path = self.root / "session.json"
        saved = save_view_session(path, self.source, self.state, source_crs="SOURCE_LOCAL",
                                  cache_identity={"source_sha256": before})
        loaded = load_view_session(path)
        self.assertEqual(loaded.session_id, saved.session_id)
        self.assertEqual(session_view_state(loaded), self.state)
        self.assertEqual(loaded.visibility["quality"], "AUTOMATIC")
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), before)

    def test_existing_journal_survives_view_save(self):
        path = self.root / "session.json"
        session = save_view_session(path, self.source, self.state, source_crs="SOURCE_LOCAL")
        selection = SpatialSelection("s", session.source.sha256, (0, 0, 0, 3, 3, 3), "SOURCE_LOCAL")
        session.stage(selection, 5)
        session.undo()
        saved = save_view_session(path, self.source, self.state, existing=session)
        self.assertTrue(saved.can_redo)
        self.assertTrue(load_view_session(path).can_redo)

    def test_changed_source_cannot_restore_or_save_old_session(self):
        path = self.root / "session.json"
        session = save_view_session(path, self.source, self.state)
        self.source.write_bytes(b"changed source")
        with self.assertRaisesRegex(ViewerSourceChanged, "source has changed"):
            load_view_session(path)
        with self.assertRaises(ViewerSourceChanged):
            save_view_session(self.root / "new.json", self.source, self.state, existing=session)
        self.assertFalse((self.root / "new.json").exists())

    def test_invalid_view_state_rejected(self):
        for state in ({**self.state, "classes": [256]}, {**self.state, "height_filter": [9, 2]},
                      {**self.state, "camera": {**self.state["camera"], "radius": float("nan")}}):
            with self.assertRaises(ValueError):
                validate_view_state(state)

    def test_cancellation_never_publishes_session(self):
        path = self.root / "session.json"
        with self.assertRaises(InterruptedError):
            save_view_session(path, self.source, self.state, cancelled=lambda: True)
        self.assertFalse(path.exists())

    def test_restore_requires_renderer_acknowledgement(self):
        self.assertTrue(view_state_matches(self.state, self.state))
        self.assertFalse(view_state_matches({**self.state, "mode": "Classification"}, self.state))
        self.assertFalse(view_state_matches({**self.state, "classes": None}, self.state))
        self.assertFalse(view_state_matches({}, self.state))
        moved = {**self.state, "camera": {**self.state["camera"], "position": [2, 2, 3]}}
        self.assertFalse(view_state_matches(moved, self.state))


if __name__ == "__main__":
    unittest.main()
