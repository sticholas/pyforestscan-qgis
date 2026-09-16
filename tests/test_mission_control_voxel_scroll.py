"""Regression coverage for Mission Control voxel controls and wheel safety."""
from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PAGES = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")


class MissionControlVoxelAndScrollTests(unittest.TestCase):
    def test_wheel_over_product_controls_moves_page_instead_of_values(self) -> None:
        self.assertIn('install_enum_aliases(QEvent, "Type", ("Enter", "FocusIn", "FocusOut", "Leave", "Wheel"))', PAGES)
        self.assertIn('isinstance(watched, (QComboBox, QAbstractSpinBox))', PAGES)
        self.assertIn('scrollbar.setValue(scrollbar.value() - vertical)', PAGES)
        self.assertIn('widget.setProperty("ignoreWheelValueChange", True)', PAGES)

    def test_batch_voxel_controls_cover_supported_request_options(self) -> None:
        for token in (
            "self.voxel_stat_dimension_combo",
            "self.voxel_stat_stat_combo",
            "self.voxel_stat_z_range_check",
            "self.voxel_stat_z_min_spin",
            "self.voxel_stat_z_max_spin",
            '"voxel_stat_dimension": self.voxel_stat_dimension_combo.currentText().strip()',
            '"voxel_stat_stat": self.voxel_stat_stat_combo.currentText().strip().lower()',
            '"voxel_stat_z_index_range": voxel_z_index_range',
        ):
            self.assertIn(token, PAGES)

    def test_planning_passes_voxel_options_to_product_plan(self) -> None:
        for token in (
            "self.planning_voxel_stat_dimension_combo",
            "self.planning_voxel_stat_stat_combo",
            "self.planning_voxel_stat_z_range_check",
            "voxel_stat_dimension=self.planning_voxel_stat_dimension_combo.currentText().strip()",
            "voxel_stat_z_index_range=voxel_z_index_range",
        ):
            self.assertIn(token, PAGES)


if __name__ == "__main__":
    unittest.main()
