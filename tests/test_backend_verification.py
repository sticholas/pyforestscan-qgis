"""Tests for backend verification."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.backend.config import load_backend_config, planned_backend_config, save_backend_config
from pyforestscan_qgis.core.backend.models import BackendStatus, DependencyVerificationStatus
from pyforestscan_qgis.core.backend.paths import resolve_backend_paths
from pyforestscan_qgis.core.backend.verification import format_verification_result, verify_backend


class BackendVerificationTests(unittest.TestCase):
    """Validate safe verification of missing and partial backends."""

    def test_missing_backend_does_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = resolve_backend_paths(backend_root=Path(tmpdir) / "missing")
            result = verify_backend(paths)
        self.assertEqual(result.status, BackendStatus.NOT_INSTALLED)
        self.assertIn("not installed", result.summary.lower())

    def test_partial_backend_requires_repair(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "backend"
            paths = resolve_backend_paths(backend_root=root)
            paths.environment_path.mkdir(parents=True)
            result = verify_backend(paths)
        self.assertEqual(result.status, BackendStatus.REPAIR_REQUIRED)
        self.assertTrue(any(check.status is DependencyVerificationStatus.FAIL for check in result.checks))

    def test_config_serialization_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = resolve_backend_paths(backend_root=Path(tmpdir) / "backend")
            config = planned_backend_config(paths)
            save_backend_config(config, paths.config_file)
            restored = load_backend_config(paths.config_file)
        self.assertIsNotNone(restored)
        self.assertEqual(restored.backend_root, config.backend_root)
        self.assertEqual(restored.registry.dependency_names(), config.registry.dependency_names())

    def test_report_formatting(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = verify_backend(resolve_backend_paths(backend_root=Path(tmpdir) / "backend"))
        text = format_verification_result(result)
        self.assertIn("PyForestScan Backend Manager Verification", text)
        self.assertIn("Backend root:", text)


if __name__ == "__main__":
    unittest.main()
