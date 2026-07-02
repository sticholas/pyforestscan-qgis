"""Tests for PBM subprocess environment isolation."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.backend.installer import BACKEND_INSTALL_ENABLE_ENV, BackendInstaller, staging_paths
from pyforestscan_qgis.core.backend.models import BackendDependency, BackendPlatform, BackendRegistry, BackendStatus
from pyforestscan_qgis.core.backend.paths import resolve_backend_paths
from pyforestscan_qgis.core.backend.process_env import backend_pip_install_command, build_clean_subprocess_env


class BackendProcessEnvironmentTests(unittest.TestCase):
    """Validate clean subprocess environments without running QGIS."""

    def test_clean_env_removes_python_and_qgis_profile_paths(self) -> None:
        qgis_profile = r"C:\Users\Alala\AppData\Roaming\QGIS\QGIS3\profiles\default\python\dependencies\3.12"
        clean = build_clean_subprocess_env(
            {
                "PATH": f"C:\\Windows\\System32;{qgis_profile};C:\\Tools",
                "PYTHONPATH": qgis_profile,
                "PYTHONHOME": "C:\\QGIS\\apps\\Python312",
                "PYTHONUSERBASE": qgis_profile,
                "PIP_USER": "1",
                "TEMP": "C:\\Temp",
                "SystemRoot": "C:\\Windows",
            }
        )

        self.assertNotIn("PYTHONPATH", clean)
        self.assertNotIn("PYTHONHOME", clean)
        self.assertNotIn("PYTHONUSERBASE", clean)
        self.assertNotIn("PIP_USER", clean)
        self.assertEqual(clean["PYTHONNOUSERSITE"], "1")
        self.assertEqual(clean["PIP_NO_INPUT"], "1")
        self.assertNotIn("QGIS3", clean["PATH"])
        self.assertIn("C:\\Windows\\System32", clean["PATH"])

    def test_clean_env_prepends_requested_backend_paths(self) -> None:
        clean = build_clean_subprocess_env({"PATH": "/usr/bin"}, prepend_paths=(Path("/backend/bin"),))

        self.assertTrue(clean["PATH"].startswith("/backend/bin"))

    def test_micromamba_create_uses_clean_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            paths = resolve_backend_paths(backend_root=root / "backend", platform=BackendPlatform.LINUX)
            staged = staging_paths(paths)
            staged.micromamba_executable.parent.mkdir(parents=True, exist_ok=True)
            staged.micromamba_executable.write_text("micromamba", encoding="utf-8")
            spec = root / "environment.yml"
            spec.write_text("name: test\n", encoding="utf-8")
            calls = []

            def runner(command, **kwargs):  # type: ignore[no-untyped-def]
                calls.append((command, kwargs))
                return subprocess.CompletedProcess(command, 0, stdout="created", stderr="")

            installer = BackendInstaller(
                paths=paths,
                environ={BACKEND_INSTALL_ENABLE_ENV: "1", "PYTHONPATH": "/qgis/profile/python", "PATH": "/usr/bin"},
                runner=runner,
            )
            result = installer.create_environment(spec)

        self.assertTrue(result.success)
        command, kwargs = calls[0]
        self.assertEqual(command[0], str(staged.micromamba_executable))
        self.assertIn("env", kwargs)
        self.assertNotIn("PYTHONPATH", kwargs["env"])
        self.assertEqual(kwargs["env"]["PYTHONNOUSERSITE"], "1")

    def test_backend_pip_install_uses_backend_python_and_clean_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            paths = resolve_backend_paths(backend_root=root / "backend", platform=BackendPlatform.LINUX)
            staged = staging_paths(paths)
            staged.python_executable.parent.mkdir(parents=True, exist_ok=True)
            staged.python_executable.write_text("python", encoding="utf-8")
            calls = []
            registry = BackendRegistry(
                dependencies=(
                    BackendDependency("pyforestscan", "PyForestScan", "scientific", True, ">=0.4", "PyPI", python_import_name="pyforestscan"),
                )
            )

            def runner(command, **kwargs):  # type: ignore[no-untyped-def]
                calls.append((command, kwargs))
                return subprocess.CompletedProcess(command, 0, stdout="installed", stderr="")

            installer = BackendInstaller(
                paths=paths,
                environ={BACKEND_INSTALL_ENABLE_ENV: "1", "PYTHONUSERBASE": "/qgis/userbase", "PATH": "/usr/bin"},
                runner=runner,
                registry=registry,
            )
            result = installer.install_python_packages()

        self.assertTrue(result.success)
        command, kwargs = calls[0]
        self.assertEqual(command, backend_pip_install_command(staged.python_executable, ["pyforestscan>=0.4"]))
        self.assertNotIn("PYTHONUSERBASE", kwargs["env"])
        self.assertEqual(kwargs["env"]["PYTHONNOUSERSITE"], "1")

    def test_failed_staging_cleanup_removes_empty_env_prefix_for_retry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = resolve_backend_paths(backend_root=Path(tmpdir) / "backend", platform=BackendPlatform.LINUX)
            installer = BackendInstaller(paths=paths, environ={BACKEND_INSTALL_ENABLE_ENV: "1"})
            installer.prepare_staging()
            staged = staging_paths(paths)
            (staged.environment_path / "empty").mkdir(parents=True, exist_ok=True)
            rolled_back = installer.rollback_failed_install()

        self.assertTrue(rolled_back.success)
        self.assertEqual(rolled_back.status, BackendStatus.REPAIR_REQUIRED)
        self.assertFalse(staged.root.exists())


if __name__ == "__main__":
    unittest.main()
