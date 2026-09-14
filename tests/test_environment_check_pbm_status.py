"""Regression tests for PBM status in Environment Check."""

from __future__ import annotations

import unittest

from pathlib import Path

import pyforestscan_qgis.core.backend as backend_module
from pyforestscan_qgis.core.backend.models import BackendPlatform, BackendRegistry, BackendState, BackendStatus, BackendVerificationResult
from pyforestscan_qgis.core.dependency_check import CheckStatus, _pbm_backend_status_check, collect_environment_report


class EnvironmentCheckPBMStatusTests(unittest.TestCase):
    """Ensure PBM diagnostics never crash clean-machine Environment Check."""

    def test_default_pbm_status_check_reports_without_name_error(self) -> None:
        report = collect_environment_report(import_module=lambda name: (_ for _ in ()).throw(ImportError(name)), include_pbm_backend=True)
        checks = {check.name: check for check in report.checks}

        self.assertIn("PBM managed backend", checks)
        self.assertIn(checks["PBM managed backend"].status, (CheckStatus.PASS, CheckStatus.WARNING))

    def test_repair_required_backend_reports_warning(self) -> None:
        original = backend_module.BackendService

        class FakeService:
            def verify_backend(self):
                return BackendVerificationResult(
                    status=BackendStatus.REPAIR_REQUIRED,
                    state=BackendState(BackendStatus.REPAIR_REQUIRED, BackendPlatform.LINUX, Path("/backend"), True, True, True, False, "repair"),
                    checks=(),
                    registry=BackendRegistry(()),
                    summary="Backend files are incomplete or required dependencies are missing.",
                )

        try:
            backend_module.BackendService = FakeService
            check = _pbm_backend_status_check()
        finally:
            backend_module.BackendService = original

        self.assertIs(check.status, CheckStatus.WARNING)
        self.assertIn("requires repair", check.message)


if __name__ == "__main__":
    unittest.main()
