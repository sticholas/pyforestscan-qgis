"""Tests for Scientific Advisor support helpers."""

from __future__ import annotations

import unittest
from pathlib import Path

from pyforestscan_qgis.core.jobs import JobMode, JobRecord, JobResultRecord, JobStatus
from pyforestscan_qgis.ui.advisor import (
    PRODUCT_EXPLANATIONS,
    QGIS_TOOL_INSTRUCTIONS,
    completed_products_from_job,
    product_explanations_by_id,
)


class AdvisorSupportTests(unittest.TestCase):
    """Advisor content helpers stay independent from QGIS."""

    def test_product_explanations_cover_all_implemented_products(self) -> None:
        """Every implemented product has an explanation card."""
        explanations = product_explanations_by_id()

        self.assertEqual({"chm", "canopy_cover", "pad", "pai", "fhd", "rumple"}, set(explanations))
        for explanation in PRODUCT_EXPLANATIONS:
            self.assertTrue(explanation.measures)
            self.assertTrue(explanation.use_when)
            self.assertTrue(explanation.be_cautious_when)
            self.assertIn("QGIS", explanation.qgis_inspection)

    def test_qgis_tool_instructions_recommend_existing_qgis_tools(self) -> None:
        """Advisor tool guidance references QGIS tools rather than rebuilding them."""
        names = {item.tool_name for item in QGIS_TOOL_INSTRUCTIONS}

        self.assertIn("Processing Toolbox", names)
        self.assertIn("Layer Styling / Symbology", names)
        self.assertIn("Raster Histogram", names)
        self.assertIn("Raster Calculator", names)
        self.assertIn("3D View", names)
        self.assertIn("Layout Manager", names)

    def test_completed_products_from_job_uses_result_records(self) -> None:
        """Completed products are derived from job result types."""
        job = JobRecord(
            job_id="job-1",
            title="Advisor job",
            status=JobStatus.COMPLETED,
            mode=JobMode.PROCESSING,
            product_plan_path=Path("plan.json"),
            output_folder=Path("outputs"),
            summary_path=None,
            created_at="now",
            updated_at="now",
            results=(
                JobResultRecord(Path("chm.tif"), "chm_geotiff", "CHM"),
                JobResultRecord(Path("pad.tif"), "pad_geotiff", "PAD"),
                JobResultRecord(Path("summary.json"), "job_summary_json", "Summary"),
            ),
        )

        self.assertEqual(("chm", "pad"), completed_products_from_job(job))


if __name__ == "__main__":
    unittest.main()
