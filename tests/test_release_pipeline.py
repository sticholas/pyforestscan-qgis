"""Tests for the versioned ZIP release pipeline."""

from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from scripts.package_plugin import (
    PLUGIN_DIR_NAME,
    _copy_clean_tree,
    assert_clean_repository,
    package_plugin,
    read_metadata_version,
    read_version_info,
    versioned_zip_path,
    verify_package_source,
)
from scripts.prepare_github_release import prepare_release, release_notes_path
from scripts.validate_release import _validate_changelog, validate_release


class ReleasePipelineTests(unittest.TestCase):
    """Validate Phase 23A release pipeline behavior."""

    def test_version_source_and_metadata_are_synchronized(self) -> None:
        version = read_version_info()

        self.assertEqual(version.plugin_version, "0.1.0-beta.3")
        self.assertEqual(read_metadata_version(), version.plugin_version)
        self.assertEqual(version.minimum_qgis_version, "3.28")
        self.assertIn(3, version.supported_qgis_major_versions)
        self.assertEqual(version.compatible_pbm_manifest_version, "1.0.0")

    def test_versioned_zip_name(self) -> None:
        self.assertEqual(versioned_zip_path("0.1.0-beta.3", Path("dist")).as_posix(), "dist/pyforestscan_qgis-v0.1.0-beta.3.zip")

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

    def test_package_matches_the_complete_included_source_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            dist = Path(tmpdir)
            version = read_version_info().plugin_version
            result = package_plugin(output_path=versioned_zip_path(version, dist), latest_path=None)
            verification = verify_package_source(result.versioned_zip_path, require_clean=False)

        self.assertEqual(verification["status"], "PASS")
        self.assertEqual(verification["missing_files"], [])
        self.assertEqual(verification["unexpected_files"], [])
        self.assertEqual(verification["hash_mismatches"], [])

    def test_release_packaging_rejects_a_dirty_repository(self) -> None:
        with mock.patch("scripts.package_plugin._git_status", return_value=" M source.py"):
            with self.assertRaisesRegex(RuntimeError, "clean Git worktree"):
                assert_clean_repository()

    def test_clean_stage_removes_retired_and_deleted_modules(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "source"
            destination = root / "stage"
            source.mkdir()
            destination.mkdir()
            (source / "current.py").write_text("CURRENT = True\n", encoding="utf-8")
            (destination / "legacy_module.py").write_text("RETIRED_STAGE_MARKER\n", encoding="utf-8")
            _copy_clean_tree(source, destination)

            self.assertTrue((destination / "current.py").is_file())
            self.assertFalse((destination / "legacy_module.py").exists())

    def test_changelog_contains_current_version(self) -> None:
        self.assertEqual(_validate_changelog(read_version_info().plugin_version), [])

    def test_prepare_github_release_dry_run_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            dist = Path(tmpdir)
            version = read_version_info().plugin_version
            package_plugin(output_path=versioned_zip_path(version, dist), latest_path=dist / "pyforestscan_qgis.zip")
            values = prepare_release(dist)

        self.assertEqual(values["tag_name"], "v0.1.0-beta.3")
        self.assertTrue(values["release_notes_path"].endswith("docs/releases/v0.1.0-beta.3.md"))
        self.assertTrue(values["zip_artifact_path"].endswith("pyforestscan_qgis-v0.1.0-beta.3.zip"))
        self.assertEqual(len(values["sha256"]), 64)
        self.assertEqual(release_notes_path(version).name, "v0.1.0-beta.3.md")

    def test_clean_machine_release_docs_exist(self) -> None:
        root = Path(__file__).resolve().parents[1]
        smoke = root / "docs/releases/CLEAN_MACHINE_SMOKE_TEST.md"
        matrix = root / "docs/releases/DEPENDENCY_STATE_MATRIX.md"

        self.assertIn("dist/pyforestscan_qgis-v0.1.0-beta.2.zip", smoke.read_text(encoding="utf-8"))
        self.assertIn("No backend / no QGIS deps", matrix.read_text(encoding="utf-8"))
        self.assertIn("Backend auto-install ready", smoke.read_text(encoding="utf-8"))


    def test_release_candidate_gate_docs_are_linked(self) -> None:
        root = Path(__file__).resolve().parents[1]
        release_docs = root / "docs/releases"
        roadmap = release_docs / "RELEASE_ROADMAP.md"
        checklist = release_docs / "RC1_CHECKLIST.md"
        qa_script = release_docs / "RC1_MANUAL_QA_SCRIPT.md"
        triage = release_docs / "RELEASE_TRIAGE_POLICY.md"
        qa_results = release_docs / "RC1_QA_RESULTS.md"
        blockers = release_docs / "RC1_BLOCKERS.md"

        for doc in (roadmap, checklist, qa_script, triage, qa_results, blockers):
            self.assertTrue(doc.exists(), doc)

        roadmap_text = roadmap.read_text(encoding="utf-8")
        checklist_text = checklist.read_text(encoding="utf-8")
        qa_text = qa_script.read_text(encoding="utf-8")
        triage_text = triage.read_text(encoding="utf-8")
        qa_results_text = qa_results.read_text(encoding="utf-8")
        blockers_text = blockers.read_text(encoding="utf-8")
        docs_index = (root / "docs/README.md").read_text(encoding="utf-8")
        releases_index = (release_docs / "README.md").read_text(encoding="utf-8")
        readme = (root / "README.md").read_text(encoding="utf-8")

        self.assertIn("RC1 Definition", roadmap_text)
        self.assertIn("RC2 Definition", roadmap_text)
        self.assertIn("v1.0 Definition", roadmap_text)
        self.assertIn("PBM installs on clean Windows QGIS", checklist_text)
        self.assertIn("Advanced Toolbox", qa_text)
        self.assertIn("Blocker", triage_text)
        self.assertIn("Critical", triage_text)
        self.assertIn("RC1 is **not ready for tag/release draft**", qa_results_text)
        self.assertIn("Clean Windows/QGIS ZIP Install Evidence Missing", blockers_text)
        for linked_name in (
            "RELEASE_ROADMAP.md",
            "RC1_CHECKLIST.md",
            "RC1_MANUAL_QA_SCRIPT.md",
            "RC1_QA_RESULTS.md",
            "RC1_BLOCKERS.md",
            "RELEASE_TRIAGE_POLICY.md",
        ):
            self.assertIn(linked_name, docs_index)
            self.assertIn(linked_name, releases_index)
        self.assertIn("Release Roadmap", readme)


if __name__ == "__main__":
    unittest.main()
