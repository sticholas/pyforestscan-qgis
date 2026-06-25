"""Plugin-owned exceptions for the PyForestScan adapter boundary."""

from __future__ import annotations


class AdapterError(Exception):
    """Base class for all PyForestScan adapter failures."""


class EnvironmentError(AdapterError):
    """Raised when the runtime environment cannot support adapter work."""


class DatasetError(AdapterError):
    """Raised when an input dataset is missing, unsupported, or invalid."""


class ProcessingError(AdapterError):
    """Raised when a future PyForestScan processing workflow fails."""
