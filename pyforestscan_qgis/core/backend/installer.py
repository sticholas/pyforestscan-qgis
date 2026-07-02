"""Controlled PBM installer prototype with developer-only guardrails."""

from __future__ import annotations

import os
import shutil
import subprocess
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .checksums import ChecksumResult, verify_checksum
from .config import planned_backend_config, save_backend_config, utc_now_iso
from .downloads import DownloadResult, Downloader, download_file
from .micromamba import MicromambaBootstrapPolicy, micromamba_bootstrap_policy
from .models import BackendOperationResult, BackendPlatform, BackendStatus, BackendVerificationResult
from .paths import BackendPaths, resolve_backend_paths
from .verification import verify_backend

BACKEND_INSTALL_ENABLE_ENV = "PYFORESTSCAN_QGIS_ENABLE_BACKEND_INSTALL"

CommandRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]
Verifier = Callable[[BackendPaths], BackendVerificationResult]


@dataclass(frozen=True)
class StagingPaths:
    """Installer staging paths below the user-local backend root."""

    root: Path
    micromamba_dir: Path
    micromamba_executable: Path
    environment_path: Path
    python_executable: Path


def backend_install_enabled(environ: dict[str, str] | None = None) -> bool:
    """Return whether the developer-only installer flag is enabled."""
    env = environ if environ is not None else os.environ
    return env.get(BACKEND_INSTALL_ENABLE_ENV) == "1"


def install_disabled_result(operation: str) -> BackendOperationResult:
    """Return the standard refusal result when the developer flag is absent."""
    return BackendOperationResult(
        operation=operation,
        status=BackendStatus.NOT_INSTALLED,
        success=False,
        message=f"Backend installer is planned and disabled. Set {BACKEND_INSTALL_ENABLE_ENV}=1 only for development testing.",
        modified_system=False,
    )


def staging_paths(paths: BackendPaths) -> StagingPaths:
    """Return the staging filesystem layout for one install attempt."""
    suffix = ".exe" if paths.platform is BackendPlatform.WINDOWS else ""
    env_python = "python.exe" if paths.platform is BackendPlatform.WINDOWS else "bin/python"
    return StagingPaths(
        root=paths.staging_dir,
        micromamba_dir=paths.staging_dir / "micromamba",
        micromamba_executable=paths.staging_dir / "micromamba" / f"micromamba{suffix}",
        environment_path=paths.staging_dir / "env",
        python_executable=paths.staging_dir / "env" / env_python,
    )


def staged_backend_paths(paths: BackendPaths) -> BackendPaths:
    """Return a BackendPaths object rooted in staging for verification."""
    return resolve_backend_paths(backend_root=paths.staging_dir, platform=paths.platform)


