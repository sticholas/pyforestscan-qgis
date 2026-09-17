"""QGIS-free contracts for the explicit non-destructive thinning entry point."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PAGE = (ROOT / "pyforestscan_qgis/ui/point_cloud_page.py").read_text(encoding="utf-8")
WORKER = (ROOT / "pyforestscan_qgis/viewer/thin_source.py").read_text(encoding="utf-8")


class PointCloudThinningContractTests(unittest.TestCase):
    def test_compact_prepare_menu_exposes_both_methods(self):
        self.assertIn('self.prepare_button.setText("Prepare")', PAGE)
        self.assertIn('"Voxel grid (recommended)"', PAGE)
        self.assertIn('"Poisson disk"', PAGE)
        self.assertIn('"Canopy and trunk detail: 0.25 m (recommended)"', PAGE)
        self.assertIn("meters_per_source_unit", PAGE)
        self.assertIn('"Fine vegetation detail: 0.10 m"', PAGE)

    def test_viewer_source_is_not_replaced_implicitly(self):
        self.assertIn("Original source unchanged.", PAGE)
        self.assertIn('open_copy.clicked.connect(open_output)', PAGE)
        self.assertNotIn("self.start_source(result[\"output_path\"])", PAGE)

    def test_worker_uses_preparation_safety_contract(self):
        self.assertIn("PreparationRequest.from_dict", WORKER)
        self.assertIn("prepare_arrays", WORKER)
        self.assertIn("stage_preparation", WORKER)
        self.assertIn("request.verify_input", WORKER)

    def test_dialog_provides_hoverable_explanation_and_never_guesses_unknown_units(self):
        self.assertIn("StableViewerHelp(dialog)", PAGE)
        self.assertIn("Tools & Setup", PAGE)
        self.assertIn("control.installEventFilter(self)", PAGE)

    def test_worker_writes_and_verifies_copy_before_publish(self):
        self.assertIn("writers.las", WORKER)
        self.assertIn('progress("Validating thinned copy")', WORKER)
        self.assertIn("transaction.publish(validate", WORKER)


if __name__ == "__main__":
    unittest.main()
