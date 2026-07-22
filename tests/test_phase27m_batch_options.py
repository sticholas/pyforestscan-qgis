"""Phase 27M shared Batch option and output registry tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.batch import BatchProductSettings
from pyforestscan_qgis.core.batch_options import BatchExecutionOptions, polygon_option_applicability, requested_effective_concurrency
from pyforestscan_qgis.core.output_registry import generated_output_for_path, read_output_registry, write_output_registry
from pyforestscan_qgis.core.polygon_batch import PolygonBatchRequest, run_polygon_batch_preflight, write_polygon_batch_manifest
from pyforestscan_qgis.core.polygon_source import PolygonSource
from pyforestscan_qgis.core.polygon_normalization import normalize_polygon_source
from pyforestscan_qgis.core.types import ProductType
from pyforestscan_qgis.ui.output_loading import collect_loadable_outputs, output_loading_summary


class Phase27MBatchOptionsTests(unittest.TestCase):
    def test_shared_settings_map_to_execution_options(self) -> None:
        settings = BatchProductSettings(
            products=(ProductType.CHM,),
            grid_resolution=1.0,
            execution_mode="parallel_safe",
            max_workers=4,
            load_outputs_into_qgis=True,
            stop_on_error=False,
            retry_failed_only=True,
            overwrite_existing=True,
        )

        options = BatchExecutionOptions.from_batch_settings(settings)

        self.assertEqual(options.maximum_parallel_jobs, 4)
        self.assertEqual(options.worker_count, 4)
        self.assertFalse(options.run_sequentially)
        self.assertTrue(options.load_outputs_after_completion)
        self.assertTrue(options.retry_failed_jobs)
        self.assertEqual(options.output_conflict_policy, "overwrite")

    def test_ept_single_product_effective_concurrency_is_one(self) -> None:
        options = BatchExecutionOptions(maximum_parallel_jobs=4, worker_count=4)
        summary = requested_effective_concurrency(options, source_types={"ept"}, product_count=1)

        self.assertEqual(summary["requested_concurrent_jobs"], 4)
        self.assertEqual(summary["effective_concurrent_jobs"], 1)
        self.assertIn("one logical EPT", summary["reason"])

    def test_applicability_explains_supported_shared_options(self) -> None:
        options = BatchExecutionOptions(maximum_parallel_jobs=2, load_outputs_after_completion=True)
        rows = polygon_option_applicability(options, source_types={"laz"}, product_count=2)
        by_key = {row.option_key: row for row in rows}

        self.assertTrue(by_key["load_outputs_after_completion"].supported)
        self.assertEqual(by_key["maximum_parallel_jobs"].effective_value, 2)
        self.assertIn("logical jobs", by_key["maximum_parallel_jobs"].reason)

    def test_polygon_manifest_records_options_and_concurrency(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "ept.json").write_text(json.dumps({"bounds": [0, 0, 0, 10, 10, 5], "srs": {"authority": "EPSG:32610"}, "points": 100}), encoding="utf-8")
            polygon = normalize_polygon_source(PolygonSource("wkt", polygon_wkt="POLYGON ((1 1, 4 1, 4 4, 1 4, 1 1))", source_crs="EPSG:32610", processing_crs="EPSG:32610"))
            settings = BatchProductSettings(products=(ProductType.CHM,), grid_resolution=1.0, max_workers=4, load_outputs_into_qgis=True)
            report = run_polygon_batch_preflight(PolygonBatchRequest(root, root / "out", polygon, (ProductType.CHM,), settings), backend_probe=lambda: (True, "PBM ready"))

            manifest = json.loads(write_polygon_batch_manifest(report).read_text(encoding="utf-8"))

            self.assertTrue(manifest["shared_execution_options"]["load_outputs_after_completion"])
            self.assertEqual(manifest["concurrency"]["requested_concurrent_jobs"], 4)
            self.assertEqual(manifest["concurrency"]["effective_concurrent_jobs"], 1)
            self.assertTrue(manifest["polygon_options"]["exact_raster_mask"])
            self.assertTrue(any(row["option_key"] == "maximum_parallel_jobs" for row in manifest["option_applicability"]))

    def test_registry_expands_into_loadable_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            chm = root / "chm.tif"
            chm.write_text("fake", encoding="utf-8")
            registry = write_output_registry((generated_output_for_path(chm, job_id="job", product_key="chm", source_mode="polygon_area_processing", masked=True),), root)

            loaded = read_output_registry(registry)
            outputs = collect_loadable_outputs((registry,))

            self.assertEqual(loaded[0].product_key, "chm")
            self.assertTrue(loaded[0].masked)
            self.assertEqual([item.path for item in outputs], [chm])

    def test_output_loading_summary_reports_state_counts(self) -> None:
        summary = output_loading_summary(1, 4, already_loaded_count=1, skipped_count=1, failed_count=1)

        self.assertIn("Loaded: 1", summary)
        self.assertIn("Already loaded: 1", summary)
        self.assertIn("Skipped: 1", summary)
        self.assertIn("Failed: 1", summary)


if __name__ == "__main__":
    unittest.main()
