"""Plan and dispatch attempt lifecycle regression coverage."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pyforestscan_qgis.core.backend.processing_engine import ProcessingRuntimeToken
from pyforestscan_qgis.core.batch import BatchProductSettings
from pyforestscan_qgis.core.lidar_catalog_builder import build_lidar_catalog
from pyforestscan_qgis.core.polygon_batch import PolygonBatchRequest, record_polygon_dispatch_validation, run_polygon_batch_preflight, validate_polygon_execution_manifest, write_polygon_batch_manifest
from pyforestscan_qgis.core.polygon_normalization import normalized_selection_from_wkt
from pyforestscan_qgis.core.types import ProductType


def _manifest(plan_generation: str, dispatch_generation: str | None) -> dict[str, object]:
    runtime = {field: "value" for field in ("engine_id", "executable", "environment_fingerprint", "contract_hash", "protocol", "backend_runner_hash", "dependency_manifest_hash", "product_capability_hash", "plugin_build_id")}
    runtime["runtime_generation_id"] = plan_generation
    return {
        "processing_runtime": runtime,
        "runtime_validation_at_dispatch": None if dispatch_generation is None else {"generation_id": dispatch_generation},
        "selected_source_paths": ["source.las"], "plan_signature": "plan",
        "execution_plan": {"products": ["pai"], "polygon_context": {"processing_geometry": "POLYGON EMPTY"}},
        "source_aware_raster_plan": None,
    }


class Phase32HPlanAttemptLifecycleTests(unittest.TestCase):
    def test_new_plan_needs_no_dispatch_evidence(self):
        validate_polygon_execution_manifest(_manifest("current", None), lifecycle="plan")

    def test_plan_ignores_stale_historical_dispatch(self):
        validate_polygon_execution_manifest(_manifest("current", "old"), lifecycle="plan")

    def test_execution_requires_dispatch_and_matching_generation(self):
        with self.assertRaisesRegex(ValueError, "runtime_validation_at_dispatch"):
            validate_polygon_execution_manifest(_manifest("current", None), lifecycle="execution")
        with self.assertRaisesRegex(ValueError, "generation_id_mismatch"):
            validate_polygon_execution_manifest(_manifest("current", "old"), lifecycle="execution")
        validate_polygon_execution_manifest(_manifest("current", "current"), lifecycle="execution")

    def test_windows_attempt_path_round_trips_without_control_characters(self):
        value = r"D:\tmp\pyforestscan_polygon_batch_planned\attempts\20260828T185000409369Z-e7c93c7f\launch_attempt.json"
        restored = json.loads(json.dumps({"attempt_path": value}))["attempt_path"]
        self.assertEqual(restored, value)
        self.assertFalse(any(character in restored for character in ("\a", "\b", "\t", "\n", "\r")))

    def test_new_attempt_files_do_not_reuse_previous_dispatch(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old = root / "attempts" / "old" / "dispatch_validation.json"
            new = root / "attempts" / "new" / "dispatch_validation.json"
            old.parent.mkdir(parents=True)
            old.write_text(json.dumps({"runtime_generation_id": "old"}), encoding="utf-8")
            self.assertFalse(new.exists())
            new.parent.mkdir(parents=True)
            new.write_text(json.dumps({"runtime_generation_id": "current"}), encoding="utf-8")
            self.assertEqual(json.loads(old.read_text())["runtime_generation_id"], "old")
            self.assertEqual(json.loads(new.read_text())["runtime_generation_id"], "current")

    def test_real_prerun_clears_old_dispatch_and_attempt_owns_current_generation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "ept.json").write_text(json.dumps({"bounds": [0, 0, 0, 5, 5, 5], "points": 100, "srs": {"authority": "EPSG:32610"}}), encoding="utf-8")
            build_lidar_catalog(root)
            polygon = normalized_selection_from_wkt("POLYGON ((1 1, 4 1, 4 4, 1 4, 1 1))", "EPSG:32610")
            settings = BatchProductSettings(products=(ProductType.PAI,), grid_resolution=1.0)
            request = PolygonBatchRequest(root, root / "out", polygon, (ProductType.PAI,), settings)
            report = run_polygon_batch_preflight(request, backend_probe=lambda: (True, "PBM ready"))
            token = ProcessingRuntimeToken("python", "env", "contract", "2", "now", "products", "engine", "runner", "plugin", "deps", "current-generation")
            report = replace(report, request=replace(report.request, runtime_token=token))
            report.batch_folder.mkdir(parents=True, exist_ok=True)
            (report.batch_folder / "engine_decision_trace.json").write_text(json.dumps({"runtime_token": {"runtime_generation_id": "old-generation"}, "dispatch_validation": {"status": "VALID"}}), encoding="utf-8")
            plan = json.loads(write_polygon_batch_manifest(report).read_text(encoding="utf-8"))
            self.assertIsNone(plan["runtime_validation_at_dispatch"])
            self.assertEqual(plan["runtime_generation_id"], "current-generation")
            attempt = report.batch_folder / "attempts" / "attempt-current"
            service = SimpleNamespace(paths=SimpleNamespace(backend_root=root / "backend"))
            with patch("pyforestscan_qgis.core.backend.BackendService", return_value=SimpleNamespace(processing_engine_service=lambda: service)):
                record_polygon_dispatch_validation(report, {"runtime_generation_id": {"status": "MATCH"}}, attempt_folder=attempt)
            dispatch = json.loads((attempt / "dispatch_validation.json").read_text(encoding="utf-8"))
            execution = json.loads((attempt / "polygon_execution_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(dispatch["plan_id"], report.plan_signature)
            self.assertEqual(dispatch["runtime_generation_id"], "current-generation")
            self.assertEqual(execution["runtime_validation_at_dispatch"]["generation_id"], "current-generation")

    def test_process_ready_transition_replaces_stale_engine_message_and_refreshes_plan(self):
        from tests.test_phase32g_dispatch_consistency import _import_pages_with_qt_stubs
        pages = _import_pages_with_qt_stubs()
        status = []
        page = SimpleNamespace(
            engine_setup_button=__import__("unittest.mock").mock.MagicMock(),
            engine_status_label=__import__("unittest.mock").mock.MagicMock(),
            status_label=__import__("unittest.mock").mock.MagicMock(),
            preflight_summary_label=__import__("unittest.mock").mock.MagicMock(),
            preflight_report=object(), _update_run_button_enabled=lambda: None, run_preflight=lambda: None,
        )
        engine = SimpleNamespace(ready_for_processing=True, repair_needed=False, status=SimpleNamespace(value="READY"), message="Ready")
        with patch.object(pages, "_set_status_badge", side_effect=lambda _label, state, message: status.append((state, message))), patch.object(pages.QTimer, "singleShot") as delayed:
            pages.BatchPage.set_processing_engine_state(page, engine)
        page.engine_status_label.setText.assert_called_with("Processing Engine: Ready")
        self.assertTrue(any("Processing plan: Refreshing" in message for _state, message in status))
        self.assertFalse(any("not current" in message.lower() for _state, message in status))
        delayed.assert_called_once()

    def test_detailed_check_reports_dispatch_not_started_as_non_blocking(self):
        source = (Path(__file__).resolve().parents[1] / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")
        method = source[source.index("    def _polygon_guided_review_text"):source.index("    def _current_spatial_report")]
        self.assertIn('"DISPATCH", "Not started', method)
        self.assertIn('"ENGINE"', method)
        self.assertIn('"PLAN"', method)


if __name__ == "__main__":
    unittest.main()
