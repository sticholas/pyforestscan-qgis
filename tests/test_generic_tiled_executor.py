from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pyforestscan_qgis.core.generic_tiled_executor import execute_tiled_product
from pyforestscan_qgis.core.source_aware_processing import SpatialExtent, WorkUnit, WorkUnitType
from pyforestscan_qgis.core.work_unit_scheduler import CheckpointStore, WorkUnitResult


class GenericTiledExecutorTests(unittest.TestCase):
    def test_tiles_retry_and_mosaic(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            units = tuple(WorkUnit(f"tile-{i}", WorkUnitType.EPT_WINDOW, (), SpatialExtent(i, 0, i + 1, 1), SpatialExtent(i, 0, i + 1, 1), 0, 1, 0, 1, i, 1) for i in range(2))
            attempts = {}
            def execute(unit, attempt):
                attempts[unit.work_unit_id] = attempt
                output = root / f"{unit.work_unit_id}.tif"
                if unit.work_unit_id == "tile-0" and attempt == 1:
                    raise OSError("temporary remote read")
                output.write_bytes(b"tile")
                return WorkUnitResult(unit.work_unit_id, "Complete", output, attempt_count=attempt)
            result = execute_tiled_product(product="voxel_stat", work_units=units, checkpoint=CheckpointStore(root / "checkpoint", "sig"), execute_tile=execute, mosaic_tiles=lambda results: root / "mosaic.tif")
            self.assertEqual(result.status, "completed")
            self.assertEqual(attempts["tile-0"], 2)

    def test_empty_plan_fails_fast(self):
        with TemporaryDirectory() as folder:
            result = execute_tiled_product(product="dtm", work_units=(), checkpoint=CheckpointStore(Path(folder), "sig"), execute_tile=lambda *_: None, mosaic_tiles=lambda _: Path(folder) / "x.tif")
            self.assertEqual(result.status, "failed")

    def test_scheduler_progress_is_forwarded_as_product_event(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            units = tuple(WorkUnit(f"tile-{i}", WorkUnitType.EPT_WINDOW, (), SpatialExtent(i, 0, i + 1, 1), SpatialExtent(i, 0, i + 1, 1), 0, 1, 0, 1, i, 1) for i in range(2))
            events = []
            def execute(unit, attempt):
                output = root / f"{unit.work_unit_id}.tif"
                output.write_bytes(b"tile")
                return WorkUnitResult(unit.work_unit_id, "Complete", output, attempt_count=attempt)
            result = execute_tiled_product(product="voxel_stat", work_units=units, checkpoint=CheckpointStore(root / "checkpoint", "sig"), execute_tile=execute, mosaic_tiles=lambda results: root / "mosaic.tif", progress_callback=events.append)
            self.assertEqual(result.status, "completed")
            self.assertTrue(events)
            self.assertEqual(events[-1].completed, 2)

    def test_finalization_uses_completed_tiles_without_extra_source_read(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            units = tuple(WorkUnit(f"tile-{i}", WorkUnitType.EPT_WINDOW, (), SpatialExtent(i, 0, i + 1, 1), SpatialExtent(i, 0, i + 1, 1), 0, 1, 0, 1, i, 1) for i in range(4))
            source_reads = []
            def execute(unit, attempt):
                source_reads.append(unit.work_unit_id)
                output = root / f"{unit.work_unit_id}.tif"
                output.write_bytes(b"tile")
                return WorkUnitResult(unit.work_unit_id, "Complete", output, attempt_count=attempt)
            def mosaic(results):
                self.assertEqual(4, len(results))
                output = root / "mosaic.tif"
                output.write_bytes(b"mosaic")
                return output
            result = execute_tiled_product(product="voxel_stat", work_units=units, checkpoint=CheckpointStore(root / "checkpoint", "sig"), execute_tile=execute, mosaic_tiles=mosaic)
            self.assertEqual("completed", result.status)
            reads_after_tiles = len(source_reads)
            self.assertEqual(4, reads_after_tiles)
            self.assertEqual(reads_after_tiles, len(source_reads))

    def test_one_empty_tile_is_mosaicked_as_nodata_without_reread(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            units = tuple(WorkUnit(f"tile-{i}", WorkUnitType.EPT_WINDOW, (), SpatialExtent(i, 0, i + 1, 1), SpatialExtent(i, 0, i + 1, 1), 0, 1, 0, 1, i, 1) for i in range(3))
            calls = []
            def execute(unit, attempt):
                calls.append(unit.work_unit_id)
                output = root / f"{unit.work_unit_id}.tif"
                output.write_bytes(b"nodata" if unit.work_unit_id == "tile-1" else b"data")
                return WorkUnitResult(unit.work_unit_id, "CompleteNoData" if unit.work_unit_id == "tile-1" else "Complete", output, attempt_count=attempt, error_code="EMPTY_EPT_READ" if unit.work_unit_id == "tile-1" else "")
            seen = []
            def mosaic(results):
                seen.extend(results)
                output = root / "mosaic.tif"
                output.write_bytes(b"mosaic")
                return output
            result = execute_tiled_product(product="voxel_stat", work_units=units, checkpoint=CheckpointStore(root / "checkpoint", "sig"), execute_tile=execute, mosaic_tiles=mosaic)
            self.assertEqual(result.status, "completed")
            self.assertEqual([item.status for item in seen], ["Complete", "CompleteNoData", "Complete"])
            self.assertEqual(calls.count("tile-1"), 1)


if __name__ == "__main__":
    unittest.main()
