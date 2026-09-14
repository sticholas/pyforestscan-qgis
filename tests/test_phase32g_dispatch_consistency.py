"""Regression coverage for the Phase 32G dispatch and identity defects."""

from __future__ import annotations

import tempfile
import unittest
import importlib
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from scripts.check_undefined_names import undefined_names
from pyforestscan_qgis.core.polygon_batch import validate_polygon_execution_manifest


ROOT = Path(__file__).resolve().parents[1]


class Phase32GDispatchConsistencyTests(unittest.TestCase):
    def test_pages_has_no_undefined_production_names(self):
        findings = undefined_names(ROOT / "pyforestscan_qgis/ui/pages.py")
        self.assertNotIn("runtime_comparison", {name for _line, name in findings})
        self.assertEqual(findings, [])

    def test_checker_detects_the_exact_phase32f_scope_regression(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "broken.py"
            path.write_text("def launch():\n    return runtime_comparison\n", encoding="utf-8")
            self.assertEqual(undefined_names(path), [(1, "runtime_comparison")])

    def test_dispatch_uses_one_validation_result_and_controller_boundary(self):
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")
        wrapper = source[source.index("    def _run_polygon_batch"):source.index("    def _dispatch_polygon_batch")]
        dispatch = source[source.index("    def _dispatch_polygon_batch"):source.index("    def _build_batch_request")]
        self.assertIn("except Exception as exc", wrapper)
        self.assertIn('"DISPATCH_FAILED"', wrapper)
        self.assertIn('code="DISPATCH_INTERNAL_ERROR"', wrapper)
        self.assertIn("runtime_validation: dict[str, dict[str, str]] =", dispatch)
        self.assertIn("record_polygon_dispatch_validation(report, runtime_validation", dispatch)
        self.assertNotIn("runtime_comparison", dispatch)
        self.assertLess(dispatch.index('"DISPATCH_VALIDATION_RECORDED"'), dispatch.index('"DISPATCH_STARTED"'))

    def test_setup_completion_projects_canonical_engine_state(self):
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")
        method = source[source.index("    def _on_backend_install_complete"):source.index("    def _on_backend_install_failed")]
        self.assertIn("processing_engine_state(quick=True)", method)
        self.assertNotIn("processingEngineStateChanged.emit(result)", method)

    def test_diagnostics_name_identity_domains_without_cross_comparison(self):
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")
        method = source[source.index("    def show_backend_advanced"):source.index("    def show_manual_setup_instructions")]
        self.assertIn("Package build ID", method)
        self.assertIn("Plugin contract fingerprint", method)
        self.assertNotIn("identity.processing_engine_plugin_build_id", method)
        self.assertIn("Compatibility authority: ProcessingEngineService", method)

    def test_real_batch_page_method_reaches_dispatch_started_with_validation_result(self):
        pages = _import_pages_with_qt_stubs()
        validation = {"engine_id": {"status": "MATCH", "expected": "engine", "observed": "engine"}}
        runtime_token = SimpleNamespace(runtime_generation_id="generation", executable="python")
        report = SimpleNamespace(
            request=SimpleNamespace(products=(SimpleNamespace(value="pai"), SimpleNamespace(value="fhd")), runtime_token=runtime_token, spatial_policy="policy"),
            batch_folder=Path(tempfile.mkdtemp()), plan_signature="plan", blockers=(), selected_sources=(SimpleNamespace(path=Path("source.las")),),
        )
        stage_names: list[str] = []
        recorded: list[object] = []
        page = SimpleNamespace(
            preflight_report=report, _active_launch_attempt=None, _last_launch_heartbeat_ms=0,
            _begin_logical_job=lambda: object(), _completed_job_summary=None,
            processing_profile_combo=SimpleNamespace(currentText=lambda: "Automatic (Recommended)"),
            _transition_processing_ui_state=lambda _state: None, batch_items=[], failed_paths=[],
            cancel_requested=False, pause_requested=False, batch_results=MagicMock(), progress_bar=MagicMock(),
            run_button=MagicMock(), resume_button=MagicMock(), pause_button=MagicMock(), cancel_button=MagicMock(),
            retry_failed_button=MagicMock(), status_label=MagicMock(), worker_status_label=MagicMock(),
            _batch_control_state=lambda: None, _on_batch_item=lambda _item: None,
            _on_batch_job_update=lambda _job: None, _on_batch_complete=lambda _result: None,
            _on_batch_failed=lambda _message: None, _clear_batch_thread=lambda: None,
            _retain_recent_error=lambda *args, **kwargs: None, _finish_batch_run=lambda _state: None,
        )
        page._dispatch_polygon_batch = lambda: pages.BatchPage._dispatch_polygon_batch(page)
        attempt = SimpleNamespace(folder=report.batch_folder / "attempt", trace_path=report.batch_folder / "attempt.json", attempt_id="attempt")
        service = SimpleNamespace(validate_runtime_token_for_launch=lambda *_args: validation)
        backend = SimpleNamespace(processing_engine_service=lambda: service)
        thread = MagicMock()
        worker = MagicMock()
        with (
            patch.object(pages, "create_launch_attempt", return_value=attempt),
            patch.object(pages, "verify_session_files_unchanged", return_value=SimpleNamespace(status="PLUGIN_VALID")),
            patch.object(pages, "default_source_local_policy_store", return_value=SimpleNamespace(read=lambda: "policy")),
            patch.object(pages, "BackendService", return_value=backend),
            patch.object(pages, "record_polygon_dispatch_validation", side_effect=lambda _report, result, **_kwargs: recorded.append(result)),
            patch.object(pages, "append_attempt_stage", side_effect=lambda _attempt, stage, **_details: stage_names.append(stage)),
            patch.object(pages, "QThread", return_value=thread),
            patch.object(pages, "_PolygonBatchExecutionWorker", return_value=worker),
            patch.object(pages, "_set_status_badge"),
        ):
            pages.BatchPage._run_polygon_batch(page)
        self.assertEqual(recorded, [validation])
        self.assertIn("DISPATCH_VALIDATION_RECORDED", stage_names)
        self.assertIn("DISPATCH_STARTED", stage_names)
        self.assertNotIn("DISPATCH_FAILED", stage_names)

    def test_different_package_and_contract_ids_do_not_override_ready_projection(self):
        pages = _import_pages_with_qt_stubs()
        projected: list[tuple[str, str]] = []
        package_build_id = "18b7a05c99b84c88e332"
        plugin_contract_build_id = "794c3927cb039b4fcc56967aaf38808b2227afd79b3a62ef0583cd32e9d1801e"
        self.assertNotEqual(package_build_id, plugin_contract_build_id)
        page = SimpleNamespace(
            engine_setup_button=MagicMock(), engine_status_label=MagicMock(), run_button=MagicMock(),
            status_label=MagicMock(), preflight_summary_label=MagicMock(), preflight_report=None, _update_run_button_enabled=lambda: None,
        )
        engine = SimpleNamespace(
            ready_for_processing=True, repair_needed=False,
            status=SimpleNamespace(value="READY"), message="Processing Engine is ready.",
            runtime_token=SimpleNamespace(plugin_build_id=plugin_contract_build_id),
        )
        with patch.object(pages, "_set_status_badge", side_effect=lambda _label, status, message: projected.append((status, message))):
            pages.BatchPage.set_processing_engine_state(page, engine)
        page.engine_status_label.setText.assert_called_with("Processing Engine: Ready")
        self.assertFalse(any("not current" in message.lower() for _status, message in projected))

    def test_synchronous_dispatch_exception_is_terminal_plugin_failure(self):
        pages = _import_pages_with_qt_stubs()
        stages: list[tuple[str, dict[str, object]]] = []
        page = SimpleNamespace(
            _dispatch_polygon_batch=lambda: (_ for _ in ()).throw(NameError("missing launch variable")),
            _active_launch_attempt=object(), _retain_recent_error=MagicMock(),
            status_label=MagicMock(), _finish_batch_run=MagicMock(),
        )
        with patch.object(pages, "append_attempt_stage", side_effect=lambda _attempt, stage, **details: stages.append((stage, details))), patch.object(pages, "_set_status_badge"):
            pages.BatchPage._run_polygon_batch(page)
        self.assertEqual([stage for stage, _details in stages], ["DISPATCH_FAILED", "FAILED"])
        self.assertTrue(all(details["code"] == "DISPATCH_INTERNAL_ERROR" for _stage, details in stages))
        self.assertTrue(all(details["failure_domain"] == "PLUGIN" for _stage, details in stages))
        page._retain_recent_error.assert_called_once()

    def test_manifest_rejects_cross_generation_dispatch_evidence(self):
        runtime = {field: "value" for field in ("engine_id", "executable", "environment_fingerprint", "contract_hash", "protocol", "backend_runner_hash", "dependency_manifest_hash", "product_capability_hash", "plugin_build_id")}
        runtime["runtime_generation_id"] = "generation-current"
        payload = {
            "processing_runtime": runtime,
            "runtime_validation_at_dispatch": {"generation_id": "generation-stale"},
            "selected_source_paths": ["source.las"], "plan_signature": "plan",
            "execution_plan": {"products": ["pai"], "polygon_context": {"processing_geometry": "POLYGON EMPTY"}},
            "source_aware_raster_plan": None,
        }
        with self.assertRaisesRegex(ValueError, "generation_id_mismatch"):
            validate_polygon_execution_manifest(payload, lifecycle="execution")


def _import_pages_with_qt_stubs():
    if "pyforestscan_qgis.ui.pages" in sys.modules:
        return sys.modules["pyforestscan_qgis.ui.pages"]

    class DummyMeta(type):
        def __getattr__(cls, _name):
            return 0

    class Dummy(metaclass=DummyMeta):
        def __init__(self, *args, **kwargs): pass
        def __getattr__(self, _name): return MagicMock()

    class Signal:
        def connect(self, *_args): pass
        def disconnect(self, *_args): pass
        def emit(self, *_args): pass

    class StubModule(types.ModuleType):
        def __getattr__(self, name):
            if name == "pyqtSignal": return lambda *_args, **_kwargs: Signal()
            if name == "Qt": return Dummy
            return Dummy

    modules = {
        "qgis": StubModule("qgis"), "qgis.PyQt": StubModule("qgis.PyQt"),
        "qgis.PyQt.QtCore": StubModule("qgis.PyQt.QtCore"),
        "qgis.PyQt.QtGui": StubModule("qgis.PyQt.QtGui"),
        "qgis.PyQt.QtWidgets": StubModule("qgis.PyQt.QtWidgets"),
        "qgis.core": StubModule("qgis.core"),
    }
    with patch.dict(sys.modules, modules):
        return importlib.import_module("pyforestscan_qgis.ui.pages")


if __name__ == "__main__":
    unittest.main()
