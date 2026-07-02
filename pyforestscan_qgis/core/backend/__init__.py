"""PyForestScan Backend Manager core package.

PBM is the plugin-owned architecture for managing an isolated backend runtime.
Phase 22D adds production installer architecture: manifest-driven dependency
selection, resumable downloads, transactional install stages, repair planning,
structured logs, version checks, and future backend modules. Internal beta installation is enabled on Windows with confirmation, while Linux/macOS remain planned until platform smoke testing is complete.
"""

from .checksums import ChecksumPolicy, ChecksumResult, verify_checksum
from .download_manager import CancellationToken, DownloadManager, DownloadRequest, DownloadSource, ManagedDownloadResult
from .downloads import DownloadResult, download_file, download_path
from .install_plan import BackendInstallPlan, BackendInstallStep, create_backend_install_plan, format_install_plan
from .installer import BACKEND_INSTALL_ENABLE_ENV, BackendInstallAvailability, BackendInstaller, backend_install_availability, backend_install_enabled
from .manifest import BackendManifest, BackendManifestError, load_backend_manifest
from .micromamba import MicromambaBootstrapPolicy, micromamba_bootstrap_policy, micromamba_source_url
from .models import (
    BackendConfig,
    BackendDependency,
    BackendLogEntry,
    BackendOperationResult,
    BackendPlatform,
    BackendRegistry,
    BackendState,
    BackendStatus,
    BackendVerificationResult,
)
from .modules import BackendModuleRegistry, default_backend_module_registry
from .paths import BackendPaths, resolve_backend_paths
from .registry import default_backend_registry
from .repair import RepairPlan, plan_backend_repair
from .service import BackendService
from .transaction import BackendInstallTransaction, BackendTransactionResult, BackendTransactionStage
from .version_manager import BackendVersionManager, VersionCompatibilityResult

__all__ = [
    "BACKEND_INSTALL_ENABLE_ENV",
    "BackendConfig",
    "BackendDependency",
    "BackendInstallAvailability",
    "BackendInstallPlan",
    "BackendInstallStep",
    "BackendInstallTransaction",
    "BackendInstaller",
    "BackendLogEntry",
    "BackendManifest",
    "BackendManifestError",
    "BackendModuleRegistry",
    "BackendOperationResult",
    "BackendPaths",
    "BackendPlatform",
    "BackendRegistry",
    "BackendService",
    "BackendState",
    "BackendStatus",
    "BackendTransactionResult",
    "BackendTransactionStage",
    "BackendVerificationResult",
    "BackendVersionManager",
    "CancellationToken",
    "ChecksumPolicy",
    "ChecksumResult",
    "DownloadManager",
    "DownloadRequest",
    "DownloadResult",
    "DownloadSource",
    "ManagedDownloadResult",
    "MicromambaBootstrapPolicy",
    "RepairPlan",
    "VersionCompatibilityResult",
    "backend_install_availability",
    "backend_install_enabled",
    "create_backend_install_plan",
    "default_backend_module_registry",
    "default_backend_registry",
    "download_file",
    "download_path",
    "format_install_plan",
    "load_backend_manifest",
    "micromamba_bootstrap_policy",
    "micromamba_source_url",
    "plan_backend_repair",
    "resolve_backend_paths",
    "verify_checksum",
]
