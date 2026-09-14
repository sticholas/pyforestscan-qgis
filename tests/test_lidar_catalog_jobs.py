"""QGIS-free tests for responsive and resumable LiDAR catalog jobs."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pyforestscan_qgis.core.lidar_catalog import catalog_summary
from pyforestscan_qgis.core.lidar_catalog_jobs import (
    CatalogJobRunner,
    CatalogJobSpec,
    CatalogJobStage,
    CatalogJobStatus,
    catalog_job_lock_path,
    latest_catalog_job_state,
    stage_percent,
)
from pyforestscan_qgis.core.lidar_catalog_models import CatalogBuildOptions, CatalogThresholds, default_lidar_catalog_path
from pyforestscan_qgis.core.lidar_catalog_probe import quick_probe_lidar_repository, select_lidar_repository_path


def write_ept(path: Path, points: int = 10) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"bounds": [0, 0, 0, 5, 5, 5], "points": points, "srs": {"authority": "EPSG:32610"}}), encoding="utf-8")


class LidarCatalogResponsiveTests(unittest.TestCase):
    def test_path_selection_performs_no_walk_or_metadata_inspection(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with patch("os.walk", side_effect=AssertionError("os.walk should not run on selection")):
                status = select_lidar_repository_path(root)

        self.assertTrue(status.valid)
        self.assertFalse(status.catalog_exists)
        self.assertIn("No Catalog", status.message)

    def test_quick_probe_respects_item_limit_and_is_not_recursive(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for index in range(10):
                (root / f"dir_{index}").mkdir()
            write_ept(root / "ept.json")
            with patch("os.walk", side_effect=AssertionError("quick probe must not recurse")):
                probe = quick_probe_lidar_repository(root, max_entries=3, max_seconds=2.0)

        self.assertLessEqual(probe.inspected_entries, 3)
        self.assertTrue(probe.stopped_by_limit)
        self.assertIn("Build Catalog", probe.recommendation)

    def test_catalog_job_writes_progress_state_and_completes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_ept(root / "a" / "ept.json", points=100)
            progress = []
            spec = CatalogJobSpec.create("lidar_catalog_build", root)
            result = CatalogJobRunner(spec, progress_callback=progress.append).run()
            latest = latest_catalog_job_state(spec.catalog_path)

        self.assertFalse(result.cancelled)
        self.assertEqual(latest.status, CatalogJobStatus.COMPLETED)
        self.assertEqual(latest.stage, CatalogJobStage.READY)
        self.assertTrue(any(item.stage in {CatalogJobStage.PREPARING, CatalogJobStage.READING_METADATA, CatalogJobStage.WRITING_INDEX} for item in progress))

    def test_single_writer_lock_blocks_second_job(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            spec = CatalogJobSpec.create("lidar_catalog_build", root)
            lock = catalog_job_lock_path(spec.catalog_path)
            lock.parent.mkdir(parents=True, exist_ok=True)
            lock.write_text("locked", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                CatalogJobRunner(spec).run()

    def test_pause_after_current_chunk_marks_interrupted_and_resume_skips_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_ept(root / "a" / "ept.json")
            write_ept(root / "b" / "ept.json")
            options = CatalogBuildOptions(thresholds=CatalogThresholds(batch_commit_size=1, checkpoint_interval=1))
            spec = CatalogJobSpec.create("lidar_catalog_build", root, options=options)
            calls = {"count": 0}
            def pause_after_first() -> bool:
                calls["count"] += 1
                return calls["count"] > 1
            interrupted = CatalogJobRunner(spec, pause_callback=pause_after_first).run()
            resume = CatalogJobRunner(CatalogJobSpec.create("lidar_catalog_resume", root, spec.catalog_path, options=options)).run()
            summary = catalog_summary(spec.catalog_path, root)

        self.assertTrue(interrupted.cancelled)
        self.assertEqual(summary.indexed_count, 2)
        self.assertGreaterEqual(resume.unchanged_count, 1)

    def test_incremental_update_added_modified_deleted_and_error_retry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            good = root / "good" / "ept.json"
            bad = root / "bad.laz"
            write_ept(good, points=10)
            bad.write_bytes(b"")
            first = CatalogJobRunner(CatalogJobSpec.create("lidar_catalog_build", root)).run()
            bad.write_bytes(b"LASF" + (b"\0" * 371))
            write_ept(root / "new" / "ept.json", points=20)
            good.unlink()
            second = CatalogJobRunner(CatalogJobSpec.create("lidar_catalog_update", root, first.catalog_path)).run()
            summary = catalog_summary(first.catalog_path, root)

        self.assertEqual(first.error_count, 1)
        self.assertGreaterEqual(second.indexed_count, 1)
        self.assertEqual(second.deleted_count, 1)
        self.assertGreaterEqual(summary.source_count, 2)

    def test_stage_percent_is_indeterminate_when_total_unknown(self) -> None:
        self.assertEqual(stage_percent(CatalogJobStage.PREPARING, total_known=False), 5)
        self.assertIsNone(stage_percent(CatalogJobStage.DISCOVERING, total_known=False))
        self.assertEqual(stage_percent(CatalogJobStage.DETECTING_DELETED, total_known=False), 88)
        self.assertEqual(stage_percent(CatalogJobStage.READY, total_known=False), 100)

    def test_static_ui_has_explicit_actions_and_no_selection_scan_hook(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")
        batch = source[source.index("class BatchPage"):]
        self.assertIn("editingFinished.connect(self.use_polygon_repository_path)", batch)
        self.assertIn("Prepare Repository", batch)
        self.assertIn("Quick Probe", batch)
        self.assertIn("Pause After Current Chunk", batch)
        self.assertIn("Resume Catalog Build", batch)
        self.assertIn("No repository scan was performed", batch)
        self.assertNotIn("build_lidar_catalog(root", batch)


if __name__ == "__main__":
    unittest.main()
