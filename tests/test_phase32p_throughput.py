"""Phase 32P high-throughput planning, execution, and telemetry regressions."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from pyforestscan_qgis.core.adapter import _write_chm_stage_timing
from pyforestscan_qgis.backend_runner.job_coordinator import aggregate_work_unit_statuses
from pyforestscan_qgis.core.polygon_batch import _requires_chunked_ept_parent
from pyforestscan_qgis.core.source_aware_processing import SpatialExtent


class Phase32PThroughputTests(unittest.TestCase):
    def test_ordinary_ept_component_uses_one_managed_operation(self):
        read = SpatialExtent(0, 0, 1170, 1170)
        self.assertFalse(_requires_chunked_ept_parent(SimpleNamespace(estimated_memory=2 * 1024**3), read))

    def test_only_genuinely_large_ept_component_uses_nested_isolation(self):
        self.assertTrue(_requires_chunked_ept_parent(SimpleNamespace(estimated_memory=1), SpatialExtent(0, 0, 2001, 500)))
        self.assertTrue(_requires_chunked_ept_parent(SimpleNamespace(estimated_memory=7 * 1024**3), SpatialExtent(0, 0, 500, 500)))

    def test_current_work_unit_is_exposed_by_status_aggregation(self):
        with tempfile.TemporaryDirectory() as folder:
            status = Path(folder) / "wu-0042" / "status.json"
            status.parent.mkdir()
            status.write_text(json.dumps({"status": "Running", "work_unit_id": "wu-0042"}), encoding="utf-8")
            result = aggregate_work_unit_statuses(Path(folder), 10, 10)
        self.assertEqual(result["running"], 1)
        self.assertEqual(result["current_work_unit_ids"], ["wu-0042"])

    def test_science_timing_is_written_to_the_work_unit_diagnostics(self):
        with tempfile.TemporaryDirectory() as folder:
            diagnostics = Path(folder) / "diagnostics"
            request = SimpleNamespace(diagnostics_path=diagnostics)
            _write_chm_stage_timing(request, {"total_seconds": 12.5, "point_count": 42})
            payload = json.loads((diagnostics / "science_timing.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["total_seconds"], 12.5)
        self.assertEqual(payload["point_count"], 42)


if __name__ == "__main__":
    unittest.main()
