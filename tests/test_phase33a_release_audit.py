"""Phase 33A release-audit and semantic-help contracts."""

from __future__ import annotations

import unittest
from pathlib import Path

from pyforestscan_qgis.ui.help_topics import SEMANTIC_ACTION_HELP, SEMANTIC_CONTEXT_HELP


ROOT = Path(__file__).resolve().parents[1]


class Phase33AReleaseAuditTests(unittest.TestCase):
    def test_version_drop_is_consistent(self) -> None:
        version = (ROOT / "pyforestscan_qgis/__version__.py").read_text(encoding="utf-8")
        metadata = (ROOT / "pyforestscan_qgis/metadata.txt").read_text(encoding="utf-8")
        self.assertIn('PLUGIN_VERSION = "0.2.0-beta.1"', version)
        self.assertIn("version=0.2.0-beta.1", metadata)

    def test_release_audit_files_exist(self) -> None:
        for relative in (
            "docs/development/PHASE_33A_RELEASE_PRODUCT_MAP.md",
            "docs/release/PHASE_33A_RELEASE_READINESS_SCORECARD.md",
            "docs/releases/v0.2.0-beta.1.md",
            "scripts/audit_qgis_controls.py",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_semantic_help_has_no_forbidden_placeholders(self) -> None:
        text = " ".join((*SEMANTIC_ACTION_HELP.values(), *SEMANTIC_CONTEXT_HELP.values())).lower()
        for phrase in ("this option", "this value", "continue this action", "use this control", "choose this option"):
            self.assertNotIn(phrase, text)

    def test_release_visible_actions_have_specific_help(self) -> None:
        for label in ("Analyze Dataset", "Build Plan", "Prerun Check", "Run Processing", "Cancel Processing", "Load into QGIS", "Repair Processing Engine"):
            self.assertGreater(len(SEMANTIC_ACTION_HELP[label]), 45)

    def test_qgis_smoke_uses_cross_qt_deferred_delete(self) -> None:
        source = (ROOT / "scripts/qgis_ui_startup_smoke.py").read_text(encoding="utf-8")
        self.assertIn('install_enum_aliases(QEvent, "Type", ("DeferredDelete",))', source)


if __name__ == "__main__":
    unittest.main()
