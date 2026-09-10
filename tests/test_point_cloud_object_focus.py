"""Presentation-only object focus policy tests without QGIS."""
from pathlib import Path
import shutil
import subprocess
import unittest

from pyforestscan_qgis.core.point_cloud.object_focus import (
    MAX_EXACT_RENDER_ID, ObjectFocusMode, normalize_object_focus_mode,
    object_focus_command, object_focus_summary)


class ObjectFocusTests(unittest.TestCase):
    def setUp(self):
        self.active = {"field": "Tree_ID", "object_id": 42}
        self.selection = {"selection_id": "exact", "resolved_point_count": 1250}

    def test_focus_command_references_authoritative_selection_without_membership_data(self):
        command = object_focus_command(ObjectFocusMode.ISOLATE, self.active, self.selection)
        self.assertEqual(command, {"action": "object_focus", "mode": "ISOLATE",
            "scope": "AUTHORITATIVE_ACTIVE_OBJECT_SELECTION", "field": "Tree_ID", "object_id": "42"})
        self.assertNotIn("indices", command)
        self.assertNotIn("points", command)

    def test_nondefault_focus_requires_active_resolved_object(self):
        for active, selection in ((None, self.selection), (self.active, None),
                                  (self.active, {"resolved_point_count": 0})):
            with self.subTest(active=active, selection=selection):
                with self.assertRaisesRegex(ValueError, "Select an exact catalog object"):
                    object_focus_command("FADE_OTHERS", active, selection)
        self.assertEqual(object_focus_command("SHOW_ALL"), {"action": "object_focus",
            "mode": "SHOW_ALL", "scope": "AUTHORITATIVE_ACTIVE_OBJECT_SELECTION"})

    def test_renderer_precision_guard_rejects_ambiguous_large_ids(self):
        self.active["object_id"] = MAX_EXACT_RENDER_ID
        self.assertEqual(object_focus_command("ISOLATE", self.active, self.selection)["object_id"],
                         str(MAX_EXACT_RENDER_ID))
        self.active["object_id"] += 1
        with self.assertRaisesRegex(ValueError, "exact integer range"):
            object_focus_command("ISOLATE", self.active, self.selection)

    def test_mode_and_summary_are_explicit(self):
        self.assertEqual(normalize_object_focus_mode(ObjectFocusMode.FADE_OTHERS), "FADE_OTHERS")
        self.assertIn("Tree_ID = 42", object_focus_summary("FADE_OTHERS", self.active))
        with self.assertRaisesRegex(ValueError, "Unknown object focus mode"):
            normalize_object_focus_mode("GHOST")

    def test_editor_integrates_focus_without_changing_source_buffers(self):
        root = Path(__file__).parents[1]
        editor = (root / "pyforestscan_qgis/viewer/editor.js").read_text(encoding="utf-8")
        self.assertIn('command.action === "object_focus"', editor)
        self.assertIn("context.cloud.material.opacity = focus.opacity", editor)
        self.assertIn("source_buffers_unchanged", editor)

    @unittest.skipUnless(shutil.which("node"), "Node.js is optional for the Python test host")
    def test_javascript_focus_policy(self):
        root = Path(__file__).parents[1]
        completed = subprocess.run(["node", str(root / "scripts/testing/viewer_render_policy_test.cjs")],
                                   check=False, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
