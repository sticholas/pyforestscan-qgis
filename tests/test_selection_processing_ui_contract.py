import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SelectionProcessingUiContractTests(unittest.TestCase):
    def test_editor_exposes_selection_to_product_action(self):
        source = (ROOT / "pyforestscan_qgis/ui/point_cloud_editor.py").read_text()
        self.assertIn("selectionProcessingRequested", source)
        self.assertIn('self.prepare_product_button.setText("Run Product on Selection")', source)
        self.assertIn("selection_product_row.addWidget(self.prepare_product_button)", source)
        self.assertIn("has_product_selection", source)
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
        self.assertIn("self.prepare_selection_product_button.clicked.connect(self.run_selected_product)", source)
        self.assertIn("self.validate_selected_product()", source)
        self.assertIn("self.promote_selected_product()", source)
        self.assertIn("Run Product on Selection stopped before reading source points", source)

    def test_completed_selected_rasters_load_in_qgis_and_viewer(self):
        source = (ROOT / "pyforestscan_qgis/ui/mission_control.py").read_text()
        loader = source[source.index("def _load_job_outputs"):source.index("def _adopt_output_crs_for_empty_project")]
        self.assertIn("self.iface.addRasterLayer", loader)
        self.assertIn("scoped_run = bool(self.processing_page.selection_scope)", loader)
        self.assertIn("load_scientific_overlay_path(result.path)", loader)
        self.assertIn("viewer_overlay_paths", loader)

    def test_viewer_overlay_loader_has_an_automatic_noninteractive_path(self):
        source = (ROOT / "pyforestscan_qgis/ui/point_cloud_page.py").read_text()
        self.assertIn("def load_scientific_overlay_path", source)
        self.assertIn("choose_band: bool = False", source)
        self.assertIn("and choose_band", source)
        self.assertIn("return True", source)
        self.assertIn("return False", source)

    def test_hag_is_limited_to_the_selection_or_active_detail_view(self):
        editor = (ROOT / "pyforestscan_qgis/ui/point_cloud_editor.py").read_text()
        limits = (ROOT / "pyforestscan_qgis/ui/point_cloud_selection_limits.py").read_text()
        self.assertIn("active_view=view_scope", editor)
        self.assertIn("Prepare HAG for This View", limits)
        self.assertIn("Whole-source preparation is disabled here", limits)

    def test_process_exposes_selected_points_as_a_first_class_mode(self):
        pages = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text()
        control = (ROOT / "pyforestscan_qgis/ui/mission_control.py").read_text()
        self.assertIn("Selected Points", pages)
        self.assertIn("selected_points", pages)
        self.assertIn("set_selected_points_scope", pages)
        self.assertIn("selectedPointsProcessingRequested", pages)
        self.assertIn("self.batch_page.set_selected_points_scope(scope)", control)
        self.assertIn("_open_selected_points_processing", control)

    def test_selected_points_locks_source_and_selection_context(self):
        pages = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text()
        self.assertIn("original source unchanged", pages)
        self.assertIn("Point cloud: {model.source_path}", pages)
        self.assertIn("selection_product_options(model)", pages)
        self.assertIn('option.status == "AVAILABLE"', pages)
        self.assertNotIn("selected_points_product_combo", pages)
        self.assertIn("Choose one available product below", pages)
