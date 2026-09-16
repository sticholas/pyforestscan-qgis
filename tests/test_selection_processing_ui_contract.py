import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SelectionProcessingUiContractTests(unittest.TestCase):
    def test_editor_exposes_selection_to_product_action(self):
        source = (ROOT / "pyforestscan_qgis/ui/point_cloud_editor.py").read_text()
        self.assertIn("selectionProcessingRequested", source)
        self.assertIn('self.prepare_product_button.setText("Process Selected Points")', source)
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
        self.assertIn("Process Selected Points stopped before reading source points", source)

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

    def test_selected_product_controls_are_owned_and_automatic_path_stays_compact(self):
        pages = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text()
        self.assertIn("selection_product_row.addWidget(self.validate_selection_button", pages)
        self.assertIn("selection_product_row.addWidget(self.promote_selection_button", pages)
        self.assertIn("self.validate_selection_button.setVisible(False)", pages)
        self.assertIn("self.promote_selection_button.setVisible(False)", pages)
        self.assertIn("self.preflight_details_group.setVisible(False)", pages)
        self.assertIn("self.selected_points_section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)", pages)

    def test_processing_uses_pbm_activity_and_hides_legacy_prerun_banners(self):
        pages = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text()
        self.assertIn("activityUpdated = pyqtSignal(str)", pages)
        self.assertIn("progress_sink=lambda snapshot", pages)
        self.assertIn("def _on_backend_activity", pages)
        self.assertIn("Current activity: {activity}", pages)
        self.assertIn("self.preflight_summary_label.setVisible(False)", pages)
        self.assertIn("self.next_action_label.setVisible(False)", pages)
        self.assertIn("self.preflight_details_group.setVisible(False)", pages)
        self.assertIn("self.prerun_section.layout().setContentsMargins(0, 0, 0, 0)", pages)
        self.assertIn("self.process_workspace_layout.setSpacing(SPACING_SM)", pages)

    def test_selected_points_creates_a_bounded_plan_without_folder_prerun(self):
        pages = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text()
        control = (ROOT / "pyforestscan_qgis/ui/mission_control.py").read_text()
        self.assertIn('"Process Selected Points" if selected_points else "Run Prerun Check"', pages)
        self.assertIn('QPushButton("Process Selected Points")', pages)
        self.assertIn("from ..core.processing_spatial_context import default_source_local_policy_store", control)
        self.assertIn("default_source_local_policy_store().read().fallback_crs", control)
        self.assertIn("Preparing the bounded selected-point request", pages)
        self.assertIn("create_run_context(source, output_root).ensure_directories()", control)
        self.assertIn('"processing_executed": False', control)
        self.assertIn("self.processing_page.set_run_context(context)", control)
        self.assertIn("QTimer.singleShot(0, self.processing_page.run_selected_product)", control)

    def test_selected_points_locks_source_and_selection_context(self):
        pages = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text()
        self.assertIn("original source unchanged", pages)
        self.assertIn("Point cloud: {model.source_path}", pages)
        self.assertIn("selection_product_options(model)", pages)
        self.assertIn('option.status == "AVAILABLE"', pages)
        self.assertNotIn("selected_points_product_combo", pages)
        self.assertIn("Choose one product, then process this bounded area", pages)

    def test_selected_points_uses_its_own_details_and_background_execution(self):
        pages = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text()
        self.assertIn('selected_points_layout, "Selection Details", checked=False', pages)
        self.assertIn("self.selected_points_details_text.setText", pages)
        self.assertIn("Exact geometry:", pages)
        self.assertIn("CRS:", pages)
        self.assertIn("self.process_section.setVisible(not selected_points)", pages)
        self.assertIn("Process Selected Points runs the required bounded safety checks automatically.", pages)
        self.assertIn("class _ProcessingJobWorker(QObject)", pages)
        self.assertIn("self.processing_worker.moveToThread(self.processing_thread)", pages)
        self.assertIn("self.processing_elapsed_label", pages)
        self.assertIn("self.processing_sequence_label", pages)
        self.assertIn("self.processing_activity_label", pages)
        self.assertIn("Running in the background.", pages)
        self.assertIn("selectedPointsProcessingStateChanged", pages)
        self.assertIn("self.selected_points_progress.setRange(0, 0)", pages)
        self.assertIn('"Processing Selected Points..."', pages)
        self.assertIn("self.workflow_action_row.addWidget(self.preflight_button, 0, 0, 1, 2)", pages)
