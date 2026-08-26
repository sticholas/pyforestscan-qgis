import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from pyforestscan_qgis.backend_runner.job_spec import BackendJobSpec
from pyforestscan_qgis.core.backend.models import BackendPlatform
from pyforestscan_qgis.core.backend.paths import resolve_backend_paths
from pyforestscan_qgis.core.backend.process_env import build_processing_engine_environment
from pyforestscan_qgis.core.backend.processing_engine import (
    ProcessingEngineError,
    ProcessingEngineVerifier,
    ProcessingRuntimeToken,
)
from pyforestscan_qgis.core.backend.runtime_manifest import PRODUCT_CAPABILITIES, PYFORESTSCAN_FUNCTION_CONTRACT
from pyforestscan_qgis.core.product_parameters import PRODUCT_PARAMETERS
from pyforestscan_qgis.core.scientific_boundary import assert_scientific_import_allowed


class RuntimeConvergenceTests(unittest.TestCase):
    def _paths(self, root):
        paths = resolve_backend_paths(Path(root), BackendPlatform.WINDOWS)
        paths.python_executable.parent.mkdir(parents=True)
        paths.python_executable.touch()
        return paths

    def _runner(self, paths, failures=()):
        payload = {
            "python_executable": str(paths.python_executable),
            "protocol_compatible": True,
            "protocol_version": "2",
            "failed_required_components": list(failures),
            "required_functions": {"pyforestscan.handlers": {"read_lidar": True}},
            "product_capabilities": PRODUCT_CAPABILITIES,
            "runner_sha256": "runner",
            "plugin_build_id": "build",
            "versions": {"pyforestscan": "0.4.1"},
            "module_locations": {"pyforestscan.handlers": "managed/handlers.py"},
        }
        return lambda command, **kwargs: subprocess.CompletedProcess(command, 0, json.dumps(payload), "")

    def test_qgis_python_scientific_import_is_blocked(self):
        fake_qgis = types.ModuleType("qgis")
        with patch.dict(sys.modules, {"qgis": fake_qgis}), patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "SCIENTIFIC_RUNTIME_BOUNDARY"):
                assert_scientific_import_allowed("pyforestscan.handlers")

    def test_managed_runtime_allows_scientific_import(self):
        fake_qgis = types.ModuleType("qgis")
        with patch.dict(sys.modules, {"qgis": fake_qgis}), patch.dict(os.environ, {"PYFORESTSCAN_MANAGED_ENGINE": "1"}, clear=True):
            assert_scientific_import_allowed("pyforestscan.handlers")

    def test_environment_builder_marks_managed_engine(self):
        with tempfile.TemporaryDirectory() as folder:
            env = build_processing_engine_environment(Path(folder), "windows", {"PATH": "C:\\Windows"})
        self.assertEqual(env["PYFORESTSCAN_MANAGED_ENGINE"], "1")
        self.assertEqual(env["PYTHONNOUSERSITE"], "1")

    def test_runtime_token_round_trip_and_drift_rejection(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = self._paths(folder)
            verifier = ProcessingEngineVerifier(paths, self._runner(paths), Path(folder))
            token = verifier.assert_ready_for(("chm", "rumple"))
            self.assertEqual(ProcessingRuntimeToken.from_dict(token.to_dict()), token)
            changed = ProcessingRuntimeToken(**{**token.to_dict(), "contract_hash": "changed"})
            with self.assertRaises(ProcessingEngineError):
                verifier.validate_token(changed, ("chm", "rumple"))

    def test_job_spec_persists_runtime_token(self):
        token = {"executable": "managed-python", "contract_hash": "abc"}
        spec = BackendJobSpec("job", Path("in.las"), "EPSG:6635", Path("run"), "chm", {}, {"primary": Path("out.tif")}, Path("result.json"), runtime_token=token)
        self.assertEqual(BackendJobSpec.from_dict(spec.to_dict()).runtime_token, token)

    def test_contract_covers_every_advertised_product_and_parameters(self):
        self.assertEqual(set(PRODUCT_CAPABILITIES), {"chm", "rumple", "pad", "pai", "fhd", "canopy_cover", "dtm", "point_density", "voxel_stat"})
        self.assertIn("read_lidar", PYFORESTSCAN_FUNCTION_CONTRACT["pyforestscan.handlers"])
        self.assertTrue(all(item.function and item.argument for item in PRODUCT_PARAMETERS))

    def test_normal_folder_and_polygon_paths_force_pbm(self):
        root = Path(__file__).parents[1]
        pages = (root / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")
        polygon = (root / "pyforestscan_qgis/core/polygon_batch.py").read_text(encoding="utf-8")
        self.assertIn('PyForestScanAdapter(execution_mode="pbm_backend")', pages)
        self.assertIn('PyForestScanAdapter(execution_mode="pbm_backend")', polygon)
        self.assertIn("execution_runtime_trace.json", (root / "pyforestscan_qgis/core/backend/execution.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
