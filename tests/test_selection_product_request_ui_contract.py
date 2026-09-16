import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class SelectionProductRequestUiContractTests(unittest.TestCase):
    def test_processing_offers_explicit_product_preparation(self):
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text()
        self.assertIn("Run Product on Selection", source)
        self.assertIn("selection_product_combo", source)
        self.assertIn("build_selection_product_request", source)

    def test_selection_run_keeps_review_artifacts_and_source_safety(self):
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text()
        self.assertIn("processing has not started", source)
        self.assertIn("No source data was modified", source)
        self.assertIn("selection_product_request", source)
        self.assertIn("previous_context", source)
        self.assertIn("self.set_selection_scope(None)", source)
