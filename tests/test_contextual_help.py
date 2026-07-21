"""QGIS-free/static checks for Mission Control contextual help."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ContextualHelpStaticTests(unittest.TestCase):
    def test_info_help_button_component_exists_with_accessible_fields(self) -> None:
        source = (ROOT / "pyforestscan_qgis/ui/help.py").read_text(encoding="utf-8")
        self.assertIn("class InfoBadge", source)
        self.assertIn("class InfoHelpButton", source)
        self.assertIn("INFO_BADGE_STYLESHEET", source)
        self.assertIn("#1976d2", source)
        self.assertIn("border-radius", source)
        self.assertIn("setToolTip", source)
        self.assertIn("setAccessibleName", source)
        self.assertIn("keyPressEvent", source)
        self.assertIn("show_detail", source)

    def test_guided_batch_uses_plain_language_not_internal_strategy_labels(self) -> None:
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")
        batch = source[source.index("class BatchPage"):]
        self.assertIn("Automatic Setup (Recommended)", batch)
        self.assertIn("Prepare Repository", batch)
        self.assertIn("Use Built-in Spatial Access", batch)
        self.assertNotIn('addItem("existing_spatial_index"', batch)
        self.assertNotIn('addItem("native_hierarchical_source"', batch)

    def test_help_topics_registry_and_coverage_script_exist(self) -> None:
        topics = (ROOT / "pyforestscan_qgis/ui/help_topics.py").read_text(encoding="utf-8")
        script = (ROOT / "scripts/check_help_coverage.py").read_text(encoding="utf-8")
        self.assertIn("class HelpTopic", topics)
        self.assertIn("HELP_TOPICS", topics)
        self.assertIn("home.backend_status", topics)
        self.assertIn("processing.chm", topics)
        self.assertIn("registered_topics", script)
        self.assertIn("used_topics", script)

    def test_batch_help_uses_registered_topic_keys(self) -> None:
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")
        self.assertIn('info_badge("batch.lidar_repository"', source)
        self.assertIn('info_badge("batch.polygon"', source)
        self.assertIn('info_badge("batch.repository_setup_method"', source)


if __name__ == "__main__":
    unittest.main()
