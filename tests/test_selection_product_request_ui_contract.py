import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class SelectionProductRequestUiContractTests(unittest.TestCase):
    def test_processing_offers_explicit_product_preparation(self):
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text()
        self.assertIn("Prepare Selected Product", source)
        self.assertIn("selection_product_combo", source)
        self.assertIn("build_selection_product_request", source)

    def test_preparation_is_review_only(self):
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text()
        self.assertIn("processing has not started", source)
        self.assertIn("No source data was modified", source)
        self.assertIn("selection_product_request", source)
        self.assertIn("previous_context", source)
        self.assertIn("self.set_selection_scope(None)", source)
