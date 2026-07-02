"""Tests for Phase 23D PBM processing execution routing."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from pyforestscan_qgis.backend_runner.job_result import BackendJobResult
from pyforestscan_qgis.backend_runner.job_spec import BackendJobSpec, build_job_spec_from_request
from pyforestscan_qgis.core.adapter import EXECUTION_MODE_PBM_BACKEND, PyForestScanAdapter
from pyforestscan_qgis.core.backend.execution import BackendExecutionService, validate_backend_python_executable
from pyforestscan_qgis.core.backend.models import BackendRegistry, BackendState, BackendStatus, BackendVerificationResult
from pyforestscan_qgis.core.backend.paths import resolve_backend_paths
from pyforestscan_qgis.core.batch import BatchProductSettings, BatchRequest
from pyforestscan_qgis.core.batch_preflight import run_batch_preflight
from pyforestscan_qgis.core.dependency_check import EnvironmentReport, ReadinessStatus
from pyforestscan_qgis.core.types import ChmRequest, ProductType


def ready_verification(paths):
    return BackendVerificationResult(
        status=BackendStatus.READY,
        state=BackendState(BackendStatus.READY, paths.platform, paths.backend_root, True, True, True, True, "ready"),
        checks=(),
        registry=BackendRegistry(()),
        summary="Backend verification checks passed.",
    )


class PBMProcessingExecutionTests(unittest.TestCase):
    """Validate backend runner protocol and routing without QGIS."""

    def test_job_spec_serialization(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            request = ChmRequest(root / "plot.laz", root / "chm.tif", 1.0, "EPSG:32610")
            spec = build_job_spec_from_request("chm", request, run_folder=root, job_id="job-1")
            path = spec.write(root / "spec.json")
            loaded = BackendJobSpec.read(path)

        self.assertEqual(loaded.job_id, "job-1")
        self.assertEqual(loaded.product, "chm")
        self.assertEqual(loaded.output_paths["primary"].name, "chm.tif")
        self.assertEqual(loaded.product_parameters["grid_resolution"], 1.0)

    def test_job_result_serialization(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "result.json"
            result = BackendJobResult("job-1", "chm", "success", outputs={"primary": Path(tmpdir) / "chm.tif"}, product_metrics={"grid_resolution": 1.0})
            result.write(path)
            loaded = BackendJobResult.read(path)

        self.assertTrue(loaded.success)
        self.assertEqual(loaded.outputs["primary"].name, "chm.tif")
        self.assertEqual(loaded.product_metrics["grid_resolution"], 1.0)

    def test_backend_runner_command_construction(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            python = root / "python.exe"
            python.write_text("", encoding="utf-8")
            paths = resolve_backend_paths(backend_root=root / "backend")
            paths = resolve_backend_paths(backend_root=root / "backend", platform=paths.platform)
            paths.python_executable.parent.mkdir(parents=True, exist_ok=True)
            paths.python_executable.write_text("", encoding="utf-8")
            service = BackendExecutionService(paths, verifier=lambda: ready_verification(paths))
            command = service.runner_command(root / "spec.json")

        self.assertEqual(command[1:3], ["-m", "pyforestscan_qgis.backend_runner.run_processing_job"])
        self.assertEqual(command[-2:], ["--spec", str(root / "spec.json")])

    def test_refuses_qgis_gui_executable_as_backend_python(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bad = Path(tmpdir) / "qgis-ltr-bin.exe"
            bad.write_text("", encoding="utf-8")
            ok, message = validate_backend_python_executable(bad)

        self.assertFalse(ok)
        self.assertIn("Refusing", message)

    def test_run_product_uses_mocked_subprocess_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            paths = resolve_backend_paths(backend_root=root / "backend")
            paths.python_executable.parent.mkdir(parents=True, exist_ok=True)
            paths.python_executable.write_text("", encoding="utf-8")

            def runner(command, **kwargs):  # type: ignore[no-untyped-def]
                spec = BackendJobSpec.read(Path(command[-1]))
                BackendJobResult(
                    spec.job_id,
                    spec.product,
                    "success",
                    outputs={"primary": spec.output_paths["primary"]},
                    product_metrics={"output_path": str(spec.output_paths["primary"]), "spatial_extent": [0, 1, 0, 1], "grid_resolution": 1.0, "crs": spec.crs},
                ).write(spec.result_path)
                return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

            service = BackendExecutionService(paths, verifier=lambda: ready_verification(paths), runner=runner)
            result = service.run_product("chm", ChmRequest(root / "plot.laz", root / "chm.tif", 1.0, "EPSG:32610"))

        self.assertTrue(result.success)
        self.assertEqual(result.outputs["primary"].name, "chm.tif")

    def test_adapter_prefers_pbm_when_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            class FakeService:
                def can_execute_processing(self):
                    return SimpleNamespace(ready=True, backend_python=Path("/backend/python"), message="ready")

                def run_product(self, product, request):  # type: ignore[no-untyped-def]
                    return BackendJobResult(product, product, "success", outputs={"primary": request.output_path}, product_metrics={"output_path": str(request.output_path), "spatial_extent": [0, 1, 0, 1], "grid_resolution": request.grid_resolution, "crs": request.crs})

            adapter = PyForestScanAdapter(backend_service_factory=FakeService)
            result = adapter.create_chm(ChmRequest(root / "plot.laz", root / "chm.tif", 1.0, "EPSG:32610"))

        self.assertEqual(adapter.selected_execution_backend(), "pbm_backend")
        self.assertEqual(result.output_path.name, "chm.tif")

    def test_forced_pbm_reports_missing_backend(self) -> None:
        class FakeService:
            def can_execute_processing(self):
                return SimpleNamespace(ready=False, backend_python=None, message="PBM backend is not ready")

        adapter = PyForestScanAdapter(execution_mode=EXECUTION_MODE_PBM_BACKEND, backend_service_factory=FakeService)
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(Exception) as ctx:
                adapter.create_chm(ChmRequest(Path(tmpdir) / "plot.laz", Path(tmpdir) / "chm.tif", 1.0, "EPSG:32610"))
        self.assertIn("PBM backend is not ready", str(ctx.exception))

    def test_batch_preflight_allows_pbm_backend_when_qgis_deps_missing(self) -> None:
        class FakeAdapter:
            def check_environment(self):
                return EnvironmentReport((), ReadinessStatus.NOT_READY, "missing qgis deps")

            def selected_execution_backend(self):
                return "pbm_backend"

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            lidar = root / "plot.laz"
            lidar.write_text("lidar", encoding="utf-8")
            request = BatchRequest(
                input_folder=root,
                output_folder=root / "out",
                recursive=False,
                datasets=(lidar,),
                settings=BatchProductSettings(products=(ProductType.CHM,), grid_resolution=1.0),
            )
            report = run_batch_preflight(request, adapter=FakeAdapter())  # type: ignore[arg-type]

        self.assertTrue(report.ready)
        self.assertTrue(any("PBM backend is READY" in warning for warning in report.warnings))


if __name__ == "__main__":
    unittest.main()
