"""Tests for conda geospatial backend environment discovery."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pyforestscan_qgis.core.backend.models import BackendDependency, BackendPlatform, BackendRegistry, DependencyVerificationStatus
from pyforestscan_qgis.core.backend.paths import resolve_backend_paths
from pyforestscan_qgis.core.backend.process_env import build_clean_subprocess_env, conda_environment_path_entries
from pyforestscan_qgis.core.backend.verification import _dependency_path, verify_backend


class BackendGeospatialEnvironmentTests(unittest.TestCase):
    """Validate Windows conda geospatial executable and DLL path handling."""

    def test_windows_conda_path_entries_include_library_bin_for_dlls(self) -> None:
        env = Path(r"C:\Users\Alala\AppData\Local\PyForestScan\backend\env")
        entries = conda_environment_path_entries(env, "windows")

        self.assertEqual(entries[0], env)
        self.assertEqual(entries[1], env / "Scripts")
        self.assertEqual(entries[2], env / "Library" / "bin")
        clean = build_clean_subprocess_env({"PATH": r"C:\Windows\System32"}, prepend_paths=entries)
        path_value = clean["PATH"]
        self.assertLess(path_value.index(str(env)), path_value.index(str(env / "Library" / "bin")))
        self.assertIn(str(env / "Library" / "bin"), path_value)

    def test_windows_dependency_path_finds_pdal_in_library_bin(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = resolve_backend_paths(backend_root=Path(tmpdir) / "backend", platform=BackendPlatform.WINDOWS)
            pdal = paths.environment_path / "Library" / "bin" / "pdal.exe"
            pdal.parent.mkdir(parents=True, exist_ok=True)
            pdal.write_text("pdal", encoding="utf-8")
            dependency = BackendDependency("pdal", "PDAL", "geospatial runtime", True, executable_name="pdal", verification_command=("--version",))

            found = _dependency_path(dependency, paths)

        self.assertEqual(found, pdal)

    def test_windows_dependency_path_finds_gdalinfo_in_library_bin(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = resolve_backend_paths(backend_root=Path(tmpdir) / "backend", platform=BackendPlatform.WINDOWS)
            gdalinfo = paths.environment_path / "Library" / "bin" / "gdalinfo.exe"
            gdalinfo.parent.mkdir(parents=True, exist_ok=True)
            gdalinfo.write_text("gdalinfo", encoding="utf-8")
            dependency = BackendDependency("gdal", "GDAL", "geospatial runtime", True, executable_name="gdalinfo", verification_command=("--version",))

            found = _dependency_path(dependency, paths)

        self.assertEqual(found, gdalinfo)

    def test_import_verification_uses_backend_conda_dll_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = resolve_backend_paths(backend_root=Path(tmpdir) / "backend", platform=BackendPlatform.WINDOWS)
            paths.backend_root.mkdir(parents=True, exist_ok=True)
            paths.environment_path.mkdir(parents=True, exist_ok=True)
            paths.python_executable.parent.mkdir(parents=True, exist_ok=True)
            paths.python_executable.write_text("python", encoding="utf-8")
            registry = BackendRegistry(
                dependencies=(BackendDependency("rasterio", "rasterio", "python package", True, source="conda-forge", python_import_name="rasterio"),)
            )
            captured_env = {}

            def fake_run(command, **kwargs):  # type: ignore[no-untyped-def]
                captured_env.update(kwargs["env"])
                return subprocess.CompletedProcess(command, 0, stdout="1.3.9\n", stderr="")

            with patch("pyforestscan_qgis.core.backend.verification.subprocess.run", fake_run):
                result = verify_backend(paths, registry, require_config=False)

        rasterio = next(check for check in result.checks if check.name == "rasterio")
        self.assertIs(rasterio.status, DependencyVerificationStatus.PASS)
        self.assertIn(str(paths.environment_path / "Library" / "bin"), captured_env["PATH"])
        self.assertIn(str(paths.environment_path / "Scripts"), captured_env["PATH"])

    def test_environment_specs_keep_geospatial_stack_on_conda_forge(self) -> None:
        text = "\n".join((Path(__file__).resolve().parents[1] / name).read_text(encoding="utf-8") for name in (
            "backend_specs/environment.yml",
            "backend_specs/environment.windows.yml",
            "backend_specs/environment.linux.yml",
            "backend_specs/environment.macos.yml",
        ))

        self.assertIn("  - pdal", text)
        self.assertIn("  - python-pdal", text)
        self.assertIn("  - gdal", text)
        self.assertIn("  - libgdal", text)
        self.assertIn("  - rasterio", text)
        self.assertNotIn("pip:\n", text)
        self.assertNotIn("GDAL", text.split("  - pip")[-1])
        self.assertNotIn("rasterio", text.split("  - pip")[-1])


if __name__ == "__main__":
    unittest.main()
