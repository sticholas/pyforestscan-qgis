"""PyForestScan Backend Manager core package.

PBM is the plugin-owned architecture for managing a future isolated backend
runtime. Phase 22C adds a developer-only controlled installer prototype with
staging and rollback; general user installation remains disabled.
"""

from .checksums import ChecksumPolicy, ChecksumResult, verify_checksum
from .downloads import DownloadResult, download_file, download_path
from .install_plan import BackendInstallPlan, BackendInstallStep, create_backend_install_plan, format_install_plan
from .installer import BACKEND_INSTALL_ENABLE_ENV, BackendInstaller, backend_install_enabled
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
from .paths import BackendPaths, resolve_backend_paths
from .registry import default_backend_registry
from .service import BackendService

__all__ = [
    "BACKEND_INSTALL_ENABLE_ENV",
    "BackendConfig",
    "BackendDependency",
    "BackendInstallPlan",
    "BackendInstallStep",
    "BackendInstaller",
    "BackendLogEntry",
    "BackendOperationResult",
    "BackendPaths",
    "BackendPlatform",
    "BackendRegistry",
    "BackendService",
    "BackendState",
    "BackendStatus",
    "BackendVerificationResult",
    "ChecksumPolicy",
    "ChecksumResult",
    "DownloadResult",
    "MicromambaBootstrapPolicy",
    "backend_install_enabled",
    "create_backend_install_plan",
    "default_backend_registry",
    "download_file",
    "download_path",
    "format_install_plan",
    "micromamba_bootstrap_policy",
    "micromamba_source_url",
    "resolve_backend_paths",
    "verify_checksum",
]
