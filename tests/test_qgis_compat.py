"""Tests for QGIS compatibility reporting without QGIS."""

from __future__ import annotations

import unittest

from pyforestscan_qgis.core.qgis_compat import build_qgis_compatibility_report, format_qgis_compatibility_report, parse_qgis_major


class _FakeRegistry:
    def addProvider(self, provider):
        return None

    def removeProvider(self, provider):
        return None


class _FakeQgsApplication:
    @staticmethod
    def processingRegistry():
        return _FakeRegistry()


class _FakeCore3:
    class Qgis:
        QGIS_VERSION = "3.44.1"

    QgsApplication = _FakeQgsApplication
    QgsProcessingProvider = object
    QgsProject = object
    QgsMessageLog = object


class _FakeCore4:
    class Qgis:
        QGIS_VERSION = "4.0.0"

    QgsApplication = _FakeQgsApplication
    QgsProcessingProvider = object
    QgsProject = object
    QgsMessageLog = object


class _FakeQtCore:
    QT_VERSION_STR = "6.7.0"
    QSettings = object


class QgisCompatibilityTests(unittest.TestCase):
    """Validate defensive QGIS compatibility parsing and reporting."""

    def test_parse_qgis_major(self) -> None:
        self.assertEqual(parse_qgis_major("3.44.1"), 3)
        self.assertEqual(parse_qgis_major("4.0.0 future"), 4)
        self.assertIsNone(parse_qgis_major("unknown"))

    def test_qgis_3_report_is_supported(self) -> None:
        report = build_qgis_compatibility_report(qgis_core=_FakeCore3, qt_core=_FakeQtCore, python_version="3.12.5", platform_name="test")

        self.assertEqual(report.major_version, 3)
        self.assertTrue(report.plugin_api_available)
        self.assertTrue(report.processing_provider_compatible)
        self.assertTrue(report.supported_target)
        self.assertEqual(report.warnings, ())

    def test_qgis_4_report_is_defensive_supported_target(self) -> None:
        report = build_qgis_compatibility_report(qgis_core=_FakeCore4, qt_core=_FakeQtCore, python_version="3.12.5", platform_name="test")

        self.assertEqual(report.major_version, 4)
        self.assertTrue(report.supported_target)
        self.assertTrue(any("QGIS 4.x" in warning for warning in report.warnings))

    def test_missing_qgis_fails_gracefully(self) -> None:
        report = build_qgis_compatibility_report(qgis_version="Unavailable", qt_version="Unavailable", platform_name="test")
        text = format_qgis_compatibility_report(report)

        self.assertFalse(report.supported_target)
        self.assertIn("QGIS Compatibility", text)
        self.assertTrue(report.warnings)


if __name__ == "__main__":
    unittest.main()
