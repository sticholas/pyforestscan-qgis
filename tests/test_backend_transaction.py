"""Tests for transactional backend installer orchestration."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.backend.download_manager import CancellationToken
from pyforestscan_qgis.core.backend.models import BackendOperationResult, BackendPlatform, BackendStatus
from pyforestscan_qgis.core.backend.paths import resolve_backend_paths
from pyforestscan_qgis.core.backend.transaction import BackendInstallTransaction, BackendTransactionStage


class FakeDownload:
    success = True
    message = "downloaded"
    path = Path("artifact")


class FakeChecksum:
    message = "checksum ok"

    def passed(self) -> bool:
        return True


class FakeVerification:
    summary = "verified"

    def passed(self) -> bool:
        return True


class FakeInstaller:
    def __init__(self, fail_stage: str | None = None) -> None:
        self.fail_stage = fail_stage
        self.rollback_called = False

    def require_enabled(self, operation: str):
        return None

    def prepare_staging(self):
        return self._result("prepare_staging")

    def download_micromamba(self, policy=None):
        if self.fail_stage == "download":
            return type("Download", (), {"success": False, "message": "download failed", "path": Path("artifact")})()
        return FakeDownload()

    def verify_micromamba_download(self, policy=None):
        if self.fail_stage == "verify":
            return type("Checksum", (), {"message": "bad checksum", "passed": lambda self: False})()
        return FakeChecksum()

    def extract_micromamba(self, policy=None):
        return self._result("extract_micromamba")

    def create_environment(self, spec_file=None):
        return self._result("create_environment")

    def verify_environment(self):
        if self.fail_stage == "verify_environment":
            return type("Verification", (), {"summary": "missing packages", "passed": lambda self: False})()
        return FakeVerification()

    def verify_active_backend(self):
        if self.fail_stage == "verify_active_backend":
            return type("Verification", (), {"summary": "active backend incomplete", "passed": lambda self: False})()
        return FakeVerification()

    def promote_staging(self):
        return self._result("promote_staging")

    def write_backend_config(self, status=BackendStatus.READY):
        return self._result("write_backend_config", status=status)

    def rollback_failed_install(self):
        self.rollback_called = True
        return BackendOperationResult("rollback_failed_install", BackendStatus.REPAIR_REQUIRED, True, "rolled back", True)

    def _result(self, operation: str, status: BackendStatus = BackendStatus.INSTALLING):
        if self.fail_stage == operation:
            return BackendOperationResult(operation, BackendStatus.FAILED, False, f"{operation} failed", True)
        return BackendOperationResult(operation, status, True, f"{operation} ok", True)


class BackendTransactionTests(unittest.TestCase):
    """Validate rollback, success, and cancellation transaction behavior."""

    def test_transaction_success_reaches_ready(self) -> None:
        installer = FakeInstaller()
        result = BackendInstallTransaction(installer).run()

        self.assertTrue(result.success)
        self.assertEqual(result.status, BackendStatus.READY)
        self.assertEqual(result.stage, BackendTransactionStage.READY)
        self.assertTrue(installer.rollback_called)

    def test_transaction_rolls_back_on_stage_failure(self) -> None:
        installer = FakeInstaller(fail_stage="extract_micromamba")
        result = BackendInstallTransaction(installer).run()

        self.assertFalse(result.success)
        self.assertEqual(result.stage, BackendTransactionStage.EXTRACT)
        self.assertTrue(result.rolled_back)
        self.assertTrue(installer.rollback_called)

    def test_transaction_rolls_back_on_verification_failure(self) -> None:
        installer = FakeInstaller(fail_stage="verify_environment")
        result = BackendInstallTransaction(installer).run()

        self.assertFalse(result.success)
        self.assertEqual(result.status, BackendStatus.REPAIR_REQUIRED)
        self.assertEqual(result.stage, BackendTransactionStage.VERIFY_PACKAGES)
        self.assertTrue(installer.rollback_called)

    def test_transaction_cancelled_rolls_back(self) -> None:
        installer = FakeInstaller()
        token = CancellationToken(cancelled=True)
        result = BackendInstallTransaction(installer).run(cancel_token=token)

        self.assertFalse(result.success)
        self.assertTrue(result.rolled_back)
        self.assertEqual(result.stage, BackendTransactionStage.DOWNLOAD)

    def test_guarded_installer_still_does_not_modify_without_flag(self) -> None:
        from pyforestscan_qgis.core.backend.installer import BackendInstaller

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = resolve_backend_paths(backend_root=Path(tmpdir) / "backend", platform=BackendPlatform.LINUX)
            result = BackendInstaller(paths, environ={}).install_backend()

        self.assertFalse(result.success)
        self.assertFalse(result.modified_system)
        self.assertIn("planned/experimental", result.message)


if __name__ == "__main__":
    unittest.main()
