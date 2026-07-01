"""Backend Manager exceptions."""

from __future__ import annotations


class BackendError(Exception):
    """Base exception for PyForestScan Backend Manager failures."""


class BackendConfigError(BackendError):
    """Raised when backend configuration cannot be read or parsed."""


class BackendVerificationError(BackendError):
    """Raised when backend verification cannot be completed safely."""


class BackendOperationNotImplementedError(BackendError):
    """Raised for planned backend operations that are intentionally disabled."""
