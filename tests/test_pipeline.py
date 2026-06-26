"""Tests for the processing pipeline framework."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.pipeline import build_default_pipeline_registry, registered_product_ids
from pyforestscan_qgis.core.pipeline_context import load_pipeline_contexts
from pyforestscan_qgis.core.pipeline_results import PipelineStepStatus
from pyforestscan_qgis.core.pipeline_steps import PipelineStepKind


class PipelineFrameworkTests(unittest.TestCase):
    """Plain-Python tests for pipeline registration and validation."""

    def test_default_registry_contains_all_product_pipelines(self) -> None:
        """Each planned product has a registered pipeline."""
        registry = build_default_pipeline_registry()

        self.assertEqual(set(registered_product_ids()), {pipeline.product for pipeline in registry.all()})

    def test_validation_run_executes_only_validation_steps(self) -> None:
        """Dry-run pipeline execution validates and skips future science steps."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dataset_report = root / "dataset_report.json"
            dataset_report.write_text(json.dumps({"geometry": {"crs": "EPSG:32610"}}), encoding="utf-8")
            product_plan = _write_product_plan(root / "product_plan.json", dataset_report)
            context = load_pipeline_contexts(product_plan, root / "outputs")[0]
            pipeline = build_default_pipeline_registry().get("chm")

            result = pipeline.run_validation(context)

            self.assertTrue(result.passed)
            self.assertEqual(PipelineStepStatus.PASSED, result.steps[0].status)
            self.assertEqual(PipelineStepStatus.PASSED, result.steps[1].status)
            self.assertEqual(PipelineStepStatus.PASSED, result.steps[2].status)
            self.assertEqual(PipelineStepStatus.SKIPPED, result.steps[-1].status)

    def test_scientific_step_raises_when_called_directly(self) -> None:
        """Future scientific steps are explicit placeholders."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            product_plan = _write_product_plan(root / "product_plan.json", root / "missing_dataset.json")
            context = load_pipeline_contexts(product_plan, root / "outputs")[0]
            pipeline = build_default_pipeline_registry().get("chm")
            scientific_step = next(step for step in pipeline.steps if step.kind is PipelineStepKind.SCIENTIFIC)

            with self.assertRaises(NotImplementedError):
                scientific_step.execute(context)

    def test_missing_crs_is_warning_not_failure(self) -> None:
        """CRS validation warns when Dataset Explorer details are unavailable."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            product_plan = _write_product_plan(root / "product_plan.json", root / "missing_dataset.json")
            context = load_pipeline_contexts(product_plan, root / "outputs")[0]
            pipeline = build_default_pipeline_registry().get("chm")

            result = pipeline.run_validation(context)

            self.assertTrue(result.passed)
            self.assertIn(PipelineStepStatus.WARNING, {step.status for step in result.steps})


def _write_product_plan(path: Path, dataset_report: Path) -> Path:
    payload = {
        "title": "Pipeline Test Plan",
        "source_dataset": "plot.laz",
        "source_report": str(dataset_report),
        "processing_executed": False,
        "products": [
            {
                "product": "chm",
                "label": "Canopy Height Model (CHM)",
                "requested": True,
                "feasibility_status": "Available",
                "plan_status": "Ready",
                "reason": "Ready for future processing.",
                "warnings": [],
                "estimated_outputs": [],
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


if __name__ == "__main__":
    unittest.main()
