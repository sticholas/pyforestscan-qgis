"""Tests for the plain-Python environment validation layer."""

from __future__ import annotations

import unittest
from types import ModuleType, SimpleNamespace

from pyforestscan_qgis.core.dependency_check import (
    CheckStatus,
    EnvironmentCheckResult,
    ReadinessStatus,
    build_environment_report,
    collect_environment_report,
    format_environment_report,
)


class FakeImporter:
    """Small import hook used to test diagnostics without QGIS installed."""

    def __init__(self, modules: dict[str, ModuleType]) -> None:
        self.modules = modules

    def __call__(self, name: str) -> ModuleType:
        if name not in self.modules:
            raise ImportError(f"No module named {name}")
        return self.modules[name]


def module_with_version(version: str) -> ModuleType:
    """Create a fake module with a __version__ attribute."""
    module = ModuleType("fake")
    module.__version__ = version
    return module


class DependencyCheckTests(unittest.TestCase):
    """Plain-Python tests for environment diagnostics."""

    def test_missing_dependencies_are_reported_without_crashing(self) -> None:
        def unexpected_lookup(package: str) -> str:
            self.fail(f"unexpected lookup: {package}")

        report = collect_environment_report(
            plugin_path="/tmp/plugin",
            import_module=FakeImporter({}),
            version_lookup=unexpected_lookup,
            pbm_backend_check=lambda: EnvironmentCheckResult("PBM managed backend", CheckStatus.PASS, "Managed backend verified as READY."),
            execution_backend_check=lambda: EnvironmentCheckResult("Active execution backend", CheckStatus.PASS, "PyForestScan Backend Manager will be preferred."),
        )

        statuses = {check.name: check.status for check in report.checks}

        self.assertIs(statuses["pyforestscan"], CheckStatus.WARNING)
        self.assertIs(statuses["pdal"], CheckStatus.WARNING)
        self.assertIs(statuses["osgeo.gdal"], CheckStatus.WARNING)
        self.assertIs(statuses["rasterio"], CheckStatus.WARNING)
        self.assertIs(statuses["numpy"], CheckStatus.WARNING)
        self.assertIs(statuses["QGIS version"], CheckStatus.WARNING)
        self.assertIs(report.readiness, ReadinessStatus.READY)
        self.assertIn("Execution Backend: PBM Backend", report.summary)
        guidance = {check.name: check.guidance for check in report.checks}
        self.assertIn("QGIS-Python-only tools", guidance["pyforestscan"])
        self.assertIn("manual fallback", guidance["pdal"])
        self.assertIn("manual fallback", guidance["osgeo.gdal"])

    def test_dependency_report_creation_for_ready_environment(self) -> None:
        gdal = ModuleType("osgeo.gdal")
        gdal.VersionInfo = lambda argument="": "GDAL 3.8.0"
        qgis_core = ModuleType("qgis.core")
        qgis_core.Qgis = SimpleNamespace(QGIS_VERSION="3.34.0")
        modules = {
            "qgis.core": qgis_core,
            "pyforestscan": module_with_version("0.2.0"),
            "pdal": module_with_version("3.4.5"),
            "osgeo.gdal": gdal,
            "rasterio": module_with_version("1.3.9"),
            "numpy": module_with_version("1.26.0"),
        }

        report = collect_environment_report(
            plugin_path="/tmp/plugin",
            import_module=FakeImporter(modules),
            version_lookup=lambda package: "metadata-version",
            pbm_backend_check=lambda: EnvironmentCheckResult("PBM managed backend", CheckStatus.PASS, "Managed backend verified as READY."),
            execution_backend_check=lambda: EnvironmentCheckResult("Active execution backend", CheckStatus.PASS, "PyForestScan Backend Manager will be preferred."),
        )

        self.assertIs(report.readiness, ReadinessStatus.READY)
        self.assertTrue(all(check.status is CheckStatus.PASS for check in report.checks))
        versions = {check.name: check.version for check in report.checks}
        self.assertEqual(versions["QGIS version"], "3.34.0")
        self.assertEqual(versions["osgeo.gdal"], "GDAL 3.8.0")

    def test_pbm_backend_warning_is_reported_without_lowering_missing_dependency_clarity(self) -> None:
        report = collect_environment_report(
            plugin_path="/tmp/plugin",
            import_module=FakeImporter({}),
            version_lookup=lambda package: "metadata-version",
            pbm_backend_check=lambda: EnvironmentCheckResult("PBM managed backend", CheckStatus.WARNING, "Managed backend status: Not Installed."),
            execution_backend_check=lambda: EnvironmentCheckResult("Active execution backend", CheckStatus.WARNING, "QGIS Python will be used."),
        )

        statuses = {check.name: check.status for check in report.checks}
        self.assertIs(statuses["PBM managed backend"], CheckStatus.WARNING)
        self.assertIs(statuses["pyforestscan"], CheckStatus.FAIL)
        self.assertIs(statuses["pdal"], CheckStatus.FAIL)
        self.assertIs(report.readiness, ReadinessStatus.NOT_READY)

    def test_qgis_dependencies_missing_and_pbm_ready_is_overall_ready(self) -> None:
        report = collect_environment_report(
            plugin_path="/tmp/plugin",
            import_module=FakeImporter({}),
            version_lookup=lambda package: "metadata-version",
            pbm_backend_check=lambda: EnvironmentCheckResult("PBM managed backend", CheckStatus.PASS, "PBM backend is READY. Backend Python: /tmp/pbm/env/bin/python."),
            execution_backend_check=lambda: EnvironmentCheckResult("Active execution backend", CheckStatus.PASS, "PyForestScan Backend Manager will be preferred."),
        )
        rendered = format_environment_report(report)
        statuses = {check.name: check.status for check in report.checks}
        messages = {check.name: check.message for check in report.checks}

        self.assertIs(report.readiness, ReadinessStatus.READY)
        self.assertIn("QGIS Python fallback environment", rendered)
        self.assertNotIn("QGIS Python Scientific Packages", rendered)
        self.assertIs(statuses["pyforestscan"], CheckStatus.WARNING)
        self.assertIs(statuses["pdal"], CheckStatus.WARNING)
        self.assertIn("Not installed — optional when PBM backend is READY.", messages["pyforestscan"])
        self.assertIn("Not installed — optional when PBM backend is READY.", messages["pdal"])
        self.assertNotIn("[FAIL] pyforestscan", rendered)
        self.assertNotIn("[FAIL] pdal", rendered)
        self.assertIn("PBM Backend: READY", rendered)
        self.assertIn("Backend Python", rendered)
        self.assertIn("Execution Backend: PBM Backend", rendered)
        self.assertIn("PBM-routed products", rendered)
        self.assertIn("Overall Environment Status: READY", rendered)
        self.assertIn("Final summary: READY", rendered)
        self.assertNotIn("Final summary: NOT READY", rendered)
        self.assertNotIn("processing cannot run", rendered.lower())

    def test_pbm_ready_report_does_not_list_pyforestscan_or_pdal_as_blocking_failures(self) -> None:
        report = collect_environment_report(
            plugin_path="/tmp/plugin",
            import_module=FakeImporter({}),
            version_lookup=lambda package: "metadata-version",
            pbm_backend_check=lambda: EnvironmentCheckResult("PBM managed backend", CheckStatus.PASS, "Managed backend verified as READY."),
            execution_backend_check=lambda: EnvironmentCheckResult("Active execution backend", CheckStatus.PASS, "PBM Backend"),
        )
        rendered = format_environment_report(report)

        self.assertNotIn("[FAIL] pyforestscan", rendered)
        self.assertNotIn("[FAIL] pdal", rendered)
        self.assertNotIn("pyforestscan: Could not import", rendered)
        self.assertNotIn("pdal: Could not import", rendered)

    def test_qgis_dependencies_missing_and_pbm_missing_is_not_ready(self) -> None:
        report = collect_environment_report(
            plugin_path="/tmp/plugin",
            import_module=FakeImporter({}),
            version_lookup=lambda package: "metadata-version",
            pbm_backend_check=lambda: EnvironmentCheckResult("PBM managed backend", CheckStatus.WARNING, "Managed backend status: Not Installed."),
            execution_backend_check=lambda: EnvironmentCheckResult("Active execution backend", CheckStatus.WARNING, "QGIS Python will be used."),
        )

        self.assertIs(report.readiness, ReadinessStatus.NOT_READY)

    def test_qgis_dependencies_ready_and_pbm_missing_is_ready_with_qgis_python(self) -> None:
        gdal = ModuleType("osgeo.gdal")
        gdal.VersionInfo = lambda argument="": "GDAL 3.8.0"
        modules = {
            "pyforestscan": module_with_version("0.2.0"),
            "pdal": module_with_version("3.4.5"),
            "osgeo.gdal": gdal,
            "rasterio": module_with_version("1.3.9"),
            "numpy": module_with_version("1.26.0"),
        }
        report = collect_environment_report(
            plugin_path="/tmp/plugin",
            import_module=FakeImporter(modules),
            version_lookup=lambda package: "metadata-version",
            pbm_backend_check=lambda: EnvironmentCheckResult("PBM managed backend", CheckStatus.WARNING, "Managed backend status: Not Installed."),
            execution_backend_check=lambda: EnvironmentCheckResult("Active execution backend", CheckStatus.WARNING, "QGIS Python will be used."),
        )

        self.assertIs(report.readiness, ReadinessStatus.READY_WITH_QGIS_PYTHON)
        self.assertIn("QGIS Python fallback environment is ready", report.summary)

    def test_no_manual_setup_scope_reports_routed_products(self) -> None:
        report = collect_environment_report(
            plugin_path="/tmp/plugin",
            import_module=FakeImporter({}),
            version_lookup=lambda package: "metadata-version",
            pbm_backend_check=lambda: EnvironmentCheckResult("PBM managed backend", CheckStatus.PASS, "Managed backend verified as READY."),
            execution_backend_check=lambda: EnvironmentCheckResult("Active execution backend", CheckStatus.PASS, "PyForestScan Backend Manager will be preferred."),
        )

        checks = {check.name: check for check in report.checks}
        self.assertIs(checks["No-manual-setup scope"].status, CheckStatus.PASS)
        self.assertIn("Dataset Explorer", checks["No-manual-setup scope"].message)
        self.assertIn("Voxel Statistic", checks["No-manual-setup scope"].guidance)

    def test_report_formatting_includes_statuses_guidance_and_summary(self) -> None:
        report = build_environment_report(
            [
                EnvironmentCheckResult(
                    name="pyforestscan",
                    status=CheckStatus.FAIL,
                    message="Could not import pyforestscan",
                    guidance="Install PyForestScan into QGIS Python.",
                ),
                EnvironmentCheckResult(
                    name="QGIS version",
                    status=CheckStatus.WARNING,
                    message="Version unknown.",
                ),
            ]
        )

        rendered = format_environment_report(report)

        self.assertIn("[FAIL] pyforestscan: Could not import pyforestscan", rendered)
        self.assertIn("Guidance: Install PyForestScan into QGIS Python.", rendered)
        self.assertIn("[WARNING] QGIS version: Version unknown.", rendered)
        self.assertIn("Final summary: NOT READY", rendered)
        self.assertIn("Recommended Next Step:", rendered)
        self.assertIn("Installation guidance:", rendered)
        self.assertIn("ZIP installation only installs the QGIS plugin", rendered)

    def test_warning_only_report_is_partially_ready(self) -> None:
        report = build_environment_report(
            [
                EnvironmentCheckResult(
                    name="rasterio",
                    status=CheckStatus.WARNING,
                    message="Imported, version unknown.",
                )
            ]
        )

        self.assertIs(report.readiness, ReadinessStatus.PARTIALLY_READY)


if __name__ == "__main__":
    unittest.main()
