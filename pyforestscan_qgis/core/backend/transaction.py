"""Transactional backend installer orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from .models import BackendOperationResult, BackendStatus, BackendVerificationResult
from .progress import BackendProgressModel, BackendProgressStage, BackendProgressUpdate


class BackendTransactionStage(str, Enum):
    """Atomic stages for backend installation transactions."""

    DOWNLOAD = "DOWNLOAD"
    VERIFY = "VERIFY"
    EXTRACT = "EXTRACT"
    CREATE_ENVIRONMENT = "CREATE ENVIRONMENT"
    INSTALL_PACKAGES = "INSTALL PACKAGES"
    VERIFY_PACKAGES = "VERIFY PACKAGES"
    WRITE_CONFIG = "WRITE CONFIG"
    PROMOTE_BACKEND = "PROMOTE BACKEND"
    READY = "READY"


@dataclass(frozen=True)
class BackendTransactionResult:
    """Result from a backend installation transaction."""

    success: bool
    status: BackendStatus
    stage: BackendTransactionStage | None
    message: str
    rolled_back: bool
    modified_system: bool
    progress: tuple[BackendProgressUpdate, ...]
    operations: tuple[BackendOperationResult, ...]


class BackendInstallTransaction:
    """Run installer operations as a rollback-protected transaction."""

    def __init__(self, installer: Any, logger: Callable[[str, str, str], None] | None = None) -> None:
        self.installer = installer
        self.logger = logger
        self.progress = BackendProgressModel()
        self.operations: list[BackendOperationResult] = []

    def run(self, policy: Any = None, spec_file: Path | None = None, cancel_token: Any = None) -> BackendTransactionResult:
        """Run the full install transaction and rollback on failure or cancellation."""
        self._emit(BackendProgressStage.QUEUED, 0, "Installer transaction queued.")
        disabled = self.installer.require_enabled("install_backend")
        if disabled:
            self.operations.append(disabled)
            return self._result(False, disabled.status, None, disabled.message, False, disabled.modified_system)
        try:
            prepare = self.installer.prepare_staging()
            if not self._accept_operation(BackendTransactionStage.DOWNLOAD, prepare):
                return self._fail(BackendTransactionStage.DOWNLOAD, prepare.message)

            if _cancelled(cancel_token):
                return self._cancel(BackendTransactionStage.DOWNLOAD)
            self._emit(BackendProgressStage.DOWNLOADING, 10, "Downloading backend bootstrap artifact.")
            download = self.installer.download_micromamba(policy)
            if not download.success:
                return self._fail(BackendTransactionStage.DOWNLOAD, download.message, modified_system=download.path.exists())

            if _cancelled(cancel_token):
                return self._cancel(BackendTransactionStage.VERIFY)
            self._emit(BackendProgressStage.VERIFYING, 25, "Verifying backend bootstrap artifact.")
            checksum = self.installer.verify_micromamba_download(policy)
            if not checksum.passed():
                return self._fail(BackendTransactionStage.VERIFY, checksum.message)

            if _cancelled(cancel_token):
                return self._cancel(BackendTransactionStage.EXTRACT)
            self._emit(BackendProgressStage.EXTRACTING, 40, "Extracting backend bootstrap artifact.")
            extract = self.installer.extract_micromamba(policy)
            if not self._accept_operation(BackendTransactionStage.EXTRACT, extract):
                return self._fail(BackendTransactionStage.EXTRACT, extract.message)

            if _cancelled(cancel_token):
                return self._cancel(BackendTransactionStage.CREATE_ENVIRONMENT)
            self._emit(BackendProgressStage.INSTALLING, 55, "Creating managed backend environment.")
            create = self.installer.create_environment(spec_file)
            if not self._accept_operation(BackendTransactionStage.CREATE_ENVIRONMENT, create):
                return self._fail(BackendTransactionStage.CREATE_ENVIRONMENT, create.message)

            if _cancelled(cancel_token):
                return self._cancel(BackendTransactionStage.INSTALL_PACKAGES)
            self._emit(BackendProgressStage.INSTALLING, 70, "Installing PyPI-only packages with backend Python.")
            package_step = self.installer.install_python_packages()
            if not self._accept_operation(BackendTransactionStage.INSTALL_PACKAGES, package_step):
                return self._fail(BackendTransactionStage.INSTALL_PACKAGES, package_step.message)

            if _cancelled(cancel_token):
                return self._cancel(BackendTransactionStage.VERIFY_PACKAGES)
            self._emit(BackendProgressStage.CHECKING, 82, "Verifying managed backend environment.")
            verification = self.installer.verify_environment()
            if not _verification_passed(verification):
                return self._fail(BackendTransactionStage.VERIFY_PACKAGES, verification.summary, status=BackendStatus.REPAIR_REQUIRED)

            if _cancelled(cancel_token):
                return self._cancel(BackendTransactionStage.PROMOTE_BACKEND)
            self._emit(BackendProgressStage.FINALIZING, 92, "Promoting verified backend into active location.")
            promote = self.installer.promote_staging()
            if not self._accept_operation(BackendTransactionStage.PROMOTE_BACKEND, promote):
                return self._fail(BackendTransactionStage.PROMOTE_BACKEND, promote.message)

            config = self.installer.write_backend_config(BackendStatus.READY)
            if not self._accept_operation(BackendTransactionStage.WRITE_CONFIG, config):
                return self._fail(BackendTransactionStage.WRITE_CONFIG, config.message)

            self._emit(BackendProgressStage.CHECKING, 96, "Verifying active backend location.")
            active_verification = self.installer.verify_active_backend()
            if not _verification_passed(active_verification):
                return self._fail(BackendTransactionStage.VERIFY_PACKAGES, active_verification.summary, status=BackendStatus.REPAIR_REQUIRED)
            self.installer.rollback_failed_install()
            self._emit(BackendProgressStage.READY, 100, "Backend installed and verified.")
            return self._result(True, BackendStatus.READY, BackendTransactionStage.READY, "Backend installed and verified in the user-local PBM directory.", False, True)
        except Exception as exc:  # noqa: BLE001 - transactions convert crashes into rollback results.
            return self._fail(None, f"Backend install failed safely: {exc}")

    def _accept_operation(self, stage: BackendTransactionStage, result: BackendOperationResult) -> bool:
        self.operations.append(result)
        self._log(stage, "INFO" if result.success else "ERROR", result.message)
        return result.success

    def _fail(self, stage: BackendTransactionStage | None, message: str, status: BackendStatus = BackendStatus.FAILED, modified_system: bool = True) -> BackendTransactionResult:
        rollback = self.installer.rollback_failed_install()
        self.operations.append(rollback)
        self._emit(BackendProgressStage.FAILED, None, message)
        if stage is not None:
            self._log(stage, "ERROR", message)
        return self._result(False, status, stage, message, rollback.modified_system, modified_system)

    def _cancel(self, stage: BackendTransactionStage) -> BackendTransactionResult:
        rollback = self.installer.rollback_failed_install()
        self.operations.append(rollback)
        self._emit(BackendProgressStage.CANCELLED, None, "Backend installation cancelled and staging was rolled back.")
        self._log(stage, "WARNING", "Backend installation cancelled.")
        return self._result(False, BackendStatus.FAILED, stage, "Backend installation cancelled.", rollback.modified_system, rollback.modified_system)

    def _result(self, success: bool, status: BackendStatus, stage: BackendTransactionStage | None, message: str, rolled_back: bool, modified_system: bool) -> BackendTransactionResult:
        return BackendTransactionResult(success, status, stage, message, rolled_back, modified_system, tuple(self.progress.updates), tuple(self.operations))

    def _emit(self, stage: BackendProgressStage, percentage: float | None, message: str) -> None:
        self.progress.emit(BackendProgressUpdate(stage=stage, percentage=percentage, message=message))

    def _log(self, stage: BackendTransactionStage, severity: str, message: str) -> None:
        if self.logger:
            self.logger(stage.value, severity, message)


def _cancelled(cancel_token: Any) -> bool:
    return bool(cancel_token is not None and getattr(cancel_token, "cancelled", False))


def _verification_passed(result: BackendVerificationResult) -> bool:
    return result.passed()
