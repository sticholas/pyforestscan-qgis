"""QGIS-free contracts for deterministic Processing Engine setup."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.backend.models import BackendPlatform
from pyforestscan_qgis.core.backend.paths import resolve_backend_paths
from pyforestscan_qgis.core.backend.processing_engine import (
    ProcessingEngineService,
    ProcessingEngineState,
    ProcessingEngineVerifier,
    current_plugin_build_id,
    current_runner_hash,
    processing_engine_manifest_path,
)
from pyforestscan_qgis.core.backend.runtime_manifest import PRODUCT_CAPABILITIES
from pyforestscan_qgis.ui.ux_summary import processing_engine_setup_action


ROOT = Path(__file__).resolve().parents[1]


class DeterministicSetupTests(unittest.TestCase):
    def _paths(self, root: str):
        return resolve_backend_paths(Path(root), BackendPlatform.WINDOWS)

    @staticmethod
    def _runtime_payload(paths):
        return {
            "python_executable": str(paths.python_executable),
            "protocol_compatible": True,
            "protocol_version": "2",
            "failed_required_components": [],
            "runner_sha256": current_runner_hash(),
            "plugin_build_id": current_plugin_build_id(),
            "product_capabilities": PRODUCT_CAPABILITIES,
            "versions": {"pyforestscan": "0.4.1"},
        }

    @staticmethod
    def _runner(payload):
        def run(command, **kwargs):
            return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")
        return run

    def _complete_setup(self, folder: str):
        paths = self._paths(folder)
        paths.python_executable.parent.mkdir(parents=True, exist_ok=True)
        paths.python_executable.touch()
        verifier = ProcessingEngineVerifier(paths, self._runner(self._runtime_payload(paths)), Path(folder))
        report = verifier.verify(setup_completed=True)
        self.assertTrue(report.ready)
        return paths, verifier

    def test_quick_state_matrix_rejects_partial_stale_and_corrupt_setups(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = self._paths(folder)
            self.assertEqual(ProcessingEngineVerifier(paths).quick().state, ProcessingEngineState.SETUP_REQUIRED)

            paths.python_executable.parent.mkdir(parents=True)
            paths.python_executable.touch()
            verifier = ProcessingEngineVerifier(paths)
            self.assertEqual(verifier.quick().state, ProcessingEngineState.REPAIR_REQUIRED)

            processing_engine_manifest_path(paths).write_text("{broken", encoding="utf-8")
            self.assertEqual(verifier.quick().state, ProcessingEngineState.REPAIR_REQUIRED)

            paths, verifier = self._complete_setup(folder)
            self.assertEqual(verifier.quick().state, ProcessingEngineState.READY)

            manifest_path = processing_engine_manifest_path(paths)
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload["setup_plugin_build_id"] = "old-build"
            manifest_path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(verifier.quick().state, ProcessingEngineState.REPAIR_REQUIRED)

    def test_ensure_marks_current_valid_runtime_without_reinstall(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = self._paths(folder)
            paths.python_executable.parent.mkdir(parents=True)
            paths.python_executable.touch()
            setup_calls = []
            service = ProcessingEngineService(paths, setup_callback=lambda **kwargs: setup_calls.append(kwargs))
            service.verifier = ProcessingEngineVerifier(paths, self._runner(self._runtime_payload(paths)), Path(folder))

            first = service.ensure_processing_engine_ready()
            first_token = service.runtime_token_for(("chm",))
            second = service.ensure_processing_engine_ready()
            second_token = service.runtime_token_for(("chm",))

            self.assertTrue(first.ready_for_processing)
            self.assertTrue(second.ready_for_processing)
            self.assertEqual(setup_calls, [])
            manifest = json.loads(processing_engine_manifest_path(paths).read_text(encoding="utf-8"))
            self.assertEqual(manifest["setup_plugin_build_id"], current_plugin_build_id())
            self.assertTrue(manifest["setup_completed_at"])
            self.assertEqual(manifest["runner_hash"], current_runner_hash())
            self.assertTrue(manifest["contract_hash"])
            self.assertNotEqual(first_token.contract_hash, second_token.contract_hash)

    def test_service_does_not_cache_ready_across_manifest_replacement(self):
        with tempfile.TemporaryDirectory() as folder:
            paths, verifier = self._complete_setup(folder)
            service = ProcessingEngineService(paths)
            service.verifier = verifier
            self.assertTrue(service.state(quick=True).ready_for_processing)
            manifest_path = processing_engine_manifest_path(paths)
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload["dependency_manifest_hash"] = "stale"
            manifest_path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(service.state(quick=True).status, ProcessingEngineState.REPAIR_REQUIRED)

    def test_setup_action_is_always_visible_and_recheck_is_removed(self):
        self.assertEqual(processing_engine_setup_action("READY"), (True, "Repair"))
        self.assertEqual(processing_engine_setup_action("SETUP_REQUIRED"), (True, "Set Up Processing Engine"))
        pages = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")
        settings = pages[pages.index("class SettingsPage"):pages.index("def _processing_lifecycle_stage")]
        self.assertNotIn('QPushButton("Recheck Processing Engine")', settings)
        self.assertNotIn('add_section("LiDAR Spatial Reference', settings)
        self.assertIn("set_spatial_intervention", pages)
        self.assertIn("self.run_preflight()", pages)


if __name__ == "__main__":
    unittest.main()
