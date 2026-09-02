"""Phase 32S release-candidate UI regression contracts."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PAGES = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")
BATCH = PAGES[PAGES.index("class BatchPage"):PAGES.index("class ResultsPage")]


class Phase32SRcUxTests(unittest.TestCase):
    def test_prerun_callback_has_no_retired_guided_widget(self) -> None:
        callback = BATCH[BATCH.index("def _on_polygon_preflight_complete"):BATCH.index("def _on_polygon_preflight_failed")]
        self.assertNotIn("polygon_guided_step_label", callback)
        self.assertNotIn("guided_step_indicator", PAGES)

    def test_shared_context_help_supports_pointer_and_keyboard(self) -> None:
        self.assertIn("class ContextHelpBanner(QFrame)", PAGES)
        self.assertIn("QEvent.Enter, QEvent.FocusIn", PAGES)
        self.assertIn("QEvent.Leave, QEvent.FocusOut", PAGES)
        self.assertIn("Help  |  ", PAGES)

    def test_polygon_primary_controls_are_compact(self) -> None:
        self.assertIn("polygon_area_actions.addWidget(self.polygon_refresh_layers_button", BATCH)
        self.assertIn("polygon_area_actions.addWidget(self.zoom_polygon_button", BATCH)
        self.assertIn("self.polygon_dissolve_check.setVisible(False)", BATCH)
        self.assertNotIn("polygon_layout.addWidget(self.zoom_polygon_button", BATCH)
        self.assertGreaterEqual(BATCH.count("AdjustToMinimumContentsLengthWithIcon"), 4)
        self.assertIn("self.zoom_polygon_button.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)", BATCH)

    def test_expert_controls_stay_out_of_normal_workflow(self) -> None:
        self.assertIn("self.advanced_repository_section.setVisible(False)", BATCH)
        self.assertIn("self.advanced_batch_section.setVisible(False)", BATCH)
        self.assertIn("settings_layout.addWidget(self.retain_unmasked_intermediate_check)", BATCH)


if __name__ == "__main__":
    unittest.main()
