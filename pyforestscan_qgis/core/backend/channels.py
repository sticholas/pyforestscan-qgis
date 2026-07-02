"""Package channel definitions for planned PBM environments."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BackendChannel:
    """One package source planned for backend dependency resolution."""

    name: str
    url: str
    priority: int
    package_manager: str = "conda"
    notes: str = ""


def default_backend_channels() -> tuple[BackendChannel, ...]:
    """Return the initial package-channel policy for Phase 22B dry runs."""
    return (
        BackendChannel(
            name="conda-forge",
            url="https://conda.anaconda.org/conda-forge",
            priority=1,
            notes="Primary source for Python, PDAL, GDAL, rasterio, numpy, and compatible geospatial binaries.",
        ),
        BackendChannel(
            name="pypi-placeholder",
            url="https://pypi.org/simple",
            priority=2,
            package_manager="pip",
            notes="Placeholder for PyForestScan if a conda-compatible package is unavailable in a future installer phase.",
        ),
    )


def format_channels(channels: tuple[BackendChannel, ...]) -> tuple[str, ...]:
    """Return readable channel lines for install-plan previews."""
    return tuple(f"{channel.name} ({channel.package_manager}, priority {channel.priority}) - {channel.url}" for channel in channels)
