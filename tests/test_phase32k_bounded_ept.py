import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pyforestscan_qgis.backend_runner.pbm_lidar_preparation import _pipeline
from pyforestscan_qgis.core.classification_inspection import (
    ClassificationAssessment,
    ClassificationInspectionService,
)
from pyforestscan_qgis.core.polygon_batch import _prepare_source_dependency, _run_chunked_ept_parent_chm
from pyforestscan_qgis.core.source_aware_processing import SpatialExtent
from pyforestscan_qgis.core.types import ChmRequest


class _Array:
    dtype = SimpleNamespace(names=("X", "Y", "Z", "Classification", "HeightAboveGround"))

    def __len__(self):
        return 4

    def __getitem__(self, name):
        if name == "Classification":
            return (2, 2, 3, 5)
        if name == "HeightAboveGround":
            return (0.0, 1.5, 4.0, 12.0)
        raise KeyError(name)


class _Pipeline:
    specs = []

    def __init__(self, spec):
        self.specs.append(json.loads(spec))
        self.arrays = (_Array(),)

    def execute(self):
        return 4


class BoundedEptTests(unittest.TestCase):
    def test_ept_classification_uses_reader_level_bounds(self):
        _Pipeline.specs.clear()
        bounds = {"xmin": 1, "ymin": 2, "xmax": 3, "ymax": 4}
        result = ClassificationInspectionService(_Pipeline).inspect("ept.json", bounds=bounds, strata=1)
        reader = _Pipeline.specs[0]["pipeline"][0]
        self.assertEqual(reader["type"], "readers.ept")
        self.assertEqual(reader["bounds"], "([1.0,3.0],[2.0,4.0])")
        self.assertTrue(result.ground_class_2_observed)
        self.assertTrue(result.existing_hag_valid)
        self.assertEqual(dict(result.height_quantiles)["p95"], 12.0)

    def test_ept_preparation_pipeline_bounds_the_reader(self):
        assessment = SimpleNamespace(source=Path("ept.json"), coordinate_units=SimpleNamespace(from_meters=lambda value: value), crs="EPSG:26905")
        plan = SimpleNamespace(height_mode=SimpleNamespace())
        stages = _pipeline(assessment, plan, Path("prepared.laz"), {"xmin": 1, "ymin": 2, "xmax": 3, "ymax": 4})
        self.assertEqual(stages[0]["bounds"], "([1.0,3.0],[2.0,4.0])")
        self.assertFalse(any(stage.get("type") == "filters.crop" for stage in stages))

    def test_polygon_ept_strategy_never_materializes_source_wide_laz(self):
        assessment = ClassificationAssessment(
            True, 4, True, 0.5, (3, 5), "HIGH", "spatially bounded EPT sample",
            class_counts=((2, 2), (3, 1), (5, 1)),
            observed_dimensions=("X", "Y", "Z", "Classification", "HeightAboveGround"),
            strata_sampled=1, strata_with_ground=1, ground_coverage_ratio=1.0,
            existing_hag_available=True, existing_hag_valid=True,
            height_quantiles=(("p05", 0.0), ("p50", 4.0), ("p95", 12.0)),
        )
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source_path = root / "ept.json"
            source_path.write_text("{}", encoding="utf-8")
            extent = SimpleNamespace(xmin=10, ymin=20, xmax=30, ymax=40)
            plan = SimpleNamespace(
                plan_signature="plan-109",
                work_units=tuple(SimpleNamespace(work_unit_id=f"wu-{index:03d}", read_extent=extent) for index in range(1, 110)),
            )
            context = SimpleNamespace(run_folder=root / "run")
            source = SimpleNamespace(path=source_path)
            with patch("pyforestscan_qgis.core.classification_inspection.ClassificationInspectionService.inspect", return_value=assessment), patch("pyforestscan_qgis.backend_runner.pbm_lidar_preparation.prepare_durable_source") as durable:
                prepared, dimensions, status_path = _prepare_source_dependency(SimpleNamespace(), source, plan, context, None)
            durable.assert_not_called()
            status = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual(prepared, source_path)
            self.assertEqual(status["preparation_mode"], "logical_bounded_ept")
            self.assertFalse(status["source_wide_materialization"])
            self.assertEqual(status["chosen_hag_method"], "existing_normalized_height")
            self.assertEqual(status["required_work_units"], 109)
            self.assertEqual(status["pilot_bounds"], {"xmin": 10, "ymin": 20, "xmax": 30, "ymax": 40})
            self.assertIn("Classification", dimensions)

    def test_source_aware_lifecycle_exposes_scheduler_and_watchdog(self):
        source = (Path(__file__).parents[1] / "pyforestscan_qgis/core/polygon_batch.py").read_text(encoding="utf-8")
        self.assertIn('"PILOT_COMPLETED"', source)
        self.assertIn('"HAG_STRATEGY_RESOLVED"', source)
        self.assertIn('"WORK_UNIT_SCHEDULER_STARTED"', source)
        self.assertIn('"POSSIBLE_STALL"', source)
        self.assertIn("suppress_local_discovery_warning", source)
        self.assertIn("build_processing_engine_environment", source)
        self.assertIn("ept_chm_subread.py", source)

    def test_large_parent_uses_checkpointed_memory_bounded_subreads(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            request = ChmRequest(
                Path("ept.json"), root / "parent.tif", 1.0, "EPSG:6635",
                hag_method="existing_normalized_height", hag_source_dimension="HeightAboveGround",
                hag_method_signature="hag-signature", work_unit_id="wu-parent",
            )
            calls = []
            adapter = SimpleNamespace(close_calls=0)
            adapter.close = lambda: setattr(adapter, "close_calls", adapter.close_calls + 1)

            def run(bounded, _folder):
                calls.append(bounded)
                bounded.output_path.parent.mkdir(parents=True, exist_ok=True)
                bounded.output_path.write_bytes(b"buffered")
                return SimpleNamespace(output_path=bounded.output_path)

            def extract(_source, output, _extent):
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(b"core")

            def mosaic(_paths, output, _plan):
                output.write_bytes(b"parent")

            extent = SpatialExtent(0, 0, 1170, 1170)
            with patch("pyforestscan_qgis.core.polygon_batch._run_isolated_ept_subread", side_effect=run), patch("pyforestscan_qgis.core.polygon_batch._extract_core_raster", side_effect=extract), patch("pyforestscan_qgis.core.polygon_batch._mosaic_core_rasters", side_effect=mosaic):
                result = _run_chunked_ept_parent_chm(adapter, request, root, extent, "EPSG:6635", -9999.0)
                first_count = len(calls)
                _run_chunked_ept_parent_chm(adapter, request, root, extent, "EPSG:6635", -9999.0)
            self.assertEqual(result, root / "parent.tif")
            self.assertEqual(first_count, 9)
            self.assertEqual(len(calls), first_count)
            self.assertEqual(adapter.close_calls, first_count)
            for bounded in calls:
                bounds = bounded.bounds
                self.assertLessEqual(float(bounds["xmax"]) - float(bounds["xmin"]), 600.0)
                self.assertLessEqual(float(bounds["ymax"]) - float(bounds["ymin"]), 600.0)


if __name__ == "__main__":
    unittest.main()
