"""Tests for the deterministic Knowledge Engine."""

from __future__ import annotations

import unittest

from pyforestscan_qgis.core.knowledge import (
    KnowledgeConfig,
    KnowledgeEngine,
    KnowledgeThreshold,
    evaluate_dataset_explorer_report,
    report_to_dict,
)


def explorer_payload() -> dict[str, object]:
    """Return a representative Dataset Explorer JSON payload."""
    return {
        "dataset": {"source_path": "plot.laz", "format": "laz", "metadata_source": "pdal-pipeline"},
        "geometry": {
            "bounds": {"min_x": 0.0, "max_x": 100.0, "min_y": 0.0, "max_y": 50.0, "min_z": 0.0, "max_z": 25.0},
            "crs": "EPSG:32610",
            "estimated_density_points_per_square_unit": 25.0,
        },
        "point_statistics": {
            "point_count": 125000,
            "dimensions": ["X", "Y", "Z", "Classification", "HeightAboveGround"],
            "classification_summary": [
                {"classification": 2, "count": 25000},
                {"classification": 5, "count": 100000},
            ],
        },
        "warnings": [],
        "supported_products": [
            {"product": "chm", "label": "Canopy Height Model (CHM)", "status": "Available", "reason": "Ready."},
            {"product": "pad", "label": "Plant Area Density (PAD)", "status": "Warning", "reason": "Review bins."},
        ],
    }


class KnowledgeEngineTests(unittest.TestCase):
    """Knowledge Engine behavior is deterministic and transparent."""

    def test_report_contains_products_parameters_tools_and_thresholds(self) -> None:
        """A ready high-density report produces structured recommendations."""
        report = evaluate_dataset_explorer_report(explorer_payload())

        self.assertGreaterEqual(report.dataset_score, 90)
        self.assertEqual(5, report.confidence_stars)
        self.assertEqual("recommended", report.recommended_products[0].status)
        chm_parameters = [item for item in report.recommended_parameters if item.product == "chm"]
        self.assertEqual(1, len(chm_parameters))
        self.assertEqual(0.5, chm_parameters[0].value)
        self.assertTrue(chm_parameters[0].calibration_required)
        self.assertTrue(report.qgis_tool_suggestions)
        self.assertTrue(any(threshold.calibration_required for threshold in report.thresholds))

    def test_low_density_threshold_is_configurable(self) -> None:
        """Density guidance follows explicit configuration, not hidden constants."""
        payload = explorer_payload()
        payload["geometry"]["estimated_density_points_per_square_unit"] = 3.0  # type: ignore[index]
        config = KnowledgeConfig(
            low_density_points_per_square_unit=KnowledgeThreshold(
                "low_density_points_per_square_unit", 4.0, "points per square map unit", "Project-specific conservative threshold."
            ),
            conservative_chm_resolution=KnowledgeThreshold(
                "conservative_chm_resolution", 2.0, "map units", "Project-specific conservative grid."
            ),
        )

        report = KnowledgeEngine(config=config).evaluate_dataset_explorer_report(payload)

        chm_parameter = next(item for item in report.recommended_parameters if item.product == "chm")
        self.assertEqual(2.0, chm_parameter.value)
        self.assertIn("low_density_points_per_square_unit", chm_parameter.threshold_names)

    def test_missing_hag_and_geographic_crs_are_reported(self) -> None:
        """Known scientific prerequisites become warnings, not silent assumptions."""
        payload = explorer_payload()
        payload["geometry"]["crs"] = "EPSG:4326"  # type: ignore[index]
        payload["point_statistics"]["dimensions"] = ["X", "Y", "Z", "Classification"]  # type: ignore[index]

        report = evaluate_dataset_explorer_report(payload)
        warning_codes = {item.code for item in report.warnings}

        self.assertIn("HAG_MISSING", warning_codes)
        self.assertIn("CRS_GEOGRAPHIC", warning_codes)
        self.assertLess(report.dataset_score, 100)

    def test_rumple_area_threshold_is_not_invented_by_default(self) -> None:
        """Rumple area stability is documented as unconfigured unless supplied."""
        report = evaluate_dataset_explorer_report(explorer_payload())

        notes = {item.code for item in report.scientific_notes}
        self.assertIn("RUMPLE_AREA_THRESHOLD_UNCONFIGURED", notes)

    def test_report_serialization_uses_plain_values(self) -> None:
        """Recommendation reports can be serialized for future JSON outputs."""
        payload = report_to_dict(evaluate_dataset_explorer_report(explorer_payload()))

        self.assertIn("dataset_score", payload)
        self.assertEqual("info", payload["scientific_notes"][0]["severity"])
        self.assertIn("thresholds", payload)


if __name__ == "__main__":
    unittest.main()
