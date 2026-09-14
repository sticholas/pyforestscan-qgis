"""QGIS-free regression coverage for packaged identity and clean profile installs."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from pyforestscan_qgis.core.build_identity import (
    CRITICAL_MODULES,
    PLUGIN_MIXED_INSTALL,
    PLUGIN_VALID,
    inspect_plugin_installation,
)
from pyforestscan_qgis.core.launch_attempt import append_attempt_stage, create_launch_attempt
from scripts.install_qgis_plugin import compare_zip_to_install, install_plugin


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Phase32EBuildIdentityTests(unittest.TestCase):
    def _packaged_tree(self, root: Path, build_id: str = "build-b") -> None:
        for index, relative in enumerate(CRITICAL_MODULES):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"module-{index}\n", encoding="utf-8")
        hashes = {relative: _digest(root / relative) for relative in CRITICAL_MODULES}
        (root / "build_info.json").write_text(json.dumps({
            "version": "0.1.0-beta.3",
            "git_commit": "005da242",
            "build_id": build_id,
            "package_identity": "package-b",
            "processing_engine_plugin_build_id": "engine-b",
            "built_at": "2026-08-28T00:00:00Z",
            "critical_module_hashes": hashes,
        }), encoding="utf-8")

    def test_packaged_installation_reports_current_then_mixed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "pyforestscan_qgis"
            self._packaged_tree(root)
            self.assertEqual(inspect_plugin_installation(root).status, PLUGIN_VALID)
            (root / "core/adapter.py").write_text("stale\n", encoding="utf-8")
            result = inspect_plugin_installation(root)
            self.assertEqual(result.status, PLUGIN_MIXED_INSTALL)
            self.assertIn("core/adapter.py", result.mismatches)
            self.assertIn("Reinstall the plugin ZIP", result.message)

    def test_clean_profile_install_replaces_obsolete_files_and_matches_zip(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            source = base / "source" / "pyforestscan_qgis"
            self._packaged_tree(source)
            zip_path = base / "plugin.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                for path in source.rglob("*"):
                    if path.is_file():
                        archive.write(path, Path("pyforestscan_qgis") / path.relative_to(source))
            destination = base / "profiles/default/python/plugins/pyforestscan_qgis"
            destination.mkdir(parents=True)
            (destination / "obsolete.py").write_text("old", encoding="utf-8")
            installed = install_plugin(zip_path, destination)
            self.assertEqual(installed["status"], PLUGIN_VALID)
            comparison = compare_zip_to_install(zip_path, destination)
            self.assertEqual(comparison["missing_files"], [])
            self.assertEqual(comparison["extra_files"], [])
            self.assertEqual(comparison["differing_files"], [])

    def test_each_process_attempt_is_unique_and_preserves_failure_history(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch("pyforestscan_qgis.core.launch_attempt._global_latest_attempt_path", return_value=root / "global_latest.json"):
                first = create_launch_attempt(root, ("pai", "fhd"), "plan")
                append_attempt_stage(first, "FAILED", reason="guard")
                second = create_launch_attempt(root, ("pai", "fhd"), "plan")
            self.assertNotEqual(first.attempt_id, second.attempt_id)
            self.assertTrue(first.trace_path.is_file())
            latest = json.loads((root / "latest_attempt.json").read_text(encoding="utf-8"))
            self.assertEqual(latest["attempt_id"], second.attempt_id)
            first_payload = json.loads(first.trace_path.read_text(encoding="utf-8"))
            self.assertEqual(first_payload["outcome"], "FAILED")

    def test_polygon_process_creates_attempt_before_engine_guard(self):
        source = (Path(__file__).resolve().parents[1] / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")
        method = source[source.index("    def _run_polygon_batch"):source.index("    def _build_batch_request", source.index("    def _run_polygon_batch"))]
        self.assertLess(method.index("create_launch_attempt("), method.index("validate_runtime_token_for_launch("))
        self.assertIn("PLUGIN_INSTALLATION", method)
        self.assertIn("Do not repair the Processing Engine", method)


if __name__ == "__main__":
    unittest.main()
