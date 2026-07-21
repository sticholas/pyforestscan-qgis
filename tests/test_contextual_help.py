"""QGIS-free/static checks for Mission Control contextual help."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ContextualHelpStaticTests(unittest.TestCase):
    def test_info_help_button_component_exists_with_accessible_fields(self) -> None:
        source = (ROOT / "pyforestscan_qgis/ui/help.py").read_text(encoding="utf-8")
        self.assertIn("class InfoHelpButton", source)
        self.assertIn("setToolTip", source)
        self.assertIn("setAccessibleName", source)
        self.assertIn("show_detail", source)

    def test_guided_batch_uses_plain_language_not_internal_strategy_labels(self) -> None:
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")
        batch = source[source.index("class BatchPage"):]
        self.assertIn("Automatic Setup (Recommended)", batch)
        self.assertIn("Prepare Repository", batch)
        self.assertIn("Use Built-in Spatial Access", batch)
        self.assertNotIn('addItem("existing_spatial_index"', batch)
        self.assertNotIn('addItem("native_hierarchical_source"', batch)


if __name__ == "__main__":
    unittest.main()
