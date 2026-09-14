"""Regression coverage for frozen-token launch authority and product parity."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pyforestscan_qgis.core.adapter import PBM_ROUTED_PRODUCTS, PyForestScanAdapter
from pyforestscan_qgis.core.backend.models import BackendPlatform
from pyforestscan_qgis.core.backend.paths import resolve_backend_paths
from pyforestscan_qgis.core.backend.processing_engine import (
    ProcessingEngineError,
    ProcessingEngineService,
    ProcessingEngineVerifier,
    current_plugin_build_id,
    current_runner_hash,
    processing_engine_manifest_path,
)
from pyforestscan_qgis.core.backend.runtime_manifest import PRODUCT_CAPABILITIES
from pyforestscan_qgis.ui.availability import engine_state_update_is_current


ROOT = Path(__file__).resolve().parents[1]


class RuntimeAuthorityTests(unittest.TestCase):
    @staticmethod
    def _runner(paths):
        payload = {
            "python_executable": str(paths.python_executable),
            "protocol_compatible": True,
            "protocol_version": "2",
            "failed_required_components": [],
            "runner_sha256": current_runner_hash(),
            "plugin_build_id": current_plugin_build_id(),
            "product_capabilities": PRODUCT_CAPABILITIES,
            "versions": {"pyforestscan": "0.4.1"},
        }

        def run(command, **kwargs):
            return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")
        return run

    def _ready_service(self, folder):
        paths = resolve_backend_paths(Path(folder), BackendPlatform.WINDOWS)
        paths.python_executable.parent.mkdir(parents=True)
        paths.python_executable.touch()
        service = ProcessingEngineService(paths)
        service.verifier = ProcessingEngineVerifier(paths, self._runner(paths), Path(folder))
        service.verifier.verify(setup_completed=True)
        return service

    def test_valid_frozen_token_launch_does_not_call_discovery(self):
        with tempfile.TemporaryDirectory() as folder:
            service = self._ready_service(folder)
            token = service.runtime_token_for(("pai", "fhd"))
            service.state = lambda **kwargs: self.fail("readiness discovery called after token freeze")
            comparison = service.validate_runtime_token_for_launch(token, ("pai", "fhd"), Path(folder))
            self.assertTrue(all(item["status"] == "MATCH" for item in comparison.values()))

    def test_every_routed_product_uses_bound_token_without_backend_discovery(self):
        token = object()
        calls = []

        class Service:
            def can_execute_processing(self):
                raise AssertionError("duplicate readiness discovery")

            def run_product(self, product, request, runtime_token=None, runtime_products=()):
                calls.append((product, runtime_token, runtime_products))
                return SimpleNamespace(product_metrics={}, outputs={})

        requested_products = ("pai", "fhd")
        adapter = PyForestScanAdapter(
            execution_mode="pbm_backend",
            backend_service_factory=Service,
            runtime_token=token,
            runtime_products=requested_products,
        )
        with patch("pyforestscan_qgis.core.adapter._adapter_result_from_backend", return_value=object()):
            for product in sorted(PBM_ROUTED_PRODUCTS, key=lambda item: item.value):
                self.assertIsNotNone(adapter._run_pbm_product_if_selected(product, object()))
        self.assertEqual({name for name, _token, _products in calls}, {product.value for product in PBM_ROUTED_PRODUCTS})
        self.assertTrue(all(observed is token for _name, observed, _products in calls))
        self.assertTrue(all(products == requested_products for _name, _token, products in calls))

    def test_plugin_build_mismatch_has_precise_code(self):
        with tempfile.TemporaryDirectory() as folder:
            service = self._ready_service(folder)
            token = service.runtime_token_for(("pai",))
            path = processing_engine_manifest_path(service.paths)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["plugin_build_id"] = "different-build"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ProcessingEngineError) as raised:
                service.validate_runtime_token_for_launch(token, ("pai",))
            self.assertEqual(raised.exception.code, "ENGINE_PLUGIN_BUILD_CHANGED")
            self.assertIn("plugin_build_id", raised.exception.technical_message)

    def test_missing_executable_has_precise_code(self):
        with tempfile.TemporaryDirectory() as folder:
            service = self._ready_service(folder)
            token = service.runtime_token_for(("fhd",))
            service.paths.python_executable.unlink()
            with self.assertRaises(ProcessingEngineError) as raised:
                service.validate_runtime_token_for_launch(token, ("fhd",))
            self.assertEqual(raised.exception.code, "ENGINE_EXECUTABLE_MISSING")

    def test_delayed_startup_state_cannot_replace_newer_reload(self):
        self.assertTrue(engine_state_update_is_current("", "2026-08-27T23:24:43+00:00"))
        self.assertTrue(engine_state_update_is_current("2026-08-27T23:24:43+00:00", "2026-08-27T23:25:22+00:00"))
        self.assertFalse(engine_state_update_is_current("2026-08-27T23:25:22+00:00", "2026-08-27T23:24:43+00:00"))
        self.assertFalse(engine_state_update_is_current("2026-08-27T23:25:22+00:00", ""))

    def test_polygon_dispatch_binds_prerun_token_and_writes_decision_trace(self):
        source = (ROOT / "pyforestscan_qgis/core/polygon_batch.py").read_text(encoding="utf-8")
        self.assertIn("adapter.bind_processing_runtime(report.request.runtime_token, products)", source)
        self.assertIn('"launch_route": "polygon_managed_engine"', source)
        self.assertIn('"engine_decision_trace.json"', source)
        self.assertIn('"runtime_validation_at_dispatch"', source)
        self.assertNotIn('raise ProcessingError("Processing Engine needs repair before this job can start.")', source)


if __name__ == "__main__":
    unittest.main()
