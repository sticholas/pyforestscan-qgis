"""Phase 32R release-candidate UX and adaptive policy contracts."""
from pathlib import Path
from types import SimpleNamespace
import unittest

from pyforestscan_qgis.core.adaptive_concurrency import AdaptiveConcurrencyController


ROOT = Path(__file__).resolve().parents[1]
PAGES = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")


def completed(ept_seconds: float = 1.0):
    return SimpleNamespace(status="Completed", error_code="", metrics={
        "ept_read_and_point_decode_seconds": ept_seconds,
        "worker_peak_rss": 512 * 1024**2,
    })


class Phase32RAdaptivePolicyTests(unittest.TestCase):
    def controller(self, location: str = "network") -> AdaptiveConcurrencyController:
        return AdaptiveConcurrencyController(
            requested=5,
            source_location=location,
            estimated_worker_memory=512 * 1024**2,
            available_memory_provider=lambda: 32 * 1024**3,
            cpu_count=16,
        )

    def test_network_baseline_stays_at_two_until_evidence_exists(self) -> None:
        controller = self.controller()
        for _ in range(7):
            controller.observe(completed())
        self.assertEqual(controller.target, 2)
        self.assertEqual(controller.ceiling, 2)
        self.assertFalse(controller.network_probation_attempted)

    def test_network_worker_three_is_probationary_and_non_oscillating(self) -> None:
        controller = self.controller()
        for _ in range(8):
            controller.observe(completed())
        self.assertEqual(controller.target, 3)
        self.assertTrue(controller.network_probation_attempted)
        controller.observe(SimpleNamespace(
            status="Failed", error_code="QHULL_INTERNAL_ERROR", metrics={}
        ))
        self.assertEqual(controller.target, 2)
        self.assertTrue(controller.network_probation_revoked)
        for _ in range(12):
            controller.observe(completed())
        self.assertEqual(controller.ceiling, 2)
        self.assertEqual(controller.target, 2)

    def test_local_sources_may_use_resource_safe_higher_capacity(self) -> None:
        controller = self.controller("local")
        for _ in range(12):
            controller.observe(completed())
        self.assertEqual(controller.ceiling, 5)
        self.assertEqual(controller.target, 5)


class Phase32RUiContractTests(unittest.TestCase):
    def test_wizard_strip_is_removed_but_compatibility_hook_remains(self) -> None:
        self.assertNotIn('setObjectName("workflowStepIndicator")', PAGES)
        self.assertIn("def set_workflow_indicator", PAGES)

    def test_help_banner_supports_hover_and_keyboard_focus(self) -> None:
        self.assertIn('setObjectName("contextHelpBanner")', PAGES)
        self.assertIn("QEvent.Enter, QEvent.FocusIn", PAGES)
        self.assertIn("Hover over or focus a control", PAGES)

    def test_primary_polygon_workflow_hides_engineering_controls(self) -> None:
        self.assertIn("self.advanced_repository_section.setVisible(False)", PAGES)
        self.assertIn("self.advanced_spatial_section.setVisible(False)", PAGES)
        self.assertIn("self.advanced_batch_section.setVisible(False)", PAGES)
        self.assertIn('self.zoom_polygon_button.setText("Zoom to Area")', PAGES)
        self.assertIn('QPushButton("Prerun Check")', PAGES)

    def test_normal_progress_uses_regions_not_worker_targets(self) -> None:
        progress = PAGES[PAGES.index("def _on_polygon_progress"):PAGES.index("def _on_batch_job_update")]
        self.assertIn("regions processing", progress)
        self.assertNotIn("target_concurrency", progress)
        self.assertIn("Completed regions are saved", PAGES)


if __name__ == "__main__":
    unittest.main()
