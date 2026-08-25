"""Tests for safe batch executor guardrails and parallel framework."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.batch import BatchProductSettings, BatchRequest
from pyforestscan_qgis.core.batch_executor import BatchExecutor, PARALLEL_SAFE_MODE, SEQUENTIAL_MODE
from pyforestscan_qgis.core.batch_runner import BatchExecutionError
from pyforestscan_qgis.core.types import ProductType


class FailingAdapter:
    """Adapter stub that forces per-file failures without QGIS."""

    def inspect_dataset(self, _path: Path) -> object:
        """Raise like a failed dataset inspection."""
        raise RuntimeError("inspection failed")


class BatchExecutorTests(unittest.TestCase):
    """BatchExecutor remains conservative and QGIS-free."""

    def _request(self, root: Path, count: int = 2, mode: str = SEQUENTIAL_MODE, workers: int = 2, confirm: bool = False) -> BatchRequest:
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
                execution_mode=mode,
                max_workers=workers,
                confirm_large_parallel=confirm,
            ),
        )

    def test_parallel_worker_limit_allows_six_with_confirmation(self) -> None:
        """Parallel safe mode can be increased to six workers after confirmation."""
        with tempfile.TemporaryDirectory() as tmp:
            request = self._request(Path(tmp), mode=PARALLEL_SAFE_MODE, workers=6, confirm=True)
            executor = BatchExecutor(adapter_factory=FailingAdapter)  # type: ignore[arg-type]

            report = executor.guardrails(request)

            self.assertEqual(6, report.max_workers)
            self.assertTrue(report.is_parallel)

    def test_parallel_worker_limit_rejects_above_six(self) -> None:
        """Worker counts outside the safe range are rejected."""
        with tempfile.TemporaryDirectory() as tmp:
            request = self._request(Path(tmp), mode=PARALLEL_SAFE_MODE, workers=7, confirm=True)
            executor = BatchExecutor(adapter_factory=FailingAdapter)  # type: ignore[arg-type]

            with self.assertRaises(BatchExecutionError):
                executor.guardrails(request)

    def test_sequential_mode_is_default_effective_mode(self) -> None:
        """Sequential remains the default fallback."""
        with tempfile.TemporaryDirectory() as tmp:
            request = self._request(Path(tmp))
            report = BatchExecutor(adapter_factory=FailingAdapter).guardrails(request)  # type: ignore[arg-type]

            self.assertEqual(SEQUENTIAL_MODE, report.effective_mode)
            self.assertFalse(report.is_parallel)

    def test_parallel_large_workload_is_planner_owned(self) -> None:
        """Warnings inform but do not require a global acknowledgement."""
        with tempfile.TemporaryDirectory() as tmp:
            request = self._request(Path(tmp), count=10, mode=PARALLEL_SAFE_MODE, workers=2, confirm=False)
            report = BatchExecutor(adapter_factory=FailingAdapter).guardrails(request)  # type: ignore[arg-type]

            self.assertFalse(report.blocked)
            self.assertTrue(report.warnings)

    def test_automatic_single_source_uses_one_worker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            request = self._request(Path(tmp), count=1, mode="automatic", workers=5)
            report = BatchExecutor(adapter_factory=FailingAdapter).guardrails(request)  # type: ignore[arg-type]
            self.assertEqual(SEQUENTIAL_MODE, report.effective_mode)
            self.assertEqual(1, report.max_workers)

    def test_automatic_multiple_sources_parallelize_up_to_five(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            request = self._request(Path(tmp), count=20, mode="automatic", workers=5)
            report = BatchExecutor(adapter_factory=FailingAdapter).guardrails(request)  # type: ignore[arg-type]
            self.assertEqual(PARALLEL_SAFE_MODE, report.effective_mode)
            self.assertEqual(5, report.max_workers)

    def test_parallel_mode_records_failed_files_and_writes_summary(self) -> None:
        """Parallel worker failures are isolated per file."""
        with tempfile.TemporaryDirectory() as tmp:
            request = self._request(Path(tmp), count=2, mode=PARALLEL_SAFE_MODE, workers=2, confirm=True)
            result = BatchExecutor(adapter_factory=FailingAdapter).run(request)  # type: ignore[arg-type]

            self.assertEqual(2, result.failure_count)
            self.assertEqual(0, result.success_count)
            self.assertTrue(result.summary_json.exists())
            self.assertTrue(result.summary_html.exists())

    def test_parallel_cancel_records_skipped_remaining_files(self) -> None:
        """Cancel remaining leaves skipped records and still writes summaries."""
        with tempfile.TemporaryDirectory() as tmp:
            calls = {"count": 0}

            def control() -> str | None:
                calls["count"] += 1
                return "cancel" if calls["count"] > 1 else None

            request = self._request(Path(tmp), count=3, mode=PARALLEL_SAFE_MODE, workers=2, confirm=True)
            result = BatchExecutor(adapter_factory=FailingAdapter).run(request, control_callback=control)  # type: ignore[arg-type]

            self.assertGreaterEqual(result.skipped_count, 1)
            self.assertTrue(result.summary_csv.exists())


if __name__ == "__main__":
    unittest.main()
