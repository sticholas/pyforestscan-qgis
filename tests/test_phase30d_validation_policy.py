"""Phase 30D validation, scheduling, and state isolation regressions."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.automatic_execution import choose_automatic_execution
from pyforestscan_qgis.core.batch import BatchProductSettings, BatchRequest
from pyforestscan_qgis.core.batch_preflight import run_batch_preflight
from pyforestscan_qgis.core.pipeline import build_default_pipeline_registry
from pyforestscan_qgis.core.pipeline_context import load_pipeline_contexts
from pyforestscan_qgis.core.pipeline_results import ProductValidationSeverity
from pyforestscan_qgis.core.types import ProductType, RumpleResult


class _Adapter:
    def create_chm(self, request):
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        request.output_path.write_bytes(b"chm")
        return type("Result", (), {"output_path": request.output_path})()

    def create_rumple(self, request):
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        request.output_path.write_bytes(b"rumple")
        return RumpleResult(request.output_path, 1.0, (0.0, 1.0, 0.0, 1.0), request.grid_resolution, request.crs)


class _ReadyAdapter:
    def check_environment(self):
        return type("Check", (), {"readiness": type("R", (), {"value": "READY"})()})()

    def selected_execution_backend(self):
        return "pbm_backend"


def _plan(root: Path, product: str) -> Path:
    report = root / "report.json"
    report.write_text(json.dumps({"geometry": {"crs": None}, "dimensions": ["X", "Y", "Z", "HeightAboveGround"], "classification_counts": {"1": 57266, "2": 751}}), encoding="utf-8")
    plan = root / f"{product}.json"
    plan.write_text(json.dumps({
        "source_dataset": "ohia_01_5m_norm.las", "source_report": str(report), "output_folder": str(root / "outputs"), "processing_executed": False,
        "parameters": {"grid_resolution": 1.0, "chm_output_filename": "chm.tif", "rumple_output_filename": "rumple.tif"},
        "products": [{"product": product, "label": product.upper(), "requested": True, "plan_status": "Needs review", "warnings": ["UNKNOWN_CRS", "NO_VEGETATION_CLASSES"]}],
    }), encoding="utf-8")
    return plan


class Phase30DValidationTests(unittest.TestCase):
    def test_hag_unknown_crs_no_vegetation_classes_reaches_chm_and_rumple(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for product in ("chm", "rumple"):
                context = load_pipeline_contexts(_plan(root, product), root / "logs")[0]
                result = build_default_pipeline_registry().get(product).run(context, adapter=_Adapter(), execute_products=True)
                self.assertTrue(result.passed)
                self.assertEqual(ProductValidationSeverity.NEEDS_ATTENTION, result.validation.severity)
                self.assertTrue(result.output_paths)

    def test_automatic_policy_bounds_source_concurrency(self):
        self.assertEqual(1, choose_automatic_execution(1).effective_workers)
        self.assertEqual(2, choose_automatic_execution(2).effective_workers)
        self.assertEqual(5, choose_automatic_execution(20).effective_workers)
        self.assertEqual(2, choose_automatic_execution(20, memory_worker_limit=2).effective_workers)
        self.assertEqual(1, choose_automatic_execution(1, source_type="ept").effective_workers)

    def test_new_request_does_not_reuse_historical_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "plot.las"
            source.touch()
            old = root / "out" / "pyforestscan_batch_old"
            old.mkdir(parents=True)
            (old / "batch_manifest.json").write_text("{}", encoding="utf-8")
            request = BatchRequest(root, root / "out", False, (source,), BatchProductSettings((ProductType.CHM,), 1.0))
            report = run_batch_preflight(request, adapter=_ReadyAdapter(), disk_usage_provider=lambda _p: (10**12, 0, 10**12))
            self.assertNotEqual(old, report.batch_folder)
            self.assertEqual((), report.files_completed)


if __name__ == "__main__":
    unittest.main()
