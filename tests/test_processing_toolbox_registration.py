"""Static tests for QGIS Processing Toolbox registration decisions."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ProcessingToolboxRegistrationTests(unittest.TestCase):
    """Provider registration remains QGIS-free to audit by source."""

    def test_legacy_guided_toolbox_algorithms_are_not_registered(self) -> None:
        provider = (ROOT / "pyforestscan_qgis/processing_provider.py").read_text(encoding="utf-8")

        self.assertIn("self.addAlgorithm(EnvironmentCheckAlgorithm())", provider)
        self.assertNotIn("self.addAlgorithm(DatasetExplorerAlgorithm())", provider)
        self.assertNotIn("self.addAlgorithm(ProductPlannerAlgorithm())", provider)
        self.assertNotIn("self.addAlgorithm(ForestMetricsPackAlgorithm())", provider)

    def test_environment_check_is_in_diagnostics_group(self) -> None:
        source = (ROOT / "pyforestscan_qgis/algorithms/placeholder_algorithms.py").read_text(encoding="utf-8")

        self.assertIn('return self.tr("PyForestScan / Diagnostics")', source)
        self.assertIn('return "pyforestscan_diagnostics"', source)

    def test_expert_toolbox_uses_clean_groups_without_advanced_prefix(self) -> None:
        common = (ROOT / "pyforestscan_qgis/algorithms/advanced/common.py").read_text(encoding="utf-8")
        advanced_dir = ROOT / "pyforestscan_qgis/algorithms/advanced"
        combined = "\n".join(path.read_text(encoding="utf-8") for path in advanced_dir.glob("*.py"))

        self.assertIn('return self.tr(f"PyForestScan / {self.ADVANCED_GROUP}")', common)
        self.assertNotIn("PyForestScan / Advanced", common)
        for old_name in (
            "Advanced CHM",
            "Advanced PAD",
            "Advanced PAI",
            "Advanced Canopy Cover",
            "Advanced FHD",
            "Advanced Rumple",
            "Advanced Point Density",
            "Advanced Voxel Statistic",
            "Advanced DTM",
            "Advanced Point Cloud Preprocess / Filters",
        ):
            self.assertNotIn(f'return self.tr("{old_name}")', combined)


if __name__ == "__main__":
    unittest.main()
