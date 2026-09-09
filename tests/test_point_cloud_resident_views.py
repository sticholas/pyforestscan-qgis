"""QGIS-free lifecycle tests for warm view ownership, not rendering substitutes."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from pyforestscan_qgis.ui.point_cloud_resident_views import ResidentViews


class Signal:
    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)

    def disconnect(self, slot):
        self.slots.remove(slot)


class Worker:
    def __init__(self):
        self.update, self.finished = Signal(), Signal()
        self.send, self.stop = Mock(), Mock()


class ResidentViewTests(unittest.TestCase):
    def setUp(self):
        self.page = Mock()
        self.page.workspace.views = {"overview": object(), "area": object(), "slice": object()}
        self.page.linked.rendered_id = "overview"
        self.page._view_state = {"ready": True, "editor": {"event": {"id": 12}}}
        self.page._source_info = {"source": "original"}
        self.page._render_only = True
        self.page._filter_bounds_initialized = True
        self.page._restore_after_open = None
        self.page._restore_expected = None
        self.worker = Worker()
        self.worker.update.connect(self.page._update)
        self.worker.finished.connect(self.page._finished)
        self.page.worker = self.worker
        self.pool = ResidentViews(self.page)
        self.pool.key = "overview"
        self.pool.geometry = {}

    def park(self):
        module = SimpleNamespace(ViewerSurface=Mock())
        with patch.dict("sys.modules", {"pyforestscan_qgis.ui.point_cloud_page": module}):
            self.pool.park()

    def test_park_suspends_without_stopping_or_replacing_authority(self):
        editor = self.page.editor
        surface = self.page.surface
        self.park()
        self.assertIsNone(self.page.worker)
        self.assertIs(self.pool.parked["overview"]["surface"], surface)
        self.assertIs(self.page.editor, editor)
        self.worker.stop.assert_not_called()
        self.worker.send.assert_called_with({"action": "visible", "visible": False})
        self.assertNotIn(self.page._update, self.worker.update.slots)

    def test_resume_preserves_worker_and_suppresses_old_selection_event(self):
        self.park()
        self.assertTrue(self.pool.prepare(SimpleNamespace(view_id="overview", geometry={})))
        self.assertIs(self.page.worker, self.worker)
        self.assertEqual(self.page.editor.event_id, 12)
        self.assertEqual(self.page.linked.rendered_id, "overview")
        self.assertEqual(self.pool.parked, {})
        self.assertIn(self.page._update, self.worker.update.slots)
        self.worker.stop.assert_not_called()

    def test_changed_geometry_invalidates_cached_renderer(self):
        self.park()
        self.assertFalse(self.pool.prepare(SimpleNamespace(view_id="overview", geometry={"width": 10})))
        self.worker.stop.assert_called_once_with("inactive_view_evicted")

    def test_source_reset_drains_parked_workers(self):
        self.park()
        self.pool.clear()
        self.assertFalse(self.pool.parked)
        self.assertIsNone(self.pool.key)
        self.worker.stop.assert_called_once()

    def test_unacknowledged_view_is_not_cached(self):
        self.page.linked.rendered_id = None
        self.park()
        self.assertIs(self.page.worker, self.worker)
        self.assertFalse(self.pool.parked)

    def test_new_renderer_evicts_lru_beyond_three_total(self):
        for name in ("overview", "area", "slice"):
            self.pool.parked[name] = {"worker": Worker(), "surface": Mock(),
                                      "update": Mock(), "finished": Mock()}
            entry = self.pool.parked[name]
            entry["worker"].update.connect(entry["update"])
            entry["worker"].finished.connect(entry["finished"])
        first = self.pool.parked["overview"]["worker"]
        self.page.linked.active.return_value = SimpleNamespace(view_id="fourth", geometry={})
        self.pool.started()
        self.assertEqual(list(self.pool.parked), ["area", "slice"])
        first.stop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
