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

    def test_visible_tool_names_are_professional(self) -> None:
        advanced_dir = ROOT / "pyforestscan_qgis/algorithms/advanced"
        combined = "\n".join(path.read_text(encoding="utf-8") for path in advanced_dir.glob("*.py"))

        for expected_name in (
            "CHM",
            "PAD",
            "PAI",
            "Canopy Cover",
            "FHD",
            "Rumple",
            "Point Density",
            "Voxel Statistic",
            "Generate DTM",
            "Normalize Heights",
            "Preprocess Point Cloud",
        ):
            self.assertIn(f'return self.tr("{expected_name}")', combined)

    def test_critical_parameter_labels_and_defaults_are_present(self) -> None:
        advanced_dir = ROOT / "pyforestscan_qgis/algorithms/advanced"
        combined = "\n".join(path.read_text(encoding="utf-8") for path in advanced_dir.glob("*.py"))
        common = (advanced_dir / "common.py").read_text(encoding="utf-8")

        for label in (
            "Input LiDAR dataset (LAS, LAZ, COPC, or EPT)",
            "Dataset CRS / SRS",
            "X resolution (map units)",
            "Y resolution (map units)",
            "voxel_height / height bin size (map units)",
            "min_height (map units)",
            "max_height (map units, optional)",
            "beer_lambert_constant",
            "drop_ground",
            "k / extinction coefficient",
            "SMRF cell",
            "voxel downsample cell",
            "HAG method",
            "resolution (map units)",
            "nodata",
        ):
            self.assertIn(label, combined + common)

        for default in ("defaultValue=1.0", "defaultValue=0.5", "defaultValue=-9999.0", "defaultValue=18.0"):
            self.assertIn(default, combined + common)

    def test_metadata_describes_current_processing_capabilities(self) -> None:
        metadata = (ROOT / "pyforestscan_qgis/metadata.txt").read_text(encoding="utf-8")

        self.assertIn("CHM", metadata)
        self.assertIn("Canopy Cover", metadata)
        self.assertIn("point-cloud preprocessing", metadata)
        self.assertNotIn("Scientific product generation is not implemented yet", metadata)

    def test_external_workers_remain_disabled_in_release_docs(self) -> None:
        limitations = (ROOT / "docs/KNOWN_LIMITATIONS.md").read_text(encoding="utf-8")
        external_workers = (ROOT / "docs/development/EXTERNAL_WORKERS.md").read_text(encoding="utf-8")

        self.assertIn("External Worker mode is disabled", limitations)
        self.assertIn("disabled", external_workers.lower())



if __name__ == "__main__":
    unittest.main()
