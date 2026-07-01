"""PyForestScan Backend Manager core package.

PBM is the plugin-owned architecture for managing a future isolated backend
runtime. Phase 22A provides path resolution, registry models, detection, and
verification only; it does not download or install dependencies.
"""

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
    "BackendLogEntry",
    "BackendOperationResult",
    "BackendPaths",
    "BackendPlatform",
    "BackendRegistry",
    "BackendService",
    "BackendState",
    "BackendStatus",
    "BackendVerificationResult",
    "default_backend_registry",
    "resolve_backend_paths",
]
