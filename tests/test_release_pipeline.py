"""Tests for the versioned ZIP release pipeline."""

from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.package_plugin import (
    PLUGIN_DIR_NAME,
    package_plugin,
    read_metadata_version,
    read_version_info,
    versioned_zip_path,
)
from scripts.prepare_github_release import prepare_release, release_notes_path
from scripts.validate_release import _validate_changelog, validate_release


class ReleasePipelineTests(unittest.TestCase):
    """Validate Phase 23A release pipeline behavior."""

    def test_version_source_and_metadata_are_synchronized(self) -> None:
        version = read_version_info()

        self.assertEqual(version.plugin_version, "0.1.0-beta.1")
        self.assertEqual(read_metadata_version(), version.plugin_version)
        self.assertEqual(version.minimum_qgis_version, "3.28")
        self.assertIn(3, version.supported_qgis_major_versions)
        self.assertEqual(version.compatible_pbm_manifest_version, "1.0.0")

    def test_versioned_zip_name(self) -> None:
        self.assertEqual(versioned_zip_path("0.1.0-beta.1", Path("dist")).as_posix(), "dist/pyforestscan_qgis-v0.1.0-beta.1.zip")

    def test_package_plugin_writes_manifest_and_latest_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            dist = Path(tmpdir)
            version = read_version_info().plugin_version
            result = package_plugin(output_path=versioned_zip_path(version, dist), latest_path=dist / "pyforestscan_qgis.zip")
            manifest = json.loads(result.release_manifest_path.read_text(encoding="utf-8"))

            self.assertTrue(result.versioned_zip_path.exists())
            self.assertTrue((dist / "pyforestscan_qgis.zip").exists())
            self.assertEqual(manifest["plugin_version"], version)
            self.assertEqual(manifest["zip_filename"], result.versioned_zip_path.name)
            self.assertEqual(manifest["zip_sha256"], result.sha256)
            self.assertIn("python_file_count", manifest["python_module_summary"])

    def test_release_validation_passes_for_temp_dist(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            dist = Path(tmpdir)
            version = read_version_info().plugin_version
            package_plugin(output_path=versioned_zip_path(version, dist), latest_path=dist / "pyforestscan_qgis.zip")
            errors = validate_release(dist)
            manifest = json.loads((dist / "release_manifest.json").read_text(encoding="utf-8"))

            self.assertEqual(errors, [])
            self.assertEqual(manifest["validation_status"], "passed")
            self.assertEqual(manifest["docs_link_check_status"], "passed")

    def test_release_zip_excludes_tests_and_dev_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            dist = Path(tmpdir)
            version = read_version_info().plugin_version
            result = package_plugin(output_path=versioned_zip_path(version, dist), latest_path=dist / "pyforestscan_qgis.zip")
            with zipfile.ZipFile(result.versioned_zip_path) as archive:
                names = archive.namelist()

        self.assertIn(f"{PLUGIN_DIR_NAME}/backend_manifest.json", names)
        self.assertFalse(any("/tests/" in name or name.startswith("tests/") for name in names))
        self.assertFalse(any("__pycache__" in name or name.endswith(".pyc") for name in names))

    def test_changelog_contains_current_version(self) -> None:
        self.assertEqual(_validate_changelog(read_version_info().plugin_version), [])

    def test_prepare_github_release_dry_run_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            dist = Path(tmpdir)
            version = read_version_info().plugin_version
            package_plugin(output_path=versioned_zip_path(version, dist), latest_path=dist / "pyforestscan_qgis.zip")
            values = prepare_release(dist)

        self.assertEqual(values["tag_name"], "v0.1.0-beta.1")
        self.assertTrue(values["release_notes_path"].endswith("docs/releases/v0.1.0-beta.1.md"))
        self.assertTrue(values["zip_artifact_path"].endswith("pyforestscan_qgis-v0.1.0-beta.1.zip"))
        self.assertEqual(len(values["sha256"]), 64)
        self.assertEqual(release_notes_path(version).name, "v0.1.0-beta.1.md")


if __name__ == "__main__":
    unittest.main()
