import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory

from pyforestscan_qgis.core.tile_diagnostics import (
    EMPTY_EPT_READ,
    EMPTY_AFTER_POLYGON_CLIP,
    EMPTY_AFTER_HEIGHT_PREPARATION,
    ScientificConditionError,
    classify_empty,
    write_stage_record,
)


class TileDiagnosticsTests(unittest.TestCase):
    def test_empty_classification_distinguishes_expected_source_gap(self):
        self.assertEqual(classify_empty(point_count=0, stage="EPT_READ", expected_source_coverage="unknown"), (EMPTY_EPT_READ, True))
        self.assertEqual(classify_empty(point_count=0, stage="EPT_READ", expected_source_coverage="expected"), (EMPTY_EPT_READ, False))
        self.assertEqual(classify_empty(point_count=0, stage="POLYGON_CLIP"), (EMPTY_AFTER_POLYGON_CLIP, True))
        self.assertEqual(classify_empty(point_count=0, stage="HEIGHT_PREPARATION"), (EMPTY_AFTER_HEIGHT_PREPARATION, False))

    def test_stage_records_are_metadata_only_and_merge(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "tile_diagnostics.json"
            write_stage_record(path, stage="EPT_READ_STARTED", payload={"points_read": 0})
            write_stage_record(path, stage="EPT_READ_COMPLETED", payload={"points_read": 0, "dimensions": []})
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema"], "pyforestscan-tile-diagnostics-v1")
            self.assertEqual(payload["stages"]["EPT_READ_COMPLETED"]["points_read"], 0)
            self.assertNotIn("coordinates", path.read_text(encoding="utf-8"))

    def test_scientific_condition_has_no_fake_traceback(self):
        error = ScientificConditionError(EMPTY_EPT_READ, "empty", stage="EPT_READ")
        self.assertEqual(error.failure_kind, "SCIENTIFIC_CONDITION")
        self.assertIsNone(error.traceback)

    def test_repeated_and_concurrent_updates_are_idempotent(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "tile_diagnostics.json"
            for index in range(20):
                write_stage_record(path, stage=f"STAGE_{index}", payload={"index": index})
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(lambda index: write_stage_record(path, stage=f"THREAD_{index}", payload={"index": index}), range(20)))
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["stages"]), 40)
            self.assertEqual(payload["stages"]["STAGE_19"]["index"], 19)

    def test_directory_collision_is_best_effort_and_recorded_outside_tile(self):
        with TemporaryDirectory() as folder:
            root = Path(folder) / "run"
            target = root / "work_units" / "voxel_stat" / "wu" / "diagnostics" / "tile_diagnostics.json"
            target.mkdir(parents=True)
            write_stage_record(target, stage="VOXEL_STAT_STARTED", payload={"ok": True})
            self.assertTrue(target.is_dir())
            failures = list((root / "diagnostics").glob("filesystem_failure_*.json"))
            self.assertTrue(failures)


if __name__ == "__main__":
    unittest.main()
