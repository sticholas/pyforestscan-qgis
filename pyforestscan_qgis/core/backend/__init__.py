"""PyForestScan Backend Manager core package.

PBM is the plugin-owned architecture for managing a future isolated backend
runtime. Phase 22B provides path resolution, registry models, detection,
verification, dry-run install planning, and compatibility checks only; it does
not download or install dependencies.
"""

from .install_plan import BackendInstallPlan, BackendInstallStep, create_backend_install_plan, format_install_plan
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
    "BackendConfig",
    "BackendDependency",
    "BackendInstallPlan",
    "BackendInstallStep",
    "BackendLogEntry",
    "BackendOperationResult",
    "BackendPaths",
    "BackendPlatform",
    "BackendRegistry",
    "BackendService",
    "BackendState",
    "BackendStatus",
    "BackendVerificationResult",
    "create_backend_install_plan",
    "default_backend_registry",
    "format_install_plan",
    "resolve_backend_paths",
]
