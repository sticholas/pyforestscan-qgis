"""Regression coverage for polygon progress and execution control."""

from __future__ import annotations

import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from pyforestscan_qgis.core.atomic_state import atomic_write_json
from pyforestscan_qgis.core.launch_attempt import append_attempt_stage, create_launch_attempt
from pyforestscan_qgis.core.polygon_progress import PolygonProgressProjection, progress_event
from pyforestscan_qgis.core.polygon_batch import _prepare_polygon_input, _terminate_owned_process


ROOT = Path(__file__).resolve().parents[1]


class Phase32IProgressControlTests(unittest.TestCase):
    def test_one_dataset_500_heartbeats_never_increment_completion(self):
        projection = PolygonProgressProjection(1, 2)
        projection.apply(progress_event(
            attempt_id="attempt", sequence=1, event_type="STAGE_TRANSITION",
            stage="POLYGON_INPUT_PREPARATION_STARTED", entity_type="dataset",
            entity_id="source.las",
        ))
        for sequence in range(2, 502):
            projection.apply(progress_event(
                attempt_id="attempt", sequence=sequence, event_type="HEARTBEAT",
                stage="POLYGON_INPUT_PREPARATION", entity_type="dataset",
                entity_id="source.las",
            ))
        self.assertEqual(projection.completed_datasets, 0)
        self.assertEqual(projection.completed_products, 0)
        self.assertEqual(len(projection.datasets), 1)
        self.assertEqual(projection.summary(), "Datasets: 0 / 1 complete; Products: 0 / 2 complete")

    def test_duplicate_event_delivery_is_idempotent(self):
        projection = PolygonProgressProjection(1, 2)
        event = progress_event(
            attempt_id="attempt", sequence=8, event_type="STAGE_TRANSITION",
            stage="PREPARATION_COMPLETE", entity_type="dataset", entity_id="source.las",
        )
        self.assertTrue(projection.apply(event))
        for _ in range(100):
            self.assertFalse(projection.apply(event))
        self.assertEqual(len(projection.datasets), 1)
        self.assertEqual(projection.completed_datasets, 0)

    def test_terminal_state_is_derived_not_incremented(self):
        projection = PolygonProgressProjection(1, 2)
        projection.apply(progress_event(
            attempt_id="attempt", sequence=1, event_type="TERMINAL",
            stage="DATASET_SUCCEEDED", entity_type="dataset", entity_id="source.las",
            state="SUCCEEDED",
        ))
        self.assertEqual(projection.completed_datasets, 1)

    def test_heartbeats_do_not_grow_launch_history(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch("pyforestscan_qgis.core.launch_attempt._global_latest_attempt_path", return_value=root / "global.json"):
                attempt = create_launch_attempt(root, ("pai", "fhd"), "plan")
                for sequence in range(500):
                    append_attempt_stage(attempt, "HEARTBEAT", active_stage="POLYGON_INPUT_PREPARATION", sequence=sequence)
            payload = json.loads(attempt.trace_path.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["stages"]), 1)
            self.assertEqual(payload["heartbeat"]["sequence"], 499)

    def test_atomic_progress_snapshot_survives_repeated_reads(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "progress.json"
            for sequence in range(100):
                atomic_write_json(path, {"sequence": sequence, "event_type": "HEARTBEAT"})
                self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["sequence"], sequence)

    def test_coordinator_separates_heartbeat_from_stage_sequence(self):
        source = (ROOT / "pyforestscan_qgis/backend_runner/generic_polygon_coordinator.py").read_text(encoding="utf-8")
        self.assertIn('write_snapshot("HEARTBEAT")', source)
        self.assertNotIn('state["sequence"] += 1\n            atomic_write_json', source)
        self.assertIn('pause_requested.json', source)

    def test_preparation_is_owned_and_cancellable(self):
        source = (ROOT / "pyforestscan_qgis/core/polygon_batch.py").read_text(encoding="utf-8")
        helper = source[source.index("def _prepare_polygon_input"):source.index("def _submit_and_observe_generic_polygon")]
        self.assertIn("polygon_preparation_worker", helper)
        self.assertIn("_terminate_owned_process(process)", helper)
        self.assertIn("preparation_timing.json", helper)
        self.assertIn('"state": "PREPARED"', helper)
        self.assertIn("POLYGON_INPUT_PREPARATION_REUSED", helper)

    def test_owned_process_can_be_terminated(self):
        process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        _terminate_owned_process(process)
        self.assertIsNotNone(process.poll())

    def test_valid_preparation_checkpoint_is_reused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source.las"
            output = root / "source_polygon_clip.laz"
            source.write_bytes(b"source")
            output.write_bytes(b"prepared")
            polygon = "POLYGON ((0 0, 1 0, 1 1, 0 0))"
            request = SimpleNamespace(output_path=output, crop_polygon=polygon, bounds=None, crs="EPSG:6635")
            fingerprint = {
                "path": str(source), "size": source.stat().st_size,
                "mtime_ns": source.stat().st_mtime_ns,
                "polygon_sha256": hashlib.sha256(polygon.encode("utf-8")).hexdigest(),
                "bounds": "None", "crs": "EPSG:6635",
                "method": "pyforestscan.handlers.read_lidar_hag_then_write_las",
            }
            output.with_suffix(output.suffix + ".prepared.json").write_text(json.dumps({
                "source_fingerprint": fingerprint,
                "output_size_bytes": output.stat().st_size,
                "points_retained": 42,
            }), encoding="utf-8")
            stages = []
            with patch.dict("os.environ", {"PYFORESTSCAN_GENERIC_POLYGON_COORDINATOR": "1"}):
                result = _prepare_polygon_input(
                    request, SimpleNamespace(path=source), root,
                    lambda name, **details: stages.append((name, details)),
                    lambda: None, root / "attempt", MagicMock(),
                )
            self.assertEqual(result.point_count, 42)
            self.assertEqual(stages[0][0], "POLYGON_INPUT_PREPARATION_REUSED")

    def test_ui_uses_upsert_and_indeterminate_preparation_progress(self):
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")
        method = source[source.index("    def _on_batch_item"):source.index("    def _on_batch_job_update")]
        self.assertIn("_batch_items_by_dataset[key] = item", method)
        self.assertNotIn("_processed_items = getattr", method)
        self.assertIn("self.progress_bar.setRange(0, 0)", method)
        self.assertIn("Pause After Current Step", source)
        self.assertIn("Cancel Processing", source)


if __name__ == "__main__":
    unittest.main()
