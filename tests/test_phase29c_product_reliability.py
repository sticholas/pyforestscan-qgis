"""Phase 29C current-attempt and workflow-state reliability contracts."""

from pathlib import Path
import unittest

from pyforestscan_qgis.ui.session_state import MissionControlSessionState, workflow_input_signature


ROOT = Path(__file__).resolve().parents[1]


class WorkflowIdentityTests(unittest.TestCase):
    def test_signature_is_stable_and_changes_with_advanced_input(self) -> None:
        base = {"repository": "repo", "products": ("CHM",), "mask_failure_policy": "fail_product"}
        reordered = {"mask_failure_policy": "fail_product", "products": ("CHM",), "repository": "repo"}
        changed = dict(base, mask_failure_policy="warn_unmasked")
        self.assertEqual(workflow_input_signature(base), workflow_input_signature(reordered))
        self.assertNotEqual(workflow_input_signature(base), workflow_input_signature(changed))

    def test_session_plan_invalidation_preserves_input_identity(self) -> None:
        state = MissionControlSessionState(input_signature="current", plan_signature="old", current_execution_plan={"old": True})
        invalidated = state.invalidate_plan()
        self.assertEqual(invalidated.input_signature, "current")
        self.assertEqual(invalidated.plan_signature, "")
        self.assertIsNone(invalidated.current_execution_plan)


class CurrentAttemptUiContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pages = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")
        cls.control = (ROOT / "pyforestscan_qgis/ui/mission_control.py").read_text(encoding="utf-8")

    def test_results_never_scan_output_folder_for_unregistered_files(self) -> None:
        candidate = self.pages[self.pages.index("def _candidate_output_paths"):self.pages.index("def _project_layer_sources")]
        self.assertNotIn("rglob", candidate)
        self.assertIn("explicitly registered current-job paths", candidate)

    def test_failed_and_running_job_results_are_not_loadable(self) -> None:
        jobs = self.pages[self.pages.index("def set_jobs"):self.pages.index("def load_outputs_to_qgis")]
        self.assertIn("if job.status == JobStatus.COMPLETED", jobs)
        loader = self.control[self.control.index("def _load_job_outputs"):self.control.index("def _layer_name")]
        self.assertIn("if job.status != JobStatus.COMPLETED", loader)

    def test_partial_batch_does_not_register_successful_item_outputs(self) -> None:
        method = self.control[self.control.index("def _set_batch_status"):self.control.index("def _set_outputs_loaded_status")]
        self.assertIn("registered_outputs = output_paths if failure_count == 0 else ()", method)

    def test_input_change_clears_active_run_context(self) -> None:
        invalidation = self.control[self.control.index("def _invalidate_current_workflow_outputs"):self.control.index("def _set_environment_status")]
        self.assertIn("self.state = self.state.without_active_run()", invalidation)

    def test_all_preflight_defining_controls_invalidate_state(self) -> None:
        wiring = self.pages[self.pages.index("def _wire_session_state_inputs"):self.pages.index("def _on_session_input_changed")]
        for control in ("recursive_check", "polygon_direct_fallback_check", "mask_failure_policy_combo"):
            self.assertIn(control, wiring)
        self.assertIn("file_list.itemChanged.connect(self._on_session_input_changed)", self.pages)

    def test_workflow_controls_are_frozen_for_active_job(self) -> None:
        locking = self.pages[self.pages.index("def _set_workflow_inputs_enabled"):self.pages.index("def _clear_batch_thread")]
        for section in ("mode_section", "repository_section", "polygon_section", "products_section", "output_section"):
            self.assertIn(section, locking)


if __name__ == "__main__":
    unittest.main()
