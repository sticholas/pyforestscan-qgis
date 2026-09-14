"""Phase 32Z product-owned Advanced scientific settings contracts."""

from __future__ import annotations

import unittest
from pathlib import Path

from pyforestscan_qgis.ui.help_topics import scientific_group_help
from pyforestscan_qgis.core.qgis_compat import QgisCompatibilityReport, qgis_release_qualification


ROOT = Path(__file__).resolve().parents[1]
PAGES = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")


class Phase32ZScientificGroupingTests(unittest.TestCase):
    @staticmethod
    def _compat(version: str, platform: str) -> QgisCompatibilityReport:
        return QgisCompatibilityReport(version, int(version.split(".")[0]), "3.12", "6.0", platform, True, True, True, True, True)

    def test_groups_are_stacked_in_stable_scientific_order(self) -> None:
        expected = '("Shared Settings", "CHM", "DTM", "PAD", "PAI", "FHD", "Canopy Cover", "Rumple", "Point Density")'
        self.assertIn(expected, PAGES)
        self.assertNotIn("scientific_form_columns", PAGES)
        self.assertNotIn("min(range(2), key=lambda index: loads[index])", PAGES)

    def test_empty_groups_have_zero_layout_presence(self) -> None:
        self.assertIn("group_widget.setVisible(bool(rows))", PAGES)
        self.assertNotIn("heading = _details_label(group_name)\n            form.addRow", PAGES)

    def test_rows_have_stable_semantic_identities(self) -> None:
        for key in (
            "shared.grid_resolution", "shared.height_bin_size", "chm.interpolation",
            "pad.beer_lambert_constant", "pad.drop_ground", "pai.min_height",
            "pai.max_height", "fhd.min_height", "fhd.max_height",
            "canopy_cover.min_height", "canopy_cover.max_height", "canopy_cover.k",
            "rumple.min_height", "point_density.per_area",
        ):
            self.assertIn(f'"{key}"', PAGES)
        self.assertIn('field.setProperty("scientificParameterKey", key)', PAGES)

    def test_accessible_names_include_product_context(self) -> None:
        self.assertIn('field.setAccessibleName(f"{group_name} {label_text or field.text()}".strip())', PAGES)
        self.assertIn("Foliage Height Diversity", scientific_group_help("FHD"))
        self.assertIn("Plant Area Density", scientific_group_help("PAD"))

    def test_dependency_defaults_do_not_create_unselected_product_groups(self) -> None:
        self.assertIn("self.pad_beer_lambert_spin: ProductType.PAD in selected", PAGES)
        self.assertIn("self.pad_drop_ground_check: ProductType.PAD in selected", PAGES)
        self.assertIn("ProductType.CANOPY_COVER", PAGES)

    def test_rebuild_moves_existing_widgets_without_recreating_values(self) -> None:
        rebuild = PAGES[PAGES.index("def _rebuild_product_settings_form"):PAGES.index("def _update_adaptive_visibility")]
        self.assertNotIn("QDoubleSpinBox(", rebuild)
        self.assertNotIn("deleteLater", rebuild)
        self.assertIn("form.takeAt(0)", rebuild)

    def test_diagnostics_do_not_overstate_qgis_release_support(self) -> None:
        self.assertEqual("SUPPORTED WITH LIMITATIONS", qgis_release_qualification(self._compat("3.44.13", "Windows-11")))
        self.assertIn("UI-COMPATIBLE", qgis_release_qualification(self._compat("4.0.0", "Windows-11")))
        self.assertIn("NOT TESTED", qgis_release_qualification(self._compat("4.2.2", "Windows-11")))
        self.assertIn("NOT TESTED", qgis_release_qualification(self._compat("3.44.14", "macOS")))


if __name__ == "__main__":
    unittest.main()
