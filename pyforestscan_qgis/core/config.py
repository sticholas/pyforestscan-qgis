"""Immutable configuration objects for the PyForestScan adapter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AdapterConfig:
    """Runtime options for adapter behavior that are independent of QGIS."""

    allow_remote_ept: bool = True
    inspect_classifications: bool = True
    max_points_for_classification_summary: int | None = 5_000_000
    default_crs: str | None = None
    working_directory: Path | None = None


@dataclass(frozen=True)
class DatasetOpenOptions:
    """Options used when opening or validating a point cloud dataset."""

    crs: str | None = None
    allow_remote: bool = True


@dataclass(frozen=True)
class InspectionOptions:
    """Options controlling non-output dataset inspection."""

    include_classification_summary: bool = True
    max_points_for_classification_summary: int | None = 5_000_000
    include_dimensions: bool = True