class BackendInstaller:
    """Developer-only controlled installer prototype."""

    def __init__(
        self,
        paths: BackendPaths,
        environ: dict[str, str] | None = None,
        downloader: Downloader | None = None,
        runner: CommandRunner | None = None,
        verifier: Verifier | None = None,
    ) -> None:
        self.paths = paths
        self.environ = environ if environ is not None else os.environ
        self.downloader = downloader
        self.runner = runner or self._default_runner
        self.verifier = verifier or verify_backend

    def enabled(self) -> bool:
        """Return whether real installer actions are enabled."""
        return backend_install_enabled(self.environ)

    def require_enabled(self, operation: str) -> BackendOperationResult | None:
        """Return a refusal result when the developer installer flag is absent."""
        if self.enabled():
            return None
        return install_disabled_result(operation)

    def plan_install(self) -> BackendOperationResult:
        """Return installer readiness without modifying the filesystem."""
        if not self.enabled():
            return install_disabled_result("plan_install")
        return BackendOperationResult(
            operation="plan_install",
            status=BackendStatus.NOT_INSTALLED,
            success=True,
            message="Developer backend installer is enabled. Install operations remain experimental.",
            modified_system=False,
        )

    def prepare_staging(self) -> BackendOperationResult:
        """Create clean staging, download, and log directories under the backend root."""
        disabled = self.require_enabled("prepare_staging")
        if disabled:
            return disabled
        self.rollback_failed_install()
        self.paths.backend_root.mkdir(parents=True, exist_ok=True)
        self.paths.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.paths.logs_dir.mkdir(parents=True, exist_ok=True)
        staged = staging_paths(self.paths)
        staged.micromamba_dir.mkdir(parents=True, exist_ok=True)
        staged.environment_path.mkdir(parents=True, exist_ok=True)
        return BackendOperationResult(
            operation="prepare_staging",
            status=BackendStatus.INSTALLING,
            success=True,
            message=f"Created staging layout at {staged.root}.",
            modified_system=True,
        )

    def download_micromamba(self, policy: MicromambaBootstrapPolicy | None = None) -> DownloadResult:
        """Download the Micromamba archive into the user-local download cache."""
        disabled = self.require_enabled("download_micromamba")
        if disabled:
            return DownloadResult(False, disabled.message, self.paths.downloads_dir, "", attempts=0)
        policy_value = policy or micromamba_bootstrap_policy(self.paths)
        return download_file(policy_value.source_url, policy_value.download_path, retries=policy_value.retry_count, downloader=self.downloader)

    def verify_micromamba_download(self, policy: MicromambaBootstrapPolicy | None = None) -> ChecksumResult:
        """Verify the downloaded Micromamba archive checksum."""
        policy_value = policy or micromamba_bootstrap_policy(self.paths)
        return verify_checksum(policy_value.download_path, policy_value.checksum_policy)

    def extract_micromamba(self, policy: MicromambaBootstrapPolicy | None = None) -> BackendOperationResult:
        """Extract Micromamba into staging and place the executable at the staged path."""
        disabled = self.require_enabled("extract_micromamba")
        if disabled:
            return disabled
        policy_value = policy or micromamba_bootstrap_policy(self.paths)
        staged = staging_paths(self.paths)
        try:
            with tarfile.open(policy_value.download_path, "r:*") as archive:
                archive.extractall(staged.root)  # noqa: S202 - developer-only installer extracts a checksum-verified artifact.
            candidate = _find_extracted_micromamba(staged.root, self.paths.platform)
            if candidate is None:
                return BackendOperationResult("extract_micromamba", BackendStatus.FAILED, False, "Micromamba executable was not found after extraction.", True)
            staged.micromamba_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(candidate, staged.micromamba_executable)
            staged.micromamba_executable.chmod(staged.micromamba_executable.stat().st_mode | 0o700)
        except (OSError, tarfile.TarError) as exc:
            return BackendOperationResult("extract_micromamba", BackendStatus.FAILED, False, f"Micromamba extraction failed: {exc}", True)
        return BackendOperationResult("extract_micromamba", BackendStatus.INSTALLING, True, f"Extracted Micromamba to {staged.micromamba_executable}.", True)

    def create_environment(self, spec_file: Path | None = None) -> BackendOperationResult:
        """Create the staged backend environment using Micromamba."""
        disabled = self.require_enabled("create_environment")
        if disabled:
            return disabled
        staged = staging_paths(self.paths)
        spec = spec_file or default_environment_spec_file(self.paths.platform)
        command = [str(staged.micromamba_executable), "create", "-y", "-p", str(staged.environment_path), "-f", str(spec)]
        try:
            completed = self.runner(command)
        except Exception as exc:  # noqa: BLE001 - installer reports failures.
            return BackendOperationResult("create_environment", BackendStatus.FAILED, False, f"Environment creation failed: {exc}", True)
        if completed.returncode != 0:
            output = (completed.stderr or completed.stdout or "").strip()
            return BackendOperationResult("create_environment", BackendStatus.FAILED, False, f"Environment creation failed: {output}", True)
        return BackendOperationResult("create_environment", BackendStatus.INSTALLING, True, f"Created staged backend environment at {staged.environment_path}.", True)

    def verify_environment(self) -> BackendVerificationResult:
        """Verify the staged backend environment."""
        return self.verifier(staged_backend_paths(self.paths))

    def promote_staging(self) -> BackendOperationResult:
        """Promote verified staged files into the active backend layout."""
        disabled = self.require_enabled("promote_staging")
        if disabled:
            return disabled
        staged = staging_paths(self.paths)
        if not staged.micromamba_executable.exists() or not staged.environment_path.exists():
            return BackendOperationResult("promote_staging", BackendStatus.FAILED, False, "Staging is incomplete; cannot promote backend.", False)
        for target in (self.paths.micromamba_executable.parent, self.paths.environment_path):
            if target.exists():
                shutil.rmtree(target)
        self.paths.micromamba_executable.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(staged.micromamba_dir, self.paths.micromamba_executable.parent, dirs_exist_ok=True)
        shutil.copytree(staged.environment_path, self.paths.environment_path, dirs_exist_ok=True)
        return BackendOperationResult("promote_staging", BackendStatus.VERIFYING, True, "Promoted staged backend files into the active backend layout.", True)

    def write_backend_config(self, status: BackendStatus = BackendStatus.READY) -> BackendOperationResult:
        """Write backend config after successful verification."""
        disabled = self.require_enabled("write_backend_config")
        if disabled:
            return disabled
        config = planned_backend_config(self.paths)
        config = type(config)(
            backend_version=config.backend_version,
            backend_root=config.backend_root,
            environment_path=config.environment_path,
            python_executable=config.python_executable,
            micromamba_executable=config.micromamba_executable,
            created_at=config.created_at,
            updated_at=utc_now_iso(),
            platform=config.platform,
            status=status,
            registry=config.registry,
        )
        save_backend_config(config, self.paths.config_file)
        return BackendOperationResult("write_backend_config", status, True, f"Wrote backend config at {self.paths.config_file}.", True)

    def rollback_failed_install(self) -> BackendOperationResult:
        """Remove staging files after a failed install attempt."""
        if self.paths.staging_dir.exists():
            shutil.rmtree(self.paths.staging_dir)
            return BackendOperationResult("rollback_failed_install", BackendStatus.REPAIR_REQUIRED, True, f"Removed staging directory {self.paths.staging_dir}.", True)
        return BackendOperationResult("rollback_failed_install", BackendStatus.NOT_INSTALLED, True, "No staging directory was present.", False)

    def install_backend(self, policy: MicromambaBootstrapPolicy | None = None, spec_file: Path | None = None) -> BackendOperationResult:
        """Run the controlled installer prototype when explicitly enabled."""
        disabled = self.require_enabled("install_backend")
        if disabled:
            return disabled
        try:
            for step in (self.prepare_staging(),):
                if not step.success:
                    return step
            policy_value = policy or micromamba_bootstrap_policy(self.paths)
            download = self.download_micromamba(policy_value)
            if not download.success:
                self.rollback_failed_install()
                return BackendOperationResult("install_backend", BackendStatus.FAILED, False, download.message, download.path.exists())
            checksum = self.verify_micromamba_download(policy_value)
            if not checksum.passed():
                self.rollback_failed_install()
                return BackendOperationResult("install_backend", BackendStatus.FAILED, False, checksum.message, True)
            for step in (self.extract_micromamba(policy_value), self.create_environment(spec_file)):
                if not step.success:
                    self.rollback_failed_install()
                    return BackendOperationResult("install_backend", BackendStatus.FAILED, False, step.message, step.modified_system)
            verification = self.verify_environment()
            if not verification.passed():
                self.rollback_failed_install()
                return BackendOperationResult("install_backend", BackendStatus.REPAIR_REQUIRED, False, verification.summary, True)
            for step in (self.promote_staging(), self.write_backend_config(BackendStatus.READY)):
                if not step.success:
                    self.rollback_failed_install()
                    return step
            self.rollback_failed_install()
            return BackendOperationResult("install_backend", BackendStatus.READY, True, "Backend installed and verified in the user-local PBM directory.", True)
        except Exception as exc:  # noqa: BLE001 - rollback is more important than surfacing raw crashes.
            self.rollback_failed_install()
            return BackendOperationResult("install_backend", BackendStatus.FAILED, False, f"Backend install failed safely: {exc}", True)

    def _default_runner(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(command, check=False, capture_output=True, text=True, timeout=1800)


def default_environment_spec_file(platform: BackendPlatform) -> Path:
    """Return the platform-specific environment spec file path."""
    source_root = Path(__file__).resolve().parents[3]
    package_root = Path(__file__).resolve().parents[2]
    for spec_dir in (source_root / "backend_specs", package_root / "backend_specs"):
        if spec_dir.exists():
            if platform is BackendPlatform.WINDOWS:
                return spec_dir / "environment.windows.yml"
            if platform is BackendPlatform.LINUX:
                return spec_dir / "environment.linux.yml"
            if platform is BackendPlatform.MACOS:
                return spec_dir / "environment.macos.yml"
            return spec_dir / "environment.yml"
    return source_root / "backend_specs" / "environment.yml"


def _find_extracted_micromamba(root: Path, platform: BackendPlatform) -> Path | None:
    expected = "micromamba.exe" if platform is BackendPlatform.WINDOWS else "micromamba"
    for candidate in root.rglob(expected):
        if candidate.is_file():
            return candidate
    return None
