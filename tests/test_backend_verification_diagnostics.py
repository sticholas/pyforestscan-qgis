"""Tests for actionable PBM verification diagnostics."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.backend.installer import staged_backend_paths, staging_paths

ROOT = Path(__file__).resolve().parents[1]
from pyforestscan_qgis.core.backend.manifest import load_backend_manifest
from pyforestscan_qgis.core.backend.models import (
    BackendCheckResult,
    BackendDependency,
    BackendPlatform,
    BackendRegistry,
    BackendState,
    BackendStatus,
    BackendVerificationResult,
    DependencyVerificationStatus,
)
from pyforestscan_qgis.core.backend.paths import resolve_backend_paths
from pyforestscan_qgis.core.backend.registry import default_backend_registry
from pyforestscan_qgis.core.backend.transaction import BackendInstallTransaction
from pyforestscan_qgis.core.backend.verification import failed_check_summary, format_verification_result, python_import_command, verify_backend


class BackendVerificationDiagnosticsTests(unittest.TestCase):
    """Validate per-check command diagnostics and user-facing failure summaries."""

    def test_staged_verification_includes_failed_import_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = resolve_backend_paths(backend_root=Path(tmpdir) / "backend", platform=BackendPlatform.LINUX)
            staged = staging_paths(paths)
            staged.micromamba_executable.parent.mkdir(parents=True, exist_ok=True)
            staged.micromamba_executable.write_text("micromamba", encoding="utf-8")
            staged.environment_path.mkdir(parents=True, exist_ok=True)
            staged.python_executable.parent.mkdir(parents=True, exist_ok=True)
            staged.python_executable.symlink_to(Path(sys.executable))
            registry = BackendRegistry(
                dependencies=(
                    BackendDependency(
                        "python-pdal",
                        "PDAL Python bindings",
                        "python package",
                        True,
                        "compatible",
                        "conda-forge",
                        python_import_name="__definitely_missing_pbm_module__",
                    ),
                )
            )
            result = verify_backend(staged_backend_paths(paths), registry, require_config=False)

        failed = {check.name: check for check in result.checks if check.status is DependencyVerificationStatus.FAIL}
        self.assertIn("PDAL Python bindings", failed)
        self.assertIn("import __definitely_missing_pbm_module__ failed", failed["PDAL Python bindings"].message)
        self.assertIn("No module named", failed["PDAL Python bindings"].stderr_preview)
        self.assertIn("-c", failed["PDAL Python bindings"].command)
        self.assertEqual(failed["PDAL Python bindings"].executable, staged.python_executable)

    def test_install_failure_message_includes_failed_dependency_name(self) -> None:
        class FakeInstaller:
            def require_enabled(self, operation):  # type: ignore[no-untyped-def]
                return None

            def prepare_staging(self):
                return _operation("prepare_staging")

            def download_micromamba(self, policy=None):
                return type("Download", (), {"success": True, "message": "downloaded", "path": Path("artifact")})()

            def verify_micromamba_download(self, policy=None):
                return type("Checksum", (), {"message": "ok", "passed": lambda self: True})()

            def extract_micromamba(self, policy=None):
                return _operation("extract_micromamba")

            def create_environment(self, spec_file=None):
                return _operation("create_environment")

            def install_python_packages(self):
                return _operation("install_python_packages")

            def verify_environment(self):
                return BackendVerificationResult(
                    BackendStatus.REPAIR_REQUIRED,
                    BackendState(BackendStatus.REPAIR_REQUIRED, BackendPlatform.LINUX, Path("/backend/staging"), True, True, True, True, "repair"),
                    (
                        BackendCheckResult(
                            "PDAL Python bindings",
                            DependencyVerificationStatus.FAIL,
                            "import pdal failed: No module named pdal",
                            command=("/backend/staging/env/bin/python", "-c", "import pdal"),
                            executable=Path("/backend/staging/env/bin/python"),
                            stderr_preview="ModuleNotFoundError: No module named 'pdal'",
                        ),
                    ),
                    BackendRegistry(()),
                    "Backend verification failed",
                )

            def rollback_failed_install(self):
                return _operation("rollback_failed_install", status=BackendStatus.REPAIR_REQUIRED)

        result = BackendInstallTransaction(FakeInstaller()).run()

        self.assertFalse(result.success)
        self.assertIn("PDAL Python bindings", result.message)
        self.assertIn("No module named", result.message)

    def test_python_import_command_construction(self) -> None:
        command = python_import_command(Path("/backend/env/python.exe"), "pdal")

        self.assertEqual(command[0], "/backend/env/python.exe")
        self.assertEqual(command[1], "-c")
        self.assertIn("import_module('pdal')", command[2])

    def test_pyforestscan_import_command_smokes_public_modules(self) -> None:
        command = python_import_command(Path("/backend/env/python.exe"), "pyforestscan")

        self.assertIn("pyforestscan.calculate", command[2])
        self.assertIn("pyforestscan.filters", command[2])
        self.assertIn("pyforestscan.handlers", command[2])
        self.assertIn("pyforestscan.process", command[2])
        self.assertIn("pyforestscan.visualize", command[2])
        self.assertIn("pyforestscan_modules=", command[2])

    def test_package_import_mapping_consistency(self) -> None:
        registry = default_backend_registry()
        required = {dependency.name: dependency for dependency in registry.required_dependencies()}
        manifest = load_backend_manifest()
        manifest_packages = {package.name: package for package in manifest.required_packages()}
        env_text = "\n".join((ROOT / name).read_text(encoding="utf-8") for name in (
            "backend_specs/environment.yml",
            "backend_specs/environment.windows.yml",
            "backend_specs/environment.linux.yml",
            "backend_specs/environment.macos.yml",
        ))

        self.assertEqual(required["python-pdal"].python_import_name, "pdal")
        self.assertEqual(required["gdal"].python_import_name, "osgeo.gdal")
        self.assertEqual(required["rasterio"].python_import_name, "rasterio")
        self.assertEqual(required["numpy"].python_import_name, "numpy")
        self.assertEqual(required["scipy"].python_import_name, "scipy")
        self.assertEqual(required["geopandas"].python_import_name, "geopandas")
        self.assertEqual(required["matplotlib"].python_import_name, "matplotlib")
        self.assertEqual(manifest_packages["pyforestscan"].source.lower(), "pypi")
        self.assertIn("python-pdal", env_text)
        self.assertIn("gdal", env_text)
        self.assertIn("scipy", env_text)
        self.assertIn("geopandas", env_text)
        self.assertIn("matplotlib", env_text)
        self.assertNotIn("- pyforestscan", env_text)

    def test_diagnostic_formatting_includes_staged_section(self) -> None:
        script_path = ROOT / "scripts" / "pbm_backend_diagnostics.py"
        spec = importlib.util.spec_from_file_location("pbm_backend_diagnostics", script_path)
        module = importlib.util.module_from_spec(spec)
        assert spec is not None and spec.loader is not None
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = resolve_backend_paths(backend_root=Path(tmpdir) / "backend", platform=BackendPlatform.LINUX)
            paths.staging_dir.mkdir(parents=True)
            text = module.collect_backend_diagnostics(paths.backend_root)

        self.assertIn("PyForestScan PBM Backend Diagnostics", text)
        self.assertIn("Staged Backend Verification", text)
        self.assertIn("Final Backend Verification", text)

    def test_format_verification_result_includes_command_output(self) -> None:
        result = BackendVerificationResult(
            BackendStatus.REPAIR_REQUIRED,
            BackendState(BackendStatus.REPAIR_REQUIRED, BackendPlatform.LINUX, Path("/backend"), True, True, True, True, "repair"),
            (
                BackendCheckResult(
                    "PDAL",
                    DependencyVerificationStatus.FAIL,
                    "pdal command failed",
                    command=("/backend/env/bin/pdal", "--version"),
                    executable=Path("/backend/env/bin/pdal"),
                    stdout_preview="",
                    stderr_preview="pdal: not found",
                ),
            ),
            BackendRegistry(()),
            "failed",
        )
        text = format_verification_result(result)

        self.assertIn("Command: /backend/env/bin/pdal --version", text)
        self.assertIn("stderr: pdal: not found", text)
        self.assertIn("PDAL", failed_check_summary(result))


def _operation(name: str, status: BackendStatus = BackendStatus.INSTALLING):
    from pyforestscan_qgis.core.backend.models import BackendOperationResult

    return BackendOperationResult(name, status, True, f"{name} ok", True)


if __name__ == "__main__":
    unittest.main()
