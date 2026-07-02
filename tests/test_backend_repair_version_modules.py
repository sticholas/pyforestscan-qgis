"""Tests for PBM repair, versioning, and future module architecture."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.backend.config import save_backend_config
from pyforestscan_qgis.core.backend.manifest import backend_manifest_from_dict, load_backend_manifest
from pyforestscan_qgis.core.backend.models import BackendStatus
from pyforestscan_qgis.core.backend.modules import default_backend_module_registry
from pyforestscan_qgis.core.backend.paths import resolve_backend_paths
from pyforestscan_qgis.core.backend.repair import plan_backend_repair
from pyforestscan_qgis.core.backend.version_manager import BackendVersionManager


class BackendRepairVersionModuleTests(unittest.TestCase):
    """Validate repair planning, version checks, and module placeholders."""

    def test_repair_plan_detects_missing_executable_and_python(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = resolve_backend_paths(backend_root=Path(tmpdir) / "backend")
            plan = plan_backend_repair(paths, load_backend_manifest())

        codes = {issue.code for issue in plan.issues}
        self.assertEqual(plan.status, BackendStatus.REPAIR_REQUIRED)
        self.assertIn("missing_executable", codes)
        self.assertIn("missing_python", codes)
        self.assertTrue(all(action.developer_only for action in plan.actions))

    def test_repair_plan_detects_corrupt_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = resolve_backend_paths(backend_root=Path(tmpdir) / "backend")
            paths.backend_root.mkdir(parents=True)
            paths.config_file.write_text("not-json", encoding="utf-8")
            plan = plan_backend_repair(paths, load_backend_manifest())

        self.assertIn("corrupt_config", {issue.code for issue in plan.issues})

    def test_version_manager_detects_old_plugin(self) -> None:
        manifest = load_backend_manifest()
        manager = BackendVersionManager("0.0.1")
        result = manager.check_manifest(manifest)

        self.assertFalse(result.compatible)
        self.assertTrue(result.errors)

    def test_version_manager_detects_migration_need(self) -> None:
        manifest = load_backend_manifest()
        manager = BackendVersionManager("0.1.0")

        self.assertTrue(manager.needs_migration("0.0.1", manifest))
        self.assertFalse(manager.can_downgrade("2.0.0", "1.0.0"))

    def test_module_registry_contains_future_modules(self) -> None:
        registry = default_backend_module_registry()
        names = registry.names()

        self.assertIn("pdal", names)
        self.assertIn("pytorch", names)
        self.assertIn("sam", names)
        self.assertIn("whiteboxtools", names)
        self.assertIn("cloudcompare", names)
        self.assertIn("potree", names)

    def test_backend_mismatch_uses_manifest_bounds(self) -> None:
        data = {
            "schema_version": 1,
            "backend_version": "1.0.0",
            "environment_version": "test",
            "micromamba_version": "latest",
            "python_version": ">=3.12,<3.13",
            "minimum_plugin_version": "0.5.0",
            "channels": [{"name": "conda-forge"}],
            "artifacts": {"micromamba": {"version": "latest", "checksum_required": True, "hashes": {"linux": {"sha256": "abc"}}, "sources": []}},
            "packages": [{"name": "python", "version_spec": ">=3.12,<3.13", "source": "conda-forge", "required": True, "category": "runtime"}],
        }
        manifest = backend_manifest_from_dict(data)
        result = BackendVersionManager("0.1.0").check_manifest(manifest)

        self.assertFalse(result.compatible)
        self.assertIn("older", result.errors[0])


if __name__ == "__main__":
    unittest.main()
