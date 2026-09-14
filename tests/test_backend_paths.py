"""Tests for backend path resolution."""

from __future__ import annotations

import unittest
from pathlib import Path

from pyforestscan_qgis.core.backend.models import BackendPlatform
from pyforestscan_qgis.core.backend.paths import default_backend_root, detect_backend_platform, resolve_backend_paths


class BackendPathTests(unittest.TestCase):
    """Validate user-local backend path selection."""

    def test_platform_detection(self) -> None:
        self.assertEqual(detect_backend_platform("Windows"), BackendPlatform.WINDOWS)
        self.assertEqual(detect_backend_platform("Linux"), BackendPlatform.LINUX)
        self.assertEqual(detect_backend_platform("Darwin"), BackendPlatform.MACOS)
        self.assertEqual(detect_backend_platform("Plan9"), BackendPlatform.UNKNOWN)

    def test_windows_backend_root_uses_local_app_data(self) -> None:
        root = default_backend_root(
            BackendPlatform.WINDOWS,
            environ={"LOCALAPPDATA": "C:/Users/Test/AppData/Local"},
            home=Path("C:/Users/Test"),
        )
        self.assertEqual(root.as_posix(), "C:/Users/Test/AppData/Local/PyForestScan/backend")

    def test_linux_backend_root_is_user_local(self) -> None:
        root = default_backend_root(BackendPlatform.LINUX, environ={}, home=Path("/home/tester"))
        self.assertEqual(root, Path("/home/tester/.local/share/PyForestScan/backend"))

    def test_macos_backend_root_is_application_support(self) -> None:
        root = default_backend_root(BackendPlatform.MACOS, environ={}, home=Path("/Users/tester"))
        self.assertEqual(root, Path("/Users/tester/Library/Application Support/PyForestScan/backend"))

    def test_phase_22c_downloads_and_staging_locations(self) -> None:
        paths = resolve_backend_paths(backend_root=Path("/tmp/pfs-backend"), platform=BackendPlatform.LINUX)
        self.assertEqual(paths.downloads_dir, paths.backend_root / "downloads")
        self.assertEqual(paths.staging_dir, paths.backend_root / "staging")

    def test_resolved_paths_stay_under_backend_root(self) -> None:
        paths = resolve_backend_paths(backend_root=Path("/tmp/pfs-backend"), platform=BackendPlatform.LINUX)
        for path in (
            paths.micromamba_executable,
            paths.environment_path,
            paths.python_executable,
            paths.logs_dir,
            paths.config_file,
            paths.registry_file,
            paths.cache_dir,
            paths.downloads_dir,
            paths.staging_dir,
            paths.scripts_dir,
        ):
            self.assertTrue(path.is_relative_to(paths.backend_root))


if __name__ == "__main__":
    unittest.main()
