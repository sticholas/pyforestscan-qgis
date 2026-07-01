"""Typed models for the PyForestScan Backend Manager."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class BackendStatus(str, Enum):
    """Lifecycle states for the managed PyForestScan backend."""

    NOT_INSTALLED = "Not Installed"
    INSTALLING = "Installing"
    VERIFYING = "Verifying"
    READY = "Ready"
    REPAIR_REQUIRED = "Repair Required"
    UPDATING = "Updating"
    REMOVING = "Removing"
    FAILED = "Failed"


class BackendPlatform(str, Enum):
    """Supported host platform families for backend path resolution."""

    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    UNKNOWN = "unknown"


class DependencyInstallStatus(str, Enum):
    """Installation state for one backend dependency."""

    UNKNOWN = "unknown"
    MISSING = "missing"
    PRESENT = "present"
    PLANNED = "planned"


class DependencyVerificationStatus(str, Enum):
    """Verification state for one backend dependency."""

    NOT_CHECKED = "not_checked"
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"


@dataclass(frozen=True)
class BackendDependency:
    """One registry-managed backend dependency."""

    name: str
    display_name: str
    category: str
    required: bool
    version_spec: str = ""
    source: str = ""
    executable_name: str | None = None
    python_import_name: str | None = None
    verification_command: tuple[str, ...] = ()
    install_status: DependencyInstallStatus = DependencyInstallStatus.PLANNED
    verification_status: DependencyVerificationStatus = DependencyVerificationStatus.NOT_CHECKED
    detected_version: str | None = None
    update_available: bool | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize the dependency for config or registry files."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "category": self.category,
            "required": self.required,
            "version_spec": self.version_spec,
            "source": self.source,
            "executable_name": self.executable_name,
            "python_import_name": self.python_import_name,
            "verification_command": list(self.verification_command),
            "install_status": self.install_status.value,
            "verification_status": self.verification_status.value,
            "detected_version": self.detected_version,
            "update_available": self.update_available,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BackendDependency":
        """Deserialize a dependency from persisted registry state."""
        return cls(
            name=str(data["name"]),
            display_name=str(data.get("display_name", data["name"])),
            category=str(data.get("category", "runtime")),
            required=bool(data.get("required", True)),
            version_spec=str(data.get("version_spec", "")),
            source=str(data.get("source", "")),
            executable_name=data.get("executable_name"),
            python_import_name=data.get("python_import_name"),
            verification_command=tuple(data.get("verification_command", ())),
            install_status=DependencyInstallStatus(data.get("install_status", DependencyInstallStatus.PLANNED.value)),
            verification_status=DependencyVerificationStatus(data.get("verification_status", DependencyVerificationStatus.NOT_CHECKED.value)),
            detected_version=data.get("detected_version"),
            update_available=data.get("update_available"),
            notes=str(data.get("notes", "")),
        )


@dataclass(frozen=True)
class BackendRegistry:
    """Dependency registry for a backend environment."""

    dependencies: tuple[BackendDependency, ...]
    registry_version: str = "1"

    def required_dependencies(self) -> tuple[BackendDependency, ...]:
        """Return dependencies required for the first managed backend."""
        return tuple(dependency for dependency in self.dependencies if dependency.required)

    def dependency_names(self) -> tuple[str, ...]:
        """Return stable dependency identifiers."""
        return tuple(dependency.name for dependency in self.dependencies)

    def to_dict(self) -> dict[str, Any]:
        """Serialize registry state."""
        return {
            "registry_version": self.registry_version,
            "dependencies": [dependency.to_dict() for dependency in self.dependencies],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BackendRegistry":
        """Deserialize registry state."""
        return cls(
            registry_version=str(data.get("registry_version", "1")),
            dependencies=tuple(BackendDependency.from_dict(item) for item in data.get("dependencies", ())),
        )


@dataclass(frozen=True)
class BackendConfig:
    """Persisted backend configuration stored below the backend root."""

    backend_version: str
    backend_root: Path
    environment_path: Path
    python_executable: Path
    micromamba_executable: Path
    created_at: str
    updated_at: str
    platform: BackendPlatform
    status: BackendStatus
    registry: BackendRegistry

    def to_dict(self) -> dict[str, Any]:
        """Serialize backend config to JSON-compatible values."""
        return {
            "backend_version": self.backend_version,
            "backend_root": str(self.backend_root),
            "environment_path": str(self.environment_path),
            "python_executable": str(self.python_executable),
            "micromamba_executable": str(self.micromamba_executable),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "platform": self.platform.value,
            "status": self.status.value,
            "dependency_registry_state": self.registry.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BackendConfig":
        """Deserialize backend config from JSON-compatible values."""
        return cls(
            backend_version=str(data.get("backend_version", "1")),
            backend_root=Path(data["backend_root"]),
            environment_path=Path(data["environment_path"]),
            python_executable=Path(data["python_executable"]),
            micromamba_executable=Path(data["micromamba_executable"]),
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
            platform=BackendPlatform(data.get("platform", BackendPlatform.UNKNOWN.value)),
            status=BackendStatus(data.get("status", BackendStatus.NOT_INSTALLED.value)),
            registry=BackendRegistry.from_dict(data.get("dependency_registry_state", {})),
        )


@dataclass(frozen=True)
class BackendState:
    """Detected backend state for the current machine."""

    status: BackendStatus
    platform: BackendPlatform
    backend_root: Path
    config_exists: bool
    environment_exists: bool
    micromamba_exists: bool
    python_exists: bool
    message: str


@dataclass(frozen=True)
class BackendCheckResult:
    """One backend verification check."""

    name: str
    status: DependencyVerificationStatus
    message: str
    detected_version: str | None = None
    path: Path | None = None


@dataclass(frozen=True)
class BackendVerificationResult:
    """Structured backend verification report."""

    status: BackendStatus
    state: BackendState
    checks: tuple[BackendCheckResult, ...]
    registry: BackendRegistry
    summary: str

    def passed(self) -> bool:
        """Return whether the backend is ready for managed execution."""
        return self.status is BackendStatus.READY


@dataclass(frozen=True)
class BackendOperationResult:
    """Result from a backend service operation."""

    operation: str
    status: BackendStatus
    success: bool
    message: str
    modified_system: bool = False
    log_path: Path | None = None


@dataclass(frozen=True)
class BackendLogEntry:
    """One structured backend log message."""

    timestamp: str
    level: str
    operation: str
    message: str
    details: dict[str, str] = field(default_factory=dict)
