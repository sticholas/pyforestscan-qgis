"""Documented dependency-check interfaces for future implementation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DependencyStatus(str, Enum):
    """Possible dependency states reported by future diagnostics."""

    AVAILABLE = "available"
    MISSING = "missing"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class DependencyCheckResult:
    """Result record for a future dependency diagnostic check."""

    package_name: str
    status: DependencyStatus
    installed_version: str | None = None
    message: str = ""


def check_runtime_dependencies() -> tuple[DependencyCheckResult, ...]:
    """Return runtime dependency diagnostics.

    Phase 1 intentionally does not inspect or import PyForestScan. Phase 2 will
    implement environment validation against the active QGIS Python runtime.
    """
    return (
        DependencyCheckResult(
            package_name="pyforestscan",
            status=DependencyStatus.UNKNOWN,
            message="Not yet implemented.",
        ),
    )

