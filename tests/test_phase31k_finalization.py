import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pyforestscan_qgis.backend_runner.job_coordinator import DurableJobCoordinator, ProcessingProgressSnapshot
from pyforestscan_qgis.core.finalization_recovery import recover_completed_polygon_job
from pyforestscan_qgis.core.polygon_batch import _source_aware_chm_plan_dict
from scripts.validate_packaged_import_graph import validate_zip_import_graph
from pyforestscan_qgis.core.backend.process_env import hidden_subprocess_kwargs
from pyforestscan_qgis.core.processing_history import ProcessingHistoryEntry, append_processing_history, read_processing_history


class FrozenFinalizationPlanTests(unittest.TestCase):
    def test_supplied_plan_is_serialized_without_replanning(self):
        plan = SimpleNamespace(to_dict=lambda: {"plan_signature": "frozen"})
        with patch("pyforestscan_qgis.core.polygon_batch.build_source_aware_chm_plan", side_effect=AssertionError("must not replan")):
            self.assertEqual(_source_aware_chm_plan_dict(SimpleNamespace(), plan)["plan_signature"], "frozen")


class CompletedScienceRecoveryTests(unittest.TestCase):
    def test_eight_complete_one_skipped_recovers_without_science(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            run = root / "run"
            required = []
            for index in range(1, 10):
                unit_id = f"wu-source-{index:04d}"
                status = "SkippedOutsidePolygon" if index == 9 else "Complete"
                if index < 9:
                    required.append(unit_id)
                path = run / "work_units" / unit_id / "status.json"
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps({"work_unit_id": unit_id, "status": status}), encoding="utf-8")
            outputs = run / "outputs"
            outputs.mkdir(parents=True)
            for name in ("chm.tif", "rumple.tif"):
                (outputs / name).write_bytes(b"valid raster fixture")
            validator = lambda path: (True, {"path": str(path), "crs": "EPSG:6635", "openable": True})
            result = recover_completed_polygon_job(run, batch_folder=root / "batch", job_id="job", attempt_id="attempt", required_work_unit_ids=required, requested_products=("chm", "rumple"), plan_signature="plan", raster_validator=validator)
            self.assertTrue(result.recovered)
            self.assertEqual(result.completed_work_units, 8)
            self.assertEqual(result.skipped_work_units, 1)
            self.assertTrue(result.registry_path.is_file())
            terminal = json.loads((run / "coordinator" / "terminal_result.json").read_text(encoding="utf-8"))
            self.assertEqual(terminal["completion_code"], "SCIENCE_COMPLETE_FINALIZATION_REPAIRED")

    def test_incomplete_science_is_never_promoted(self):
        with tempfile.TemporaryDirectory() as folder:
            result = recover_completed_polygon_job(Path(folder), batch_folder=Path(folder), job_id="job", attempt_id="attempt", required_work_unit_ids=("wu-1",), requested_products=("chm",), raster_validator=lambda path: (True, {}))
            self.assertFalse(result.recovered)


class TerminalHeartbeatTests(unittest.TestCase):
    def test_terminal_snapshot_closes_heartbeat(self):
        with tempfile.TemporaryDirectory() as folder:
            coordinator = DurableJobCoordinator(folder)
            coordinator.write_terminal_snapshot(ProcessingProgressSnapshot("job", "attempt", "complete", 8, completed=8))
            heartbeat = json.loads((Path(folder) / "heartbeat.json").read_text(encoding="utf-8"))
            self.assertFalse(heartbeat["active"])
            self.assertEqual(heartbeat["state"], "complete")
            self.assertIn("stopped_at", heartbeat)


class PackagedImportGraphTests(unittest.TestCase):
    def test_missing_adaptive_processing_fails_extracted_zip_gate(self):
        with tempfile.TemporaryDirectory() as folder:
            archive_path = Path(folder) / "plugin.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("pyforestscan_qgis/__init__.py", "")
                archive.writestr("pyforestscan_qgis/core/__init__.py", "")
                archive.writestr("pyforestscan_qgis/core/polygon_batch.py", "from pyforestscan_qgis.core import adaptive_processing\n")
            errors = validate_zip_import_graph(archive_path)
            self.assertTrue(any("adaptive_processing" in error for error in errors))

    def test_runtime_modules_are_explicit_release_requirements(self):
        root = Path(__file__).parents[1]
        source = (root / "scripts" / "validate_packaged_import_graph.py").read_text(encoding="utf-8")
        self.assertIn("pyforestscan_qgis.core.adaptive_processing", source)
        self.assertIn("pyforestscan_qgis.backend_runner.polygon_job_coordinator", source)


class BoundedReadContractTests(unittest.TestCase):
    def test_local_laz_bounds_use_explicit_pdal_crop(self):
        root = Path(__file__).parents[1]
        source = (root / "pyforestscan_qgis" / "core" / "adapter.py").read_text(encoding="utf-8")
        function = source[source.index("def _read_bounded_local_lidar"):source.index("def prepare_ept_bounds")]
        self.assertIn('"filters.crop"', function)
        self.assertIn('"readers.copc"', function)
        self.assertNotIn("handlers.read_lidar", function)

    def test_rumple_timing_declares_zero_lidar_reads(self):
        root = Path(__file__).parents[1]
        source = (root / "pyforestscan_qgis" / "core" / "polygon_batch.py").read_text(encoding="utf-8")
        self.assertIn('timing["rumple_lidar_reads"]=0', source)


class BackgroundAndHistoryTests(unittest.TestCase):
    def test_windows_background_flags_hide_console(self):
        fake = SimpleNamespace(CREATE_NO_WINDOW=0x08000000, STARTF_USESHOWWINDOW=1, SW_HIDE=0, STARTUPINFO=lambda: SimpleNamespace(dwFlags=0, wShowWindow=1))
        flags = hidden_subprocess_kwargs("nt", fake)
        self.assertEqual(flags["creationflags"], 0x08000000)
        self.assertEqual(flags["startupinfo"].wShowWindow, 0)

    def test_processing_history_is_registry_backed_and_attempt_scoped(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "history.json"
            first = ProcessingHistoryEntry("job", "attempt-1", "today", "source.laz", "polygon", ("chm",), "complete", 2.0, ("chm.tif",))
            second = ProcessingHistoryEntry("job", "attempt-2", "today", "source.laz", "polygon", ("chm",), "failed", 1.0, ())
            append_processing_history(path, first)
            append_processing_history(path, second)
            history = read_processing_history(path)
            self.assertEqual([item.attempt_id for item in history], ["attempt-2", "attempt-1"])


if __name__ == "__main__":
    unittest.main()
