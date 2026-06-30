"""Tests for batch preflight, manifest, and resume reliability."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.batch import BatchProductSettings, BatchRequest, batch_run_context
from pyforestscan_qgis.core.batch_manifest import completed_dataset_paths, create_manifest, load_manifest, update_manifest_item, write_manifest
from pyforestscan_qgis.core.batch_preflight import recommend_batch_workers, run_batch_preflight
from pyforestscan_qgis.core.batch_runner import BatchRunner
from pyforestscan_qgis.core.external_worker import EXTERNAL_WORKER_MODE
from pyforestscan_qgis.core.types import ProductType


class ReadyAdapter:
    """Environment-ready adapter stub."""

    def check_environment(self) -> object:
        class Readiness:
            value = "READY"

        class Report:
            readiness = Readiness()

        return Report()


class NotReadyAdapter:
    """Environment-not-ready adapter stub."""

    def check_environment(self) -> object:
        class Readiness:
            value = "NOT READY"

        class Report:
            readiness = Readiness()

        return Report()


class FailingInspectionAdapter(ReadyAdapter):
    """Adapter that fails every dataset inspection."""

    def inspect_dataset(self, _path: Path) -> object:
        raise RuntimeError("inspection failed")


class BatchReliabilityTests(unittest.TestCase):
    """Reliability checks are deterministic and QGIS-free."""

    def _request(self, root: Path, count: int = 1, **settings: object) -> BatchRequest:
        paths = []
        for index in range(count):
            path = root / f"dataset_{index}.las"
            path.write_text("", encoding="utf-8")
            paths.append(path)
        return BatchRequest(
            input_folder=root,
            output_folder=root / "out",
            recursive=False,
            datasets=tuple(paths),
            settings=BatchProductSettings(
                products=(ProductType.CHM,),
                grid_resolution=1.0,
                **settings,
            ),
        )

    def test_preflight_passes_ready_small_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            request = self._request(Path(tmp))
            report = run_batch_preflight(request, adapter=ReadyAdapter(), disk_usage_provider=lambda _path: (1000, 100, 10**12))  # type: ignore[arg-type]

            self.assertTrue(report.ready)
            self.assertEqual((), report.blockers)
            self.assertEqual(1, len(report.files_to_process))
            self.assertTrue(report.batch_folder.exists())

    def test_preflight_reports_warnings_for_parallel_large_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            request = self._request(Path(tmp), count=10, execution_mode="parallel_safe", confirm_large_parallel=True)
            report = run_batch_preflight(request, adapter=ReadyAdapter(), disk_usage_provider=lambda _path: (1000, 100, 10**12))  # type: ignore[arg-type]

            self.assertTrue(report.ready)
            self.assertTrue(any("Large batch" in item for item in report.warnings))
            self.assertTrue(any("Parallel safe mode" in item for item in report.warnings))


    def test_preflight_blocks_external_worker_mode_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            request = self._request(Path(tmp), execution_mode=EXTERNAL_WORKER_MODE, max_workers=2, confirm_large_parallel=True)
            report = run_batch_preflight(request, adapter=ReadyAdapter(), disk_usage_provider=lambda _path: (1000, 100, 10**12))  # type: ignore[arg-type]

            self.assertFalse(report.ready)
            self.assertTrue(any("External worker mode is disabled" in item for item in report.blockers))

    def test_recommended_worker_count_logic_is_conservative(self) -> None:
        self.assertEqual(1, recommend_batch_workers(1, 1, "parallel_safe"))
        self.assertEqual(3, recommend_batch_workers(3, 3, "parallel_safe"))
        self.assertEqual(2, recommend_batch_workers(12, 12, "parallel_safe"))
        self.assertEqual(2, recommend_batch_workers(4, 40, "parallel_safe"))

    def test_preflight_blocks_missing_input_and_not_ready_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            request = BatchRequest(
                input_folder=root,
                output_folder=root / "out",
                recursive=False,
                datasets=(root / "missing.las",),
                settings=BatchProductSettings(products=(ProductType.CHM,), grid_resolution=1.0),
            )
            report = run_batch_preflight(request, adapter=NotReadyAdapter(), disk_usage_provider=lambda _path: (1000, 100, 10**12))  # type: ignore[arg-type]

            self.assertFalse(report.ready)
            self.assertTrue(any("Missing input" in item for item in report.blockers))
            self.assertTrue(any("Environment is NOT READY" in item for item in report.blockers))

    def test_disk_space_blocker_uses_mocked_free_space(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            request = self._request(Path(tmp), count=2)
            report = run_batch_preflight(request, adapter=ReadyAdapter(), disk_usage_provider=lambda _path: (1000, 900, 1))  # type: ignore[arg-type]

            self.assertFalse(report.ready)
            self.assertTrue(any("Free disk space" in item for item in report.blockers))

    def test_manifest_creation_and_resume_completed_skip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            request = self._request(root)
            batch_folder = root / "out" / "pyforestscan_batch_resume"
            manifest = create_manifest(request, batch_folder)
            context = batch_run_context(request.datasets[0], batch_folder, reuse_existing=True).ensure_directories()
            manifest = update_manifest_item(manifest, type("Result", (), {
                "dataset_path": request.datasets[0],
                "run_context": context,
                "status": "completed",
                "message": "done",
                "outputs": (),
            })())
            write_manifest(manifest)
            loaded = load_manifest(manifest.path)
            resume_request = BatchRequest(
                input_folder=request.input_folder,
                output_folder=request.output_folder,
                recursive=False,
                datasets=request.datasets,
                settings=request.settings,
                batch_folder=batch_folder,
            )
            report = run_batch_preflight(resume_request, adapter=ReadyAdapter(), disk_usage_provider=lambda _path: (1000, 100, 10**12))  # type: ignore[arg-type]

            self.assertEqual((request.datasets[0],), completed_dataset_paths(loaded))
            self.assertEqual((request.datasets[0],), report.files_to_skip)
            self.assertEqual((), report.files_to_process)

    def test_retry_failed_only_selects_failed_manifest_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            request = self._request(root, retry_failed_only=True)
            batch_folder = root / "out" / "pyforestscan_batch_retry"
            manifest = create_manifest(request, batch_folder)
            context = batch_run_context(request.datasets[0], batch_folder, reuse_existing=True).ensure_directories()
            manifest = update_manifest_item(manifest, type("Result", (), {
                "dataset_path": request.datasets[0],
                "run_context": context,
                "status": "failed",
                "message": "bad",
                "outputs": (),
            })())
            write_manifest(manifest)
            retry_request = BatchRequest(request.input_folder, request.output_folder, False, request.datasets, request.settings, batch_folder=batch_folder)
            report = run_batch_preflight(retry_request, adapter=ReadyAdapter(), disk_usage_provider=lambda _path: (1000, 100, 10**12))  # type: ignore[arg-type]

            self.assertEqual((request.datasets[0],), report.files_to_retry)
            self.assertEqual((request.datasets[0],), report.files_to_process)

    def test_output_conflict_blocks_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            request = self._request(root)
            batch_folder = root / "out" / "pyforestscan_batch_conflict"
            context = batch_run_context(request.datasets[0], batch_folder, reuse_existing=True).ensure_directories()
            (context.outputs_dir / "chm.tif").write_text("old", encoding="utf-8")
            conflict_request = BatchRequest(request.input_folder, request.output_folder, False, request.datasets, request.settings, batch_folder=batch_folder)
            report = run_batch_preflight(conflict_request, adapter=ReadyAdapter(), disk_usage_provider=lambda _path: (1000, 100, 10**12))  # type: ignore[arg-type]

            self.assertFalse(report.ready)
            self.assertTrue(any("Output conflicts" in item for item in report.blockers))

    def test_summary_and_manifest_update_after_each_file_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            request = self._request(Path(tmp), count=2)
            result = BatchRunner(adapter=FailingInspectionAdapter()).run(request)  # type: ignore[arg-type]
            manifest = load_manifest(result.batch_folder / "batch_manifest.json")
            payload = json.loads(result.summary_json.read_text(encoding="utf-8"))

            self.assertEqual(2, result.failure_count)
            self.assertEqual(2, len(manifest.items))
            self.assertEqual(2, payload["failure_count"])


if __name__ == "__main__":
    unittest.main()
