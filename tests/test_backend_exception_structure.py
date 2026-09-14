import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from pyforestscan_qgis.backend_runner.job_result import BackendJobResult
from pyforestscan_qgis.backend_runner.run_processing_job import _exception_structure
from pyforestscan_qgis.backend_runner.job_spec import BackendJobSpec
from pyforestscan_qgis.backend_runner import run_processing_job


class BackendExceptionStructureTests(unittest.TestCase):
    def test_file_exists_error_preserves_windows_fields(self):
        try:
            raise FileExistsError(183, "already exists", "tile_diagnostics.json")
        except FileExistsError as exc:
            details = _exception_structure(exc)
        self.assertEqual(details["root_exception_type"], "FileExistsError")
        self.assertEqual(details["root_winerror"], None)  # POSIX Python has no WinError attribute
        self.assertEqual(details["root_filename"], "tile_diagnostics.json")
        result = BackendJobResult("job", "voxel_stat", "failed", root_exception_type="FileExistsError", root_errno=details["root_errno"], root_filename=details["root_filename"])
        restored = BackendJobResult.from_dict(result.to_dict())
        self.assertEqual(restored.root_exception_type, "FileExistsError")

    def test_run_spec_sentinel_does_not_mask_original_error(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            spec = BackendJobSpec("job", root / "input.ept.json", "EPSG:6634", root, "voxel_stat", {}, {}, root / "result.json")
            with patch.object(run_processing_job, "_validate_runtime_protocol", side_effect=RuntimeError("PFS_ORIGINAL_SENTINEL")):
                result = run_processing_job.run_spec(spec)
            self.assertEqual(result.status, "failed")
            self.assertEqual(result.root_exception_type, "RuntimeError")
            self.assertIn("PFS_ORIGINAL_SENTINEL", result.root_exception_message)
            self.assertNotEqual(result.root_exception_type, "UnboundLocalError")
            self.assertIn("PFS_ORIGINAL_SENTINEL", result.traceback or "")


if __name__ == "__main__":
    unittest.main()
