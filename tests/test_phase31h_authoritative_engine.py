import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pyforestscan_qgis.core.backend.models import BackendPlatform
from pyforestscan_qgis.core.backend.paths import resolve_backend_paths
from pyforestscan_qgis.core.backend.processing_engine import (
    ProcessingEngineReport,
    ProcessingEngineService,
    ProcessingEngineState,
    ProcessingEngineStateModel,
    ProcessingEngineVerifier,
    current_plugin_build_id,
    current_runner_hash,
    environment_fingerprint,
)
from pyforestscan_qgis.core.backend.runtime_manifest import PRODUCT_CAPABILITIES


class AuthoritativeProcessingEngineTests(unittest.TestCase):
    def _paths(self, root):
        paths = resolve_backend_paths(Path(root), BackendPlatform.WINDOWS)
        paths.python_executable.parent.mkdir(parents=True)
        paths.python_executable.touch()
        return paths

    @staticmethod
    def _payload(paths):
        return {
            "python_executable": str(paths.python_executable),
            "protocol_compatible": True,
            "protocol_version": "2",
            "failed_required_components": [],
            "required_functions": {"pyforestscan.handlers": {"read_lidar": True}},
            "required_function_signatures": {"pyforestscan.handlers": {"read_lidar": "(path, crs)"}},
            "product_capabilities": PRODUCT_CAPABILITIES,
            "capability_smoke_results": {name: True for name in PRODUCT_CAPABILITIES},
            "runner_sha256": current_runner_hash(),
            "plugin_build_id": current_plugin_build_id(),
            "versions": {"pyforestscan": "0.4.1"},
            "module_locations": {"pyforestscan.handlers": "managed/handlers.py"},
        }

    def test_ready_state_publishes_and_reuses_one_runtime_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = self._paths(folder)
            calls = []

            def runner(command, **kwargs):
                calls.append(command)
                return subprocess.CompletedProcess(command, 0, json.dumps(self._payload(paths)), "")

            service = ProcessingEngineService(paths, setup_callback=lambda **kwargs: None)
            service.verifier = ProcessingEngineVerifier(paths, runner, Path(folder))
            state = service.ensure_processing_engine_ready()
            first = service.runtime_token_for(("chm", "rumple"))
            second = service.runtime_token_for(("chm", "rumple"))
            self.assertTrue(state.ready_for_processing)
            self.assertEqual(first, second)
            self.assertEqual(len(calls), 2)
            self.assertEqual(first.engine_id, state.engine_id)
            self.assertEqual(first.contract_hash, state.contract_hash)

    def test_handlers_sentinel_invalidates_stale_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = self._paths(folder)
            handlers = paths.environment_path / "Lib" / "site-packages" / "pyforestscan" / "handlers.py"
            handlers.parent.mkdir(parents=True)
            handlers.write_text("ok", encoding="utf-8")
            before = environment_fingerprint(paths)
            handlers.unlink()
            self.assertNotEqual(before, environment_fingerprint(paths))

    def test_manifest_write_failure_cannot_publish_ready(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = self._paths(folder)
            runner = lambda command, **kwargs: subprocess.CompletedProcess(command, 0, json.dumps(self._payload(paths)), "")
            verifier = ProcessingEngineVerifier(paths, runner, Path(folder))
            with patch("pathlib.Path.write_text", side_effect=PermissionError("denied")):
                report = verifier.verify()
            self.assertEqual(report.state, ProcessingEngineState.FAILED)
            self.assertIn("manifest_persistence", report.failed_components)

    def test_state_listener_observes_every_published_transition(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = self._paths(folder)
            service = ProcessingEngineService(paths)
            observed = []
            service.subscribe(lambda state: observed.append(state.status))
            for index in range(100):
                status = ProcessingEngineState.READY if index % 2 else ProcessingEngineState.REPAIR_REQUIRED
                contract = self._payload(paths) if status is ProcessingEngineState.READY else {}
                service._publish(ProcessingEngineReport(status, status.value, str(paths.python_executable), contract))
            self.assertEqual(len(observed), 100)
            self.assertEqual(observed[-1], ProcessingEngineState.READY)

    def test_setup_and_launch_share_authoritative_service_contract(self):
        root = Path(__file__).parents[1]
        service = (root / "pyforestscan_qgis/core/backend/service.py").read_text(encoding="utf-8")
        execution = (root / "pyforestscan_qgis/core/backend/execution.py").read_text(encoding="utf-8")
        pages = (root / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")
        self.assertIn("_PROCESSING_ENGINE_SERVICES", service)
        self.assertIn("engine_service=self.processing_engine_service()", service)
        self.assertIn("self.engine_service.runtime_token_for", execution)
        self.assertNotIn("ProcessingEngineVerifier(self.paths, runner=self.runner, plugin_parent=self.plugin_parent).assert_ready_for", execution)
        self.assertIn("self.service.ensure_processing_engine_ready", pages)
        self.assertNotIn("self.service.install_backend(progress_callback", pages)

    def test_normal_ui_has_one_authoritative_setup_action(self):
        source = (Path(__file__).parents[1] / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")
        self.assertIn('QPushButton("Set Up Processing Engine")', source)
        self.assertIn('"Repair / Reload Processing Engine"', source)
        self.assertNotIn('QPushButton("Recheck Processing Engine")', source)
        self.assertIn("processingEngineStateChanged", source)
        self.assertIn("ready_for_processing", source)
        self.assertNotIn("Verify Backend until status is Ready", source)

    def test_product_contract_has_complete_smoke_matrix(self):
        self.assertEqual(
            set(PRODUCT_CAPABILITIES),
            {"chm", "rumple", "pad", "pai", "fhd", "canopy_cover", "dtm", "point_density", "voxel_stat"},
        )
        runtime = (Path(__file__).parents[1] / "pyforestscan_qgis/backend_runner/runtime_contract.py").read_text(encoding="utf-8")
        self.assertIn('"capability_smoke_results": capability_smoke', runtime)
        self.assertIn('"required_function_signatures": function_signatures', runtime)

    def test_production_entry_points_ban_auto_scientific_routing(self):
        root = Path(__file__).parents[1]
        production = [root / "pyforestscan_qgis/ui/mission_control.py", root / "pyforestscan_qgis/ui/pages.py"]
        production.extend((root / "pyforestscan_qgis/algorithms/advanced").glob("*.py"))
        offenders = []
        for path in production:
            source = path.read_text(encoding="utf-8")
            if "PyForestScanAdapter()" in source:
                offenders.append(str(path.relative_to(root)))
        self.assertEqual(offenders, [], f"Default/auto scientific adapters found: {offenders}")
        pages = production[1].read_text(encoding="utf-8")
        self.assertIn('adapter_factory=lambda: PyForestScanAdapter(execution_mode="pbm_backend")', pages)


if __name__ == "__main__":
    unittest.main()
