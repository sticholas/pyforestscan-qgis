import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SelectionProcessingUiContractTests(unittest.TestCase):
    def test_editor_exposes_selection_to_product_action(self):
        source = (ROOT / "pyforestscan_qgis/ui/point_cloud_editor.py").read_text()
        self.assertIn("selectionProcessingRequested", source)
        self.assertIn('self.prepare_product_button = self.button("Use Selection for Product"', source)
        self.assertIn("authoritative selection", source)
        self.assertIn("Send the authoritative selection to Processing", source)

    def test_processing_page_labels_selection_run(self):
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text()
        self.assertIn("Selection scope:", source)
        self.assertIn("processing has not started", source)
        self.assertIn("set_selection_scope", source)

    def test_mission_control_routes_scope_to_processing(self):
        source = (ROOT / "pyforestscan_qgis/ui/mission_control.py").read_text()
        self.assertIn("selectionProcessingRequested.connect", source)
        self.assertIn("self.processing_page.set_selection_scope(scope)", source)
        self.assertIn('self._navigate_to("Processing")', source)


    def test_processing_keeps_internal_preflight_and_promotion_safety(self):
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text()
        self.assertIn('QPushButton("Validate Selected CHM")', source)
        self.assertIn('QPushButton("Promote for Execution")', source)
        self.assertIn("preflight_selection_product", source)
        self.assertIn("set_backend_readiness", source)
        self.assertIn("Run Product on Selection stopped before reading source points", source)
